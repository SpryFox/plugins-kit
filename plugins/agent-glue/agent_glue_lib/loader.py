"""Reads the kit's yaml model into a typed in-memory Catalog.

The loader is the entire boundary between yaml-on-disk and the Python systems.
Anything that wants typed access to the entity model goes through here; nothing
else reads `.yaml` files in `components/`, `entities/`, or instance directories.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Union

import yaml

from .catalog import Catalog, ComponentSchema, EntityInstance, EntityTypeDef


class LoaderError(Exception):
    pass


PathLike = Union[str, Path]


def _read_yaml(path: Path) -> object:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_component_schemas(*dirs: PathLike) -> dict[str, ComponentSchema]:
    schemas: dict[str, ComponentSchema] = {}
    for raw in dirs:
        directory = Path(raw)
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            data = _read_yaml(path) or {}
            if not isinstance(data, dict):
                raise LoaderError(f"{path}: component schema must be a yaml mapping")
            schema = ComponentSchema(source_path=str(path), **data)
            if path.stem != schema.kind:
                raise LoaderError(
                    f"{path}: filename stem '{path.stem}' does not match kind '{schema.kind}'"
                )
            if schema.kind in schemas:
                raise LoaderError(
                    f"duplicate component schema kind '{schema.kind}': "
                    f"{schemas[schema.kind].source_path} and {schema.source_path}"
                )
            schemas[schema.kind] = schema
    return schemas


def load_entity_types(*dirs: PathLike) -> dict[str, EntityTypeDef]:
    types: dict[str, EntityTypeDef] = {}
    for raw in dirs:
        directory = Path(raw)
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            data = _read_yaml(path) or {}
            if not isinstance(data, dict):
                raise LoaderError(f"{path}: entity type definition must be a yaml mapping")
            components_block = data.pop("components", {}) or {}
            etype = EntityTypeDef(
                source_path=str(path),
                required_components=list(components_block.get("required") or []),
                optional_components=list(components_block.get("optional") or []),
                **data,
            )
            if path.stem != etype.name:
                raise LoaderError(
                    f"{path}: filename stem '{path.stem}' does not match entity-type name '{etype.name}'"
                )
            if etype.name in types:
                raise LoaderError(
                    f"duplicate entity type '{etype.name}': "
                    f"{types[etype.name].source_path} and {etype.source_path}"
                )
            types[etype.name] = etype
    return types


def load_instances(*paths: PathLike) -> list[EntityInstance]:
    """Read entity instances from yaml files or directories (recursively).

    Yaml files that don't have a `type:` key are skipped (e.g. `rules.yaml`
    sidecars, `cohort.yaml` files for not-yet-modeled entities). Files that do
    have `type:` must also have `components:` (may be empty) and nothing else.
    """
    instances: list[EntityInstance] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for path in sorted(p.rglob("*.yaml")):
                instance = _maybe_instance(path)
                if instance is not None:
                    instances.append(instance)
        elif p.is_file():
            instance = _maybe_instance(p, required=True)
            if instance is not None:
                instances.append(instance)
        else:
            raise LoaderError(f"{p}: not a file or directory")
    return instances


def _maybe_instance(path: Path, required: bool = False) -> EntityInstance | None:
    data = _read_yaml(path)
    if not isinstance(data, dict):
        if required:
            raise LoaderError(f"{path}: expected a yaml mapping")
        return None
    if "type" not in data:
        if required:
            raise LoaderError(f"{path}: missing required key 'type'")
        return None
    extra = set(data) - {"type", "components"}
    if extra:
        raise LoaderError(
            f"{path}: entity instance may only have 'type' and 'components' "
            f"at top level; got unexpected keys: {sorted(extra)}"
        )
    return EntityInstance(
        source_path=str(path),
        type=data["type"],
        components=data.get("components") or {},
    )


def load_kit(plugin_root: PathLike) -> Catalog:
    """Load every component schema and entity type shipped with the kit.

    Does not load any instances. Use `load_with_instances` to additionally pull
    in a consuming project's graph/cohort/etc. yamls.
    """
    root = Path(plugin_root)
    component_schemas = load_component_schemas(
        root / "components",
        root / "graph-system" / "components",
        root / "work-system" / "components",
    )
    entity_types = load_entity_types(
        root / "graph-system" / "entities",
        root / "work-system" / "entities",
    )
    return Catalog(
        component_schemas=component_schemas,
        entity_types=entity_types,
    )


def load_with_instances(
    plugin_root: PathLike, instance_paths: Iterable[PathLike]
) -> Catalog:
    catalog = load_kit(plugin_root)
    catalog.entities = load_instances(*instance_paths)
    return catalog


def dump_instance(instance: EntityInstance) -> str:
    """Dump an instance back to yaml text. Used to verify round-trip cleanliness."""
    payload: dict[str, object] = {"type": instance.type}
    if instance.components:
        payload["components"] = instance.components
    return yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)
