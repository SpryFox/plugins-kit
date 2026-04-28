---
_schema_version: 1
name: bootstrap
skill-type: reference-skill
description: Use when interpreting SessionStart bootstrap messages or configuring user/project dependency manifests. Do NOT use for non-bootstrap debugging.
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

**Verify bootstrap ran**: Each plugin gets its own log at `~/.claude/plugins/data/<marketplace>/<plugin-name>/bootstrap.log`. Check `<marketplace>/bootstrap/bootstrap.log` for the engine itself, or `plugins-kit/unreal-kit/bootstrap.log` for unreal-kit, etc. If a plugin's log file doesn't exist, bootstrap never reached that plugin.

## How Bootstrap Remediation Works

Bootstrap uses a two-phase model: **auto-remediate first, escalate to fix-all only when user action is required**.

### Phase 1: Auto-remediation (silent)

The engine tries to resolve issues without user involvement:

- **Tool installs**: Missing CLI tool with a known install command → run the install, re-check, continue silently if it works
- **Config autodetect**: Plugin manifests can declare an `"autodetect"` script in their `config` block. The engine calls it before validating required fields — if the script discovers and fills the values (e.g. finding a `.uproject` by scanning from CWD), no user prompt is needed
- **Default values**: Required config fields with a `"default"` in the manifest are applied automatically

If auto-remediation resolves everything, the user sees nothing.

### Phase 2: Fix-all (user action needed)

When issues remain that the engine can't resolve silently, it aggregates all failures into a single **fix-all message** delivered via the SessionStart hook response:

- **`additionalContext`** (seen by the agent): Numbered remediation steps — install commands to run, config values to ask for, files to write. Ends with "type 'fix-all' or 'fixed' to re-run bootstrap."
- **`systemMessage`** (seen by the user): The bootstrap log showing what was checked and what failed

**The fix-all interaction**: The user sees the failure summary and types `fix-all`. The agent then executes the numbered steps — running install commands, asking the user for paths or API keys, writing config files. After remediation, bootstrap re-runs to verify everything is resolved.

### Example: Plugin with config autodetect

A plugin declares two required fields (`uproject`, `engine_dir`) and an autodetect script:
1. Engine copies default config (empty values) to the plugin's data directory
2. Engine calls the autodetect function — it scans the filesystem and fills both values
3. Engine validates required fields — both are present, no fix-all needed
4. If autodetect only finds one value, the other becomes a fix-all item: the agent asks the user for it

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
