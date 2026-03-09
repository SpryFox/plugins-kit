# Bootstrap Engine Internals

How the bootstrap engine discovers, processes, and remediates plugin dependencies on session start.

## Two-Phase Architecture

Bootstrap uses a fire-and-forget model to avoid blocking session start:

1. **SessionStart hook** (instant): Emits `{"continue": true, "suppressOutput": true}` immediately, then forks the engine to the background with `--background`. The shell script exits and Claude Code becomes interactive within milliseconds.

2. **Engine (background)**: Runs all checks (tools, venv, marketplace, plugins, etc.), writes results to `bootstrap.log`, and — if there's anything to display — writes display JSON atomically to `bootstrap_display.json` in the data directory. When everything passes silently, no display file is created.

3. **Stop hook** (every turn, ~0ms when idle): Checks for `bootstrap_display.json`. If present, emits its contents and deletes the file. If absent, exits immediately with no output. **Important**: Stop hooks only support top-level fields (`continue`, `suppressOutput`, `systemMessage`, `decision`, `reason`) — `hookSpecificOutput` is not valid for Stop hooks and will be rejected. All content (log + remediation instructions) is merged into `systemMessage`.

This means users see bootstrap results on the first turn after the engine completes, rather than waiting for the engine before the session starts. Console mode (`--console`) bypasses this entirely and runs synchronously with plain text output.

## Engine Phases

The bootstrap engine has two distinct setup phases:

1. **Self-setup** (step 3): Engine prerequisites — tools, PATH entries, and venv — declared in `config.json` under `self_setup`. These make the engine itself runnable (e.g. uv, git, PyYAML). Processed before any `bootstrap.json`.
2. **Plugin bootstrap** (step 4): Ecosystem management — marketplaces and plugins — declared in each plugin's `bootstrap.json`. The engine auto-discovers which installed plugins need bootstrapping by scanning for `bootstrap.json` in each plugin's install path (resolved from `plugins/installed_plugins.json`).

Discovery results are cached in `plugins/data/plugins-kit/bootstrap/config.json` under `bootstrap_cache` to avoid repeated filesystem scans — entries are added on first discovery and removed if `bootstrap.json` disappears (e.g. after a plugin update). Users can permanently opt out a plugin by adding its ref to `no_bootstrap` in that config file.

### Step 4 Processing Order

Plugins are processed in a deterministic order:
1. **Bootstrap plugin** (`plugins-kit:bootstrap`) — ensures marketplace updates happen first
2. **Same-marketplace plugins** (other plugins from plugins-kit) — alphabetically
3. **Other marketplace plugins** — alphabetically

This ordering ensures marketplace updates complete before dependent plugins check versions.

For each discovered plugin, the engine resolves the plugin's install path via `plugins/installed_plugins.json` (e.g. `~/.claude/plugins/cache/plugins-kit/unreal-kit/0.1.5`) and processes bootstrapping in two phases:

1. **Manifest phase**: If `bootstrap.json` exists, the engine reads it and calls the appropriate library primitives for each declared operation. No plugin code runs — the engine drives everything.
2. **Script phase**: If a bootstrap script exists, the engine imports it and calls its entry point. The script runs **in-process** within a try/except, so one plugin's failure doesn't affect others. Scripts share state with the engine (e.g. aggregating fix-all directives) and avoid subprocess overhead.

Either phase is optional — a plugin can provide just a manifest, just a script, or both.

## First Run Lifecycle

On a clean install (wiping `~/.claude/plugins/`), Claude Code goes through distinct phases across restarts:

### Phase 1: Marketplace Sync

**Trigger**: Claude Code starts with `additionalKnownMarketplaces` pointing to the plugins-kit repo.

**What happens**:
- Claude Code clones the marketplace repo to `plugins/marketplaces/plugins-kit/`
- Records it in `plugins/known_marketplaces.json` with source URL, install location, and `lastUpdated` timestamp
- No plugins are installed yet

**State after Phase 1**:
```
plugins/known_marketplaces.json     <- marketplace registered
plugins/marketplaces/plugins-kit/   <- full repo clone
plugins/installed_plugins.json      <- {"version": 2, "plugins": {}}
```

### Phase 2: Plugin Install + Bootstrap Hook

**Trigger**: Claude Code starts again (second run). Marketplace is known; Claude Code installs enabled plugins.

**What happens**:
1. Plugin files copied to `plugins/cache/plugins-kit/bootstrap/0.1.0/`
2. Entry written to `plugins/installed_plugins.json` (scope, installPath, version, gitCommitSha, projectPath)
3. Bootstrap plugin's SessionStart hook fires (`session-bootstrap.sh`)
4. Hook detects no Python 3 -> downloads standalone Python runtime
5. Bootstrap engine runs

**State after Phase 2**:
```
plugins/cache/plugins-kit/bootstrap/0.1.0/   <- plugin files cached
plugins/installed_plugins.json               <- plugins-kit:bootstrap entry
~/.local/share/python-standalone/            <- standalone Python runtime
```

## Messaging Protocol

An optional protocol that bootstrap scripts can use to communicate with the engine. Scripts that use the protocol get structured features (fix-all aggregation, user messaging, re-run triggers). Scripts that don't use the protocol just run and return.

The engine collects messages from all plugin scripts and emits a unified response:

- **Agent message** (`additionalContext`): Instructions to Claude on what needs fixing and how
- **User message** (`systemMessage`): Human-readable summary of what needs attention

## Execution Flow

The engine accepts a `--background` flag. When set, output is written atomically to `bootstrap_display.json` in the data directory instead of stdout. Background output uses only top-level fields (`continue`, `suppressOutput`, `systemMessage`) since it is consumed by the Stop hook, which does not support `hookSpecificOutput`. Non-background output (stdout, consumed by SessionStart hook) includes `hookSpecificOutput` with `hookEventName: "SessionStart"`. When there's nothing to display (silent success with `log_success_checks` off), no file is written.

