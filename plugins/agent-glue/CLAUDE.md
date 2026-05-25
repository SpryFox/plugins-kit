# agent-glue plugin context

A Claude Code plugin with two subsystems:

- **work subsystem** -- does individual units of work. Owns show-your-work + cache (one mechanism). Standalone; has no awareness of any consumer.
- **graph subsystem** -- wires units of work into pipelines with typed contracts, dispatch, and replayable runs. Depends on the work subsystem.

External dependency: **openrouter-kit**, a sibling plugin in the plugins-kit marketplace, ships the OpenRouter LLM-completion client that the work subsystem's `openrouter` worker calls.

## Doc conventions

This file is the single source of truth for the plugin's .md files and how they relate. The principles below govern every other doc in the plugin.

- **Single source of truth.** Each fact lives in exactly one doc. Other docs refer to the topic, not the text. No restated rules, no "companion to" preambles, no parallel summaries.
- **CLAUDE.md is the index.** The directory layout, the where-to-find table, and the .md relationships live here. Other docs do not cross-reference each other for these topics; they trust the reader consulted this index. Docs may still reference files not listed here (e.g. functional data files in their own directory).
- **Parent CLAUDE.md is assumed read.** A subdirectory CLAUDE.md does not restate anything the parent already says. Parents load automatically when the agent works in a child directory.

## Directory layout

```
plugins/agent-glue/
  .claude-plugin/plugin.json     # plugin manifest
  bootstrap.json                 # bootstrap dependencies (openrouter-kit)
  pyproject.toml                 # Python package; deps: pydantic, pyyaml, jinja2

  CLAUDE.md                      # this file (SSOT for .md layout + doc conventions)
  DESIGN.md                      # plugin overview, subsystems, show-your-work, disk-cached inference
  ARCHITECTURE.md                # MVC + ECS, shared patterns, cross-subsystem submit() interface
  IMPLEMENTATION-PLAN.md         # unified build plan

  components/                    # cross-cutting component schemas used by both subsystems (Name, Description, Timestamps, Errored, Status, SourceRunId)
                                 # one yaml per component

  graph-system/                  # graph orchestration subsystem (nodes, edges, cohorts, canonical outputs)
    CLAUDE.md                    # Python-lib internal layout for agent_glue_lib/graph/
    DESIGN.md                    # graph subsystem design
    ARCHITECTURE.md              # graph subsystem entities and components
    entities/                    # one yaml per graph-subsystem entity type (Graph, Node, Edge, Cohort, Fixture, ExpectedOutcome)
    components/                  # graph-subsystem-specific component schemas (Phase 1 deliverable)

  work-system/                   # work subsystem (workers, work requests, show-your-work + cache)
    CLAUDE.md                    # Python-lib internal layout for agent_glue_lib/work/
    DESIGN.md                    # work subsystem design
    ARCHITECTURE.md              # work subsystem entities and components
    entities/                    # one yaml per work-subsystem entity type (WorkRequest, WorkResult, Worker, WorkRecord)
    components/                  # work-subsystem-specific component schemas (Phase 1 deliverable)

  agent_glue_lib/                # (post-build) Python package
    __init__.py
    graph/                       # graph-subsystem implementation
    work/                        # work-subsystem implementation

  bin/                           # CLI entry shims (POSIX + Windows)
  scripts/                       # standalone scripts (none in v1)
  skills/agent-glue/             # SKILL.md + references (authoring guidance)
  examples/                      # reference example pipelines
```

## Where to find things

| Topic | Document |
|---|---|
| Subsystem overview, designed-in worker types, node-and-work relationship, show-your-work-as-cache (high level) | DESIGN.md |
| MVC + ECS framing, shared patterns (failure-as-first-class, fail-loudly, temp-0, pre-commit consistency, no backcompat, facades, package cohesion), cohort directory convention, cross-subsystem `submit()` interface | ARCHITECTURE.md |
| Graph topology, nodes, edges, Disposition, contracts, PipelineState, canonical outputs (Jinja path templates), HTML render | graph-system/DESIGN.md |
| Cohort substrate (Fixtures + ExpectedOutcomes; work recordings dir) | graph-system/DESIGN.md |
| Graph entities (narrative + pointer to yaml) | graph-system/ARCHITECTURE.md |
| Graph entity-type definitions (one yaml per entity) | graph-system/entities/ |
| Graph component schemas (Phase 1 deliverable) | graph-system/components/ |
| Worker types, request/result shape, failure modes, capability requirements, show-your-work-as-cache (mechanism + CLI + settings) | work-system/DESIGN.md |
| Work entities + WorkRecord cache mechanism (narrative + pointer to yaml) | work-system/ARCHITECTURE.md |
| Work entity-type definitions (one yaml per entity) | work-system/entities/ |
| Work component schemas (Phase 1 deliverable) | work-system/components/ |
| Cross-cutting component schemas (Phase 1 deliverable) | components/ |
| Build plan, phases, definition of done | IMPLEMENTATION-PLAN.md |
| Subsystem Python-lib internal file layout | graph-system/CLAUDE.md or work-system/CLAUDE.md |

## Reading the design docs

None of the design docs are auto-inlined. Use the "Where to find things" table above to pick which doc covers the topic at hand and read it then.
