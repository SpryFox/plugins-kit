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

- Logging is always on by default for easier debugging during development
- The bootstrap plugin is always enabled (engine exception) — no user opt-in required
- Self-update: when the bootstrap plugin's config schema changes, it migrates the installed config automatically

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
- **Robust Python detection + self-bootstrap**: `command -v python3` passes on Windows even for the Windows Store stub (which exits 126 and isn't a real interpreter). Detection now validates each candidate by execution. When no valid Python 3 is found, the script self-bootstraps by downloading a pinned python-build-standalone build (`cpython-3.12.9+20250317`) to `~/.claude/plugins/data/bootstrap/python/` and symlinking `~/.local/bin/python3` (already guaranteed by bootstrap's `path_entries`).

### Notes

- The additional config is how users opt in to bootstrapping plugins beyond the defaults
- test-plugin is the simplest case study — exercises tools, venv, git deps, and custom config check

---

## Milestone 3: Unreal-Kit Integration

Port unreal-kit to use the bootstrap system — the most complex case with manifest + script hybrid.

### Deliverables

- [ ] Port unreal-kit bootstrap to manifest + script per case study
- [ ] User adds unreal-kit to additional config → bootstrap plugin installs and bootstraps it
- [ ] Manifest handles: path entries, tools, venv, ini settings, PyPI package
- [ ] Script handles: `.uproject` discovery, project-specific stub copy
- [ ] Tests for hybrid manifest+script processing and variable resolution

### Notes

- This exercises the full hybrid model — manifest for standard ops, script for domain-specific logic
- The `ini_settings` manifest entry depends on `${uproject_dir}` — engine skips entries with unresolved variables until the script discovers the project

---

## Milestone 4: Update01 as Standalone Marketplace Bootstrapper

Make the update01 marketplace a carbon copy of plugins-kit, used to force-install the plugins-kit marketplace and bootstrap plugin in team environments.

### Deliverables

- [ ] Delete existing update01 content and replace with a copy of the plugins-kit repository
- [ ] update01 uses `additionalKnownMarketplaces` to install the update01 marketplace and the `update01:bootstrap` plugin
- [ ] update01's bootstrap plugin forces installation of the plugins-kit marketplace
- [ ] update01's bootstrap plugin forces installation of the `plugins-kit:bootstrap` plugin
- [ ] Support marketplace operations: install, delete, and update marketplaces (not just plugins)
- [ ] Tests for marketplace install/delete/update operations and cross-marketplace bootstrap flow

### New Requirement: Marketplace Management

In addition to plugin operations (install, delete, update), the bootstrap system must support **marketplace operations**:

| Operation | Description |
|-----------|-------------|
| Install marketplace | Register a new marketplace in `known_marketplaces.json` |
| Delete marketplace | Remove a marketplace registration |
| Update marketplace | Refresh marketplace metadata and plugin cache |

This is required for the team deployment flow:
1. Team member has `additionalKnownMarketplaces` pointing to update01 repo
2. update01's bootstrap plugin runs on session start
3. It installs the plugins-kit marketplace (via marketplace install operation)
4. It installs `plugins-kit:bootstrap` (via plugin install operation)
5. On next session, plugins-kit's bootstrap takes over normal plugin management

### Notes

- update01 is the "seed" — it exists only to bootstrap the real marketplace into existence
- Once plugins-kit is installed, update01 becomes redundant but harmless
- The `additionalKnownMarketplaces` setting is the entry point — it's the only thing a team member needs to configure manually

---

## Milestone 5: Capability Audit

Audit all desired capabilities from the ARCHITECTURE.md operation tables against the bootstrap system's actual implementation to identify gaps.

### Deliverables

- [ ] Enumerate every operation from the Shared Library tables (Configuration, Tool, Library/Data, Plugin) and Manual Operations table
- [ ] Enumerate every manifest field from the `bootstrap.json` schema
- [ ] For each operation: verify it is implemented, tested, and exercised by at least one case study
- [ ] For each manifest field: verify the engine processes it correctly
- [ ] Identify gaps: operations described in architecture but not implemented, or implemented but not covered by any case study
- [ ] Produce a gap report with prioritized remediation plan
- [ ] Verify test coverage for all implemented operations; add missing tests identified by the audit

### Notes

- This is a verification milestone — no new features, just ensuring what we documented is what we built
- The gap report becomes input for a potential Milestone 6 addressing any shortfalls
- Pay particular attention to marketplace operations (install/delete/update) added in Milestone 4 — these are the newest requirement and most likely to have gaps
