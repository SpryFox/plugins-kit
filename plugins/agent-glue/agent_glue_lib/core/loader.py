"""yaml-on-disk -> typed catalog + entity instances.

The loader is the single boundary between yaml-on-disk and the Python subsystems. It reads
component schemas, entity-type definitions, and entity instances; rejects structural breakage
loudly; preserves round-trip identity for instance dicts.

Named refs (e.g. `Topology.in: "LoadIn"`) are left as strings; the runtime subsystem that owns
the consuming domain resolves them.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Iterable, Union

import yaml
from pydantic import ValidationError

from agent_glue_lib.core.catalog import (
    Catalog,
    ComponentSchema,
    EntityComponentsSpec,
    EntityInstance,
    EntityTypeDef,
    FieldSchema,
    pascal_to_snake,
)

PathLike = Union[str, Path]
INSTANCE_TOP_LEVEL_KEYS = {"type", "components"}


class LoaderError(Exception):
    """Raised when yaml on disk fails to load into the catalog."""


def _read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        try:
            return yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise LoaderError(f"{path}: yaml parse error: {exc}") from exc


def _expect_mapping(path: Path, doc: Any) -> dict[str, Any]:
    if doc is None:
        raise LoaderError(f"{path}: file is empty.")
    if not isinstance(doc, dict):
        raise LoaderError(f"{path}: top-level must be a mapping, got {type(doc).__name__}.")
    return doc


def _build_field_schema(path: Path, where: str, raw: Any) -> FieldSchema:
    if not isinstance(raw, dict):
        raise LoaderError(f"{path}: {where}: field schema must be a mapping.")
    try:
        return FieldSchema.model_validate(raw)
    except ValidationError as exc:
        raise LoaderError(f"{path}: {where}: invalid field schema: {exc}") from exc


def _load_component_schema(path: Path) -> ComponentSchema:
    doc = _expect_mapping(path, _read_yaml(path))
    extra = set(doc.keys()) - {"kind", "description", "fields"}
    if extra:
        raise LoaderError(f"{path}: unexpected top-level keys: {sorted(extra)!r}.")
    kind = doc.get("kind")
    if not isinstance(kind, str) or not kind:
        raise LoaderError(f"{path}: `kind` must be a non-empty string.")
    if kind != path.stem:
        raise LoaderError(
            f"{path}: filename stem {path.stem!r} must match kind {kind!r}."
        )
    raw_fields = doc.get("fields") or {}
    if not isinstance(raw_fields, dict):
        raise LoaderError(f"{path}: `fields` must be a mapping.")
    fields: dict[str, FieldSchema] = {}
    for fname, fraw in raw_fields.items():
        if not isinstance(fname, str):
            raise LoaderError(f"{path}: field name must be a string, got {fname!r}.")
        fields[fname] = _build_field_schema(path, f"fields.{fname}", fraw)
    return ComponentSchema(
        kind=kind,
        description=doc.get("description"),
        fields=fields,
        source_path=str(path),
    )


def _load_entity_type(path: Path) -> EntityTypeDef:
    doc = _expect_mapping(path, _read_yaml(path))
    allowed = {"name", "description", "stored_at", "components"}
    extra = set(doc.keys()) - allowed
    if extra:
        raise LoaderError(f"{path}: unexpected top-level keys: {sorted(extra)!r}.")
    name = doc.get("name")
    if not isinstance(name, str) or not name:
        raise LoaderError(f"{path}: `name` must be a non-empty string.")
    if name != path.stem:
        raise LoaderError(
            f"{path}: filename stem {path.stem!r} must match name {name!r}."
        )
    raw_components = doc.get("components") or {}
    if not isinstance(raw_components, dict):
        raise LoaderError(f"{path}: `components` must be a mapping.")
    try:
        spec = EntityComponentsSpec.model_validate(raw_components)
    except ValidationError as exc:
        raise LoaderError(f"{path}: invalid components spec: {exc}") from exc
    return EntityTypeDef(
        name=name,
        description=doc.get("description"),
        stored_at=doc.get("stored_at"),
        components=spec,
        source_path=str(path),
    )


def _scan_yaml_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    if not directory.is_dir():
        raise LoaderError(f"{directory}: not a directory.")
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix == ".yaml")


def load_catalog(
    component_dirs: Iterable[PathLike],
    entity_dirs: Iterable[PathLike],
) -> Catalog:
    """Read every `components/*.yaml` and `entities/*.yaml` in the given directories."""
    components: dict[str, ComponentSchema] = {}
    for raw_dir in component_dirs:
        directory = Path(raw_dir)
        for path in _scan_yaml_files(directory):
            schema = _load_component_schema(path)
            if schema.kind in components:
                prior = components[schema.kind].source_path
                raise LoaderError(
                    f"duplicate component schema {schema.kind!r}: {prior} and {path}."
                )
            components[schema.kind] = schema

    entities: dict[str, EntityTypeDef] = {}
    for raw_dir in entity_dirs:
        directory = Path(raw_dir)
        for path in _scan_yaml_files(directory):
            ent = _load_entity_type(path)
            if ent.name in entities:
                prior = entities[ent.name].source_path
                raise LoaderError(
                    f"duplicate entity type {ent.name!r}: {prior} and {path}."
                )
            entities[ent.name] = ent

    return Catalog(component_schemas=components, entity_types=entities)


def _is_entity_instance(doc: Any) -> bool:
    return isinstance(doc, dict) and "type" in doc


def _load_entity_instance(path: Path) -> EntityInstance:
    doc = _expect_mapping(path, _read_yaml(path))
    extra = set(doc.keys()) - INSTANCE_TOP_LEVEL_KEYS
    if extra:
        raise LoaderError(
            f"{path}: instance has unexpected top-level keys: {sorted(extra)!r}; "
            f"only {sorted(INSTANCE_TOP_LEVEL_KEYS)!r} are allowed."
        )
    type_name = doc.get("type")
    if not isinstance(type_name, str) or not type_name:
        raise LoaderError(f"{path}: `type` must be a non-empty string.")
    raw_components = doc.get("components", {}) or {}
    if not isinstance(raw_components, dict):
        raise LoaderError(f"{path}: `components` must be a mapping.")
    components: dict[str, dict[str, Any]] = {}
    for key, value in raw_components.items():
        if not isinstance(key, str):
            raise LoaderError(f"{path}: component key {key!r} must be a string.")
        if value is None:
            value = {}
        if not isinstance(value, dict):
            raise LoaderError(
                f"{path}: component {key!r} value must be a mapping, got {type(value).__name__}."
            )
        components[key] = value
    return EntityInstance(type=type_name, components=components, source_path=str(path))


def load_instances(
    root: PathLike,
    *,
    skip: Iterable[PathLike] = (),
) -> list[EntityInstance]:
    """Recursively scan `root` for yaml files; return every doc that looks like an instance.

    Files whose top-level lacks a `type` key are skipped (they are not entity instances).
    Files in `skip` (or under any skipped directory) are excluded.
    """
    root_path = Path(root)
    if not root_path.exists():
        return []
    if not root_path.is_dir():
        raise LoaderError(f"{root_path}: not a directory.")
    skip_paths = [Path(s).resolve() for s in skip]
    instances: list[EntityInstance] = []
    for path in sorted(root_path.rglob("*.yaml")):
        resolved = path.resolve()
        if any(_is_within(resolved, sp) for sp in skip_paths):
            continue
        doc = _read_yaml(path)
        if not _is_entity_instance(doc):
            continue
        instances.append(_load_entity_instance(path))
    return instances


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def dump_instance(instance: EntityInstance) -> str:
    """Serialize an EntityInstance back to yaml such that round-trip is identity.

    The output yaml parses back to a dict equal to the input components-plus-type dict.
    """
    doc: dict[str, Any] = {"type": instance.type}
    if instance.components:
        doc["components"] = instance.components
    buf = io.StringIO()
    yaml.safe_dump(
        doc,
        buf,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=False,
        width=10**6,
    )
    return buf.getvalue()
