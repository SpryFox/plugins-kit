# agent-glue: Build Map

This document is the cross-subsystem view of how v1 gets built. It defines the dependency edges between subsystems, lists the increments at a glance, names what counts as "v1 done," and frames what is intentionally out of scope.

Each subsystem has its own IMPLEMENTATION-PLAN.md with named increments and acceptance criteria. The full picture requires reading all four together along with the corresponding DESIGN.md and ARCHITECTURE.md files; see the top-level `CLAUDE.md` for the doc reading conventions.

## Subsystem build order and dependencies

Subsystems develop against dependencies, not against each other directly. The structural facts:

- **core** has no upstream dependencies. It builds first; once its single increment is complete, every other subsystem can start.
- **claude-work-queue** depends on core only. Once core is complete it can start. Its open design questions (queue storage, signal mechanism, writer scope) gate its plan from being more than a sketch.
- **work-system** depends on core. Its first several increments (WorkRequest contract + JSON Schema validation, submit pipeline + python_script worker, show-your-work-as-cache substrate, openrouter worker) need only core and openrouter-kit. The `claude_inference` and `claude_agent` worker increment depends on claude-work-queue having reached its "Execute-and-report loop" increment.
- **graph-system** depends on core for its first three increments (entity-yaml model, contracts module + PipelineState binding, runtime variant dispatch). Its `submit()` integration increment depends on work-system having reached its "Show-your-work-as-cache substrate" increment. Subsequent increments depend only on graph-system's own previous increments.

A subsystem that has reached an increment may have downstream subsystems unblocked at the matching point. Each subsystem's IMPLEMENTATION-PLAN.md names the specific increment that opens a dependent's path.

## v1 definition of done

v1 ships when **every** subsystem has reached the end of its own IMPLEMENTATION-PLAN. Concretely:

- core: the entity-yaml model + ECS loader increment is complete; the pre-commit hook validates the kit and every example pipeline.
- claude-work-queue: all four provisional increments (queue storage, signaling, execute-and-report, consumer API) are complete; the work subsystem's claude workers dispatch through it.
- work-system: all eight increments are complete; all four worker types submit with the correct cache + audit semantics; the CLI is operable.
- graph-system: all eight increments are complete; graphs run end-to-end; cohort replay works; the stub HTML render emits without crashing; the CLI is operable.

No partial shipping. The plugin is not published to the marketplace until all of the above hold.

## Out of scope for v1 (post-v1, planned separately)

These are intentionally not part of v1. They become candidates once v1 ships.

- **Example pipelines.** Two example pipelines (character animation, localization) are intended as the first consumers of agent-glue but are not part of v1. They get their own detailed plans when v1 is ready and they're set up to validate the kit's surface against real workloads.
- **Extraction to standalone plugins.** Several subsystems and adapters could plausibly move out of agent-glue into their own plugins in the plugins-kit marketplace -- the claude-work-queue primitive (broadly useful beyond this kit), the worker submitters that wrap external services (the openrouter-worker registration could move into openrouter-kit alongside its client), claude-workers as a sibling. v1 develops everything in-tree to keep the iteration loop tight; extraction decisions wait for the in-tree shape to settle.
- **The richer HTML render.** v1 ships a stub. The full design-artifact render described in `graph-system/DESIGN.md` (sidecar-driven color coding, schema-rendered contracts, latest-WorkRecord example I/O) lands when a consumer needs the design artifact to be browseable beyond `graph.yaml` as text.
- **Async / streaming variants.** Both `submit()` and the graph runtime are synchronous in v1. A `submit_stream()` for streaming-LLM workers, async runtime for genuinely-parallel-across-workers pipelines, etc., land when a consumer needs them.
