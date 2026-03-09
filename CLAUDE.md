# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**plugins-kit** is the **development repository** (source of truth) for the plugins-kit Claude Code marketplace. It contains the source code for all plugins in the marketplace. Currently ships: **bootstrap** (dependency management) and **unreal-kit** (Unreal Engine Python API automation).

This repo is a **Claude Code plugin marketplace** — it extends Claude Code with skills, commands, and hooks via the `.claude-plugin/marketplace.json` manifest. Plugins are loaded either via `--plugin-dir` (local development) or `enabledPlugins` in settings (production installs from the remote repo).

## Architecture

```
plugins-kit/                          # Marketplace root
  .claude-plugin/marketplace.json     # Marketplace manifest (lists all plugins)
  plugins/
    installed_plugins.json            # Plugin registry
    bootstrap/                        # Bootstrap plugin (always enabled)
      .claude-plugin/plugin.json      # Plugin manifest
      bootstrap.json                  # Bootstrap plugin's own manifest
      engine/                         # Bootstrap engine + config
      bootstrap_lib/                  # Shared libraries (cache, tool_check, etc.) — installable Python package
      hooks/sessionstart/             # SessionStart hook (bash wrapper)
      defaults/                       # Default config files
    test-plugin/                      # Test plugin (exercises bootstrap system)
      .claude-plugin/plugin.json      # Plugin manifest
      bootstrap.json                  # Test plugin's bootstrap manifest
      scripts/                        # Config setup
    local-review-kit/                 # P4/Swarm AI code review plugin
      .claude-plugin/plugin.json      # Plugin manifest
      hooks/sessionstart/             # 5-step bootstrap scripts
      hooks/stop/                     # Bootstrap re-check
      scripts/                        # Review execution + config setup
      defaults/                       # Default config template
    unreal-kit/                       # The UE plugin
      .claude-plugin/plugin.json      # Plugin manifest
      lib/                            # Shared Python libraries (synced to data dir by bootstrap)
      skills/
        ue-python-api/                # The main skill
          SKILL.md                    # Skill definition (loaded by Claude Code)
          bin/                        # Entry points (runner + setup)
          scripts/                    # Utility scripts
          stubs/                      # UE Python API stubs (generated, gitignored)
          references/                 # Detailed docs loaded conditionally by SKILL.md
```

### Key Files

| File | Purpose |
|------|---------|
| `plugins/bootstrap/engine/bootstrap_engine.py` | Main engine — processes manifests, runs checks, emits hook JSON |
| `plugins/bootstrap/bootstrap_lib/cache.py` | Content-hash caching (compute, check, write) |
| `plugins/bootstrap/bootstrap_lib/tool_check.py` | System tool availability checks |
| `plugins/bootstrap/bootstrap_lib/platform_detect.py` | OS detection |
| `plugins/bootstrap/bootstrap_lib/log.py` | File-based bootstrap logging |
| `plugins/bootstrap/bootstrap_lib/venv_check.py` | Python venv validation |
| `plugins/bootstrap/bootstrap_lib/git_dep_check.py` | Git dependency validation |
| `plugins/bootstrap/bootstrap_lib/plugin_resolve.py` | Plugin registry resolution |
| `plugins/bootstrap/bootstrap_lib/path_check.py` | PATH entry validation |
| `plugins/bootstrap/bootstrap_lib/manifest_merge.py` | Deep-merge for layered bootstrap.json files |
| `plugins/bootstrap/engine/config.py` | Config loading, migration, persistence |
| `plugins/bootstrap/hooks/sessionstart/session-bootstrap.sh` | SessionStart hook (bash wrapper for engine) |
| `plugins/bootstrap/bootstrap.json` | Bootstrap plugin's own manifest |
| `plugins/bootstrap/skills/bootstrap/references/engine-internals.md` | Bootstrap engine internals |
| `docs/planning/bootstrap/MILESTONES.md` | Development milestones and progress |
| `plugins/test-plugin/bootstrap.json` | Test plugin's bootstrap manifest (includes config section) |
| `tests/bootstrap/` | All bootstrap tests (mirrors bootstrap_lib/ structure) |

