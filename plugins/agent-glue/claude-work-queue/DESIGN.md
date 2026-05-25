# claude-work-queue: Design

## TL;DR

A standalone primitive: a requester drops a work item on a queue, Claude is notified, Claude does the work, Claude writes the result back. Useful directly to any consumer that wants Claude to do a thing and report what happened. The work subsystem's `claude_inference` and `claude_agent` workers will be built on top of this primitive -- they shape a work item, push, wait for the result, and surface it as a WorkResult.

## What "queue + signal + execute-and-report" means

Three responsibilities, separable:

1. **Queue** -- a place where work items live. A work item carries instructions for Claude (a prompt, an optional input payload, a result-schema), an identifier, and somewhere the result will be written.
2. **Signal** -- the mechanism by which Claude becomes aware that there is work to do.
3. **Execute-and-report** -- once Claude knows about an item, the path by which Claude does the work, writes the result, and marks the item as done.

A consumer interacts with the primitive at two boundaries: pushing items (`submit(item) -> id`) and reading results (`result(id) -> ...`). Everything in between is the subsystem's responsibility.

## Open design questions

Three questions gate the implementation plan.

### Where does the queue live?

Options under consideration:

- **File-based on disk** (`~/.claude/queue/pending/<id>.yaml`, `~/.claude/queue/done/<id>.yaml`). Cross-process, cross-session, survives restarts. Easy to inspect, easy to back up, easy to lose to a missed `git status`.
- **SQLite database** at a known path. Transactional pickup (no two consumers grab the same item), structured queries (list pending by tag, list completed by requester), still cross-process. More code than the file approach.
- **In-memory in the Claude Code session.** Lost on session end. Fast, no on-disk footprint. Eliminates any cross-process or scheduled-job consumer.

The choice affects what the queue can express. File-based and SQLite both admit external writers; in-memory only admits same-session writers.

### What signals Claude that work is available?

Options under consideration:

- **Session-start hook.** Claude checks the queue when a session boots; pending items get surfaced as the first thing Claude sees. Simple, predictable, but only fires when a session starts -- items added mid-session don't get attention until the next boot.
- **Stop hook with re-prompt.** When Claude finishes a turn, a hook checks the queue and re-prompts Claude with the next pending item if one exists. Picks up items added at any point. Couples the queue to turn boundaries.
- **External trigger spawns a fresh session.** A scheduled job or external program detects a pending item and starts a new Claude session pointed at the queue. Decouples the queue from any running session. Adds a launch dependency (scheduler / cron / OS-level service).

These compose: a deployment could use the session-start hook for items present at boot, the Stop hook for items added during the session, and the external trigger for items that need attention when no session is running.

### Who else writes to it?

Options under consideration:

- **Claude-only.** Only the current Claude Code session pushes items. The queue is an in-session task list with some persistence. Simplest scope; least powerful.
- **Claude + scheduled jobs.** A cron-style scheduler can drop items in alongside Claude itself. Useful for "every day at 9am, ask Claude to do X."
- **Open to any writer.** External programs (CI, IDE plugins, terminal scripts) drop items in directly using the queue's wire format. The queue becomes a general inter-process inbox for Claude. Requires the wire format to be human-authorable and stable across versions.

Cross-process writers force the queue to live in a known place with a stable on-disk shape. Claude-only allows more flexibility in storage.

## How the work subsystem consumes this

When the design questions are answered, the work subsystem's claude_inference and claude_agent workers become thin submitters over this primitive:

```python
# inside agent_glue_lib/work/workers/claude_inference.py (sketch; not implemented yet)
def submit(request: WorkRequest, ...) -> WorkResult:
    item = build_claude_work_item(request)
    item_id = claude_work_queue.submit(item)
    raw_result = claude_work_queue.wait(item_id, timeout=...)
    return shape_as_workresult(raw_result, request)
```

The work subsystem's caching and audit substrate wraps the queue call; the queue itself doesn't know about WorkRequest, WorkResult, or any of the work-subsystem entities.

## Out of scope (today)

- Queue priority, scheduling fairness, multi-tenant isolation.
- Distributed queues across machines.
- Worker pool autoscaling (one Claude per item is the conceptual model; multiple parallel Claude sessions is a future concern).
- Streaming partial results back to the requester before the work is fully done.
