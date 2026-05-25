# agent-glue: Architecture Overview

Both subsystems share the same internal patterns:

- **MVC layering.** Model = yaml entities. View = renderer (one View ships in v1; more are possible). Controller = runtime + CLI. Some Views may also act as Controllers (V+C hybrid) -- a renderer that exposes operations to mutate state is permissible. The constraint is that the Model remains the source of truth; mutations flow through it, not around it.
- **ECS data model.** Entities are composed of typed components. No class hierarchy to extend; new entity flavors are new component definitions plus systems that operate on them.
- **Yaml primitives only in the model.** Scalars, lists, maps, named refs. No custom yaml tags, no expressions, no eval.
- **Two things stay Python.** Contracts (Pydantic, referenced from yaml by name) and Implementations (`impl.py` / worker modules). The model knows they exist by name; Python provides validation and execution.

Subsystem-specific entities, components, and systems live in `graph-system/ARCHITECTURE.md` and `work-system/ARCHITECTURE.md`.

## Shared patterns

Architectural decisions that apply across both subsystems.

### Pydantic at the yaml boundary

Both subsystems load yaml into Pydantic models at the system boundary, then operate on typed in-memory objects. The yaml is the durable model; Pydantic provides validation and type hints in the Python systems. Pydantic models are *derived from* the yaml model, not the source of truth.

### Show-your-work as cache (work subsystem)

The work subsystem owns show-your-work end-to-end. Every successful `submit()` writes a `WorkRecord` keyed by request hash; the next identical request returns the cached result without re-invoking the worker. Records are the audit trail and the cache, simultaneously.

The graph subsystem does **not** maintain its own per-run trace. Nodes that want auditability or caching delegate via `submit()`; in-impl node work has no record by design. This keeps show-your-work in one place (one mechanism, one storage convention) and makes the cache + audit story uniform regardless of consumer.

### Cohort directory convention

Cohorts live under the graph that owns them, by convention:

```
graphs/<name>/cohorts/<cohort_name>/
  recordings/<worker_type>/<request_hash>.yaml    # WorkRecords; cohort-mode submit() looks here
  cohort.yaml                                     # Cohort entity (Fixtures + ExpectedOutcomes)
  inputs/<fixture_id>.yaml                        # Fixture entities (start input + init state)
  expected/<fixture_id>.yaml                      # ExpectedOutcome entities (terminal assertions)
```

Cohort recordings reuse the work subsystem's record format and lookup mechanism -- cohort-mode at `submit()` time just points the cache directory at the cohort's `recordings/`. No separate "cohort recording" entity; recordings are `WorkRecord`s in a different home.

### One thing at a time, fail clearly

Both subsystems treat failure as a first-class outcome. The graph subsystem's iron contract (`Disposition = Accepted | AcceptedWithAudit | Rejected`) and the work subsystem's failure modes (`CapabilityUnavailable`, `OutputSchemaViolation`, `WorkerError`) are different shapes but the same philosophy: never silently substitute, never auto-retry without consumer instruction, never return a partial result without raising.

### Fail loudly on changed conditions

agent-glue checks ambient conditions (available tools, MCP servers, registered functions, on-disk capability sets) ONCE -- at startup or on first use -- caches the result, and fails loudly if a subsequent operation discovers the condition has changed. The plugin does not adapt to changing conditions to keep things working; adapting silently hides bugs and produces non-deterministic behavior.

When a cached condition is invalidated mid-run (an MCP server becomes unreachable, an allowlisted function disappears, a previously-present capability is now missing), the next operation that depends on it raises a clear error naming the condition and the change observed. The consumer either restarts the session against a stable environment or fixes the upstream cause; the runtime does not paper over the drift.

This is the source of several specific behaviors elsewhere: claude_agent worker checks `provided_capabilities` once and fails loudly if missing later; `agent-glue work validate` does NOT pre-check capabilities (the actual failure at execution time is the signal); the cache invalidates aggressively when any input or worker config changes.

