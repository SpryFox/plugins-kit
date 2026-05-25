# Work-system context

## Python-lib internal layout

The post-build Python package lives at `../agent_glue_lib/work/`:

```
agent_glue_lib/work/
  __init__.py           # exposes submit(), WorkRequest, WorkResult, error classes; registers workers explicitly
  request.py            # WorkRequest + WorkResult Pydantic models
  submit.py             # the submit() pipeline (hash, cache lookup, dispatch, record write)
  registry.py           # worker registry (dict of WorkerType.name -> Worker entity)
  errors.py             # WorkerNotAvailable, CapabilityUnavailable, OutputSchemaViolation, WorkerError
  cache.py              # WorkRecord read/write; live cache + cohort recording dir selection
  schema.py             # JSON Schema validation (jsonschema package wrapper)
  workers/
    __init__.py
    openrouter.py       # single-shot LLM completion via openrouter-kit (default deterministic + temp 0; non_deterministic override -> temp 0.7)
    claude_inference.py # single-shot Claude Code subagent dispatch, no tools (same determinism rules as openrouter)
    claude_agent.py     # Claude Code subagent with tool + MCP access; Determinism requires_declaration
    python_script.py    # any dotted-name Python function (may shell out); Determinism requires_declaration; consumes_dirs/produces_dirs convention
  hashing.py            # compute_subhashes() and other request-hash helpers for consumers that need sub-element invalidation
  helpers.py            # optional convenience helpers (e.g. run_subprocess() that returns result + pre-populated SideEffects record)
```
