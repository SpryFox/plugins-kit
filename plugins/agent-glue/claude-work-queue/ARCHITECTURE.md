# claude-work-queue: Architecture

Shared patterns are in `core/ARCHITECTURE.md`.

## Entities

Entity-type definitions live as yaml files in `./entities/`; they are authored in the first implementation increment.

- `WorkItem` -- one unit of work for Claude (prompt, optional input payload, optional result schema, identifier, requested timestamp).
- `WorkItemResult` -- Claude's response to a WorkItem (output payload conforming to the optional result schema, completion timestamp; or an Errored component instead of output).

## Components

Per-component schemas live in `./components/`; they are authored alongside the entity types in the first implementation increment.

Subsystem-specific components: `Prompt`, `InputPayload`, `ResultSchema`, `WorkItemId`, `RequestedAt`, `CompletedAt`.

The work-queue references the cross-cutting `Errored` component from `core/components/` for the failure shape on a WorkItemResult.

## Storage layout

The queue is a directory on disk:

```
<queue_root>/
  pending/                  # WorkItems awaiting pickup; lexicographic-first wins
    <item_id>.yaml
  in_progress/              # WorkItems currently being processed
    <item_id>.yaml
  done/                     # completed items + their result siblings
    <item_id>.yaml
    <item_id>.result.yaml
```

Default `<queue_root>` is `<consumer_root>/.claude-work-queue/`. The directory layout, the atomic-claim mechanism (rename from `pending/` to `in_progress/`), and the consumer API are detailed in DESIGN.md.

## Cross-subsystem interface

The primitive is consumed via:

```python
from agent_glue_lib.claude_work_queue import submit, wait, result

item_id = submit(prompt=..., input=..., schema=..., queue_root=...)
output = wait(item_id, timeout=...)
# or, non-blocking:
status = result(item_id)
```

The work subsystem's claude_inference and claude_agent worker submitters call this surface; other consumers (a CI script, a scheduled job, a hand-rolled tool, a shell command writing directly into `pending/`) use the same surface or the documented wire format.
