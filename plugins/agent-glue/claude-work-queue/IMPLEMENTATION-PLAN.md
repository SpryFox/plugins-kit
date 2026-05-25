# claude-work-queue: Implementation Plan

This plan is a sketch pending the three open design questions in DESIGN.md. Once the questions are answered, each provisional increment below gets concrete deliverables and acceptance criteria.

Provisional increments, in dependency order:

## Queue storage

The on-disk (or in-memory) substrate that holds work items and their results. Includes the wire format for a work item, the read/write API the rest of the subsystem uses, and the consistency guarantees (atomic pickup if multi-consumer is in scope).

**Acceptance:** a consumer can `submit` a work item and `result` reads it back; if the storage is cross-process, two consumers cannot pick up the same item.

**Depends on:** the answer to "where does the queue live?"

## Signaling

The mechanism that brings a pending work item to Claude's attention. May be a hook, an external trigger, or a polling loop -- depends on the design answer.

**Acceptance:** an item submitted to the queue while Claude is in scope reaches Claude's attention without manual prompt.

**Depends on:** the answer to "what signals Claude?"

## Execute-and-report loop

The path by which Claude does the work and writes the result back to the queue. Covers prompt-rendering, optional schema validation of Claude's output, marking the item done, surfacing any error in a typed shape.

**Acceptance:** a consumer who submits an item with a result-schema gets back either a schema-valid result or a typed failure; the queue reflects the item as done in both cases.

**Depends on:** queue storage + signaling.

## Consumer API

The `submit / wait / result` surface (or whatever final shape lands). Stable across the writer-scope answer; the wire format may vary.

**Acceptance:** any caller -- the work subsystem, a scheduled job, a hand-rolled script -- can drive the queue through this API.

**Depends on:** the answer to "who else writes to it?" for the wire-format stability requirements.
