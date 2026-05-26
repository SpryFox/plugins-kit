# graph-system subsystem context

The **graph-system** of agent-glue. Wires units of work into typed pipelines with discriminated-union dispatch, canonical outputs, and replayable cohorts.

Depends on **core** and **work-system**. Nodes that delegate auditability or caching call `agent_glue_lib.work.submit()`; the graph runtime itself does not maintain a per-run trace.

## Internal lib layout

```
agent_glue_lib/graph/
  __init__.py
  loader.py             # discovers graph.yaml + nodes/<name>/node.yaml + edges + cohorts; builds typed catalog
  contracts.py          # imports a graph's contracts.py; resolves Topology.in/out names
  state.py              # PipelineState builder from StateDecl; StateDelta merge
  runtime.py            # walks the graph; variant dispatch; fan-out via ThreadPoolExecutor
  outputs.py            # Jinja path-template substitution; canonical artifact writes
  cohort.py             # Cohort/Fixture/ExpectedOutcome loader; replay driver; assertion
  render.py             # Markdeep + Mermaid HTML render (stub initially)
```

The `Disposition` primitive lives in core (`agent_glue_lib.core.disposition`); the graph runtime imports and dispatches on it natively. The variant-dispatch logic itself also lives in core (`agent_glue_lib.core.dispatch`) and is callable directly by any consumer that wants discriminated-union branching without instantiating a graph.

## Where to find things

| Topic | Document |
|---|---|
| Graph topology, nodes, edges, Disposition dispatch, contracts, PipelineState, canonical outputs, fan-out, render | DESIGN.md |
| Cohort substrate (Fixtures + ExpectedOutcomes; recordings live in the work subsystem) | DESIGN.md |
| Graph entities, graph-side component list, worked Node / Edge / Fixture examples | ARCHITECTURE.md |
| Build increments and acceptance criteria | IMPLEMENTATION-PLAN.md |
| Graph entity-type definitions | entities/ |
| Graph component schemas | components/ |
