# graph-system: Implementation Plan

Graph-system increments, in dependency order. Each increment leaves the product able to do something it could not do before; that "after this" line is the acceptance criterion. Names, not numbers; order is the order this document presents them in.

Graph-system depends on **core**. It additionally depends on **work-system** at the increment named below; that dependency is called out explicitly.

## Graph entity-yaml model

Make graph-side entities (Graph, Node, Edge, Cohort, Fixture, ExpectedOutcome) load and validate.

**Deliverables:**

- The six entity-type yamls and ~23 graph-side component schemas load via core's loader. (Already shipped at the schema level; this increment adds Python that walks a consuming project's graph directory.)
- `agent_glue_lib/graph/loader.py` -- given a graph directory (`graphs/<name>/`), discovers graph.yaml + nodes/<name>/node.yaml + edge yamls + cohort directories; returns a typed catalog of Graph + Node + Edge entities for that graph.
- Pre-commit hook (shipped with core) loads every example graph directory as part of its validation pass.

**After this:** the product can load and validate a graph yaml directory. Broken graph CLs fail the pre-commit hook with a precise error. The catalog is ready for downstream systems but no runtime walks it yet.

## Contracts module + PipelineState binding

Resolve the Python contract refs that the loader leaves as strings, and instantiate the PipelineState.

**Deliverables:**

- `agent_glue_lib/graph/contracts.py` -- imports a graph's contracts module (`graphs/<name>/contracts.py`); resolves contract names referenced by `Topology.in` / `Topology.out` to Pydantic classes; raises a precise error when a name doesn't resolve.
- `agent_glue_lib/graph/state.py` -- builds a `PipelineState` Pydantic class from a graph's `StateDecl` (init + accumulated fields); given an `InitState`, instantiates it; given a node's `StateDelta`, merges into the running PipelineState.
- `agent-glue validate <graph_path>` CLI -- structural integrity: start node exists, edges resolve, contract names import, sidecar paths exist when components reference them.

**After this:** the product can verify that a graph + contracts + sidecars are internally consistent before any node runs. PipelineState can be instantiated and mutated through StateDelta. The graph subsystem now has every piece in place to walk a graph except the runtime itself.

## Graph runtime: variant dispatch

Walk a graph, call nodes, dispatch on output variants. No fan-out, no work-subsystem integration yet.

**Deliverables:**

- `agent_glue_lib/graph/runtime.py` -- given a graph + a start input + an init state, instantiates PipelineState, walks the graph from the Start node: validates input against `Topology.in`, calls the node's `Implementation`, validates output against `Topology.out`, merges any StateDelta, inspects the output variant, finds the matching Edge via `Source.on_variant`, dispatches.
- Halt cleanly at terminals (no outgoing edge for the produced variant); multiple terminal nodes are fine.
- Pure in-impl node work: nodes whose `execute` does its own computation work end-to-end. Nodes that try to delegate via `submit()` raise (the work-subsystem integration is the next increment).

**After this:** the product can run a graph whose nodes do their own work in Python. Variant dispatch is exercised; the iron contract holds (every input gets a recorded disposition). A graph of pure computation (loaders, validators, format converters) runs end-to-end.

## submit() integration

Wire graph nodes to the work subsystem so nodes that want auditability or caching can delegate.

**Depends on:** work-system's "Show-your-work-as-cache substrate" increment being complete.

**Deliverables:**

- Nodes that call `agent_glue_lib.work.submit()` from their `execute` see WorkRecords land in the live cache; identical submissions on subsequent runs hit cache without re-invoking workers.
- Cohort mode at the graph runtime level: passing a `cohort` argument to `runtime.run` swaps the work cache directory to the cohort's `recordings/` so all `submit()` calls inside node `execute`s replay from the cohort instead of invoking live workers. The CLI flag (`--cohort`) that exposes this lands with `agent-glue run` in the CLI surface increment.

**After this:** the product can run a graph that mixes pure-Python nodes with worker-delegating nodes; the delegating nodes' work is cached and auditable. Cohort mode replays a full pipeline run from a recordings directory without invoking any live worker. This is the integration point where the graph subsystem becomes a true orchestration kit.

## Fan-out (parallel edges)

Honor `ParallelSpec` on edges so a node whose output is `list[Variant]` can dispatch downstream per-element.

**Deliverables:**

- Runtime detects `parallel: true` edges; dispatches the downstream slice once per list element via `ThreadPoolExecutor` with `max_workers` taken from `ParallelSpec.max_workers` on the edge (per-node configuration; no global concurrency limit in v1).
- Accumulated `PipelineState` fields get a lock; nodes' returned `StateDelta`s are applied under lock.
- Lists of `Disposition[T]` route per-element to the matching variant edge (mixed-disposition list: each element to its own target).

**After this:** the product can run fan-out graphs. A node that produces `list[Item]` triggers per-item parallel processing in the downstream node. Localization-style chunk fan-out and any other independent-per-element pattern works.

## Canonical outputs (Jinja path templates)

Make node-declared artifacts a first-class part of a run.

**Deliverables:**

- Runtime evaluates a node's `Outputs` component after node output validation. The component's `artifacts` field is a list at the schema level, but v1 honors only a single artifact entry per node; multiple outputs is a post-v1 candidate. The artifact's `path` is rendered via Jinja2 with `state.x` and `input.x` substitutions; the artifact is written in the declared `format` (yaml, json, text); `format: managed` leaves the write to the node's own code and only verifies the path exists.
- Nodes that read prior runs' canonical outputs as inputs do so via normal `Path.read_text` -- the runtime is silent on the read side.

**After this:** the product can declare and write durable artifacts from a node's output. A consumer pipeline can produce sidecar files that other tools (or other pipelines) read as input.

## Cohort replay + ExpectedOutcome assertions

Turn cohorts into a regression-test substrate.

**Deliverables:**

- `agent-glue replay <graph> --cohort <name>` runs every Fixture against the current code with the cohort's recordings as the work cache; compares the terminal node + terminal output + terminal state against any present ExpectedOutcome; mismatch is a test failure.
- `agent-glue promote-fixture` lifts a graph's run-start into a cohort as a new Fixture.

**After this:** the product supports replay-based regression testing. Every cohort fixture either passes or fails; drift from expected is captured as a test failure. A bug found in production becomes a one-command regression test (promote-fixture from the bad run, write the corrected ExpectedOutcome, replay).

## CLI surface for graph + stub HTML render

Full graph-side CLI plus a placeholder for the render layer.

**Deliverables:**

- `agent-glue new <name>` -- scaffolds a graph in `./graphs/<name>/`.
- `agent-glue run <graph_path>` -- runs on a single input from CLI args.
- `agent-glue render <graph_path>` -- emits a stub HTML (Markdeep + Mermaid) describing the graph topology and the per-node sidecar presence (rules.yaml, prompt.md, declared outputs). Stub means it renders the graph correctly but is not the full design-artifact render described in graph-system/DESIGN.md.
- `agent-glue validate <graph_path>` -- shipped earlier; included here for the CLI surface map.
- `agent-glue replay <graph_path> --cohort <name>` -- shipped earlier; included here.
- `agent-glue promote-fixture ...` -- shipped earlier; included here.
- All CLI commands are thin facades over `agent_glue_lib.graph`.

**After this:** the graph subsystem is operable end-to-end from the command line. v1 of agent-glue is complete; both example pipelines (separately planned, post-v1) can now be built on the kit.
