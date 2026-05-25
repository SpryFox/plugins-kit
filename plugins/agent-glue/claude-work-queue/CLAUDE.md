# claude-work-queue subsystem context

The **claude-work-queue** subsystem of agent-glue. A standalone primitive for handing Claude a unit of work and getting the result back.

The capability has three parts: a **queue** that holds work items, a **signal** that tells Claude work is available, and an **execute-and-report** loop where Claude does the work and writes the result back to a location the requester can find.

This subsystem is consumable directly (any caller wants Claude to do something + come back with a structured result) and is also the substrate the work subsystem's `claude_inference` and `claude_agent` workers will dispatch through.

Depends on core. Has no other upstream dependencies.

## Status

Design is open. Three gating questions block the implementation plan from being more than a sketch:

1. Where does the queue live? (file-based on disk, SQLite, in-memory session-scoped, ...)
2. What signals Claude that work is available? (session-start hook, Stop hook re-prompt, external trigger spawning a fresh session, ...)
3. Who else writes to it? (Claude-only, scheduled jobs, external programs / CI / IDE / terminal, ...)

Each question is enumerated in DESIGN.md with options and what depends on the answer.

## Where to find things

| Topic | Document |
|---|---|
| What the primitive is, the three open design questions, the consuming patterns | DESIGN.md |
| Entities + components (TBD once the design questions are answered) | ARCHITECTURE.md |
| Build increments and acceptance criteria | IMPLEMENTATION-PLAN.md |
