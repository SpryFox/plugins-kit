# core subsystem context

The **core** subsystem of agent-glue. Provides the substrate every other subsystem composes:

- The yaml-entity-model and ECS loader (component schemas, entity types, instance loading, round-trip).
- Cross-cutting components used by more than one subsystem.
- The Disposition primitive (Accepted | AcceptedWithAudit | Rejected).
- The architectural patterns every subsystem inherits.

Core has no upstream dependencies. The other subsystems all depend on core; nothing in core depends on them.

## Internal lib layout

```
agent_glue_lib/core/
  __init__.py
  catalog.py        # Pydantic types: Catalog, ComponentSchema, EntityTypeDef, EntityInstance, FieldSchema
  loader.py         # yaml-to-Catalog reader; named-ref resolution; round-trip dump
  validator.py      # structural consistency: kit + per-instance
  disposition.py    # Disposition primitive
```

## Where to find things

| Topic | Document |
|---|---|
| Yaml-entity-model, ECS dialect, cross-cutting components catalog, Disposition primitive | DESIGN.md |
| Shared architectural patterns (MVC + ECS, pre-commit consistency, fail-loudly, no-backcompat, scripts as facades, package cohesion, TDD) | ARCHITECTURE.md |
| Cross-cutting component schemas | components/ |
| Core's build increments and acceptance criteria | IMPLEMENTATION-PLAN.md |
