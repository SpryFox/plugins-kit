# work-system: Architecture

Entities, components, and systems specific to the work subsystem. Shared patterns are in `core/ARCHITECTURE.md` and not restated here.

**Visual companions:**

- [submit-lifecycle.html](submit-lifecycle.html) -- the submit() pipeline as a 5-band lifecycle diagram (hash + read, hit short-circuit, miss + dispatch, validate + write + return, and a variants band for `CacheControl.bypass` / `non_deterministic` / cohort mode). Same algorithm as the *Show-your-work as cache* section below; the visual is faster to follow for cache-decision questions.
- [cache-substrate.html](cache-substrate.html) -- WorkRecord lifecycle as a dataflow: producer -> submit() -> live cache (always-write) / cohort recordings (read-swap), with the WorkRecord shape, cache-lookup decision tree, and cohort directory layout shown side-by-side. Covers the show-your-work-as-cache mechanism end-to-end.

The work subsystem owns the show-your-work mechanism, which doubles as the disk cache. Records written for audit are the same records consulted for cache hits; one mechanism serves both purposes. See the *Show-your-work as cache* section below.

Worker selection is "find a worker whose components satisfy the request's `CapabilityRequirement`." Capability requirements on the request side are matched against the worker entity's `ProvidedCapabilities` component. Adding a worker type is registering the worker module + declaring its components; the matching logic is unchanged.

## Entities

Entity type definitions live as yaml files in `./entities/`. Each file declares one entity type, the components it may carry (required + optional), and where instances are stored. The yaml is the source of truth; the loader reads it at startup to populate the entity catalog.

Work-subsystem entity types:

- `WorkRequest` -- one unit of work to perform
- `WorkResult` -- the worker's response to a WorkRequest
- `Worker` -- a capability-bearing fulfillment backend
- `WorkRecord` -- one unit of completed work, recorded for audit and serving as the cache entry for that request. Same shape for live runs and cohort fixtures; only the storage directory differs.

There is no separate "invocation" entity, no separate "cohort recording" entity, no separate "cohort request" entity. One WorkRecord covers all three uses (live audit, live cache, cohort replay) by virtue of identical shape and lookup mechanism.

## Components

Component schemas live as yaml files in `./components/`. Each file declares one component's `kind`, its fields, and their types. Presence is the signal -- an entity has a component or it doesn't.

Component types referenced by work-subsystem entities:

- Request shape: `Input`, `OutputSchema`, `WorkerSelection`, `CapabilityRequirement`, `CacheControl` (fields: `bypass`, `invalidate_if`, `determinism`)
- Result shape: `Output`, `SideEffects` (discriminated union: file-written, tool-used, subprocess-invoked), `Metadata`
- Worker definition: `WorkerType`, `ProvidedCapabilities`, `Submitter`, `DefaultConfig`, `Determinism` (values: `deterministic` / `requires_declaration`)
- Record shape: `RequestHash`, `InputsHash`, `Request`, `Result`, `WorkerRef`, `RecordedAt`, `Attribution`, `InvalidationCriteria`

The work subsystem references the cross-cutting components from `core/components/` by name (e.g. `SourceRunId` on a WorkRecord). The enumeration is in `core/DESIGN.md`.

`SystemPrompt` is **not** a top-level component -- it lives inside `WorkerSelection.config` because it's a worker-specific concept. LLM workers require it; non-LLM workers (e.g. `python_script`) don't have one.

## Show-your-work as cache

