# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**plugins-kit** is a Claude Code plugin marketplace containing game development plugins. Currently ships one plugin: **unreal-kit**, which provides Unreal Engine Python API automation for asset inspection, reference graph traversal, script execution, and data extraction.

This is a **Claude Code plugin** — it extends Claude Code with skills, commands, and hooks via the `.claude-plugin/marketplace.json` manifest. Plugins are loaded either via `--plugin-dir` (development) or `enabledPlugins` in settings (production).

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
      lib/                            # Shared libraries (cache, tool_check, etc.)
      hooks/sessionstart/             # SessionStart hook (bash wrapper)
      defaults/                       # Default config files
    test-plugin/                      # Test plugin (exercises bootstrap system)
      .claude-plugin/plugin.json      # Plugin manifest
      bootstrap.json                  # Test plugin's bootstrap manifest
      hooks/stop/                     # Stop hook (fallback bootstrap)
      scripts/                        # Config setup
    unreal-kit/                       # The UE plugin
      .claude-plugin/plugin.json      # Plugin manifest
      skills/
        ue-python-api/                # The main skill
          SKILL.md                    # Skill definition (loaded by Claude Code)
          bin/                        # Entry points (runner + setup)
          lib/                        # Shared Python libraries
          scripts/                    # Utility scripts
          stubs/                      # UE Python API stubs (generated, gitignored)
          references/                 # Detailed docs loaded conditionally by SKILL.md
```

### Key Files

| File | Purpose |
|------|---------|
| `plugins/bootstrap/engine/bootstrap_engine.py` | Main engine — processes manifests, runs checks, emits hook JSON |
| `plugins/bootstrap/lib/cache.py` | Content-hash caching (compute, check, write) |
| `plugins/bootstrap/lib/tool_check.py` | System tool availability checks |
| `plugins/bootstrap/lib/platform_detect.py` | OS detection |
| `plugins/bootstrap/lib/log.py` | File-based bootstrap logging |
| `plugins/bootstrap/lib/venv_check.py` | Python venv validation |
| `plugins/bootstrap/lib/git_dep_check.py` | Git dependency validation |
| `plugins/bootstrap/lib/plugin_resolve.py` | Plugin registry resolution |
| `plugins/bootstrap/lib/path_check.py` | PATH entry validation |
| `plugins/bootstrap/engine/config.py` | Config loading, migration, persistence |
| `plugins/bootstrap/hooks/sessionstart/session-bootstrap.sh` | SessionStart hook (bash wrapper for engine) |
| `plugins/bootstrap/bootstrap.json` | Bootstrap plugin's own manifest |
| `plugins/bootstrap/ARCHITECTURE.md` | Bootstrap system architecture |
| `plugins/bootstrap/MILESTONES.md` | Development milestones and progress |
| `plugins/test-plugin/hooks/stop/bootstrap-check.py` | Stop hook — fallback bootstrap for late installs |
| `plugins/test-plugin/bootstrap.json` | Test plugin's bootstrap manifest |
| `plugins/test-plugin/scripts/setup.py` | Test plugin config setup |
| `tests/bootstrap/` | All bootstrap tests (mirrors lib/ structure) |

### Key Design Decisions

- **Bootstrapping**: Two-layer system — session bootstrap (bash SessionStart hook, manifest-driven) ensures system tools, venv, and git deps; script bootstrap (Python, runs inside UE Editor) handles UE-side packages at runtime. See [docs/bootstrapping-architecture.md](docs/bootstrapping-architecture.md) for full details.
- **Config resolution order**: CLI args > project config (`~/.claude/plugins/data/unreal-kit/config.yaml`) > skill config (`ue_runner_config.yaml`) > hardcoded defaults
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
- Use `${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/lib` path prefix for imports from this skill
- Call `ensure_dependencies()` before importing packages listed in `requirements.yaml`
- `lib/unreal_pip.py` and `lib/bootstrap.py` only run inside UE Editor (they `import unreal`)
- All other `lib/` and `bin/` modules are host-side (system Python, stdlib only)

## Development Workflow

**Automated tests required** — every new module or integration point must have corresponding tests in `tests/` before the work is considered complete. Tests run via `uv run --extra dev pytest -v` from the repo root. Test directories mirror the plugin structure (e.g. `tests/bootstrap/` for the bootstrap plugin). This standard was established with the bootstrap plugin's M1 test suite and applies to all subsequent development.

**Always push changes** — the plugin cache (`~/.claude/plugins/cache/`) syncs from the remote repository, not the local working copy. Local edits won't take effect until committed and pushed.

**Never manually sync the cache** — do not copy files directly into the plugin cache. Always commit and push, then let Claude Code refresh the cache on restart.

**Keep architecture docs current** — when modifying bootstrap behavior, update `plugins/bootstrap/ARCHITECTURE.md` and `docs/bootstrapping-architecture.md` to reflect the changes. These are the source of truth for how the system works.

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

## Plugin System

Plugins follow the Claude Code plugin spec:
- **Marketplace manifest** (`.claude-plugin/marketplace.json`): Lists available plugins with name, version, source path
- **Plugin manifest** (`.claude-plugin/plugin.json`): Per-plugin metadata (name, version, description, keywords)
- **Skill discovery**: Claude Code scans `skills/` directories for `SKILL.md` files
- **Variable expansion**: `${CLAUDE_PLUGIN_ROOT}` resolves to the plugin's install path at runtime