1. **Auto-run phase**: Bootstrap runs on session start. For each tool check, the engine runs check -> remediate -> re-check:
   - Tool present -> log `<name>: passed`, continue
   - Tool missing, install command available -> run install silently -> re-check:
     - Now present -> log `<name>: installed`, continue (no fix-all entry)
     - Still missing -> log `<name>: FAILED - install attempted but <name> not found in PATH`, add to fix-all
   - Tool missing, no install command -> log `<name>: FAILED`, add to fix-all

   This means most first-run tool installs (e.g. `uv`) succeed silently. The user never sees a fix-all message unless the install itself fails or no install command exists.

2. **Fix-all phase**: Only reached if one or more operations remain unresolved after remediation attempts (install failed, user action required, information unknown). The engine emits:
   - **Agent message**: What needs fixing and how to fix it (e.g. "Ask the user where the `.uproject` file is, then write that information to `{path}` as the value of the `UPROJECT_LOCATION` variable")
   - **User message**: What needs fixing and an instruction to type `fix-all` to remediate

   The user saying `fix-all` signals consent for Claude to gather information and apply results.

3. **Fixed phase**: After the user performs a manual action (e.g. restarting an external application), they type `fixed`. This signals Claude to re-trigger the bootstrap script, which should complete the remaining steps without requiring a Claude Code restart.

## Throttling

Checks can be throttled to avoid redundant work.

- **Content-hash throttling** computes a hash of input manifests and skips re-execution when the hash matches a stored value — re-runs only when declarations change.
- **Time-based throttling** records a timestamp and skips checks within a cooldown window — useful for network operations (e.g., `git ls-remote`) where the cost is latency rather than correctness.

Both can be combined: time-throttle the remote check, content-hash the local setup.

## Design Principles

**Configuration-driven, not logic-driven.** The hook contains no platform-specific conditional branches for individual tools. It detects the OS once, reads the manifest entries for that OS, and executes what's declared. All platform knowledge lives in the manifests.

**Explicit per-OS entries.** Every tool dependency declares its check and install method for each platform it supports. No defaults, no inheritance. If `curl` is needed on all platforms, it appears three times.

**Collect independent failures.** System tool checking collects all independent failures rather than failing on the first one, so the user sees everything they need to fix. Consequential failures (e.g., a command that lives in a failed PATH directory) are detected and skipped.

**Two-tier venv management.** First checks if the existing venv is functional (Tier 1: directory exists, Python runs, packages importable) without needing uv. Only falls back to `uv sync` (Tier 2) if the venv is missing or broken. This removes the hard uv dependency for sessions where the venv is already good.

**Persistent storage.** The venv and cloned git repos live in `~/.claude/plugins/data/<plugin>/` (outside the plugin cache), so they survive cache refreshes when the plugin updates.

**Remediation, not auto-fix.** When something is missing, the hook emits structured JSON with the exact install command into Claude's `additionalContext`. The user can fix it themselves or tell Claude to do it.

## Shared Library

Python library providing check-and-remediate primitives for common operations. These are the same primitives the engine calls when processing manifest entries — scripts can call them directly for custom workflows.

### Library Design Principles

Library boundaries follow Robert C. Martin's [package cohesion principles](https://en.wikipedia.org/wiki/Package_principles):

- **Common Reuse Principle (CRP)**: If you use one module in a library, you should plausibly use them all. Don't force a plugin to depend on code it doesn't need.
- **Common Closure Principle (CCP)**: Modules that change for the same reason belong together. A bug fix or feature change should affect one library, not scatter across several.
- **Acyclic Dependencies Principle (ADP)**: Libraries must not have circular dependencies. The dependency graph is a DAG.

## Script (Optional)

A Python module at a conventional location in the plugin's install path. Runs after manifest processing. The script:

- Can use the shared library (already on `sys.path` via the engine) or not
- Can read static config from its own directory
- Can read/write dynamic config from its data directory (e.g. `plugins/data/plugins-kit/unreal-kit/`)
- Returns a result indicating success, or outstanding issues requiring user intervention

Scripts are for logic that can't be expressed declaratively — domain-specific discovery, conditional branching, multi-step workflows that depend on intermediate results.

## Testing

All bootstrap modules have automated tests at the repo level in `tests/bootstrap/`. Tests use pytest and run via `uv run --extra dev pytest -v` from the repo root.

**Structure**: Library modules get unit tests with direct imports. The engine gets integration tests that invoke `bootstrap_engine.py` as a subprocess (matching how the bash wrapper calls it). Shared fixtures in `tests/conftest.py` provide temporary data directories, manifest builders, and path helpers.

**Why repo-level**: The bootstrap engine is cross-cutting infrastructure that will orchestrate multiple plugins. Tests need to span plugin boundaries (e.g. verifying engine+plugin manifest interactions), which doesn't fit inside any single plugin's directory.

**Standard**: Every new library module or engine capability must have corresponding tests before the milestone is considered complete. See [MILESTONES.md](../../../../docs/planning/bootstrap/MILESTONES.md) for per-milestone test deliverables.

## Case Studies

- [test-plugin](../../../../docs/bootstrap/reference/case-studies/test-plugin.md) — Minimal reference implementation exercising core bootstrap operations
- [update01/bootstrap](../../../../docs/bootstrap/reference/case-studies/update01-bootstrap.md) — Marketplace sync and plugin cache refresh
- [unreal-kit](../../../../docs/bootstrap/reference/case-studies/unreal-kit.md) — Game development plugin with system tools, venv, config discovery, and external app dependencies