### Temperature zero for LLM workers

All LLM worker calls (currently the `openrouter` worker; any future LLM worker) use temperature 0 unconditionally. This is an architectural constraint, not a configurable default.

Rationale: temperature 0 makes the same request reliably produce the same output (modulo model drift between releases), which makes the work-subsystem cache (a WorkRecord per unique request) a true cache rather than a hash-pinned lookup of a non-deterministic source. Cohort recordings can be replayed with confidence; show-your-work records can be relied on as authoritative.

The openrouter worker rejects requests that try to set a non-zero temperature.

### Pre-commit consistency over schema versioning

Entity-type yamls, component-schema yamls, instance yamls, and the loader must all validate consistently before any commit. There is no per-component `version:` field and no migration shim layer; git history is the canonical record of what existed before (a commit sha identifies a coherent snapshot).

The pre-commit hook runs the loader against the full kit + every example pipeline; any inconsistency (missing component, type mismatch, instance referencing an unknown component) fails the commit. Consumers update the entity yamls, the component schemas, the instance yamls, and the loader's expectations in a single CL.

Combined with *no backwards compatibility in development*, this means rename and reshape operations are atomic per-commit and the corpus is always self-consistent.

### Yaml primitive vocabulary

Both subsystems use the same primitive vocabulary: scalars, lists, maps, named refs (bare strings resolved by loaders), and path templates (in the graph subsystem only). No custom yaml tags, no eval, no expressions. The model is a pure-yaml linter's domain.

### No backwards compatibility in development

agent-glue is in active development. Changes don't carry deprecation shims, alias layers, removed-API stubs, or backwards-compatibility facades. Renames are direct; removals are direct; field reshapings don't leave a parallel old shape behind. Git history is the canonical record of what existed before — if a developer needs to understand a prior shape, `git log` and `git show` are the tools, not surviving artifacts in the codebase.

This applies across yaml (no `_v1` / `_v2` parallel fields), Python (no `@deprecated` aliases kept around), and CLI (no hidden flags preserved for old callers). If a change breaks existing in-flight work, the migration is documented in the commit and applied in one pass.

### Scripts as facades

All CLI scripts (under `bin/`, `scripts/`) are thin facades over `agent_glue_lib/`. Scripts parse arguments, call library functions, format output for terminal display. They contain no business logic, no domain decisions, no orchestration that isn't expressible by library calls. Tests target the library, not the scripts; the script layer is verified by smoke tests that confirm the facade wiring works end-to-end.

This rule makes the library the testable surface, keeps the scripts trivially replaceable, and means that any consumer that doesn't want the CLI can use the library directly with no impedance.

### Package cohesion (CRP / CCP / ADP)

Library code organization follows Robert C. Martin's package cohesion principles:

- **Common Reuse Principle (CRP)** — code that's reused together belongs in the same module. Don't force a consumer to import unrelated code to use the one thing they need. Split modules when their contents serve different reuse patterns.
- **Common Closure Principle (CCP)** — code that changes for the same reason belongs in the same module. When a system is updated, ideally only one module needs to change.
- **Acyclic Dependencies Principle (ADP)** — the dependency graph between modules is a DAG. No circular dependencies between modules.

Applied to agent-glue: the `agent_glue_lib/graph/` and `agent_glue_lib/work/` split is a CCP application (graph things change together; work things change together; they don't share a change driver). The one-way `graph → work` dependency is an ADP application (no cycles). Within each subsystem, file organization follows the same principles — e.g. cohort logic in its own module because it's reused across multiple call sites (CRP) and changes together (CCP).

## Cross-subsystem interface

The graph subsystem reaches the work subsystem through a single function:

```python
from agent_glue_lib.work import submit, WorkRequest

result = submit(request=..., cohort=..., strict=...)
```

The graph subsystem constructs `WorkRequest` instances and calls `submit()`. The work subsystem fulfills them and returns `WorkResult`. Swapping worker types on a per-call basis is a request-config change; the caller's code is unchanged.

