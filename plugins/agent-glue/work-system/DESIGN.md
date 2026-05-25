# work-system: Design

The **work subsystem** of agent-glue. Worker-agnostic abstraction for "do a unit of work."

This document describes the full design. Build increments and acceptance criteria live in `work-system/IMPLEMENTATION-PLAN.md`.

## TL;DR

A **work request** is a contract: yaml input + JSON-Schema-shaped output schema (authored as yaml) + worker selection -> yaml output. Workers fulfill the contract. Four worker types ship: `openrouter` (third-party LLM completion), `claude_inference` (Claude Code subagent dispatch, no tools), `claude_agent` (Claude Code subagent with tool + MCP access), `python_script` (any dotted-name Python function -- may shell out to external commands). The two inference workers default to deterministic with the option to override per-request (non-deterministic implies non-zero temperature under the hood); claude_agent and python_script have no determinism default and require per-request declaration. Every successful submission writes a `WorkRecord` that doubles as audit log and cache entry: subsequent identical requests return the recorded result without re-invoking the worker. Cohort replay is the same mechanism pointed at a different directory. Failure is a first-class outcome -- no silent fallback, no auto-retry.

## Goals

- **Separate the contract from the worker.** A work request describes *what should be done* (input, output schema, worker-specific config) without committing to *who does it*. Same top-level request shape across worker types; worker-specific bits live in `worker.config`.
- **Yaml as the substrate.** Inputs are yaml. Outputs are yaml. Output schemas are JSON Schema authored as yaml (validated via the `jsonschema` Python package). Records are yaml.
- **Avoiding repetition is first-class.** Every successful work call writes a `WorkRecord` keyed by request hash. The next identical request returns the cached result without invoking the worker. Show-your-work is the audit; the cache is the same record consulted at lookup. One mechanism, two functions.
- **Cacheability is a per-worker decision.** Inference workers (openrouter, claude_inference) default to deterministic+cacheable (temp 0) but may be overridden per-request to non_deterministic, in which case the worker uses a non-zero temperature internally and skips cache lookups. Side-effect-capable workers (claude_agent, python_script) have no default -- the consumer must declare per-request whether the specific work is `deterministic_idempotent` (cacheable) or `non_deterministic` (not cacheable). The kit fails loudly if a side-effect-capable worker receives a request without a determinism declaration.
- **Pluggable workers.** Adding a worker is registering a Python module with the worker registry. No core changes needed.

## Non-goals

- Pipeline orchestration, topology management, or state coordination across multiple work calls. The work subsystem handles individual work units; orchestration is the consumer's concern.
- Prompt template authoring. Consumers supply already-rendered system prompts (for workers that use them). The subsystem does not render Jinja or run a template engine.
- Output validation against the consumer's domain types. The subsystem verifies the output is well-formed yaml against the supplied JSON Schema; the consumer parses it into their own Pydantic models if they want richer type validation.
- A worker queue / job manager. Submissions are synchronous: submit a request, get a result (or an error). Concurrency is the consumer's concern.
- Graceful degradation when a required worker capability is missing. **If a request requires a tool or MCP server the worker can't provide, the work fails outright.** No fallback to a different worker; no auto-retry without the capability. Per core's "fail loudly on changed conditions" rule, capability checks happen once and fail loudly if invalidated.

## Core concept: the work request contract

A **WorkRequest** has three required parts plus worker selection:

```yaml
input: <arbitrary yaml structure>           # the data the worker should operate on
output_schema: <yaml-schema reference>      # what shape the result must take
worker:                                      # optional; defaults to system default
  type: openrouter | claude_agent | <other worker types>
  config:                                    # worker-specific config
    system_prompt: <string>                  # required by LLM workers; absent for non-LLM workers
    # ...other worker-specific config
  requires:                                  # optional capability requirements
    tools: [list of tool names]              # only meaningful for workers that support tool use
    mcp_servers: [list of mcp server names]  # only meaningful for workers that support MCP
```

System prompt lives under `worker.config` because it's a worker-specific concept — LLM workers consume it as the model's system message; a hypothetical deterministic worker wouldn't have one. Top-level `WorkRequest` fields are the worker-agnostic contract; worker-specific concerns are inside `worker.config`.

