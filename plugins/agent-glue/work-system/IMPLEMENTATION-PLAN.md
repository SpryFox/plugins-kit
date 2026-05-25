# work-system: Implementation Plan

Work-system increments, in dependency order. Each increment leaves the product able to do something it could not do before; that "after this" line is the acceptance criterion. Names, not numbers; order is the order this document presents them in.

Work-system depends on **core**. The two claude workers additionally depend on **claude-work-queue**; that dependency is called out at the relevant increment.

## WorkRequest contract + JSON Schema validation

Build the request side of the work substrate: the structural shape of a WorkRequest and its OutputSchema.

**Deliverables:**

- WorkRequest / WorkResult / Worker / WorkRecord entity-type yamls load and validate via the core loader (already shipped at the schema level; this increment adds Python that parses an instance file into a typed request the rest of the subsystem can consume).
- `agent_glue_lib/work/request.py` -- Pydantic types for the work-side entities + a parser that takes a yaml file or dict and returns a validated request.
- `agent_glue_lib/work/output_schema.py` -- thin wrapper around the `jsonschema` package; validates a candidate output against a request's OutputSchema; raises `OutputSchemaViolation` on mismatch.
- `agent-glue work validate <request.yaml>` CLI that loads the request, checks structural integrity (required components present, OutputSchema parses as a valid JSON Schema), prints either OK or a typed error list.

**After this:** the product can validate any WorkRequest yaml for structural correctness without invoking a worker. Schema bugs surface at validate time, not at dispatch time.

## Submit pipeline + python_script worker

Wire the registry and the dispatch path; ship the first worker (python_script, in-tree, no external deps).

**Deliverables:**

- `agent_glue_lib/work/registry.py` -- worker registration + lookup keyed by `WorkerType.name`.
- `agent_glue_lib/work/submit.py` -- the `submit(request, ...) -> WorkResult` pipeline: look up worker, intersect CapabilityRequirement against ProvidedCapabilities, call the worker's Submitter, validate result Output against the request's OutputSchema, return the WorkResult.
- `agent_glue_lib/work/workers/python_script.py` -- imports a dotted-name function, calls it with the request input, validates the return, surfaces a structured WorkResult.
- Worker registration in `agent_glue_lib.work.__init__`.
- The four typed failure modes raise from the right places: `WorkerNotAvailable`, `CapabilityUnavailable`, `OutputSchemaViolation`, `WorkerError`.

**After this:** the product can submit a WorkRequest backed by any in-process Python function and get a validated, typed WorkResult back. No cache, no audit -- pure dispatch.

## Show-your-work-as-cache substrate

Add the WorkRecord cache that turns audit and cache into one mechanism. The work subsystem's defining behavior.

**Deliverables:**

- `agent_glue_lib/work/hashing.py` -- canonicalize a WorkRequest, compute its sha256 (`request_hash`); compute `inputs_hash` (equals request_hash by default; worker may declare narrower).
- `agent_glue_lib/work/cache.py` -- WorkRecord read/write; cache directory abstraction (live cache vs cohort recordings is just a directory swap).
- `submit()` is updated to: compute request_hash, look up cache, return cached result on hit (when worker is `deterministic` and request has no `CacheControl.bypass`), otherwise dispatch and write the record on success.
- `CacheControl.bypass: true` honored; `CacheControl.determinism: non_deterministic` skips the cache lookup and still writes the record.
- `show_work: never` plugin setting suppresses all writes (and disables cache as a side effect).

**After this:** the product can submit identical WorkRequests and the second submission returns a cached result without re-invoking the worker. The cache directory holds inspectable yaml records that double as audit log. Hand-authored records in a cohort directory replay deterministically.

## openrouter worker

Add the first inference worker, wrapping openrouter-kit's client.

**Deliverables:**

- `agent_glue_lib/work/workers/openrouter.py` -- imports openrouter-kit's client, packages the request input + `config.system_prompt` as an LLM call, parses the response back into a structured yaml output, populates Metadata (tokens, duration, model).
- Temperature handling per the temperature-zero constraint (see `work-system/ARCHITECTURE.md`): the worker derives the temperature from `CacheControl.determinism` and rejects requests that supply a `temperature` key in the worker config.
- `CacheControl.determinism: non_deterministic` honored: worker switches to a non-zero temperature (default 0.7) and `submit()` skips the cache lookup (writes the record for audit, but no read).
- Worker registered in `agent_glue_lib.work.__init__`.

