# agent-glue: Graph-System Architecture

Entities, components, and systems specific to the graph subsystem. MVC + ECS framing comes from the parent ARCHITECTURE.md.

## Entities

Entity type definitions live as yaml files in `./entities/`. Each file declares one entity type, the components it may carry (required + optional), and where instances are stored in a consuming project. The yaml is the source of truth; the loader reads it at startup to populate the entity catalog.

Graph-subsystem entity types:

- `Graph` -- top-level pipeline container
- `Node` -- a unit of work in a graph
- `Edge` -- a typed transition between nodes
- `Cohort` -- collection of test fixtures for replay (work recordings live in the work subsystem)
- `Fixture` -- one starting state for replay (StartInput + InitState)
- `ExpectedOutcome` -- optional assertion target for a fixture (TerminalNode + optional TerminalOutput / TerminalState)

There is no per-run trace in the graph subsystem -- no `Run` entity, no `NodeInvocation` entity. The graph runtime walks the graph and dispatches nodes; auditability for work that nodes delegate via `submit()` comes from the work subsystem's `WorkRecord` entities. In-impl node work has no record by design (nodes that need auditability should delegate).

Two entity-shaped concepts that stay Python-backed because `impl.py` consumes them with type hints:

- **Contract** -- Pydantic models (and discriminated unions) in `graphs/<name>/contracts.py`. Referenced from yaml by name; the loader resolves the name to a class.
- **PipelineState** -- the Pydantic model whose shape is declared in `graph.yaml` `state:` and instantiated by the runtime per-run. Init fields are read-only after pipeline start; accumulated fields are mutated via `StateDelta` returned by nodes.

## Components

Component schemas live as yaml files in `./components/` (authored in Phase 1 alongside the loader). Each file declares one component's `kind`, its fields, and their types. Presence is the signal -- an entity has a component or it doesn't.

Component types referenced by graph-subsystem entities (authored in Phase 1):

- Identity-shaped: `Version`, `FixtureId`
- Graph topology: `Start`, `Topology`, `Source`, `Target`, `ParallelSpec`, `Implementation`
- Graph state declaration: `StateDecl`, `InitState`
- Node sidecars: `Rules`, `Prompt`, `Outputs` (containing `OutputArtifactSpec` records)
- Cohort substrate: `Fixtures`, `Expected`, `StartInput`, `FixtureRef`, `TerminalNode`, `TerminalOutput`, `TerminalState`, `CreatedAt`
- Graph-level config: `Config`, `ShowWork` (also valid at node scope as a per-node override)

Cross-cutting components used by both subsystems (`Name`, `Description`, `Timestamps`, `Errored`, `Status`, `SourceRunId`) live at the plugin level in `agent-glue/components/`. Subsystems reference them by name; neither subsystem depends on the other.

## Yaml primitive vocabulary

The model uses only these yaml primitives:

- **scalars** -- strings, ints, bools, nulls
- **lists** -- ordered sequences
- **maps** -- key/value pairs
- **named refs** -- bare strings interpreted as references to entities defined elsewhere (e.g. `in: ValidateIn` is a string interpreted as a contract name; the loader resolves it)
- **path templates** -- strings with `{state.x}` / `{input.x}` substitutions; resolved at write time

No custom yaml tags, no expressions, no code in yaml. A pure-yaml linter can validate the model structure without instantiating anything.

## Worked example: one Node entity

A `validate_assignments` node from the character animation example, as an instance composing components:

```yaml
# graphs/character_animation/nodes/validate_assignments/node.yaml
type: Node
components:
  name:
    name: validate_assignments
  description:
    description: Check each proposed animation against the speaker's allowed set.
  topology:
    in: ValidateIn
    out: ValidateResult
  implementation:
    module: impl
    function: execute
  rules:
    path: rules.yaml
  # no `prompt` component -> not an LLM node
  # no `outputs` component -> does not write a canonical artifact
  # no `show_work` component -> follows the graph's global show-your-work setting
```

The same node's directory:

```
nodes/validate_assignments/
  node.yaml      # the entity above
  impl.py        # the Python implementation
  rules.yaml     # the rule data the impl consumes
```

Adding a `prompt` component later (e.g. to use an LLM as a fallback when the rule set is incomplete) is just adding a `prompt:` block and a `prompt.md` file. No loader change, no entity-type change.

## Worked example: one Edge entity

```yaml
# inline in graphs/character_animation/graph.yaml under edges:
- type: Edge
  components:
    source:
      from_node: validate_assignments
      on_variant: NeedsRetry
    target:
      to_node: propose_assignments
    # no `parallel_spec` component -> sequential dispatch
```

## Worked example: a Fixture entity instance

```yaml
# graphs/character_animation/cohorts/default/inputs/amano_001.yaml
type: Fixture
components:
  fixture_id:
    id: amano_001
  start_input:
    conversation_path: dialog/Amano_FirstMeeting.csv
  init_state:
    conversation_id: amano_001
    target_cl: 12345
  source_run_id:
    run_id: 2026-05-24T15-22-01_abc123    # optional: which live run produced this fixture
```

The companion ExpectedOutcome (optional) asserts the terminal state when this fixture replays.

## Systems

A "system" is Python code that traverses the model. Each does one job.

- **Loader** -- reads entity type yamls (`./entities/*.yaml`) + component schema yamls (`./components/*.yaml`) + a consuming project's graph yamls; resolves named refs (contract names -> Pydantic classes; implementation refs -> Python modules); produces an in-memory entity catalog the runtime can walk.
- **Runtime** -- given a Graph entity + a StartInput + an InitState, instantiates the PipelineState, walks nodes from the Start node, validates inputs against `Topology.in`, calls `Implementation`, validates outputs against `Topology.out`, applies dispatch via Edge `Source.on_variant`. Returns terminal node + terminal output + terminal state. No per-node serialization; auditability comes from the work subsystem when nodes delegate.
- **Renderer (one View)** -- reads any subset of entities (Graph + Nodes + Edges, or Cohort + Fixtures, etc.) plus optionally the most-recent cached `WorkRecord`s for example I/O, and emits HTML. Other Views are possible without changes to the Model or Controller; some Views may also be Controllers (V+C hybrid).
- **Cohort replayer** -- reads Cohort + Fixtures, invokes the runtime per fixture with the cohort's recordings directory as the work cache, compares the runtime's terminal output/state against ExpectedOutcome if present.
- **Promote-fixture** -- writes a new Fixture entity into a target Cohort from the start state of a live run.
- **Validator** (CLI `validate`) -- reads a Graph + its Nodes + Edges; checks structural integrity (start node exists, edges resolve, contract names import, sidecar paths exist when components reference them).

Each system has a single read/write contract over the model. No system knows about other systems' internals.

## Open questions

1. **Renderer-readable component-presence query.** The renderer derives node visualization from "which components does this entity have?" Worth a small helper in the loader (`entity.has("prompt")`) vs. just checking dict keys directly. Lean helper for discoverability. Finalize when the renderer is built (Phase 9).
