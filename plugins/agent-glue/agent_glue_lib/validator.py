"""Structural consistency checks across the loaded catalog.

Three layers of validation, all returning a flat list of error strings:
- `validate_kit`: every entity-type references known component schemas.
- `validate_instance`: an instance declares a known entity type, satisfies its
  required components, and every component value matches the component schema.
- `validate_all`: kit + every instance currently in the catalog.

The kit's loader and pre-commit hook call `validate_all`; nonzero errors fail
the commit.
"""

from __future__ import annotations

from typing import Any

from .catalog import Catalog, ComponentSchema, EntityInstance, FieldSchema


class ValidationError(Exception):
    def __init__(self, messages: list[str]) -> None:
        self.messages = messages
        super().__init__("\n".join(messages))


_PRIMITIVE_CHECKERS = {
    "string": lambda v: isinstance(v, str),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "bool": lambda v: isinstance(v, bool),
    "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "list": lambda v: isinstance(v, list),
    "map": lambda v: isinstance(v, dict),
    "any": lambda v: True,
    "enum": lambda v: isinstance(v, str),
}


def _snake_to_pascal(snake: str) -> str:
    return "".join(p[:1].upper() + p[1:] for p in snake.split("_"))


def validate_kit(catalog: Catalog) -> list[str]:
    errors: list[str] = []
    schema_names = set(catalog.component_schemas)
    for etype in catalog.entity_types.values():
        for cname in etype.required_components + etype.optional_components:
            if cname not in schema_names:
                errors.append(
                    f"entity-type '{etype.name}' ({etype.source_path}) "
                    f"references unknown component '{cname}'"
                )
    return errors


def validate_instance(instance: EntityInstance, catalog: Catalog) -> list[str]:
    errors: list[str] = []
    etype = catalog.entity_types.get(instance.type)
    src = instance.source_path or "<unknown>"
    if etype is None:
        return [f"{src}: unknown entity type '{instance.type}'"]

    pascal_present = {_snake_to_pascal(k) for k in instance.components}

    for required in etype.required_components:
        if required not in pascal_present:
            errors.append(
                f"{src} (type {etype.name}): missing required component '{required}'"
            )

    allowed = set(etype.required_components + etype.optional_components)
    for snake_key, value in instance.components.items():
        pascal = _snake_to_pascal(snake_key)
        schema = catalog.component_schemas.get(pascal)
        if schema is None:
            errors.append(
                f"{src}: component '{snake_key}' is not a known component"
            )
            continue
        if pascal not in allowed:
            errors.append(
                f"{src} (type {etype.name}): component '{snake_key}' is not "
                f"allowed on this entity type "
                f"(allowed: {sorted(allowed)})"
            )
            continue
        errors.extend(
            _validate_component_value(value, schema, prefix=f"{src}:{snake_key}")
        )

    return errors


def _validate_component_value(
    value: Any, schema: ComponentSchema, prefix: str
) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [
            f"{prefix}: component value must be a map, "
            f"got {type(value).__name__}"
        ]
    for fname, fschema in schema.fields.items():
        if fname not in value:
            if fschema.required:
                errors.append(f"{prefix}: missing required field '{fname}'")
            continue
        errors.extend(_validate_field(value[fname], fschema, f"{prefix}.{fname}"))
    for k in value:
        if k not in schema.fields:
            errors.append(
                f"{prefix}: unknown field '{k}' "
                f"(component {schema.kind} accepts: {sorted(schema.fields)})"
            )
    return errors


def _validate_field(value: Any, fschema: FieldSchema, prefix: str) -> list[str]:
    errors: list[str] = []
    checker = _PRIMITIVE_CHECKERS.get(fschema.type)
    if checker is None:
        return [f"{prefix}: schema declares unknown field type '{fschema.type}'"]
    if not checker(value):
        return [f"{prefix}: expected {fschema.type}, got {type(value).__name__}"]

    if fschema.type == "enum":
        allowed = fschema.values or []
        if value not in allowed:
            errors.append(
                f"{prefix}: value '{value}' not in allowed enum values {allowed}"
            )
    elif fschema.type == "list" and fschema.items is not None:
        for i, item in enumerate(value):
            errors.extend(_validate_field(item, fschema.items, f"{prefix}[{i}]"))
    elif fschema.type == "map":
        if fschema.keys is not None:
            for k, sub in fschema.keys.items():
                if k not in value:
                    if sub.required:
                        errors.append(f"{prefix}: missing required key '{k}'")
                    continue
                errors.extend(_validate_field(value[k], sub, f"{prefix}.{k}"))
            for k in value:
                if k not in fschema.keys:
                    errors.append(
                        f"{prefix}: unknown key '{k}' "
                        f"(allowed: {sorted(fschema.keys)})"
                    )
        elif fschema.value_type is not None:
            for k, v in value.items():
                errors.extend(
                    _validate_field(v, fschema.value_type, f"{prefix}.{k}")
                )

    return errors


def validate_all(catalog: Catalog) -> list[str]:
    errors = validate_kit(catalog)
    for instance in catalog.entities:
        errors.extend(validate_instance(instance, catalog))
    return errors
