# Bootstrap Plugin — Development Milestones

## Testing Standard

Every milestone must include automated tests for new functionality. Tests live at the repo level in `tests/bootstrap/` and run via `uv run --extra dev pytest -v`. New modules get unit tests; new integration points get integration tests using subprocess invocation of the engine.

**Baseline**: Milestone 1 established 25 tests across 7 modules covering all library, config, and engine functionality. Subsequent milestones must maintain and extend this coverage.

---

## Milestone 1: Bootstrap Plugin Foundation

Create the bootstrap plugin itself with engine, default config, and logging.

### Deliverables

- [x] Create `plugins/bootstrap/` plugin structure (`.claude-plugin/plugin.json`, etc.)
- [x] Create default config file copied to `./plugins/data/plugins-kit/bootstrap/config.json`
- [x] Default config ensures the machine has prerequisites for bootstrap scripts to run (e.g. `uv`, `git`)
- [x] Bootstrap engine processes manifests and runs scripts per ARCHITECTURE.md
- [x] Log file written on every initialization run with check results (e.g. `uv installed - passed`)
- [x] Bootstrap plugin updates its own config when out of date (self-bootstrap)
- [x] Automated tests for all lib modules (tool_check, path_check, cache, log, platform_detect), config, and engine integration

### Notes

- Success logging is off by default (config v3) — output only appears on failures or remediation. Enable `log_success_shell`/`log_success_checks` in config.json for verbose output
- The bootstrap plugin is always enabled (engine exception) — no user opt-in required
- Self-update: when the bootstrap plugin's config schema changes, it migrates the installed config automatically

### Discovered Deficiencies

- **`tool_check.py` remediation not implemented**: The engine checks tools and reports failures but never runs the platform-specific install command. ARCHITECTURE.md specified "Run platform-specific install command" as the remediation for missing tools, and the auto-run phase was designed to "apply remediations silently." The remediation loop (run install → re-check → escalate only on failure) was never built. Needs: add remediation step to `tool_check.py` and update engine to attempt remediation before escalating to fix-all. Planned install strategy: prefer `curl | sh` (or `curl | powershell -`) for any tool that provides an installer script — works on all platforms including Windows Git Bash. Chocolatey is a fallback only for tools with no curl-installable installer; install Chocolatey lazily the first time it's needed, not preemptively.

---

## Milestone 2: Test Plugin Integration

Port the test-plugin to use the bootstrap system and introduce user-configurable additional dependencies.

### Deliverables

- [x] Port test-plugin bootstrap to manifest + optional script per case study
- [x] Add additional config mechanism for non-default dependencies (user-defined plugins to bootstrap)
- [x] User adds test-plugin to additional config → bootstrap plugin installs and bootstraps it
- [x] Bootstrap plugin updates its own config when out of date
- [x] Tests for additional config loading and test-plugin manifest processing

### Discovered Requirements

