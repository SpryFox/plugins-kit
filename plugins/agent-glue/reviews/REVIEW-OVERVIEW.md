# agent-glue: Review Overview

Landing page for the per-increment review docs. Each increment in the v1 plan lands with a matching review doc under `reviews/<subsystem>/<increment-slug>.md` (convention defined in the top-level `IMPLEMENTATION-PLAN.md` *Review protocol* section). This index lists what has been authored so far.

A review doc gives a reviewer a runnable verification surface for a single increment: how to run its automated tests, how to drive it by hand to see it work, and links to the schemas and design docs that explain what the increment is. It does **not** restate the design.

## v1 progress

Increments are listed in their subsystem's IMPLEMENTATION-PLAN document order. A checked box means the review doc exists; an unchecked box means the increment is in the plan but its review doc has not been authored.

### core

- [x] [Entity-yaml model + ECS loader](core/entity-yaml-model-and-ecs-loader.md)

### work-system

- [ ] WorkRequest contract + JSON Schema validation
- [ ] Submit pipeline + python_script worker
- [ ] Show-your-work-as-cache substrate
- [ ] openrouter worker
- [ ] SideEffects + structured shell-out helper
- [ ] InvalidationCriteria + sub-element hashing helper
- [ ] Cohort recording substrate + CLI

### graph-system

- [ ] Graph entity-yaml model
- [ ] Contracts module + PipelineState binding
- [ ] Graph runtime: variant dispatch
- [ ] submit() integration
- [ ] Fan-out (parallel edges)
- [ ] Canonical outputs (Jinja path templates)
- [ ] Cohort replay + ExpectedOutcome assertions
- [ ] CLI surface for graph + stub HTML render

## Deferred to post-v1

Deferred increments do not have review docs until they are promoted into a v1 wave. The deferral rationale lives in the top-level `IMPLEMENTATION-PLAN.md` *Out of scope for v1* section.

- claude-work-queue (all four increments: Queue storage, Signaling, Execute-and-report loop, Consumer API).
- work-system: claude_inference + claude_agent workers.

## How to use this index

- **Reviewing v1 progress.** Scan the checkboxes; an unchecked increment is either not started or not review-doc'd yet.
- **Reviewing a specific increment.** Click through to its review doc and follow the *Automated tests* and *User-exercise walkthrough* sections.
- **Adding a review doc.** A new increment's review doc lands in the same CL as the increment. Check its box here at the same time. The doc's filename slug is the increment title lowercased with non-alphanumeric runs collapsed to single hyphens.
