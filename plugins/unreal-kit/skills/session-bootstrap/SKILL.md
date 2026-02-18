---
_schema_version: 1
name: session-bootstrap
description: Plugin dependency management via SessionStart hook — system tools, Python packages, and git dependencies
---

# Session Bootstrap

## Purpose

Declare and validate plugin dependencies so the SessionStart hook can ensure the runtime environment is fully resolved before any plugin hooks execute. Three manifests define what the plugin needs; the hook checks and remediates.

## Manifests

| Manifest | Format | Declares |
|----------|--------|----------|
| `system-tools.yaml` | Custom schema | Per-OS CLI tool dependencies |
| `pyproject.toml` | Standard (PEP 621) | Python package dependencies |
| `git-dependencies.yaml` | Custom schema | Git repositories to clone |

All three live at the plugin root (`plugins/<plugin-name>/`), alongside `.claude-plugin/`.

## How It Works

The SessionStart hook runs four steps in order, stopping on first failure:

1. **System tools** — Detect OS, read `system-tools.yaml` for that OS, check each tool via `command -v`, fail-fast on first missing
2. **Python .venv** — Run `uv sync` from `pyproject.toml` to create/update the virtual environment
3. **Git dependencies** — Clone missing repos, pull stale repos, fail on wrong branch
4. **Validation flag** — Write a hash of all manifests; skip re-validation on future sessions until a manifest changes

If any step fails, structured remediation lands in Claude's `additionalContext` with exact install/fix commands.

## Schema Reference

For manifest field definitions, validation rules, and examples:

```
references/manifest-schemas.md
```

## Related

- **Proposal**: `docs/plans/session-bootstrap-architecture/session-bootstrap-architecture-proposal.md`
- **Tasks**: `docs/plans/session-bootstrap-architecture/session-bootstrap-architecture-tasks.md`
- **Manifest files**: `plugins/<plugin-name>/system-tools.yaml`, `git-dependencies.yaml`, `pyproject.toml`