The runtime hands the validated request to the selected worker. The worker produces a **WorkResult**:

```yaml
output: <yaml conforming to output_schema>   # the result data
side_effects: <optional list>                # files written, tools used (workers may populate)
metadata:                                     # worker-provided audit data
  worker_type: openrouter
  duration_ms: 1234
  model: claude-sonnet-4-6
  tokens: {input: 500, output: 1200}
  # ...worker-specific fields
```

The output is validated as well-formed yaml against the supplied schema. Beyond that, the work subsystem is opinion-free — the consumer parses `output` into whatever their domain requires.

If the worker can't fulfill the request (missing capability, model unavailable, agent timeout, malformed output), the submission raises an error. Callers handle it; there is no automatic fallback to a different worker.

## Workers

A worker is a Python module that knows how to fulfill a WorkRequest. The worker interface is small enough that adding a new worker type is a focused piece of work.

### openrouter worker

**When to use:** the work is a single-shot LLM completion via OpenRouter (multi-model). Stateless. No tool use. No MCP servers.

**How it fulfills:** sends the input as a structured user message, uses `config.system_prompt` as the LLM's system message, calls openrouter-kit's client, parses the response back into a yaml output structure.

**Determinism:** defaults to `deterministic` (cached, temperature 0). A request that sets `CacheControl.determinism: non_deterministic` is accepted; the worker switches to a non-zero temperature (default 0.7) and the cache lookup is skipped. Temperature itself is NOT a user-facing config field -- it's derived from the declared determinism. To force a fresh call without changing determinism, use `CacheControl.bypass: true`.

**Config (system_prompt required):**
```yaml
worker:
  type: openrouter
  config:
    model: claude-sonnet-4-6
    max_tokens: 4096
    system_prompt: |
      Instructions for the LLM. Required.
    # temperature: NOT configurable -- derived from CacheControl.determinism by the worker.
```

**Capability requirements ignored:** if a request specifies `requires.tools` or `requires.mcp_servers`, openrouter raises an error. Use claude_agent for those.

### claude_inference worker

**When to use:** the work is a single-shot LLM completion via Claude Code's own subagent runtime (rather than a third-party API). Stateless. No tool access; the dispatched subagent runs with tools disabled. Useful when you want Claude's reasoning but explicitly do not want any file modification or tool side effects.

**How it fulfills:** invokes a Claude Code subagent (Task tool dispatch) with no tools enabled, hands it the rendered system prompt + input, parses the agent's text response into a yaml output structure.

**Determinism:** same rules as openrouter (default `deterministic` + temp 0; `non_deterministic` override -> non-zero temp + skip cache; `CacheControl.bypass: true` to force re-run without changing determinism).

**Config (system_prompt required):**
```yaml
worker:
  type: claude_inference
  config:
    agent_type: general-purpose
    timeout_s: 120
    system_prompt: |
      Instructions for the LLM. Required.
    # tools are NOT enabled for this worker -- by design.
    # temperature: NOT configurable -- derived from CacheControl.determinism by the worker.
```

**Capability requirements ignored:** if a request specifies `requires.tools` or `requires.mcp_servers`, claude_inference raises an error -- this is the tools-disabled inference worker. Use claude_agent for tool-augmented work.

### claude_agent worker

**When to use:** the work requires multi-step autonomous behavior with tool access -- file edits, tool use, validation loops, MCP server interaction. The agent operates with full Claude Code tool access (Read, Write, Bash, etc.) and any configured MCP servers.

**How it fulfills:** materializes a work file (yaml input + system prompt on disk), invokes a Claude Code subagent with the required tools and MCP servers enabled, waits for the agent to write `result.yaml`, reads the result. The agent may make tool calls and MCP server calls during the work; those count as side effects.

