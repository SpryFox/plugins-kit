"""Structural consistency validators for catalog + instances.

Three layers, all returning a flat list of error strings (empty list = success):

- `validate_kit`        -- entity-type required/optional components reference known schemas.
- `validate_instances`  -- every instance declares a known type, satisfies required components,
                           sticks to allowed components, and every component value matches its
                           schema (required fields present, types match, enum values allowed,
                           list items / map values typed correctly, no unknown fields).
- `validate_all`        -- both of the above, run together. The pre-commit hook calls this.
"""

from __future__ import annotations

from typing import Any, Iterable

from agent_glue_lib.core.catalog import (
    FIELD_TYPES,
    Catalog,
    ComponentSchema,
    EntityInstance,
    FieldSchema,
    pascal_to_snake,
)


def validate_kit(catalog: Catalog) -> list[str]:
    """Check entity-type defs reference only known component schemas; check schemas use known types."""
    errors: list[str] = []
    known_components = set(catalog.component_schemas.keys())

    for ent in catalog.entity_types.values():
        for label, refs in (("required", ent.components.required), ("optional", ent.components.optional)):
            for ref in refs:
                if ref not in known_components:
                    errors.append(
                        f"entity-type {ent.name!r} ({ent.source_path}): {label} component "
                        f"{ref!r} is not a known component schema."
                    )
        dup = set(ent.components.required) & set(ent.components.optional)
        if dup:
            errors.append(
                f"entity-type {ent.name!r} ({ent.source_path}): components listed as both "
                f"required and optional: {sorted(dup)!r}."
            )

    for schema in catalog.component_schemas.values():
        for fname, field in schema.fields.items():
            errors.extend(_check_field_schema(f"component {schema.kind!r} ({schema.source_path}).fields.{fname}", field))

    return errors


def _check_field_schema(path: str, field: FieldSchema) -> list[str]:
    errors: list[str] = []
    if field.type not in FIELD_TYPES:
        errors.append(f"{path}: unknown type {field.type!r}; allowed: {list(FIELD_TYPES)!r}.")
        return errors

    if field.type == "list":
        if field.items is None:
            errors.append(f"{path}: type=list requires `items` schema.")
        else:
            errors.extend(_check_field_schema(f"{path}.items", field.items))
        for attr in ("keys", "value_type", "values"):
            if getattr(field, attr) is not None:
                errors.append(f"{path}: type=list cannot also set `{attr}`.")
    elif field.type == "map":
        if field.keys is not None and field.value_type is not None:
            errors.append(f"{path}: map cannot set both `keys` and `value_type`.")
        if field.keys is None and field.value_type is None:
            # open-shaped map with no structural constraints; allowed (treated as dict[str, any])
            pass
        if field.keys is not None:
            for kname, kfield in field.keys.items():
                errors.extend(_check_field_schema(f"{path}.keys.{kname}", kfield))
        if field.value_type is not None:
            errors.extend(_check_field_schema(f"{path}.value_type", field.value_type))
        for attr in ("items", "values"):
            if getattr(field, attr) is not None:
                errors.append(f"{path}: type=map cannot also set `{attr}`.")
    elif field.type == "enum":
        if not field.values:
            errors.append(f"{path}: type=enum requires non-empty `values`.")
        for attr in ("items", "keys", "value_type"):
            if getattr(field, attr) is not None:
                errors.append(f"{path}: type=enum cannot also set `{attr}`.")
    else:  # string / int / float / bool / any
        for attr in ("items", "keys", "value_type", "values"):
            if getattr(field, attr) is not None:
                errors.append(f"{path}: type={field.type} cannot also set `{attr}`.")
    return errors


