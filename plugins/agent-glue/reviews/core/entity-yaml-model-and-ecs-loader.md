# Review: core / Entity-yaml model + ECS loader

## Scope

The single v1 increment of the **core** subsystem. Builds the loader, validator, cross-cutting components, Disposition primitive, and variant-dispatch primitive that the other subsystems compose on. Defined in `/d/dev/plugins-kit/plugins/agent-glue/core/IMPLEMENTATION-PLAN.md`. v1 acceptance criterion (from that plan): *the kit loads every component schema and entity-type definition shipped by every subsystem; hand-authored entity-instance yamls round-trip cleanly through `loader.load_instances` -> `dump_instance`; the pre-commit hook rejects an intentionally broken entity-component reference and accepts the shipped sample fixtures.*

## Automated tests

The increment ships 57 pytest tests under `/d/dev/plugins-kit/plugins/agent-glue/tests/core/`. They run against the kit's venv at `/d/dev/plugins-kit/.venv/`.

**Run the full suite:**

```bash
cd /d/dev/plugins-kit/plugins/agent-glue \
  && ../../.venv/Scripts/python.exe -m pytest tests/ -v
```

**Passing looks like:** `57 passed in <~1s>`. No skips, no warnings.

**Test file breakdown** (each file targets a different concern, so a partial failure tells you which subsurface broke):

- `tests/core/test_catalog.py` -- PascalCase <-> snake_case helpers; the loader's normalization invariants.
- `tests/core/test_disposition.py` -- the Disposition ADT (Accepted / AcceptedWithAudit / Rejected) constructs and carries values correctly.
- `tests/core/test_dispatch.py` -- variant-dispatch primitive: matching handler, default handler, no-match raises `NoHandlerForVariant`, custom discriminator, dict-vs-Pydantic variants.
- `tests/core/test_loader.py` -- yaml-on-disk to Catalog: filename / kind / name mismatch rejection, duplicates rejection, unexpected top-level keys rejection, instance skip-rules for non-instance yamls, round-trip identity for nested lists and maps.
- `tests/core/test_validator.py` -- kit consistency (unknown component reference, required/optional overlap, unknown field type, malformed enum/list/map schemas) and instance shape (missing required components, unknown entity type, unknown component, missing required field, wrong field type, bool-not-int, enum mismatch, list-items validated, map value_type validated, unknown field).
- `tests/core/test_full_kit.py` -- end-to-end: loads the shipped kit (50 components + 10 entity types), confirms validate_kit returns no errors, confirms the six cross-cutting components are present.
- `tests/core/test_precommit_hook.py` -- smoke tests the `scripts/precommit_consistency.py` facade: accepts the shipped kit, rejects a structurally broken instance, accepts a hand-authored valid instance.
- `tests/core/test_sample_fixtures.py` -- the shipped sample fixtures (Graph + 2 Nodes + Edge + Cohort + Fixture + ExpectedOutcome under `tests/fixtures/sample/`) load, round-trip identity, validate against the shipped kit, and the pre-commit hook accepts them; a broken fixture under `tests/fixtures/broken/` is rejected by the hook.

**Run a single test file:** add the path to the pytest command, e.g. `... -m pytest tests/core/test_loader.py -v`.

## User-exercise walkthrough

Two ways to see the increment do its job: from the command line via the pre-commit hook, or from a Python REPL via the library.

### 1. Pre-commit hook against the shipped kit

```bash
cd /d/dev/plugins-kit/plugins/agent-glue \
  && ../../.venv/Scripts/python.exe scripts/precommit_consistency.py
```

**Expected output:** `agent-glue kit OK: 50 components, 10 entity types, 0 instances.` Exit code 0.

### 2. Pre-commit hook against the shipped sample fixtures

```bash
cd /d/dev/plugins-kit/plugins/agent-glue \
  && ../../.venv/Scripts/python.exe scripts/precommit_consistency.py \
       --instances tests/fixtures/sample
```

**Expected output:** `agent-glue kit OK: 50 components, 10 entity types, 7 instances.` Exit code 0. (The seven instances are Graph + 2 Nodes + Edge + Cohort + Fixture + ExpectedOutcome.)

### 3. Pre-commit hook rejects a structurally broken instance

```bash
cd /d/dev/plugins-kit/plugins/agent-glue \
  && ../../.venv/Scripts/python.exe scripts/precommit_consistency.py \
       --instances tests/fixtures/broken
```

**Expected output:** an error block on stderr beginning `agent-glue kit is inconsistent (1 error(s)):` and naming `missing required components: ['topology']`. Exit code 1.