**Determinism: `requires_declaration`.** The consumer must declare per-request via `CacheControl.determinism` whether the specific work is `deterministic_idempotent` (cacheable -- e.g. "create file X with content Y if it doesn't exist," which is idempotent) or `non_deterministic` (not cacheable -- e.g. "summarize the current state of the repo," whose output depends on facts outside the request). Submit raises if the declaration is missing. No silent default; the consumer knows their work's nature, the kit doesn't guess.

**Config (system_prompt required):**
```yaml
worker:
  type: claude_agent
  config:
    agent_type: general-purpose
    timeout_s: 600
    system_prompt: |
      Instructions for the agent. Required.
  requires:
    tools: [Read, Write, Bash]
    mcp_servers: [unreal-engine]
cache_control:
  determinism: deterministic_idempotent     # or non_deterministic; required
```

**Capability requirements: hard preconditions.** If the listed tools or MCP servers aren't available at execution time, the worker fails the request before invoking the agent. No fallback, no skip. Per core's "fail loudly on changed conditions" rule, capability is checked once at submit time; if a capability disappears mid-run, subsequent submits fail loudly.

### python_script worker

**When to use:** the work can be expressed as a Python function. Useful for data transformations, format conversions, registered domain operations, AND for wrapping external commands (Unreal commandlets, build tools, p4 operations) via `subprocess.run`. There is no separate "subprocess" worker; python_script is the universal escape hatch.

**How it fulfills:** imports the function at the given dotted path, calls it with the request's `input`, validates the return against the request's `output_schema`, returns the result + a populated `SideEffects` record describing what the function did. No system prompt, no model. Any dotted-name function is accepted; no allowlist.

**Determinism: `requires_declaration`.** Same rule as claude_agent. A pure transformation declares `deterministic_idempotent`; a function that writes files or has external side effects declares `non_deterministic`. Submit raises if the declaration is missing.

**Config (function reference required):**
```yaml
worker:
  type: python_script
  config:
    function: my_package.my_module.my_function
cache_control:
  determinism: deterministic_idempotent     # or non_deterministic; required
```

**Capability requirements ignored:** python_script raises if a request specifies `requires.tools` or `requires.mcp_servers`.

#### Pattern: python_script that wraps an external command

When a python_script shells out to an external command (Unreal commandlet, build tool, etc.), the recommended pattern is to surface enough structured metadata in the WorkRequest config and WorkResult.SideEffects that the cache + cohort-replay + audit story behaves correctly. The kit consumes these declarations to drive invalidation and replay safety.

WorkRequest declares which directories the function consumes and produces:

```yaml
worker:
  type: python_script
  config:
    function: my_pipeline.workers.gather_loc_strings
    consumes_dirs: [Source/, Config/Localization/]    # kit auto-derives cache invalidation: any mtime change in these dirs invalidates the cached record
    produces_dirs: [Content/Localization/]            # kit knows the function writes here; cohort-replay refuses to skip the function if produces_dirs are in scope
cache_control:
  determinism: deterministic_idempotent               # the gather commandlet produces the same archive given the same source state, so cache hits are safe when consumes_dirs haven't changed
```

The function returns its typed result AND populates `SideEffects` describing what it actually did:

```python
def gather_loc_strings(input: GatherIn) -> tuple[GatherOut, SideEffects]:
    result = subprocess.run(
        ["UnrealEditor-Cmd.exe", "SpiritCrossing.uproject", "-run=GatherText", f"-config={input.config}"],
        capture_output=True, check=True,
    )
    return (
        GatherOut(success=True, manifest_path="Content/Localization/Game/Game.manifest"),
        SideEffects(
            subprocess_invoked=[{
                "cmd": result.args,
                "exit_code": result.returncode,
                "stdout_summary": result.stdout.decode()[:500],
            }],
            files_written=["Content/Localization/Game/Game.manifest", "Content/Localization/Game/Game.archive"],
        ),
    )
```

The kit ships an optional helper `agent_glue_lib.work.helpers.run_subprocess(cmd, ...)` that runs the command and returns both the result and a pre-populated `SideEffects` record so authors don't have to construct it by hand for the common case.

A reviewer looking at the WorkRecord for this call sees: the function it called, the cmd it ran, the files it wrote, which dirs it depended on, and the declared determinism. Enough to assess "is this cached correctly?" without inspecting the function body.

