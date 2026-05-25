"""In-memory typed model for the kit's entity catalog.

Component values are stored as plain dicts rather than per-component Pydantic
classes because the SSOT for component shape is the yaml schema, not Python.
Structural validation (required fields, types, enum values) is performed by the
validator against the loaded ComponentSchema; consumers that want richer Python
typing parse the dict into their own model.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class FieldSchema(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    kind: str
    description: Optional[str] = None
    fields: dict[str, FieldSchema] = Field(default_factory=dict)
    source_path: Optional[str] = None


class EntityTypeDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: Optional[str] = None
    stored_at: Optional[str] = None
    required_components: list[str] = Field(default_factory=list)
    optional_components: list[str] = Field(default_factory=list)
    source_path: Optional[str] = None


class EntityInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    components: dict[str, Any] = Field(default_factory=dict)
    source_path: Optional[str] = None


class Catalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_schemas: dict[str, ComponentSchema] = Field(default_factory=dict)
    entity_types: dict[str, EntityTypeDef] = Field(default_factory=dict)
    entities: list[EntityInstance] = Field(default_factory=list)
