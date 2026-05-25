# claude-work-queue: Implementation Plan

Increments build a file-based queue + Stop-hook-driven signal + open-to-any-writer consumer API. The three design decisions are locked (see `claude-work-queue/DESIGN.md`).

## Queue storage

Build the on-disk substrate that holds work items and their results.

**Deliverables:**

- `WorkItem` and `WorkItemResult` entity-type yamls in `entities/`; per-component schemas in `components/` (Prompt, InputPayload, ResultSchema, WorkItemId, RequestedAt, CompletedAt; Errored from core).
- `agent_glue_lib/claude_work_queue/storage.py` -- read/write WorkItem and WorkItemResult yamls against a `<queue_root>` directory; handles the `pending/` / `in_progress/` / `done/` directory layout described in DESIGN.md.
- `agent_glue_lib/claude_work_queue/claim.py` -- atomic claim by `os.rename`-ing a WorkItem from `pending/` to `in_progress/`; failed claims (two consumers racing) surface as a typed exception; the first successful rename wins.
- Pytest unit tests covering: write -> read round-trip, ordered pickup by timestamp prefix, atomic claim under simulated race, claim of non-existent item raises clearly, listing pending items.

**After this:** a consumer can write a WorkItem yaml into `<queue_root>/pending/` and later read it back, atomically claim it, and write a WorkItemResult sibling. Two consumers cannot pick up the same item.

## Signaling

Build the Stop-hook script that brings a pending work item to Claude's attention.

**Deliverables:**

- `scripts/queue_check_hook.sh` -- the shell hook that lists `<queue_root>/pending/`, picks the lexicographically-first item, claims it (atomic rename to `in_progress/`), and emits the item's prompt + identifier to stdout in the format the Claude Code Stop hook expects.
- Hook registration instructions (and a one-line installer in `bin/` if useful) so a consumer can wire the hook into their Claude Code settings without hand-editing `settings.json`.
- Smoke test: writing an item into `pending/` causes the hook to emit it; the item ends up in `in_progress/`; running the hook again with no pending items is a no-op.

**After this:** a Claude Code session with the hook installed will pick up pending items at every turn boundary and at session start. Items submitted by any process (Python API, shell script, another session) reach Claude without manual prompting.

## Execute-and-report loop

Wire the path from claimed item to written result.

**Deliverables:**

- `agent_glue_lib/claude_work_queue/report.py` -- the API Claude uses (or its consumer-side wrappers) to record a result for an in-progress item: validates against the optional ResultSchema, writes the `<item_id>.result.yaml`, moves the item from `in_progress/` to `done/`.
- Schema validation at the boundary: a result that doesn't conform to a declared ResultSchema produces an Errored WorkItemResult (mirrors the work-system's OutputSchemaViolation shape) rather than a half-written result file.
- Pytest tests: schema-valid result lands in `done/`; schema-invalid result lands in `done/` as Errored; an in-progress item that times out (no result written within a declared window) is moveable back to `pending/` by a recovery helper.

**After this:** a consumer that submits an item with a ResultSchema gets back either a schema-valid result or a typed Errored result; the queue reflects the item as done in both cases. The execute path is exercised end-to-end.

## Consumer API

Wrap the storage + signaling + execute-and-report into the `submit / wait / result` surface every consumer (the work subsystem's claude workers, scheduled jobs, hand-rolled scripts) calls.

**Deliverables:**

- `agent_glue_lib/claude_work_queue/__init__.py` exposes `submit(prompt, input=None, schema=None, queue_root=None) -> item_id`, `wait(item_id, timeout=None) -> WorkItemResult`, `result(item_id) -> WorkItemResult | None`, and the typed errors (`SchemaViolation`, `TimedOut`, `ItemNotFound`).
- Documentation in claude-work-queue/CLAUDE.md naming the wire format as stable: a producer that writes a WorkItem yaml directly into `pending/` is a first-class consumer.
- Smoke test: full round-trip with the queue running in-process (test fixture seeds the hook with a deterministic responder); identical round-trip with the queue running cross-process (a subprocess writes the item, the in-test consumer reads the result).

**After this:** any caller -- the work subsystem's claude_inference / claude_agent worker submitters, a scheduled cron-style runner, a shell script, an external program -- can drive the queue through a single documented API. The work subsystem can start building its claude-worker increment against this surface.