**After this:** the product can complete LLM-backed work via OpenRouter, with cache + audit. Identical prompts hit cache; intentionally-fresh prompts use `CacheControl.bypass` or `determinism: non_deterministic`.

## claude_inference + claude_agent workers

Add the two Claude-backed workers. Both dispatch through the claude-work-queue primitive.

**Depends on:** claude-work-queue's "Execute-and-report loop" increment being complete.

**Deliverables:**

- `agent_glue_lib/work/workers/claude_inference.py` -- builds a queue work item with the request input + `config.system_prompt`, submits to claude-work-queue with tools disabled, waits for the result, validates against the request's OutputSchema, surfaces a WorkResult. Same determinism rules as openrouter (default `deterministic`; `non_deterministic` overrides allowed; rejects CapabilityRequirement that asks for tools or MCP servers).
- `agent_glue_lib/work/workers/claude_agent.py` -- builds a queue work item with tools and MCP servers enabled per CapabilityRequirement; intersection check against the running environment's ProvidedCapabilities fails loudly via `CapabilityUnavailable`. `Determinism: requires_declaration` enforced -- submit raises if the request lacks `CacheControl.determinism`.
- Both workers registered in `agent_glue_lib.work.__init__`.

**After this:** the product can complete LLM-backed work via Claude Code's own subagent runtime, with or without tools, with cache + audit. The work subsystem now supports all four worker types that ship in v1.

## SideEffects + structured shell-out helper

Make python_script's shell-out pattern first-class and capture it in WorkRecord audit data.

**Deliverables:**

- `agent_glue_lib/work/side_effects.py` -- helpers to build a SideEffects record (file-written, tool-used, subprocess-invoked facets).
- `agent_glue_lib/work/helpers/run_subprocess.py` -- runs a command, captures stdout/stderr/exit-code, returns the result + a pre-populated SideEffects record describing what the function did.
- python_script worker accepts `config.consumes_dirs` and `config.produces_dirs`; cache invalidation auto-derives from `consumes_dirs` mtimes when these are present.

**After this:** a python_script worker that shells out to an external command (Unreal commandlet, build tool, p4 command) produces a WorkRecord that a reviewer can read end-to-end: the function called, the cmd run, the files written, the dirs the function depended on, and the determinism declaration. Enough to assess cache correctness without inspecting the function body.

## InvalidationCriteria + sub-element hashing helper

Add the per-request invalidation hooks and the helper for narrow inputs_hashing.

**Deliverables:**

- `CacheControl.invalidate_if` predicates honored at cache-lookup time: file_mtime, env_var, path_exists. Failed predicates trigger a cache miss.
- `agent_glue_lib/work/hashing.compute_subhashes` -- given a list of items and a key function, returns parallel per-item hashes. Pure utility; consumers compose it.

**After this:** consumers can express "this cache entry is fresh only while file X hasn't changed" and "for this list-shaped request, give me per-item hashes so I can carve narrow WorkRequests that hit cache on unchanged items."

## Cohort recording substrate + CLI

Wire the cohort-mode cache directory swap and the full work-side CLI.

**Deliverables:**

- `submit(request, cohort=<name>)` swaps the cache lookup to the cohort's recordings directory; strict mode fails on missing recordings, lenient falls through to live invocation.
- `agent-glue work promote-record <request_hash> --to-cohort <name>` copies a live cache record into a cohort's recordings dir.
- `agent-glue work submit <request.yaml>`, `agent-glue work submit ... --cohort <name>`, `agent-glue work submit ... --bypass-cache`, `agent-glue work list-workers`.
- All CLI commands are thin facades over `agent_glue_lib.work`.

**After this:** the work subsystem is operable end-to-end from the command line. A live run produces records; promote-record lifts the interesting ones into a cohort; `agent-glue work submit --cohort` replays from the cohort. This is the surface the graph subsystem will compose into pipeline replay.
