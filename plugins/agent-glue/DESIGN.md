# agent-glue: Plugin Overview

A lightweight kit for declaring and running pipelines that interleave LLM inference, deterministic logic, and config-driven rules. Distributed via the `plugins-kit` marketplace.

## Subsystems

### Work subsystem

Does individual units of work. A typed request goes to a worker; the worker fulfills it; a typed result comes back. Workers are pluggable.

Designed-in worker types:

- **openrouter** -- single-shot LLM completion via openrouter-kit (OpenAI SDK pointed at OpenRouter; multi-model). Determinism defaults to `deterministic` (cacheable, temperature 0); consumers may override per-request to `non_deterministic`, in which case the worker uses a non-zero temperature (default 0.7) under the hood and skips cache lookups. Temperature is not a user-facing config field; it's derived from the declared determinism.
- **claude_inference** -- single-shot Claude Code subagent dispatch with **no tools enabled** (pure inference). Same shape as openrouter, but uses Claude Code's own subagent runtime rather than a third-party API. Same determinism semantics as openrouter (default `deterministic`, overridable per-request, temperature follows).
- **claude_agent** -- Claude Code subagent with **tool access** (Read/Write/Edit/Bash/Grep/MCP servers). The agent performs autonomous multi-step work with side effects. Determinism: **must be declared per WorkRequest** -- the consumer asserts the specific usage is `deterministic_idempotent` (cacheable) or `non_deterministic` (not cacheable). Submit raises if the declaration is missing. There is no default because file-modifying work cannot be safely guessed.
- **python_script** -- any dotted-name Python function with typed input/output. The function may do anything internally, including shelling out to external processes. Determinism: **must be declared per WorkRequest** (no default). Pure transformations declare `deterministic_idempotent`; file-modifying or otherwise side-effecting scripts declare `non_deterministic`. When a script does shell out (Unreal commandlets, build tools), the recommended pattern is to declare `consumes_dirs` + `produces_dirs` on the WorkerSelection config and populate `SideEffects` on the WorkResult -- the kit uses these to drive cache invalidation and cohort-replay safety. See the worked example in work-system/DESIGN.md.

The contract is worker-agnostic: yaml input + JSON-Schema-shaped output schema (authored as yaml) + worker-specific config -> yaml output. Adding another worker type is a focused piece of work (register a Python module + declare its components).

The work subsystem also owns the **show-your-work + cache** mechanism (see below).

### Graph subsystem

Wires units of work into pipelines. Provides nodes, edges, typed contracts at every boundary, discriminated-union dispatch on output variants, and canonical persistent outputs (declared via `outputs:` on a node).

The graph subsystem has no per-run auditing of its own; nodes that want auditability or caching delegate to the work subsystem.

## How nodes and work relate

**Every node encompasses a unit of work.** How that work is performed is the node's choice:

- **In-impl** -- the node's `impl.py` does the work directly. Pure Python. Common for trivial logic, file I/O, data transformations. No audit record, no caching.
- **Delegated** -- the node's `impl.py` constructs a `WorkRequest` and calls `agent_glue_lib.work.submit(request)`. The work subsystem returns a `WorkResult` that the node parses into its typed output. The submission is automatically audited and cached.

The graph subsystem doesn't care which choice a node makes. From its perspective, every node has an `impl.py` that takes a typed input and returns a typed output. Sidecar presence (`prompt.md`, `rules.yaml`) hints at what kind of work the node does but doesn't dictate the execution path.

**Rule of thumb:** if the work is expensive (LLM call, agent invocation, long-running computation) or non-trivial (worth re-reading later to debug), delegate via `submit()`. If it's a cheap data-shape transform, do it in-impl.

Other consumers (a renderer, a test harness, future tooling) can use the work subsystem directly without touching the graph subsystem.

## Show-your-work and cache (one mechanism)

Avoiding repetition of work when inputs haven't changed is a first-class principle. The mechanism that records what happened (the audit trail) is the same mechanism that lets us skip re-doing identical work (the cache). One thing, two functions.

The work subsystem owns this mechanism end-to-end. Every successful `submit()` writes a `WorkRecord` keyed by the request hash. On the next `submit()` with the same hash, the recorded result is returned without re-invoking the worker.

- **Default behavior.** Deterministic workers (the default) get cached. Identical request -> recorded result; the worker is never invoked. Identical-cohort replay is the same lookup against a different directory.
- **Cache invalidation criteria.** A request may carry optional `CacheControl: invalidate_if: ...` criteria -- additional preconditions for the cache entry to be considered fresh (e.g. file mtime, env-var value, source-content hash). If criteria fail, treat as cache miss.
- **Per-request bypass.** A request may carry `CacheControl: bypass: true` to force a re-run regardless of cache state. The record is overwritten with the fresh result.
- **Non-deterministic workers.** A worker may declare `Determinism: non_deterministic`, in which case cache lookups never match (every call hits the worker). Records are still written for audit. The temperature-0 architectural constraint keeps all LLM workers deterministic, so this is for hypothetical future workers that genuinely cannot be cached.
- **Disabling records entirely.** The plugin-level `show_work: never` setting suppresses all `WorkRecord` writes; this also disables cache. For hot loops where records are noise.

The graph subsystem does **not** maintain a per-run trace of its own. If you want to know what happened during a run, look at the `WorkRecord`s produced during it (each carries an optional `SourceRunId` for cross-run aggregation). In-impl node work has no record by design; nodes that want auditability should delegate via `submit()`.

Full mechanism details, directory layouts, and CLI surface live in `work-system/DESIGN.md`.
