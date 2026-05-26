# agent-glue: Implementation Plan (parallel-track coordinator)

This plan coordinates parallel development across the four subsystems. It does not duplicate increment content -- each subsystem's named increments live in that subsystem's IMPLEMENTATION-PLAN.md. This document defines: which tracks can develop independently, where the dependency edges land, what the v1 definition of done is, and what is post-v1.

Read this alongside the four subsystem IMPLEMENTATION-PLAN.md documents (`core/`, `claude-work-queue/`, `work-system/`, `graph-system/`) and the matching DESIGN.md + ARCHITECTURE.md docs. Doc-reading responsibilities are in the top-level `CLAUDE.md`.

## Parallel development tracks

Four tracks. Each is owned by a subsystem; each can develop independently against its dependencies. Within a track, the named increments in that subsystem's IMPLEMENTATION-PLAN.md proceed in document order (no numeric phase labels; the order is the order they appear).

### Track: core

**Owner:** core subsystem. **Depends on:** nothing.

Single increment: *Entity-yaml model + ECS loader* (see `core/IMPLEMENTATION-PLAN.md`). Builds the loader + validator + cross-cutting components + Disposition primitive that the other three subsystems compose on.

**Unblocks:** every other track. Until this increment lands, no other subsystem can run its own loader-dependent increments.

### Track: claude-work-queue

**Owner:** claude-work-queue subsystem. **Depends on:** core (for the entity-yaml loader and the cross-cutting Errored component).

Four increments in dependency order: *Queue storage*, *Signaling*, *Execute-and-report loop*, *Consumer API* (see `claude-work-queue/IMPLEMENTATION-PLAN.md`). All design decisions are locked (file-based storage + Stop-hook signaling + open-to-any-writer scope); see `claude-work-queue/DESIGN.md` and `USER-FEEDBACK.md`.

**Unblocks:** the work-system's `claude_inference + claude_agent workers` increment (see Dependency edges below). Until claude-work-queue completes its *Execute-and-report loop* increment, work-system cannot register the two claude-backed workers.

### Track: work-system

**Owner:** work-system subsystem. **Depends on:** core (loader, cross-cutting components). Partially depends on claude-work-queue (see Dependency edges).

Eight increments in dependency order (see `work-system/IMPLEMENTATION-PLAN.md`):