## Sub-element hashing helper

When a WorkRequest's `input` is a list (e.g. 20 lines of dialogue, 50 phrases) and only a subset has actually changed, the consumer typically wants cache hits on the unchanged elements rather than treating the whole list as a single cache key. The kit provides `agent_glue_lib.work.hashing.compute_subhashes`:

```python
from agent_glue_lib.work.hashing import compute_subhashes

# Given a list and a function that produces per-item hash material,
# returns parallel per-item hashes the consumer can use to construct
# multiple WorkRequests (one per stale subset) or to build a narrower
# inputs_hash that excludes content the worker doesn't actually read.
subhashes = compute_subhashes(
    items=conversation_lines,
    key_fn=lambda line: (line.text, line.speaker, prompt_version, pool_version, disables_version),
)
stale_ids = [line.id for line, h in zip(conversation_lines, subhashes) if h != cached_subhashes.get(line.id)]
```

Pure utility, no kit-internal coupling. Consumers compose it however they want; the kit doesn't dictate how WorkRequests get carved by inputs_hash.

## Worker selection

If a WorkRequest has a `worker:` block, that worker is used. If not, the runtime falls back to a system default (configured in settings). Consumers can also pass a `worker:` override at submission time programmatically, separate from what's in the WorkRequest yaml — useful for testing one pipeline against different workers.

## Failure modes

The work subsystem treats failure as a first-class outcome. Submission can raise:

- `WorkerNotAvailable` — selected worker type isn't registered.
- `CapabilityUnavailable` — required tools / MCP servers not available.
- `OutputSchemaViolation` — worker returned output, but it doesn't validate against the declared schema.
- `WorkerError` — worker-internal failure (LLM API error, agent timeout, agent crash). Carries worker-provided error metadata.

The work subsystem never silently substitutes a different worker, never returns a partial result without raising, never retries on its own. All retry / fallback policy is the consumer's responsibility.

## Show-your-work as cache (consumer view)

Avoiding repetition of work when inputs haven't changed is a first-class principle of the work subsystem. The mechanism that records what happened (the audit trail) is the same mechanism that lets us skip re-doing identical work (the cache). One thing, two functions.

From the consumer's point of view: every successful `submit()` is recorded; identical subsequent `submit()`s return the recorded result without re-invoking the worker; `CacheControl.bypass: true` forces a fresh call; `CacheControl.invalidate_if` declares additional freshness preconditions; `CacheControl.determinism` overrides per-request when the request's nature differs from the worker's default. Records are produced live (naturally, by any cache-missing submit) or promoted (`agent-glue work promote-record` lifts a live record into a cohort).

The mechanical rules -- request_hash computation, lookup order, cache directory paths, the cohort-mode directory swap, the `show_work: never` plugin setting -- live in `work-system/ARCHITECTURE.md`. The cohort directory convention lives in top-level `ARCHITECTURE.md`.

## Cohort substrate (consumer view)

A cohort replay is `submit(request, cohort=<name>)` for every WorkRequest the pipeline issues; the cache lookup hits the cohort's recordings directory instead of the live cache. Recordings are produced curated (hand-author a file) or harvested (`agent-glue work promote-record`). Strict vs lenient (fail on missing recording vs fall through to live) is a per-call mode.

The cohort directory shape lives in top-level `ARCHITECTURE.md`; the recordings file format is the same WorkRecord shape described in `work-system/ARCHITECTURE.md`.

## Yaml shape examples

### A WorkRequest for the openrouter worker

```yaml
input:
  phrases:
    - "Hello world"
    - "Good morning"
  target_language: es

output_schema:
  type: object
  properties:
    translations:
      type: array
      items:
        type: object
        properties:
          source: { type: string }
          target: { type: string }
        required: [source, target]

worker:
  type: openrouter
  config:
    model: claude-sonnet-4-6
    system_prompt: |
      You are a translator. Given a list of English phrases, return YAML
      with each phrase translated to the target language. Use the exact
      shape: { translations: [{ source: "...", target: "..." }, ...] }.
    # temperature: NOT configurable -- fixed at 0 by the worker (architectural constraint).
```

