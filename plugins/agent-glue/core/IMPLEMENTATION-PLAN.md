# core: Implementation Plan

Core ships one v1 product increment. Every other subsystem depends on it landing.

## Entity-yaml model + ECS loader

Build the loader, validator, cross-cutting components, and Disposition primitive that the rest of the plugin composes on top of.

**Deliverables:**

- `pyproject.toml` declaring the agent-glue Python package (deps: pydantic, pyyaml, jinja2, jsonschema).
- `agent_glue_lib/core/` package with `catalog.py`, `loader.py`, `validator.py`, `disposition.py`, `dispatch.py` -- behavior is specified in `core/DESIGN.md` ("Loader behavior", "Validator behavior", and "Variant dispatch" sections).
- The cross-cutting component schemas in `core/components/` (enumerated in `core/DESIGN.md`).
- Pre-commit hook script that loads the kit + every example pipeline's instance yamls and exits nonzero if `validate_all` returns errors.
- Pytest tests covering loader edge cases (missing required fields, unknown components, name resolution failures, round-trip identity for the sample fixtures, structurally broken instances rejected with the expected error messages).

**Acceptance:** the kit can load every component schema and entity-type definition shipped by every subsystem. Hand-authored entity-instance yamls round-trip cleanly through `loader.load_instances` -> `dump_instance` such that the output yaml parses back to the same dict. The pre-commit hook rejects an intentionally broken entity-component reference and accepts the shipped sample fixtures.

After this increment exists, the other three subsystems can build their entity types and component schemas against a working loader; no subsystem has to invent its own.

## Post-v1 candidates (not in scope here)

- Per-component `version:` field if the team ever wants explicit schema versioning. The current posture is to use git shas instead.
- `type: ref` in field schemas with a typed `ref_kind` (e.g. contract name, function dotted-path, sibling-entity name) so the loader can validate reference targets structurally rather than waiting for runtime to fail. Useful once any subsystem hits a class of ref bugs the runtime catches too late.
- A second renderer for the entity catalog as a browsable HTML schema doc.