1. *WorkRequest contract + JSON Schema validation*
2. *Submit pipeline + python_script worker*
3. *Show-your-work-as-cache substrate*
4. *openrouter worker*
5. *claude_inference + claude_agent workers* (depends on claude-work-queue's *Execute-and-report loop*)
6. *SideEffects + structured shell-out helper*
7. *InvalidationCriteria + sub-element hashing helper*
8. *Cohort recording substrate + CLI*

The first four can develop in parallel with claude-work-queue once core is done. The fifth waits on claude-work-queue; the remaining three depend only on previous work-system increments.

**Unblocks:** the graph-system's `submit() integration` increment (see Dependency edges).

### Track: graph-system

**Owner:** graph-system subsystem. **Depends on:** core. Partially depends on work-system (see Dependency edges).

Eight increments in dependency order (see `graph-system/IMPLEMENTATION-PLAN.md`):

1. *Graph entity-yaml model*
2. *Contracts module + PipelineState binding*
3. *Graph runtime: variant dispatch*
4. *submit() integration* (depends on work-system's *Show-your-work-as-cache substrate*)
5. *Fan-out (parallel edges)*
6. *Canonical outputs (Jinja path templates)*
7. *Cohort replay + ExpectedOutcome assertions*
8. *CLI surface for graph + stub HTML render*

The first three can develop in parallel with both claude-work-queue and the first half of work-system, gated only on core. The fourth waits on work-system reaching its cache substrate; the remaining four depend only on previous graph-system increments.

## Dependency edges (the gates that close parallel work)

Three concrete gates:

1. **Everyone -> core's *Entity-yaml model + ECS loader*.** Until core completes, no other subsystem can land any increment. This is the only single-point-of-blocking edge in the plan.
2. **work-system's *claude_inference + claude_agent workers* -> claude-work-queue's *Execute-and-report loop*.** The two Claude-backed worker submitters dispatch through the queue's consumer API; the API surface lands in the queue's third increment. The first four work-system increments do not touch this edge.
3. **graph-system's *submit() integration* -> work-system's *Show-your-work-as-cache substrate*.** Nodes that delegate work need `submit()` to provide cached, audited dispatch; the cache substrate lands in the work-system's third increment. The first three graph-system increments do not touch this edge.

No other inter-subsystem dependencies exist. Within each subsystem, sequential dependence is captured by the document order in its own IMPLEMENTATION-PLAN.md.

## Coordination practices

- **Each subsystem's plan stands alone for its own increments.** This document only describes the inter-subsystem edges. Reading any one subsystem plan is sufficient to start work in that subsystem against its declared upstream dependencies.
- **Acceptance criteria are observable.** Every increment's "after this" line is a behavior the v1 plugin can perform that it could not before. A track is "at" an increment when the matching test (or the absence of a regression) is green.
- **No backporting.** Per the no-backwards-compatibility-in-development convention (`core/ARCHITECTURE.md`), an increment that changes a downstream consumer's expectations is applied in a single CL across all affected subsystems.

## v1 definition of done

v1 ships when **every** subsystem has reached the end of its own IMPLEMENTATION-PLAN. Concretely:

- **core:** the *Entity-yaml model + ECS loader* increment is complete; the pre-commit hook validates the kit and every example pipeline.
- **claude-work-queue:** all four increments are complete; the work subsystem's claude workers dispatch through the queue end-to-end with the locked file-based / Stop-hook / open-writer design.
- **work-system:** all eight increments are complete; all four worker types submit with the correct cache + audit semantics; the work-side CLI is operable.
- **graph-system:** all eight increments are complete; graphs run end-to-end; cohort replay works; the stub HTML render emits without crashing; the graph-side CLI is operable.

No partial shipping. The plugin is not published to the marketplace until all of the above hold.

## Out of scope for v1 (post-v1, planned separately)

These are intentionally not part of v1. They become candidates once v1 ships.

- **Example consumer pipelines.** Two example pipelines (character animation, localization) are intended as the first real consumers of agent-glue but are not part of v1. They get their own detailed plans when v1 is ready and they are set up to validate the kit's surface against real workloads.
- **Extraction to standalone plugins.** Several subsystems and adapters could plausibly move out of agent-glue into their own plugins in the plugins-kit marketplace -- the claude-work-queue primitive (broadly useful beyond this kit), the worker submitters that wrap external services (the openrouter-worker registration could move into openrouter-kit alongside its client), claude-workers as a sibling. v1 develops everything in-tree to keep the iteration loop tight; extraction decisions wait for the in-tree shape to settle.
- **The richer HTML render.** v1 ships a stub. The full design-artifact render described in `graph-system/DESIGN.md` (sidecar-driven color coding, schema-rendered contracts, latest-WorkRecord example I/O) lands when a consumer needs the design artifact to be browseable beyond `graph.yaml` as text.
- **Async / streaming variants.** Both `submit()` and the graph runtime are synchronous in v1. A `submit_stream()` for streaming-LLM workers, async runtime for genuinely-parallel-across-workers pipelines, etc., land when a consumer needs them.
- **Gaps surfaced by consumer reviews.** Six adoption-fit gaps were surfaced by the consumer reviews -- domain-shaped output validation hook, parameterized graphs, WorkRecord aggregator API, hand-edit-preserving YAML round-trip, multi-source freshness keys, GroupedSequentialFanOut. They are tracked in `USER-FEEDBACK.md` (which also gives a recommended ordering based on a follow-up use-vs-would-not-use round) and are post-v1 candidate increments; none gates v1, and none has been moved ahead of any v1 increment.
