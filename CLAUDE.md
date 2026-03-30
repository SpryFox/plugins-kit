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
| `lib/ue_runner_config.py` | Config loading with layered resolution and fallback YAML parser |
| `lib/ue_discovery.py` | Project discovery — finds `.uproject` and engine directory |
| `lib/ue_ini.py` | UE `.ini` file read/write utilities |
| `lib/unreal_pip.py` | Pip operations inside UE's embedded Python (runs in-editor) |
| `lib/bootstrap.py` | Dependency bootstrapper for UE scripts (runs in-editor) |
## Commands

```bash
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

**Local development** — use `--plugin-dir` to test plugins from the working copy:

```bash
claude --plugin-dir ~/Dev/plugins-kit/plugins/my-plugin
```

`--plugin-dir` loads the plugin directly from disk (no cache copy) and makes no persistent changes — it doesn't modify `installed_plugins.json`, the cache, or `known_marketplaces.json`. Ending the session reverts to the marketplace-installed version. Use `/reload-plugins` to pick up file changes within a session (hooks require a full restart).

**Publishing changes** — the plugin cache syncs from the remote repository's default branch, not the local working copy. Develop on the `dev` branch; merge to `master` only when releasing a version bump. This prevents silent divergence (fresh installs between releases getting HEAD code cached under the old version string). To publish:

1. Bump the plugin version in both files — they must match:
   - `plugins/<name>/.claude-plugin/plugin.json` (the plugin's own manifest)
   - `.claude-plugin/marketplace.json` (the marketplace-level listing)
2. Merge `dev` to `master` and push
3. Users with `autoUpdate: true` receive the update on next session start
4. Users without auto-update run `/plugin marketplace update` then `/plugin update`

**Why both files**: Claude Code uses the `marketplace.json` version to decide whether to fetch a new cache entry. If you only bump `plugin.json` but not `marketplace.json`, consumers won't see the update. A pre-commit hook (`scripts/pre-commit-version-check.sh`) blocks commits when these versions diverge.

**The cache keys on version** — same version = same code. The cache will NOT refresh without a version bump, even if you push new commits. Fresh installs between releases copy HEAD code under the old version string, creating **silent divergence** — two users on the "same version" with different code. The dev-branch strategy above prevents this. Never copy files directly into the plugin cache — always use this publish flow.

**Don't omit the version field** hoping for rolling updates. Claude Code substitutes a truncated git SHA, which becomes a static cache key at install time — identical behavior to a version string, with worse readability.

**Downstream consumers with git dependencies** (e.g., update06): If another project depends on `bootstrap` as a Python git dependency (`bootstrap @ git+https://...`), also bump `bootstrap`'s Python package version in `plugins/bootstrap/pyproject.toml`. Without a package version bump, `uv sync` may consider the installed copy satisfied and skip reinstallation even after the lockfile changes.

### update06 — the bootstrap bootstrapper

**Repository**: `kitaekatt/update06` (local: `~/Dev/update06`)

**Purpose**: update06 is a separate marketplace that exists to fix chicken-and-egg problems in plugins-kit. If bootstrap is broken in a way that prevents it from updating itself, update06 provides an independent code path that can repair the situation.

**How it works**: update06 contains a single plugin ("update") whose job is to ensure plugins-kit marketplace is registered and the bootstrap plugin is installed. Its `update_engine.py` is a thin facade that imports `_process_manifest` from `bootstrap_lib` and delegates all real work to it.

**Library dependency**: update06 declares `bootstrap` as a Python git dependency in its `pyproject.toml`:
```
bootstrap @ git+https://github.com/kitaekatt/plugins-kit.git#subdirectory=plugins/bootstrap
```
This installs `bootstrap_lib` into update06's own venv. The venv lives at `~/.claude/plugins/data/update06/update/.venv` and is separate from the bootstrap plugin's cache.