### The WorkResult

```yaml
output:
  translations:
    - source: "Hello world"
      target: "Hola mundo"
    - source: "Good morning"
      target: "Buenos días"

side_effects: []

metadata:
  worker_type: openrouter
  model: claude-sonnet-4-6
  duration_ms: 1842
  tokens:
    input: 312
    output: 87
  cache_hit_tokens: 0
  cost_usd: 0.00018
```

The `metadata` shape is worker-specific; the subsystem treats it as opaque pass-through. openrouter-kit's response object fields land here unchanged.

### A WorkRequest for the claude_agent worker

```yaml
input:
  source_files:
    - path: "Source/Player.cpp"
    - path: "Source/Player.h"
  goal: "Add a method GetMaxHealth() that returns the cached max health value."

output_schema:
  type: object
  properties:
    changes: { type: array }
    result: { type: string, enum: [success, failed] }

worker:
  type: claude_agent
  config:
    agent_type: general-purpose
    timeout_s: 300
    system_prompt: |
      You are a C++ refactoring agent. Read the source files, make the requested
      change, and return YAML describing what you did. Use the shape:
      { changes: [{ file: "...", summary: "..." }], result: "success" | "failed" }.
  requires:
    tools: [Read, Edit, Grep]
    mcp_servers: []
```

If `Read`, `Edit`, or `Grep` isn't available when this request is submitted, the worker raises `CapabilityUnavailable` before invoking the agent.

## CLI surface

```
agent-glue work submit <request.yaml>                       Submit a work request; print result.yaml
agent-glue work submit <request.yaml> --cohort <name>       Use cohort recordings (strict by default)
agent-glue work submit <request.yaml> --bypass-cache        Force re-run; ignore any existing cache record
agent-glue work promote-record <request_hash> --to-cohort <name>
                                                             Copy a live cache record into a cohort
agent-glue work list-workers                                 Show available worker types
agent-glue work validate <request.yaml>                     Check request structure + schema validity
```

Most consumers use the work subsystem as a Python library (`agent_glue_lib.work.submit(...)`), not the CLI. The CLI is for one-off testing and cohort management.

## Library interface (Python)

```python
from agent_glue_lib.work import submit, WorkRequest, WorkResult, CapabilityUnavailable

try:
    result: WorkResult = submit(
        request=WorkRequest(...),    # or pass a dict / load from yaml
        cohort=None,                  # optional: cohort name for replay (cache lookup directory swap)
        bypass_cache=False,           # force re-run even if a cache record exists
        strict=False,                 # cohort-mode: fail if recording missing (otherwise fall through to live)
    )
except CapabilityUnavailable as e:
    # the requested worker can't provide the required tools / MCP servers
    ...
```

`submit()` is the entire public API. Worker selection happens inside based on the request's `worker:` block (or system default). Cache lookup + cohort replay are transparent.

## Settings

```yaml
default_worker:
  type: openrouter
  config:
    model: claude-sonnet-4-6

cache_directory: .agent-glue-cache           # where live WorkRecords are stored (relative to consumer root)
cohort_directory: ./cohorts                  # where to look for cohort recordings
show_work: default                           # default | never (never suppresses all WorkRecord writes; also disables cache)
```

## Consumers

The work subsystem exposes one entry point — `submit(request) → result`. Anything upstream of that call is a consumer's concern. From inside the work subsystem there is no concept of who is calling, why, or what comes next; there is only a typed request to fulfill.

This is the entire surface that consumers see. The same `submit()` API works for any caller. How a specific consumer builds the request and handles the result is documented in that consumer's docs, not here.

## Open questions

1. **Side-effect schema.** `WorkResult.side_effects` will have a structured shape (file-written-with-path, tool-used-with-args, mcp-call-with-server-and-tool). Define when the claude_agent worker actually populates it; premature design without a concrete writer.
2. **Streaming.** Some LLM calls stream tokens. The current submission API is synchronous-only. Streaming could land later as `submit_stream()` returning an iterator. Defer until a consumer needs it.

