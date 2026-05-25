# agent-glue plugin context

A Claude Code plugin built as four composable subsystems:

- **core** -- substrate every other subsystem composes on. See `core/`.
- **claude-work-queue** -- standalone primitive for handing Claude work units and getting results back. See `claude-work-queue/`.
- **work-system** -- worker-agnostic "do a unit of work" abstraction with show-your-work-as-cache. See `work-system/`.
- **graph-system** -- wires units of work into typed pipelines. See `graph-system/`.

What each subsystem provides in detail is in `DESIGN.md`. The dependency graph between subsystems is in `ARCHITECTURE.md`.

## Doc conventions

This file is the single source of truth for the plugin's .md files and how they relate. The principles below govern every other doc in the plugin.

- **Single source of truth.** Each fact lives in exactly one doc. Other docs refer to the topic, not the text. No restated rules, no "companion to" preambles, no parallel summaries.
- **CLAUDE.md is the index.** The directory layout, the where-to-find table, and the .md relationships live here. Subsystem CLAUDE.md files index their own subsystem; this file indexes them.
- **Parent CLAUDE.md is assumed read.** A subdirectory CLAUDE.md does not restate anything the parent already says. Parents load automatically when the agent works in a child directory.

## Document hierarchy and reading responsibilities

Every subsystem ships the same four documents: `CLAUDE.md`, `DESIGN.md`, `ARCHITECTURE.md`, `IMPLEMENTATION-PLAN.md`. The top level ships these four too. **None of these documents are auto-loaded into the agent's context** -- "assumed read" means a human or agent working on a doc must open the relevant parents and siblings before writing or editing.

When working in a subsystem, read the parent equivalents first; subsystem docs only cover what is not already covered one level up. Reading responsibilities by document kind:

- **Working in any subsystem CLAUDE.md.** Read this top-level CLAUDE.md first. Subsystem CLAUDE.md files only add subsystem-scoped indexing -- they do not re-explain the conventions, the SSOT rule, or the hierarchy.
- **Working in any ARCHITECTURE.md.** Read the parent ARCHITECTURE.md first. For subsystems other than core, also read `core/ARCHITECTURE.md` -- core owns the shared patterns; subsystem ARCHITECTURE.md files add only subsystem-specific patterns (e.g. work-system's temperature-zero constraint).
- **Working in any DESIGN.md.** Read the matching ARCHITECTURE.md first; the design uses the patterns the architecture establishes. Also read the parent DESIGN.md. For subsystems other than core, also read `core/DESIGN.md` -- core owns the yaml-entity-model dialect and the Disposition primitive that subsystem designs build on.
- **Working in any IMPLEMENTATION-PLAN.md.** Read the matching subsystem's DESIGN.md and ARCHITECTURE.md first; the plan describes how the design and architecture get built incrementally, and is incoherent without them. Also read the parent IMPLEMENTATION-PLAN.md, parent DESIGN.md, and parent ARCHITECTURE.md (the cross-subsystem build map and shared patterns).

These reading responsibilities are part of the doc conventions: they make the SSOT rule operationally meaningful. A subsystem doc that restates a parent fact is a violation; a reader who skipped the parent and finds the subsystem doc incomplete is reading wrong.

## Directory layout

```
plugins/agent-glue/
  .claude-plugin/plugin.json     # plugin manifest
  bootstrap.json                 # bootstrap dependencies (openrouter-kit)  [Phase 1 deliverable: not yet authored]
  pyproject.toml                 # Python package; deps: pydantic, pyyaml, jinja2, jsonschema

  CLAUDE.md                      # this file (SSOT for .md layout + doc conventions)
  DESIGN.md                      # plugin overview, four subsystems and what each provides
  ARCHITECTURE.md                # cross-subsystem interface; pointer to core for shared patterns
  IMPLEMENTATION-PLAN.md         # build map: subsystem dependency graph + definition of done + post-v1 framing

  core/                          # yaml-entity-model + ECS loader + cross-cutting components + Disposition + shared patterns
    CLAUDE.md / DESIGN.md / ARCHITECTURE.md / IMPLEMENTATION-PLAN.md
    components/                  # cross-cutting component schemas (see core/DESIGN.md)
    entities/                    # (empty in v1; core defines no entity types)

  claude-work-queue/             # standalone primitive: queue + signal + execute-and-report
    CLAUDE.md / DESIGN.md / ARCHITECTURE.md / IMPLEMENTATION-PLAN.md
    components/ / entities/      # (populated when the three open design questions are answered)

  work-system/                   # worker-agnostic do-a-unit-of-work abstraction with show-your-work-as-cache
    CLAUDE.md / DESIGN.md / ARCHITECTURE.md / IMPLEMENTATION-PLAN.md
    entities/                    # WorkRequest, WorkResult, Worker, WorkRecord
    components/                  # work-side component schemas

  graph-system/                  # pipelines, variant dispatch, canonical outputs, cohort replay
    CLAUDE.md / DESIGN.md / ARCHITECTURE.md / IMPLEMENTATION-PLAN.md
    entities/                    # Graph, Node, Edge, Cohort, Fixture, ExpectedOutcome
    components/                  # graph-side component schemas

  agent_glue_lib/                # (post-build) Python package
    core/                        # loader, validator, catalog, Disposition
    claude_work_queue/           # queue primitive (populated when design questions are answered)
    work/                        # submit() + workers + cache substrate
    graph/                       # runtime + cohort + render

  bin/                           # CLI entry shims (POSIX + Windows)
  scripts/                       # standalone scripts (e.g. precommit_consistency hook)
  skills/agent-glue/             # SKILL.md + references (authoring guidance)
  examples/                      # reference example pipelines  [post-v1; planned separately]
```

## Where to find things

| Topic | Document |
|---|---|
| Four-subsystem overview, what each subsystem provides | DESIGN.md |
| Cross-subsystem interface (`submit()` from graph-system to work-system; claude-work-queue's consumer API) + pointer to core for shared patterns | ARCHITECTURE.md |
| Build map (subsystem dependency graph, build order, definition of done, post-v1 framing) | IMPLEMENTATION-PLAN.md |
| Yaml-entity-model dialect, ECS framing, cross-cutting components, Disposition primitive | core/DESIGN.md |
| Shared architectural patterns (MVC + ECS, pre-commit consistency, fail-loudly, no-backcompat, scripts as facades, package cohesion, TDD) | core/ARCHITECTURE.md |
| Queue + signal + execute-and-report primitive, open design questions | claude-work-queue/DESIGN.md |
| Worker types, request/result shape, show-your-work-as-cache (consumer view) | work-system/DESIGN.md |
| Show-your-work-as-cache mechanical rules, temperature-zero constraint, worked Worker / WorkRecord examples | work-system/ARCHITECTURE.md |
| Graph topology, nodes, edges, Disposition dispatch, PipelineState, canonical outputs, cohort substrate | graph-system/DESIGN.md |
| Build increments and acceptance criteria for a given subsystem | that subsystem's IMPLEMENTATION-PLAN.md |
| Cross-cutting component schemas | core/components/ |
| Per-subsystem component schemas + entity-type definitions | that subsystem's components/ and entities/ |
| Subsystem Python-lib internal file layout | that subsystem's CLAUDE.md |

## Reading the design docs

None of the design docs are auto-inlined. Use the table above to pick which doc covers the topic at hand and read it then. The hierarchy section above describes which parent docs to read along with the child doc you are working on.
