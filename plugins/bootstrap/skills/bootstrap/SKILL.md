---
_schema_version: 1
name: bootstrap
description: How the bootstrap plugin manages user and project dependencies, and how to interpret SessionStart bootstrap messages
---

## Skill Purpose

Understand bootstrap plugin behavior: what it checks, what messages it produces, how to configure it at user and project levels, and how to interpret SessionStart output.

## When to Use

- Interpreting bootstrap messages during SessionStart
- Configuring user-level or project-level bootstrap requirements
- Understanding what conditions the bootstrap engine can remediate
- Debugging why a tool, venv, or plugin isn't being set up correctly

## Bootstrap Message Types

The engine produces four message outcomes on session start:

| Outcome | What happened | User sees |
|---------|--------------|-----------|
| **Silent pass** | All checks passed or cache hit | Nothing |
| **Silent install** | Tool missing, installed automatically, re-check passed | Nothing (logged internally) |
| **Silent skip** | First session on fresh machine, Python bootstrapping | Nothing (engine runs next session) |
| **Fix-all** | Something needs user action | Remediation message with `fix-all` prompt |

**Healthy steady state**: Bootstrap is working correctly when it's invisible.

**Verify bootstrap ran**: Check `~/.claude/plugins/data/bootstrap/bootstrap.log`.

## Remediable Condition Categories

| Category | Examples | Remediation |
|----------|----------|-------------|
| **Tool** | CLI tool not installed (`uv`, `git`, `gh`) | Platform-specific install command, then re-check |
| **PATH** | Directory not in PATH (`~/.local/bin`) | Modify persistent PATH config |
| **Venv** | Python venv missing or broken | `uv sync` from `pyproject.toml` |
| **Git dependency** | Repo not cloned or out of date | `git clone` or `git pull` |
| **JSON config** | File lacks expected entries | Merge missing entries into target JSON |
| **INI settings** | Application config setting not enabled | Write setting to config/ini file |
| **PyPI package** | Extracted file missing locally | Download from PyPI and extract |
| **Marketplace** | Not registered or stale | `claude plugin marketplace add/update` |
| **Plugin** | Not installed, out of date, or wrong scope | Install, update, or reinstall at correct scope |
| **User config** | Config information missing (API keys, paths) | Ask user via fix-all flow |

## Configuration Files

The engine supports a 4-layer `bootstrap.json` model following the same pattern as Claude Code's `settings.json` / `settings.local.json`:

| Priority | File | Scope | Checked in? |
|----------|------|-------|-------------|
| 4 (highest) | `<project>/.claude/bootstrap.local.json` | Project-local | No (gitignored) |
| 3 | `<project>/.claude/bootstrap.json` | Project | Yes |
| 2 | `~/.claude/bootstrap.local.json` | User-local | N/A |
| 1 (lowest) | `~/.claude/bootstrap.json` | User | N/A |

**User-level** (`~/.claude/bootstrap.json`): Personal tools and PATH entries that should exist on every machine, across all projects.

**Project-level** (`<project>/.claude/bootstrap.json`): Project-specific tools, marketplaces, and plugins that team members need.

**Local overrides** (`bootstrap.local.json`): Machine-specific overrides not committed to git (e.g. custom install paths, disabled tools).

### Merge Semantics

- **Arrays** (tools, plugins, marketplaces): Unioned by identity key (`name`, `ref`). Same identity in multiple layers = higher-priority fields win.
- **Objects** (venv, config): Deep-merged, higher priority wins for conflicts.
- **path_entries**: String list union, deduplicated, order preserved.
- **Scalars**: Higher priority wins.

### Example

User-level `~/.claude/bootstrap.json`:
```json
{
  "tools": [
    {"name": "git", "install": {"macos": "brew install git"}},
    {"name": "uv"}
  ],
  "path_entries": ["~/.local/bin"]
}
```

Project-level `.claude/bootstrap.json`:
```json
{
  "tools": [
    {"name": "node", "install": {"macos": "brew install node"}}
  ],
  "marketplaces": [
    {"name": "team-plugins", "source": "https://github.com/team/plugins.git"}
  ]
}
```

Layered configs are merged before plugin `bootstrap.json` files are processed.

```yaml
conditional_loading:
  engine_keywords:
    keywords: [engine, internals, processing order, self-setup, manifest phase, script phase, messaging protocol, execution flow, throttling, first run, clean install, phases, design principles, shared library, hybrid model]
    load_references:
      - references/engine-internals.md

  manifest_keywords:
    keywords: [bootstrap.json, manifest, schema, fields, variable expansion, layered config, merge semantics, identity keys, example]
    load_references:
      - references/manifest-reference.md

  remediation_keywords:
    keywords: [condition, remediation, check method, tool missing, venv broken, marketplace, plugin scope, fix-all, blocking, manual operation]
    load_references:
      - references/remediation-reference.md

  setup_keywords:
    keywords: [setup pattern, config setup, setup.py, interactive setup, --check, --describe, --apply, --init-defaults, missing config, API keys]
    load_references:
      - references/plugin-setup-pattern.md
```