def validate_instances(catalog: Catalog, instances: Iterable[EntityInstance]) -> list[str]:
    errors: list[str] = []
    for inst in instances:
        ent = catalog.entity_type(inst.type)
        if ent is None:
            errors.append(
                f"instance {inst.source_path}: unknown entity type {inst.type!r}; "
                f"known: {sorted(catalog.entity_types.keys())!r}."
            )
            continue

        required_keys = {pascal_to_snake(c) for c in ent.components.required}
        optional_keys = {pascal_to_snake(c) for c in ent.components.optional}
        allowed_keys = required_keys | optional_keys

        present_keys = set(inst.components.keys())
        missing = required_keys - present_keys
        if missing:
            errors.append(
                f"instance {inst.source_path}: missing required components: {sorted(missing)!r}."
            )
        unknown = present_keys - allowed_keys
        if unknown:
            errors.append(
                f"instance {inst.source_path}: components not allowed on entity {inst.type!r}: "
                f"{sorted(unknown)!r}; allowed: {sorted(allowed_keys)!r}."
            )

        # Validate present components against their schemas.
        ent_components_by_snake = {pascal_to_snake(c): c for c in ent.components.required + ent.components.optional}
        for key, value in inst.components.items():
            kind = ent_components_by_snake.get(key)
            if kind is None:
                continue  # already reported as unknown above
            schema = catalog.component(kind)
            if schema is None:
                errors.append(
                    f"instance {inst.source_path}: component {kind!r} has no schema in the catalog."
                )
                continue
            errors.extend(
                _check_component_value(
                    f"instance {inst.source_path} component {key!r}",
                    schema,
                    value,
                )
            )
    return errors


def _check_component_value(path: str, schema: ComponentSchema, value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        errors.append(f"{path}: component value must be a mapping, got {type(value).__name__}.")
        return errors
    known_fields = set(schema.fields.keys())
    present = set(value.keys())
    missing_required = {
        fname for fname, fschema in schema.fields.items() if fschema.required and fname not in present
    }
    if missing_required:
        errors.append(f"{path}: missing required fields: {sorted(missing_required)!r}.")
    unknown = present - known_fields
    if unknown:
        errors.append(
            f"{path}: unknown fields: {sorted(unknown)!r}; allowed: {sorted(known_fields)!r}."
        )
    for fname, fvalue in value.items():
        fschema = schema.fields.get(fname)
        if fschema is None:
            continue
        errors.extend(_check_value(f"{path}.{fname}", fschema, fvalue))
    return errors


def _check_value(path: str, field: FieldSchema, value: Any) -> list[str]:
    errors: list[str] = []
    if value is None:
        if field.required:
            errors.append(f"{path}: required field is null.")
        return errors

    ftype = field.type
    if ftype == "string":
        if not isinstance(value, str):
            errors.append(f"{path}: expected string, got {type(value).__name__}.")
    elif ftype == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"{path}: expected int, got {type(value).__name__}.")
    elif ftype == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{path}: expected float, got {type(value).__name__}.")
    elif ftype == "bool":
        if not isinstance(value, bool):
            errors.append(f"{path}: expected bool, got {type(value).__name__}.")
    elif ftype == "any":
        pass
    elif ftype == "enum":
        if not isinstance(value, str):
            errors.append(f"{path}: enum value must be a string, got {type(value).__name__}.")
        elif field.values is not None and value not in field.values:
            errors.append(
                f"{path}: enum value {value!r} not in allowed values {field.values!r}."
            )
    elif ftype == "list":
        if not isinstance(value, list):
            errors.append(f"{path}: expected list, got {type(value).__name__}.")
        elif field.items is not None:
            for i, item in enumerate(value):
                errors.extend(_check_value(f"{path}[{i}]", field.items, item))
    elif ftype == "map":
        if not isinstance(value, dict):
            errors.append(f"{path}: expected map, got {type(value).__name__}.")
        elif field.keys is not None:
            allowed = set(field.keys.keys())
            present = set(value.keys())
            missing = {
                k for k, sub in field.keys.items() if sub.required and k not in present
            }
            if missing:
                errors.append(f"{path}: missing required map keys: {sorted(missing)!r}.")
            unknown = present - allowed
            if unknown:
                errors.append(
                    f"{path}: unknown map keys: {sorted(unknown)!r}; allowed: {sorted(allowed)!r}."
                )
            for k, sub in field.keys.items():
                if k in value:
                    errors.extend(_check_value(f"{path}.{k}", sub, value[k]))
        elif field.value_type is not None:
            for k, v in value.items():
                if not isinstance(k, str):
                    errors.append(f"{path}: map keys must be strings, got {type(k).__name__}.")
                errors.extend(_check_value(f"{path}[{k!r}]", field.value_type, v))
        # else: open-shaped map; any string-keyed dict accepted.
    else:
        errors.append(f"{path}: unknown field type {ftype!r}.")
    return errors


def validate_all(catalog: Catalog, instances: Iterable[EntityInstance]) -> list[str]:
    kit_errors = validate_kit(catalog)
    if kit_errors:
        # kit-consistency failures invalidate instance-shape checks; surface kit errors first.
        return kit_errors
    return validate_instances(catalog, instances)
