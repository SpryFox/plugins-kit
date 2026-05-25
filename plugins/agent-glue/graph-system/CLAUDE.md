# Graph-system context

## Python-lib internal layout

The post-build Python package lives at `../agent_glue_lib/graph/`:

```
agent_glue_lib/graph/
  __init__.py
  graph.py              # Graph entity + loader from graph.yaml
  node.py               # Node loader (impl + optional sidecars)
  edge.py               # Edge + variant matching
  contracts.py          # Disposition, PipelineState, StateDelta
  runtime.py            # the executor (no per-run trace; auditability via work subsystem)
  outputs.py            # canonical outputs writer (Jinja path templates + format dispatch)
  cohort.py             # Cohort + Fixture + ExpectedOutcome loader; replay driver
  render.py             # HTML render (stub initially; one View)
```