### Key Design Decisions

- **Bootstrapping**: Two-layer system — session bootstrap (bash SessionStart hook, manifest-driven) ensures system tools, venv, and git deps; script bootstrap (Python, runs inside UE Editor) handles UE-side packages at runtime. See [engine-internals.md](plugins/bootstrap/skills/bootstrap/references/engine-internals.md) for engine details and [script-bootstrap.md](plugins/unreal-kit/skills/ue-python-api/references/script-bootstrap.md) for UE-side bootstrapping.
- **Config resolution order**: CLI args > per-project config (`<project_root>/.claude/unreal-kit.yaml`) > global config (`~/.claude/plugins/data/plugins-kit/unreal-kit/config.yaml`, legacy fallback) > skill config (`ue_runner_config.yaml`) > hardcoded defaults
- **Auto-detection execution**: `ue_runner.py` tries remote execution (UDP via upyrc) first, falls back to headless commandlet if editor isn't running

### Core Components

| File | Purpose |
|------|---------|
| `bin/ue_runner.py` | CLI entry point — runs UE Python scripts via remote exec or commandlet |
| `bin/ue-runner.cmd` | Windows wrapper — uses `uv run` to ensure deps |
| `bin/setup.py` | One-shot setup — discovers project, enables settings, downloads stubs |
| `bin/setup.cmd` | Windows wrapper for setup |
| `lib/ue_runner_config.py` | Config loading with layered resolution and fallback YAML parser |
| `lib/ue_discovery.py` | Project discovery — finds `.uproject` and engine directory |
| `lib/ue_ini.py` | UE `.ini` file read/write utilities |
| `lib/unreal_pip.py` | Pip operations inside UE's embedded Python (runs in-editor) |
| `lib/bootstrap.py` | Dependency bootstrapper for UE scripts (runs in-editor) |
| `scripts/setup-stubs.py` | Downloads UE Python API stubs from PyPI or copies from project |

## Commands

```bash
# Setup (run once per machine, no user input needed)
plugins/unreal-kit/skills/ue-python-api/bin/setup.cmd

# Setup with stubs refresh (after editor restart with Developer Mode)
plugins/unreal-kit/skills/ue-python-api/bin/setup.cmd --refresh-stubs

# Run a UE Python script (auto-detects remote vs commandlet)
plugins/unreal-kit/skills/ue-python-api/bin/ue-runner.cmd script.py

# Force execution mode
plugins/unreal-kit/skills/ue-python-api/bin/ue-runner.cmd script.py --mode remote
plugins/unreal-kit/skills/ue-python-api/bin/ue-runner.cmd script.py --mode commandlet

# Copy output files to local directory
plugins/unreal-kit/skills/ue-python-api/bin/ue-runner.cmd script.py --copy-output ./results/

# Interactive setup (prompts before changes)
plugins/unreal-kit/skills/ue-python-api/bin/ue-runner.cmd --setup
```

## Writing UE Python Scripts

Scripts run inside UE's embedded Python (`import unreal`). Key patterns:

- Output goes to `<Project>/Saved/PythonOutput/` as YAML — the runner auto-detects new files
- Use `os.path.expanduser('~/.claude/plugins/data/plugins-kit/unreal-kit/lib')` for `sys.path.insert` — these are stable, version-independent paths synced by bootstrap
- Call `ensure_dependencies()` before importing packages listed in `lib/requirements.yaml`
- `lib/bootstrap.py` and `unreal_pip.py` (from git_deps) only run inside UE Editor (they `import unreal`)
- All other `lib/` and `bin/` modules are host-side (system Python, stdlib only)

## Development Workflow

**Automated tests required** — every new module or integration point must have corresponding tests in `tests/` before the work is considered complete. Test directories mirror the plugin structure (e.g. `tests/bootstrap/` for the bootstrap plugin). This standard was established with the bootstrap plugin's M1 test suite and applies to all subsequent development.

