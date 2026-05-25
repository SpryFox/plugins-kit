# claude-work-queue: Architecture

Shared patterns are in `core/ARCHITECTURE.md`.

## Internal lib layout

```
agent_glue_lib/claude_work_queue/
  __init__.py
  ...                  # populated once the design questions are answered
```

## Entities and components

Provisional sketch -- final shapes depend on the three open design questions in DESIGN.md.

Likely entity types:

- `WorkItem` -- one unit of work for Claude (prompt, optional input payload, optional result-schema, where the result will be written, identifier).
- `WorkItemResult` -- Claude's response (output payload, optional error, completion timestamp).

Likely components, names provisional:

- `Prompt` (the instructions for Claude).
- `InputPayload` (optional structured input).
- `ResultSchema` (optional JSON Schema the result must satisfy).
- `ResultLocation` (where Claude writes the result).
- `WorkItemId`, `RequestedAt`, `CompletedAt`.
- The cross-cutting `Errored` and `Status` from core.

These are sketches; the storage / signaling / writer-scope answers reshape them.

## Cross-subsystem interface

The primitive is consumed via:

```python
from agent_glue_lib.claude_work_queue import submit, wait, result

item_id = submit(prompt=..., input=..., schema=...)
output = wait(item_id, timeout=...)
# or, non-blocking:
status = result(item_id)
```

This is the surface the work subsystem's claude_inference and claude_agent worker submitters will call. Other consumers (a CI script, a scheduled job, a hand-rolled tool) use the same surface.