### 4. Library round-trip from Python

```bash
cd /d/dev/plugins-kit/plugins/agent-glue \
  && ../../.venv/Scripts/python.exe -c "
from pathlib import Path
from agent_glue_lib.core import load_instances, dump_instance
inst = load_instances(Path('tests/fixtures/sample/graphs/hello'))[0]
print('---')
print(dump_instance(inst))
"
```

**Expected output:** a yaml document beginning `type: <entity-type-name>` and ending with the full `components:` block. The reviewer can compare against the source file to confirm round-trip identity.

### 5. Disposition + dispatch in a single shot

```bash
cd /d/dev/plugins-kit/plugins/agent-glue \
  && ../../.venv/Scripts/python.exe -c "
from agent_glue_lib.core import Accepted, Rejected, dispatch
result = dispatch(
    Accepted[int](value=42),
    handlers={'accepted': lambda v: ('ok', v.value),
              'rejected': lambda v: ('reject', v.reason)},
)
print(result)
"
```

**Expected output:** `('ok', 42)`.

## Schemas + documentation

**Cross-cutting component schemas shipped by this increment** (full unix-style paths):

- `/d/dev/plugins-kit/plugins/agent-glue/core/components/Name.yaml`
- `/d/dev/plugins-kit/plugins/agent-glue/core/components/Description.yaml`
- `/d/dev/plugins-kit/plugins/agent-glue/core/components/Timestamps.yaml`
- `/d/dev/plugins-kit/plugins/agent-glue/core/components/Errored.yaml`
- `/d/dev/plugins-kit/plugins/agent-glue/core/components/Status.yaml`
- `/d/dev/plugins-kit/plugins/agent-glue/core/components/SourceRunId.yaml`

(Core defines no entity types; `core/entities/` is empty by design.)

**Library modules introduced** (under `/d/dev/plugins-kit/plugins/agent-glue/agent_glue_lib/core/`):

- `catalog.py` -- Pydantic types: `Catalog`, `ComponentSchema`, `EntityTypeDef`, `EntityInstance`, `FieldSchema`, plus the `pascal_to_snake` / `snake_to_pascal` helpers.
- `loader.py` -- `load_catalog(component_dirs, entity_dirs) -> Catalog`, `load_instances(root, skip=...) -> list[EntityInstance]`, `dump_instance(instance) -> str`, `LoaderError`.
- `validator.py` -- `validate_kit(catalog) -> list[str]`, `validate_instances(catalog, instances) -> list[str]`, `validate_all(catalog, instances) -> list[str]`.
- `disposition.py` -- `Accepted[T]`, `AcceptedWithAudit[T]`, `Rejected`, `Disposition` alias.
- `dispatch.py` -- `dispatch(variant, handlers, discriminator='kind', default=None)`, `NoHandlerForVariant`.

**CLI facade introduced:**

- `/d/dev/plugins-kit/plugins/agent-glue/scripts/precommit_consistency.py` -- thin wrapper over `agent_glue_lib.core`; accepts `--plugin-root` and `--instances <dir>` (repeatable).

**Sample + broken fixtures shipped:**

- `/d/dev/plugins-kit/plugins/agent-glue/tests/fixtures/sample/` -- Graph + 2 Nodes + Edge + Cohort + Fixture + ExpectedOutcome under `graphs/hello/`.
- `/d/dev/plugins-kit/plugins/agent-glue/tests/fixtures/broken/` -- a Node missing required Topology + Implementation components.

**Design + architecture docs for this increment:**

- `/d/dev/plugins-kit/plugins/agent-glue/core/IMPLEMENTATION-PLAN.md` -- this increment's deliverables and acceptance criterion.
- `/d/dev/plugins-kit/plugins/agent-glue/core/DESIGN.md` -- yaml-entity-model dialect (top-level + component schema + instance shape), cross-cutting components catalog, Disposition primitive, variant dispatch, loader behavior, validator behavior.
- `/d/dev/plugins-kit/plugins/agent-glue/core/ARCHITECTURE.md` -- MVC + ECS framing, Pydantic-at-the-yaml-boundary, yaml primitive vocabulary, failure-as-first-class-outcome, fail-loudly, pre-commit consistency, no-backwards-compatibility, scripts-as-facades, package cohesion, TDD posture.
- `/d/dev/plugins-kit/plugins/agent-glue/core/CLAUDE.md` -- core subsystem index + internal lib layout.

## What this doc is not

Not a tutorial for the loader API, not a per-function reference, not the design. The design lives in core/DESIGN.md; the architecture lives in core/ARCHITECTURE.md; this doc is the verification surface.
