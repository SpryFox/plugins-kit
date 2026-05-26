# core: Design

## TL;DR

Core ships the loader, the validator, the cross-cutting components, and the Disposition primitive. Every other subsystem composes on top of these. Core itself defines no entity types -- entity types live in the subsystems that use them.

## Yaml-entity-model

The substrate is yaml; the data model is ECS (entities composed of typed components). All four agent-glue subsystems express their model in this dialect; core defines what the dialect means.

**Entity type definitions** live as `entities/<EntityName>.yaml` files in the subsystem that owns the entity. Each file declares the entity's name, where instances are stored in a consuming project, and which components an instance may carry (required + optional).

```yaml
name: Node
description: A unit of work in a graph.
stored_at: graphs/<name>/nodes/<node_name>/node.yaml
components:
  required:
    - Name
    - Topology
    - Implementation
  optional:
    - Description
    - Rules
    - Prompt
    - Outputs
    - ShowWork
```

**Component schemas** live as `components/<ComponentName>.yaml` files in either core (for cross-cutting components) or the subsystem that owns them. Each file declares the component's `kind`, the fields it carries, and the type of each field.

```yaml
kind: Topology
description: Input and output contract names for a node.
fields:
  in:
    type: string
    required: true
  out:
    type: string
    required: true
```

**Instances** live in consuming projects (a graph at `graphs/<name>/`, a cohort at `cohorts/<name>/`, etc.). Each instance file has exactly two top-level keys -- `type` and `components` -- and the loader rejects anything else.

```yaml
type: Node
components:
  name:
    name: load
  topology:
    in: LoadIn
    out: LoadResult
  implementation:
    module: impl
    function: execute
```

Component-instance keys are snake_case versions of the component's PascalCase `kind` (`Topology` -> `topology`, `StateDecl` -> `state_decl`). The loader normalizes between them.

## Component-schema dialect

Top-level keys: `kind` (PascalCase, must match filename stem), `description`, `fields`.

Each entry in `fields` has:

- `type`: one of `string`, `int`, `float`, `bool`, `list`, `map`, `enum`, `any`.
- `required`: defaults to false.
- `description`: optional.
- `items` (for `type: list`): a nested field-schema describing each item.
- `keys` (for `type: map` with a known structure): a map of inner-field-name to nested field-schema.
- `value_type` (for `type: map` open-shaped): a nested field-schema describing every value in the map. Only one of `keys` and `value_type` is used per field.
- `values` (for `type: enum`): the list of allowed strings.

The dialect is intentionally narrow. There are no custom yaml tags, no expressions, no eval. A pure-yaml linter can structurally validate the model without instantiating anything.

## Cross-cutting components

Components used by entities in more than one subsystem live in core. Today's set:

- **Name** -- human-readable identifier; unique within the entity-type scope.
- **Description** -- free-form prose describing the entity.
- **Timestamps** -- `created_at` (required) and `updated_at` (optional) ISO-8601 strings.
- **Errored** -- failure state with `error_type`, `message`, and open-shaped `metadata`.
- **Status** -- entity-type-specific lifecycle value (allowed values constrained by the consuming subsystem).
- **SourceRunId** -- run identifier (opaque string) for entities produced by a live run.

Other subsystems reference these by name in their own entity-type definitions. New cross-cutting components land here when at least two subsystems use the same shape.

## Disposition primitive

A typed-outcome ADT shipped by core and importable from any subsystem:

```python
class Accepted(BaseModel, Generic[T]):
    kind: Literal["accepted"] = "accepted"
    value: T

class AcceptedWithAudit(BaseModel, Generic[T]):
    kind: Literal["accepted_with_audit"] = "accepted_with_audit"
    value: T
    audit_reason: str
    audit_metadata: dict

class Rejected(BaseModel):
    kind: Literal["rejected"] = "rejected"
    reason: str
    metadata: dict

Disposition = Accepted[T] | AcceptedWithAudit[T] | Rejected
```

The pattern: "every input gets a recorded disposition; failures are first-class outcomes, not exceptions." Subsystems compose `Disposition[T]` into their own output types when the typed-success / audited-success / rejected three-way split is useful.

The graph subsystem's variant dispatch knows the three Disposition variants natively (an edge can target `Accepted`, `AcceptedWithAudit`, or `Rejected` by name). Subsystems that want different outcome shapes compose plain Pydantic discriminated unions; Disposition is for the common case, not mandatory.

## Variant dispatch

A library primitive for branching on the variant of a discriminated-union output. Shipped by core; importable from any subsystem.

```python
from agent_glue_lib.core.dispatch import dispatch

result = dispatch(variant, handlers={
    "accepted": handle_accepted,
    "accepted_with_audit": handle_audit,
    "rejected": handle_rejected,
})
```

The primitive reads the variant's discriminator field (`kind` by convention) and calls the matching handler with the variant value. If no handler matches and no `default` is supplied, it raises a typed `NoHandlerForVariant` error.

The graph runtime uses this primitive internally to route on Edge `Source.on_variant`. Consumers that want the same dispatch shape inside a single worker's post-processing (e.g. routing per-line `Disposition` results without instantiating a graph) call `dispatch` directly. Per the package cohesion principles in `core/ARCHITECTURE.md`, the dispatch logic lives in one place and serves both call sites.

## Loader behavior

The loader is the single boundary between yaml-on-disk and the Python systems. It:

1. Reads every `components/*.yaml` from a list of directories, builds `ComponentSchema` objects, rejects duplicates and filename-vs-kind mismatches.
2. Reads every `entities/*.yaml` from a list of directories, builds `EntityTypeDef` objects, rejects duplicates and filename-vs-name mismatches.
3. Reads instance yamls from a consuming directory (recursively), builds `EntityInstance` objects, skips yaml files that aren't entity instances (no `type:` key), rejects entity instances with unexpected top-level keys.
4. Dumps an `EntityInstance` back to yaml such that the round-trip is identity for any valid input.

The loader does NOT resolve Python contract refs (e.g. `Topology.in: "LoadIn"` is left as a string). That resolution happens in the runtime subsystems that need it, with access to the consuming project's `contracts.py`.

## Validator behavior

Three layers, all returning a flat list of error strings (empty list = success):

- **Kit consistency** -- every entity-type's required/optional components reference known component schemas.
- **Instance shape** -- every instance declares a known entity type, satisfies the type's required components, restricts itself to allowed components, and every component value matches its schema (required fields present, types match, enum values in the allowed set, list items / map values typed correctly, no unknown fields).
- **Combined** -- both of the above, run together; this is what the pre-commit hook calls.

Pre-commit hook semantics, plus the broader posture on schema versioning and backward compatibility, live in ARCHITECTURE.md.