**Targeted test runs** — the full test suite is too slow for routine use. Always run only the specific test file(s) relevant to your changes:

```bash
# Run a specific test file
uv run --extra dev pytest tests/bootstrap/test_marketplace_lifecycle.py -v

# Run a specific test class
uv run --extra dev pytest tests/bootstrap/test_marketplace_lifecycle.py::TestCheckPluginScope -v
```

Only run the full suite (`uv run --extra dev pytest -v`) when explicitly asked or before a release.

**Publishing changes** — the plugin cache (`~/.claude/plugins/cache/`) syncs from the remote repository, not the local working copy. Local edits won't take effect until published. To publish:

1. Bump the plugin version in `.claude-plugin/plugin.json` (the cache keys on version — same version = same code)
2. Commit all changes (including the version bump)
3. Push to the remote repository
4. Restart Claude Code — it will pull the new version into the cache

The cache will NOT refresh without a version bump, even if you push new commits. Never copy files directly into the plugin cache — always use this publish flow.

**Keep architecture docs current** — when modifying bootstrap behavior, update the bootstrap skill references (`plugins/bootstrap/skills/bootstrap/references/`) to reflect the changes. These are the source of truth for how the system works.

**Anti-pattern: silent bootstrap operations.** Every bootstrap check must log its outcome — `ok_entries` when passing (verbose-only), `action_entries` when remediating (always visible). Adding a check that creates files, clones repos, or writes config without emitting a log entry is a bug. See the "Every check must log its outcome" principle in [engine-internals.md](plugins/bootstrap/skills/bootstrap/references/engine-internals.md).

**Plan non-trivial tasks**: Before implementing any non-trivial task:
1. Enter plan mode (EnterPlanMode)
2. Explore the codebase and design the approach
3. Write the plan as a proposed task update: "Update Task #{id} ({name}) with the following plan: {plan details}"
4. Exit plan mode (ExitPlanMode) — user reviews and approves
5. Update the task description with the approved plan (TaskUpdate)
6. Implement the task according to the plan

**Skill-based document placement** (package cohesion): When creating a document, ask "what skill does this belong to?" — the same way you'd ask "what package does this class belong in?" Apply these cohesion principles:

- **CRP (Common Reuse Principle)** — If you use one document in a skill, you should plausibly use them all. Don't force a skill to load content the consumer doesn't need.
- **CCP (Common Closure Principle)** — Documents that change for the same reason belong in the same skill. A schema change should affect one skill, not scatter across several.
- **ADP (Acyclic Dependencies Principle)** — Skills don't circularly depend on each other. The dependency graph is a DAG.

If no existing skill fits, create a stub skill with a description that explains why it exists. The document lives as a reference within the skill and is progressively disclosed (loaded only when the skill is invoked, not upfront).

**Reference file design** (within a skill): Apply the same cohesion principles to reference files. Each reference should serve a single audience and change for a single reason. Validate with:

- **CRP test**: "If I load this reference, do I plausibly need all of it?" If a reference mixes engine internals with manifest schema, split it.
- **CCP test**: "When X changes, how many references need updating?" If more than one, the boundary is wrong.

See `plugins/bootstrap/skills/bootstrap/` for the gold standard — 4 references split by audience (engine developers, manifest authors, debuggers, plugin authors) with clean change boundaries.

## Plugin System

Plugins follow the Claude Code plugin spec:
- **Marketplace manifest** (`.claude-plugin/marketplace.json`): Lists available plugins with name, version, source path
- **Plugin manifest** (`.claude-plugin/plugin.json`): Per-plugin metadata (name, version, description, keywords)
- **Skill discovery**: Claude Code scans `skills/` directories for `SKILL.md` files
- **Variable expansion**: `${CLAUDE_PLUGIN_ROOT}` resolves to the plugin's install path at runtime

### Hook Output JSON Schema