**Three version numbers matter when publishing fixes**:
1. `plugins/bootstrap/.claude-plugin/plugin.json` — plugin version (triggers cache refresh)
2. `.claude-plugin/marketplace.json` — marketplace listing (must match plugin.json)
3. `plugins/bootstrap/pyproject.toml` — Python package version (triggers `uv sync` reinstall in update06's venv)

All three must be bumped for a fix to reach both plugins-kit consumers and update06. After bumping, regenerate update06's lockfile:
```bash
cd ~/Dev/update06/plugins/update
uv lock --upgrade-package bootstrap
```
Then bump update06's own version in both `plugin.json` and `marketplace.json`, commit, and push.

**Keep architecture docs current** — when modifying bootstrap behavior, update the bootstrap skill references (`plugins/bootstrap/skills/bootstrap/references/`) to reflect the changes. These are the source of truth for how the system works.

**Anti-pattern: silent bootstrap operations.** Every bootstrap check must log its outcome — `ok_entries` when passing (verbose-only), `action_entries` when remediating (always visible). Adding a check that creates files, clones repos, or writes config without emitting a log entry is a bug. See the "Every check must log its outcome" principle in [engine-internals.md](plugins/bootstrap/skills/bootstrap/references/engine-internals.md).

**Always use `uv run python` in shell scripts** — never bare `python` or `python3`. On Windows, the system PATH contains Microsoft Store stubs (`WindowsApps/python.exe`) that take precedence over any user PATH entry, causing bare `python`/`python3` to fail with "Permission denied" (exit 126) in Git Bash. On macOS, bare `python` often doesn't exist. Since bootstrap guarantees `uv` is available, `uv run python` is the standard way to invoke Python from any shell script in this project. It resolves the correct Python, activates the venv (giving access to installed packages), and works on all platforms.

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

### Hook JSON Format

**Official docs**: https://code.claude.com/docs/en/hooks (canonical reference). When in doubt, fetch this URL — it is the source of truth.

On exit 0, stdout is parsed as JSON. Exit 2 = blocking error (stderr fed to Claude). Other exits = non-blocking error. JSON is only processed on exit 0.

**Universal fields** (all events):

| Field | Default | Description |
|-------|---------|-------------|
| `continue` | `true` | If `false`, Claude stops entirely. Takes precedence over other decisions |
| `stopReason` | none | Message shown to user when `continue` is `false`. Not shown to Claude |
| `suppressOutput` | `false` | If `true`, hides stdout from verbose mode |
| `systemMessage` | none | Shown to user only — Claude never sees it |

**Event-specific decision control**:

| Event | Decision pattern | To Claude |
|-------|-----------------|-----------|
| SessionStart | None | `hookSpecificOutput.additionalContext` or plain text stdout |
| UserPromptSubmit | `decision: "block"` + `reason` | `hookSpecificOutput.additionalContext` or plain text stdout |
| PreToolUse | `hookSpecificOutput.permissionDecision` (allow/deny/ask) | `hookSpecificOutput.additionalContext` |
| PostToolUse | `decision: "block"` + `reason` | `hookSpecificOutput.additionalContext` |
| PostToolUseFailure | None | `hookSpecificOutput.additionalContext` |
| Stop / SubagentStop | `decision: "block"` + `reason` | `reason` only (no `hookSpecificOutput`) |
| SubagentStart | None | `hookSpecificOutput.additionalContext` |
| Notification | None | `hookSpecificOutput.additionalContext` |
| PermissionRequest | `hookSpecificOutput.decision.behavior` (allow/deny) | — |
| ConfigChange | `decision: "block"` + `reason` | — |

`hookSpecificOutput` always requires `hookEventName` set to the event name.

**Background mode** (bootstrap-specific): The engine writes output to a pending file, which the UserPromptSubmit hook reads and outputs as its own stdout. Stop hooks do not support `hookSpecificOutput`, so UserPromptSubmit is used to inject `additionalContext` for Claude.

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
