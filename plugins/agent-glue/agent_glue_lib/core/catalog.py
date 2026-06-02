"""Pydantic-typed catalog of component schemas, entity-type definitions, and entity instances.

The catalog is the in-memory shape the loader produces from yaml-on-disk. Validation runs
against ComponentSchema (not a generated Pydantic class) so open-shaped fields (`any`, open
maps) round-trip as plain dicts.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

FIELD_TYPES = ("string", "int", "float", "bool", "list", "map", "enum", "any")


def pascal_to_snake(name: str) -> str:
    """`Topology` -> `topology`, `StateDecl` -> `state_decl`, `FixtureId` -> `fixture_id`."""
    out = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    out = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", out)
    return out.lower()


def snake_to_pascal(name: str) -> str:
    """`state_decl` -> `StateDecl`. Inverse of pascal_to_snake for round-trip purposes."""
    return "".join(part[:1].upper() + part[1:] for part in name.split("_") if part)


class FieldSchema(BaseModel):
    """Schema for a single field on a component, or a nested field inside a list/map."""

    model_config = ConfigDict(extra="forbid")

    type: str
    required: bool = False
    description: Optional[str] = None
    items: Optional["FieldSchema"] = None
    keys: Optional[dict[str, "FieldSchema"]] = None
    value_type: Optional["FieldSchema"] = None
    values: Optional[list[str]] = None


FieldSchema.model_rebuild()


class ComponentSchema(BaseModel):
    """Loaded `components/<Kind>.yaml`."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    description: Optional[str] = None
    fields: dict[str, FieldSchema] = Field(default_factory=dict)
    source_path: Optional[str] = None

    @property
    def instance_key(self) -> str:
        return pascal_to_snake(self.kind)


class EntityTypeDef(BaseModel):
    """Loaded `entities/<Name>.yaml`."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: Optional[str] = None
    stored_at: Optional[str] = None
    components: "EntityComponentsSpec"
    source_path: Optional[str] = None


class EntityComponentsSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


EntityTypeDef.model_rebuild()


class EntityInstance(BaseModel):
    """An instance yaml: `type:` + `components:`.

    `components` is keyed by snake_case (the on-disk form). Values are kept as plain dicts
    so open-shaped fields round-trip without coupling to any Pydantic-typed class.
    """

    model_config = ConfigDict(extra="forbid")

    type: str
    components: dict[str, dict[str, Any]] = Field(default_factory=dict)
    source_path: Optional[str] = None


class Catalog(BaseModel):
    """The full loaded kit: component schemas + entity-type definitions, both keyed by name."""

    model_config = ConfigDict(extra="forbid")

    component_schemas: dict[str, ComponentSchema] = Field(default_factory=dict)
    entity_types: dict[str, EntityTypeDef] = Field(default_factory=dict)

    def component(self, kind: str) -> Optional[ComponentSchema]:
        return self.component_schemas.get(kind)

    def entity_type(self, name: str) -> Optional[EntityTypeDef]:
        return self.entity_types.get(name)