Every successful `submit()` writes a `WorkRecord` keyed by `request_hash` (sha256 of the full WorkRequest yaml: input + output_schema + worker_type + worker_config + capability_requirement). The record carries an `inputs_hash` sibling computed from just the inputs the worker actually consumed -- by default this equals `request_hash`, but a worker may declare a narrower hash (e.g. excluding `max_tokens` if it doesn't affect output) in its `DefaultConfig`.

The cache key is derived from request inputs only; worker code version is NOT part of the key in v1. If a consumer edits a `python_script` worker's body without changing the WorkRequest yaml, the cache still hits. Code-version-aware invalidation is a post-v1 candidate if a consumer surfaces a concrete bug from this; consumers who want to force a fresh call after a code edit use `CacheControl: bypass: true` per request.

On the next `submit()` with the same `request_hash`:

- Look up the existing `WorkRecord` in the configured cache directory.
- If found AND any declared `InvalidationCriteria` still hold AND the worker is `Determinism: deterministic` (default) AND the request has no `CacheControl: bypass` set -> return the cached `Result`. No worker call.
- Otherwise -> dispatch to the worker, write/overwrite the `WorkRecord`, return the fresh `Result`.

This collapses what would otherwise be two mechanisms (audit log + cache) into one. Records exist *because* we want to skip re-running work; the audit trail is a free side effect of caching.

**Cache directory selection.** In normal operation, records live at `<consumer_root>/.agent-glue-cache/<request_hash>.yaml`. In cohort mode, `submit(request, cohort=<name>)` points the cache **lookup** (the read) at `cohorts/<name>/recordings/<worker_type>/<request_hash>.yaml` instead. Cache **writes** always go to the live cache regardless of mode -- show-your-work is integral, so every successful submit() produces a live cache record even when reads were satisfied from a cohort. The cohort directory holds curated or promoted recordings; the live cache holds the full audit trail of everything actually run.

**Worker determinism.** The default `Determinism: deterministic` makes cache lookups eligible. A worker may declare `Determinism: non_deterministic`, in which case cache lookups never match (every call hits the worker) but records are still written for audit. The temperature-zero constraint (below) keeps all LLM workers deterministic; this knob exists for hypothetical future workers (e.g. a "random sample" worker) that genuinely cannot be cached.

**Per-request overrides.** A WorkRequest may carry a `CacheControl` component:
- `bypass: true` -> ignore the cache lookup, always invoke the worker, **and still write the fresh record** to the live cache (so the next non-bypass submission can hit it). Bypass means "skip the read this time," not "skip both read and write."
- `invalidate_if: <criteria>` -> additional preconditions that must hold for the cached record to be considered fresh (e.g. file mtime, env-var value). If the criteria fail, treat as cache miss; the worker runs and the record is written normally.

**Disabling records entirely.** A plugin-level setting (`show_work: never`) suppresses all WorkRecord writes; this also disables cache (no records means no cache hits). Default is `show_work: default`.

## Temperature zero for LLM workers

All LLM worker calls (currently the `openrouter` worker; any future LLM worker) use temperature 0 unconditionally when the request is cacheable. This is an architectural constraint of the work subsystem, not a configurable default.

Rationale: temperature 0 makes the same request reliably produce the same output (modulo model drift between releases), which makes the WorkRecord cache a true cache rather than a hash-pinned lookup of a non-deterministic source. Cohort recordings can be replayed with confidence; show-your-work records can be relied on as authoritative.

The temperature override mechanism is `CacheControl.determinism: non_deterministic`. When the consumer declares it, the LLM worker switches to a non-zero temperature internally (default 0.7) and the submit pipeline skips the cache lookup (writes the record for audit but does not read). Temperature is not a user-facing config field on any LLM worker.

## Yaml primitive vocabulary

JSON Schema (authored as yaml) is the OutputSchema vocabulary -- it's just yaml; the `jsonschema` Python package validates against it. Work entities have hash-derived paths, so the graph subsystem's path-template substrate is not used here.

## Worked example: a Worker entity instance

All four worker entities ship **with no `DefaultConfig` component** -- per the *Demand choices; default only to guide* principle in `core/ARCHITECTURE.md`, every meaningful config field (model, max_tokens, agent_type, timeout_s, function, system_prompt) is the consumer's choice and must appear in each WorkRequest's `WorkerSelection.config`. The kit has no kit-wide preference for any specific value of these fields. (The `DefaultConfig` component remains in the schema for hypothetical workers that ship a *strongly-encouraged* default the kit wants to guide consumers toward; no shipped worker uses it today.)

The openrouter worker, composed of components:

```yaml
type: Worker
components:
  worker_type:
    name: openrouter
  submitter:
    module: agent_glue_lib.work.workers.openrouter
    function: submit
  # no `default_config` -> request must supply model, max_tokens, system_prompt
  # no `provided_capabilities` -> openrouter provides no tools or MCP servers
  # no `determinism` component -> default deterministic (cacheable). temperature is NOT a configurable field;
  # it is fixed at 0 by the worker (architectural constraint per work-system/ARCHITECTURE.md temperature-zero section).
```

The claude_agent worker (deferred to post-v1; entity-type design shown for completeness):

```yaml
type: Worker
components:
  worker_type:
    name: claude_agent
  submitter:
    module: agent_glue_lib.work.workers.claude_agent
    function: submit
  provided_capabilities:
    tools: [Read, Write, Edit, Grep, Bash, Glob]
    mcp_servers: [<dynamically discovered from environment>]
  # no `default_config` -> request must supply agent_type, timeout_s, system_prompt
  # no `determinism` component -> default deterministic. Caching a claude_agent call means subsequent
  # identical requests return the recorded result without redoing the file edits or tool calls. This
  # is the correct caching semantic: the work was done once; the result describes the new state.
```

The `provided_capabilities.mcp_servers` is dynamic -- what the worker can offer depends on the running environment's MCP configuration. The capability check at submit-time intersects `request.capability_requirement.mcp_servers` with `worker.provided_capabilities.mcp_servers` (as discovered at that moment). Missing entries -> `CapabilityUnavailable`. Per core's "fail loudly on changed conditions" rule, this check happens ONCE at submit time and fails loudly if invalidated mid-run; no graceful degradation.

The claude_inference worker (deferred to post-v1; no tools enabled):

```yaml
type: Worker
components:
  worker_type:
    name: claude_inference
  submitter:
    module: agent_glue_lib.work.workers.claude_inference
    function: submit
  determinism:
    value: deterministic         # hardcoded; CacheControl.determinism overrides are rejected
  # no `default_config` -> request must supply agent_type, timeout_s, system_prompt
  # no `provided_capabilities` -> no tools, no MCP
```

The python_script worker (universal escape hatch; may shell out internally):

```yaml
type: Worker
components:
  worker_type:
    name: python_script
  submitter:
    module: agent_glue_lib.work.workers.python_script
    function: submit
  determinism:
    value: requires_declaration   # every WorkRequest must declare CacheControl.determinism
  # no `provided_capabilities` -> no tools, no MCP
  # no `default_config` -> request must supply `function:` (and optionally `consumes_dirs` / `produces_dirs` when the function has external side effects) in WorkerSelection.config
```

## Worked example: a WorkRecord entity instance

```yaml
# <consumer_root>/.agent-glue-cache/a7b3c9d2e8f1.../record.yaml (or cohort recording dir)
type: WorkRecord
components:
  request_hash:
    sha256: a7b3c9d2e8f1...
  inputs_hash:
    sha256: a7b3c9d2e8f1...           # equals request_hash unless worker declares a narrower hash
  request:
    input: { phrases: ["Hello world", "Good morning"], target_language: "es" }
    output_schema: { type: object, properties: { translations: { ... } } }
    worker:
      type: openrouter
      config:
        model: claude-sonnet-4-6
        system_prompt: "You are a translator..."
  result:
    output:
      translations:
        - { source: "Hello world", target: "Hola mundo" }
        - { source: "Good morning", target: "Buenos dias" }
    metadata:
      worker_type: openrouter
      duration_ms: 1842
      tokens: { input: 312, output: 87 }
  worker_ref:
    worker_type: openrouter
  recorded_at: 2026-05-24T15:23:16Z
  attribution:
    model: claude-sonnet-4-6
  source_run_id: 2026-05-24T15-22-01_abc123
```

The same shape works for a cohort recording (it lives in the cohort's recordings directory rather than the live cache directory) and for a record promoted from a live run into a cohort.

## Systems

- **Submit pipeline** -- `submit(request, cohort=None, bypass_cache=False)`. Computes request_hash -> looks up cache (live cache dir, or cohort recordings dir if `cohort` set) -> if hit and valid, returns cached Result -> otherwise looks up worker by type -> checks capability requirements against worker's `ProvidedCapabilities` -> calls worker's `Submitter` -> validates result output against request's `OutputSchema` -> writes WorkRecord to the cache dir -> returns result.
- **Worker registry** -- workers register their components explicitly in `agent_glue_lib.work.__init__`. `submit()` queries by `WorkerType.name`. The registry is just a dict; no framework.
- **Cache substrate** -- reads/writes WorkRecords keyed by request_hash. The directory is configurable per-call (cohort mode swaps the directory).
- **Promote-record** -- `agent-glue work promote-record <request_hash> --to-cohort <name>` copies a live WorkRecord into a cohort's recordings directory.
- **Validator** (CLI `agent-glue work validate`) -- reads a WorkRequest yaml; checks structural integrity (required components present, schema is valid JSON Schema).

## Consumers

The work subsystem exposes one entry point -- `submit(request, cohort=None, bypass_cache=False) -> result`. Anything upstream of that call is a consumer's concern. From inside the work subsystem there is no concept of who is calling, why, or what comes next; there is only a typed request to fulfill (or a cache lookup to short-circuit).

## Open questions

- **Cache directory location for live runs.** Default `<consumer_root>/.agent-glue-cache/` proposed. Confirm vs. alternatives (e.g. `<consumer_root>/.cache/agent-glue/`, or under `~/.cache/agent-glue/<consumer_path_hash>/`). Lean `<consumer_root>/.agent-glue-cache/` for git-localness (consumer can gitignore, share via shelved work, etc.).