- **No Stop hook fallback**: Plugins installed during startup require a restart before they function — SessionStart hooks from the newly installed plugin don't fire until the next session. A Stop hook cannot bootstrap a plugin mid-session because the plugin's hooks aren't loaded yet. The Stop hook was removed.
- **Cache compute/check split**: Separate hash computation (expensive) from hash comparison (cheap). `compute_current_hash()` writes a pre-computed hash file; `check_cache_fast()` compares it against the stored cache without recomputing. Available for future per-turn checks if needed.
- **Robust Python detection + self-bootstrap**: `command -v python3` passes on Windows even for the Windows Store stub (which exits 126 and isn't a real interpreter). Detection now validates each candidate by execution. When no valid Python 3 is found, the script self-bootstraps by downloading a pinned python-build-standalone build (`cpython-3.12.9+20250317`) to `~/.local/share/python-standalone/` and linking `~/.local/bin/python3`. On Windows, hard links via `New-Item -ItemType HardLink` can't find stdlib (Python resolves relative to executable path), so detection also checks the standalone install directory directly. PowerShell `New-Item` output must be redirected to `/dev/null` to avoid corrupting hook JSON output.

### Notes

- The additional config is how users opt in to bootstrapping plugins beyond the defaults
- test-plugin is the simplest case study — exercises tools, venv, git deps, and custom config check

---

## Milestone 3: Plugin Integration

Port local-review-kit and unreal-kit to the bootstrap system. Two real-world plugins validate the engine before moving to marketplace distribution.

### Deliverables

#### Part A: local-review-kit port

- [x] Create `plugins/local-review-kit/bootstrap.json` (tools, venv, git_deps)
- [x] Implement engine config phase for config check (setup.py integration)
- [x] Remove hand-rolled hooks (sessionstart/*, stop/bootstrap-check.py, lib/)
- [x] Add local-review-kit to installed_plugins.json and bootstrap config
- [x] Tests for local-review-kit manifest processing
- [x] Verify equivalent output (cached/success/failure messages)

#### Part B: unreal-kit port

- [x] Port unreal-kit bootstrap to manifest + script per case study
- [x] User adds unreal-kit to additional config → bootstrap plugin installs and bootstraps it
- [x] Manifest handles: path entries, tools, venv, ini settings, PyPI package
- [x] Script handles: `.uproject` discovery, project-specific stub copy
- [x] Tests for hybrid manifest+script processing and variable resolution

#### Shared engine work

- [x] Implement script phase in bootstrap_engine.py (import + call entry point)
- [x] Implement ini_settings manifest processing
- [x] Implement pypi_packages manifest processing
- [x] Implement variable resolution (${plugin_root}, ${data_dir}, ${uproject_dir})

### Notes

- Part A is simpler (standard operations only) and validates the engine handles real workloads before Part B
- local-review-kit has ~600 lines of hand-rolled bash bootstrap (5 sessionstart scripts, stop hook, YAML parsers, JSON formatting) that duplicates what the engine already provides
- Part B exercises the full hybrid model — manifest for standard ops, script for domain-specific logic
- The `ini_settings` manifest entry depends on `${uproject_dir}` — engine skips entries with unresolved variables until the script discovers the project
- local-review-kit's Stop hook (re-validates bootstrap mid-session) is out of scope — the engine runs on SessionStart only

---

## Milestone 4: Update01 as Standalone Marketplace Bootstrapper

Make the update01 marketplace a self-contained seed that installs the plugins-kit marketplace and bootstrap plugin on team machines.

### Deliverables

- [x] Replace update01's hand-rolled bash scripts with plugins-kit's bootstrap engine
- [x] Adopt `marketplace:plugin` identity format across the codebase (replaces `plugin@marketplace`)
- [x] Engine cross-marketplace plugin resolution: refs like `plugins-kit:bootstrap` resolve from global registry (`~/.claude/plugins/installed_plugins.json`) when the marketplace differs from the current one
- [x] update01's `bootstrap.json` uses `json_entries` to sync `known_marketplaces.json` and `plugins` to enable `plugins-kit:bootstrap`
- [x] Tests for cross-marketplace resolution (same-marketplace local, cross-marketplace global, missing ref)
- [x] Tests for marketplace name detection from registry keys

### Implementation

**Plugin identity format change**: `plugin@marketplace` → `marketplace:plugin` (colon separator). Updated in:
- `plugin_resolve.py` (parsing logic + `parse_plugin_ref()` helper)
- `plugin_lifecycle.py` (docstring examples)
- `installed_plugins.json` (key format)
- `bootstrap_engine.py` (cross-marketplace resolution)
- All test files and documentation

**Cross-marketplace resolution**: The engine's `plugins` processing in `_process_manifest()` now detects when a plugin ref's marketplace differs from the current one (detected from local registry keys or parent directory name). Cross-marketplace refs resolve against `~/.claude/plugins/installed_plugins.json` instead of the local registry.

**update01 structure**: Identical bootstrap engine/lib/hooks as plugins-kit, with its own `bootstrap.json` that adds `json_entries` (marketplace registration) and `plugins` (force-enable `plugins-kit:bootstrap`).

### Team Deployment Flow

1. Team member has `additionalKnownMarketplaces` pointing to update01 repo
2. update01's bootstrap plugin runs on session start
3. `json_entries` registers plugins-kit in `known_marketplaces.json`
4. `plugins` ensures `plugins-kit:bootstrap` is enabled
5. On next session, plugins-kit's bootstrap takes over normal plugin management

### Notes

- update01 is the "seed" — it exists only to bootstrap the real marketplace into existence
- Once plugins-kit is installed, update01 becomes redundant but harmless
- The `additionalKnownMarketplaces` setting is the entry point — it's the only thing a team member needs to configure manually
- update01's engine/lib are copies (not symlinks) because it's a standalone repo pushed to its own remote

---

## Milestone 5: Capability Audit

Audit all desired capabilities from the ARCHITECTURE.md operation tables against the bootstrap system's actual implementation to identify gaps.

### Deliverables

- [x] Enumerate every operation from the Shared Library tables (Configuration, Tool, Library/Data, Plugin) and Manual Operations table
- [x] Enumerate every manifest field from the `bootstrap.json` schema
- [x] For each operation: verify it is implemented, tested, and exercised by at least one case study
- [x] For each manifest field: verify the engine processes it correctly
- [x] Identify gaps: operations described in architecture but not implemented, or implemented but not covered by any case study
- [x] Produce a gap report with prioritized remediation plan
- [x] Verify test coverage for all implemented operations; add missing tests identified by the audit

### Gap Report

Audit identified 7 gaps between ARCHITECTURE.md and implementation. All 7 were implemented:

| # | Gap | Resolution | New Files |
|---|-----|-----------|-----------|
| 1 | `json_entries` manifest field | `json_check.py` lib + engine processing | `lib/json_check.py`, `test_json_check.py` |
| 2 | `plugins` manifest field | Engine processing for plugin enable/disable | Engine edit |
| 3 | Plugin install/uninstall/update | `plugin_lifecycle.py` lib with register/enable/disable | `lib/plugin_lifecycle.py`, `test_plugin_lifecycle.py` |
| 4 | Personal config (user-bootstrap.json) | Engine processes `user-bootstrap.json` in data dir | `test_engine_personal.py` |
| 5 | Time-based throttling | `check_time_cache`/`write_time_cache` in `cache.py` | `test_time_cache.py` |
| 6 | `extract_pattern` in pypi_packages | `fnmatch` pattern support in `pypi_check.py` | Test added to `test_pypi_check.py` |
| 7 | `fixed` re-run directive | Updated fix-all message to mention `fixed` | N/A |

### Notes

- Originally scoped as verification-only, but all gaps were implemented since none were large
- 230 total tests pass across the full suite (179 bootstrap + 51 other)
- All ARCHITECTURE.md operations now have matching implementations