**Official docs**: https://code.claude.com/docs/en/hooks (canonical reference for all hook events, input/output schemas, exit codes, matchers, and decision control). When in doubt about hook behavior, fetch this URL — it is the source of truth.

**Universal JSON output fields** (all events):

| Field | Default | Description |
|-------|---------|-------------|
| `continue` | `true` | If `false`, Claude stops entirely. Takes precedence over event-specific decisions |
| `stopReason` | none | Message shown to user when `continue` is `false`. Not shown to Claude |
| `suppressOutput` | `false` | If `true`, hides stdout from verbose mode |
| `systemMessage` | none | Warning shown to user only — Claude never sees it |

**Decision control by event**:

| Events | Pattern | Key fields |
|--------|---------|------------|
| UserPromptSubmit, PostToolUse, PostToolUseFailure, Stop, SubagentStop, ConfigChange | Top-level `decision` | `decision: "block"`, `reason` |
| TeammateIdle, TaskCompleted | Exit code or `continue: false` | Exit 2 blocks with stderr feedback |
| PreToolUse | `hookSpecificOutput` | `permissionDecision` (allow/deny/ask), `permissionDecisionReason`, `updatedInput`, `additionalContext` |
| PermissionRequest | `hookSpecificOutput` | `decision.behavior` (allow/deny), `updatedInput`, `updatedPermissions`, `message` |

**Context injection** — how to get text to Claude vs. the user:

| Event | To user | To Claude |
|-------|---------|-----------|
| SessionStart | `systemMessage` | Plain text stdout or `hookSpecificOutput.additionalContext` |
| UserPromptSubmit | `systemMessage` | Plain text stdout or `hookSpecificOutput.additionalContext` |
| PreToolUse | `systemMessage` | `hookSpecificOutput.additionalContext` |
| PostToolUse / PostToolUseFailure | `systemMessage` | `hookSpecificOutput.additionalContext` or `decision: "block"` + `reason` |
| Stop / SubagentStop | `systemMessage` | `decision: "block"` + `reason` |
| SubagentStart | `systemMessage` | `hookSpecificOutput.additionalContext` |
| Notification | `systemMessage` | `hookSpecificOutput.additionalContext` |

**Exit codes**: 0 = success (JSON parsed from stdout), 2 = blocking error (stderr fed to Claude), other = non-blocking error. JSON is only processed on exit 0. For UserPromptSubmit and SessionStart, stdout is always added as context (not just in verbose mode).

**Background mode output** (consumed by Stop hook) must NOT include `hookSpecificOutput`.

### Plugin Cache and Registry Layout

Claude Code stores plugin data under `~/.claude/plugins/`:

| Path | Purpose |
|------|---------|
| `cache/{marketplace}/{plugin}/{version}/` | Cached plugin files (copied from marketplace clone) |
| `marketplaces/{marketplace}/` | Git clone of marketplace repo |
| `installed_plugins.json` | Registry of installed plugins (version, gitCommitSha, installPath, scope) |
| `known_marketplaces.json` | Registry of known marketplaces (source, installLocation, lastUpdated, autoUpdate) |
| `data/{plugin}/` | Per-plugin runtime data (config, logs, venv) |

### Debugging

```bash
# Version report — shows local, marketplace, installed, and cached versions for all plugins
bash scripts/plugin-versions.sh

# Run bootstrap engine in console mode (plain text, no JSON, no log writes)
python plugins/bootstrap/engine/bootstrap_engine.py --plugin-root plugins/bootstrap --data-dir ~/.claude/plugins/data/bootstrap --console

# Verbose mode (show ok/cached entries too)
python plugins/bootstrap/engine/bootstrap_engine.py --plugin-root plugins/bootstrap --data-dir ~/.claude/plugins/data/bootstrap --console --verbose
```

## Preferences

- **Never use the memory system** (`~/.claude/projects/*/memory/`). Always update `CLAUDE.md` instead — it is machine-independent and checked into the repo, so all machines and sessions share the same context.
