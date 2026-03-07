# Bootstrap Plugin Architecture

A bootstrap system for Claude Code plugins. The bootstrap engine discovers enabled plugins and processes their bootstrap configuration on session start. A hybrid model combines **declarative manifests** for common operations with **optional scripts** for custom logic.

## Goal

Each plugin that needs bootstrapping provides a `bootstrap.json` manifest and/or a bootstrap script. The engine manages *when* bootstrapping runs and *which* plugins are enabled. The manifest declares *what* standard operations to perform; the script handles anything that needs custom logic.

The hybrid model means a plugin author doesn't need to write any code for common operations — tool checks, venv setup, git dependencies, config file manipulation are all expressible as manifest entries. A shared Python library provides the primitives that the engine calls when processing manifests — the same primitives are available to scripts for custom logic.

## Engine

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

## Plugin Bootstrap

### Manifest (`bootstrap.json`)

A declarative configuration file covering automatable operations. The engine reads the manifest and calls library primitives directly — no plugin code needed.

```json
{
  "tools": [
    {"name": "git"},
    {"name": "uv", "install": {"darwin": "curl -LsSf https://astral.sh/uv/install.sh | sh", "linux": "curl -LsSf https://astral.sh/uv/install.sh | sh", "windows": "powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\""}}
  ],
  "path_entries": ["~/.local/bin"],
  "venv": {
    "check_imports": ["yaml", "upyrc"]
  },
  "git_deps": [
    {
      "url": "https://github.com/octocat/Hello-World",
      "branch": "master",
      "sparse_paths": ["README"]
    }
  ],
  "json_entries": [
    {
      "reference": "known_marketplaces.json",
      "target": "~/.claude/plugins/known_marketplaces.json",
      "merge_fields": ["source", "autoUpdate"],
      "preserve_fields": ["lastUpdated", "installLocation"]
    }
  ],
  "ini_settings": [
    {
      "file": "${uproject_dir}/Config/UserEngine.ini",
      "section": "/Script/PythonScriptPlugin.PythonScriptPluginSettings",
      "settings": {"bRemoteExecution": "True", "bIsDeveloperMode": "True"}
    }
  ],
  "pypi_packages": [
    {
      "package": "unreal-stub",
      "extract_to": "${plugin_root}/skills/ue-python-api/stubs/unreal.py",
      "extract_pattern": "*.py"
    }
  ],
  "marketplaces": [
    {"name": "plugins-kit", "source": "https://github.com/user/plugins-kit.git", "alwaysUpdate": true}
  ],
  "plugins": [
    {"ref": "plugins-kit:unreal-kit", "enabled": true}
  ],
  "config": {
    "file": "config.yaml",
    "defaults_source": "defaults/config.yaml",
    "required_fields": {
      "uproject_path": {"user_msg": "Set path to your .uproject file", "agent_msg": "Ask user for .uproject path and write it to config.yaml as uproject_path"}
    },
    "autodetect": {"script": "scripts/autodetect.py", "entry_point": "detect"}
  },
  "script": {
    "path": "scripts/bootstrap.py",
    "entry_point": "bootstrap"
  }
}
```

Every field is optional — include only what the plugin needs. Variable references like `${plugin_root}`, `${data_dir}`, and `${uproject_dir}` are expanded by the engine from plugin context and config.

### Script (optional)

A Python module at a conventional location in the plugin's install path. Runs after manifest processing. The script:

- Can use the shared library (already on `sys.path` via the engine) or not
- Can read static config from its own directory
- Can read/write dynamic config from its data directory (e.g. `plugins/data/plugins-kit/unreal-kit/`)
- Returns a result indicating success, or outstanding issues requiring user intervention

Scripts are for logic that can't be expressed declaratively — domain-specific discovery, conditional branching, multi-step workflows that depend on intermediate results.

## Messaging Protocol

An optional protocol that bootstrap scripts can use to communicate with the engine. Scripts that use the protocol get structured features (fix-all aggregation, user messaging, re-run triggers). Scripts that don't use the protocol just run and return.

The engine collects messages from all plugin scripts and emits a unified response:

- **Agent message** (`additionalContext`): Instructions to Claude on what needs fixing and how
- **User message** (`systemMessage`): Human-readable summary of what needs attention

## User Experience

From the user's perspective, there are three possible outcomes on session start:

| What the user sees | What happened |
|--------------------|---------------|
| Nothing | All checks passed (or cache hit) — environment is ready |
| Nothing (first run after install) | Tool was missing, install ran silently, re-check passed — logged internally, no user-visible output |
| Nothing (very first session, fresh machine) | Python was being bootstrapped; the engine runs fully on the next session. No `bootstrap.log` exists yet. |
| Fix-all message | Something needs user action: install failed, no install command, missing config, or external app needs restart |

**Healthy steady state**: The user sees nothing. Bootstrap is working correctly when it's invisible.

**Verifying bootstrap ran**: Check `~/.claude/plugins/data/bootstrap/bootstrap.log`. Entries appear after the first successful engine run. No log file = engine hasn't completed a full session yet (normal on first run of a fresh machine).

## Execution Flow

1. **Auto-run phase**: Bootstrap runs on session start. For each tool check, the engine runs check → remediate → re-check:
   - Tool present → log `<name>: passed`, continue
   - Tool missing, install command available → run install silently → re-check:
     - Now present → log `<name>: installed`, continue (no fix-all entry)
     - Still missing → log `<name>: FAILED - install attempted but <name> not found in PATH`, add to fix-all
   - Tool missing, no install command → log `<name>: FAILED`, add to fix-all

   This means most first-run tool installs (e.g. `uv`) succeed silently. The user never sees a fix-all message unless the install itself fails or no install command exists.

2. **Fix-all phase**: Only reached if one or more operations remain unresolved after remediation attempts (install failed, user action required, information unknown). The engine emits:
   - **Agent message**: What needs fixing and how to fix it (e.g. "Ask the user where the `.uproject` file is, then write that information to `{path}` as the value of the `UPROJECT_LOCATION` variable")
   - **User message**: What needs fixing and an instruction to type `fix-all` to remediate

   The user saying `fix-all` signals consent for Claude to gather information and apply results.

3. **Fixed phase**: After the user performs a manual action (e.g. restarting an external application), they type `fixed`. This signals Claude to re-trigger the bootstrap script, which should complete the remaining steps without requiring a Claude Code restart.

   The `fixed` directive follows the same format as `fix-all` — it tells Claude how to re-run the bootstrap engine.

## Shared Library

Python library providing check-and-remediate primitives for common operations. These are the same primitives the engine calls when processing manifest entries — scripts can call them directly for custom workflows.

### Design Principles

Library boundaries follow Robert C. Martin's [package cohesion principles](https://en.wikipedia.org/wiki/Package_principles):

- **Common Reuse Principle (CRP)**: If you use one module in a library, you should plausibly use them all. Don't force a plugin to depend on code it doesn't need.
- **Common Closure Principle (CCP)**: Modules that change for the same reason belong together. A bug fix or feature change should affect one library, not scatter across several.
- **Acyclic Dependencies Principle (ADP)**: Libraries must not have circular dependencies. The dependency graph is a DAG.

### Configuration

| Condition | Check Method | Remediation |
|-----------|-------------|-------------|
| Directory not in PATH | Read shell RC files or query OS environment variable | Modify persistent PATH configuration (platform-specific) |
| JSON file lacks expected entries | Compare reference entries against target file | Merge missing entries into target JSON |
| Application config setting not enabled | Read config/ini file for setting value | Write setting to config/ini file |

### Tool

| Condition | Check Method | Remediation |
|-----------|-------------|-------------|
| CLI tool not installed | `shutil.which(name)` | Run platform-specific install command → re-check → escalate to fix-all only if still missing |

### Library / Data

| Condition | Check Method | Remediation |
|-----------|-------------|-------------|
| Python venv missing or broken | Check dir → binary → interpreter runs → packages importable | `uv sync` from `pyproject.toml` |
| PyPI package missing | Check extracted file exists locally | Download from PyPI and extract |
| Git dependency not cloned or out of date | Check dir exists + `git ls-remote` vs local `rev-parse HEAD` | `git clone` or `git pull` |

### Marketplace

| Condition | Check Method | Remediation |
|-----------|-------------|-------------|
| Marketplace not registered | Check `known_marketplaces.json` for `installLocation` | `claude plugin marketplace add <url>` |
| Marketplace stale (`alwaysUpdate`) | Always (no check — unconditional on every session) | `claude plugin marketplace update <name>` |

### Plugin

| Condition | Check Method | Remediation |
|-----------|-------------|-------------|
| Plugin not installed | Check installed plugins registry | Install plugin at declared scope |
| Plugin installed but unwanted | Check installed plugins registry | Uninstall plugin |
| Plugin out of date | `git ls-remote` vs cached commit SHA | Update plugin at declared scope |
| Plugin at wrong scope | Compare installed scope vs declared `scope` in manifest | Uninstall from current scope, reinstall at declared scope |

## Manual Operations (Blocking Conditions)

All manual operations represent a blocking condition where auto-configuration cannot complete without user intervention. These generate fix-all directives via the messaging protocol.

| Condition | Check Method | Remediation |
|-----------|-------------|-------------|
| Config information missing and can't be auto-detected | Check config file for required fields | Ask user for information, write to config file |
| External app requires config change and/or restart | Modification applied that requires restart | User restarts external application, types `fixed` |
| Claude Code requires config change and/or restart | Modification applied that requires restart | User restarts Claude Code |

## Throttling

Checks can be throttled to avoid redundant work.

- **Content-hash throttling** computes a hash of input manifests and skips re-execution when the hash matches a stored value — re-runs only when declarations change.
- **Time-based throttling** records a timestamp and skips checks within a cooldown window — useful for network operations (e.g., `git ls-remote`) where the cost is latency rather than correctness.

Both can be combined: time-throttle the remote check, content-hash the local setup.

## Personal Config (No Plugin Needed)

The hybrid model enables a "personal config" use case: a user who just wants to declare their preferred tools and environment without creating a plugin. The bootstrap engine can process a `bootstrap.json` at a well-known user-level location (e.g. `~/.claude/plugins/data/plugins-kit/bootstrap/user-bootstrap.json`):

```json
{
  "tools": [
    {"name": "uv"},
    {"name": "git"},
    {"name": "gh"}
  ],
  "path_entries": ["~/.local/bin"]
}
```

This gives a no-code path for the most common bootstrap need: "make sure my tools are installed on every machine." No plugin directory, no manifest, no script — just a JSON file declaring what you need.

## Testing

All bootstrap modules have automated tests at the repo level in `tests/bootstrap/`. Tests use pytest and run via `uv run --extra dev pytest -v` from the repo root.

**Structure**: Library modules get unit tests with direct imports. The engine gets integration tests that invoke `bootstrap_engine.py` as a subprocess (matching how the bash wrapper calls it). Shared fixtures in `tests/conftest.py` provide temporary data directories, manifest builders, and path helpers.

**Why repo-level**: The bootstrap engine is cross-cutting infrastructure that will orchestrate multiple plugins. Tests need to span plugin boundaries (e.g. verifying engine+plugin manifest interactions), which doesn't fit inside any single plugin's directory.

**Standard**: Every new library module or engine capability must have corresponding tests before the milestone is considered complete. See [MILESTONES.md](./MILESTONES.md) for per-milestone test deliverables.

## Related Documentation

- [docs/bootstrapping-architecture.md](../../docs/bootstrapping-architecture.md) — Broader bootstrapping overview covering both the session bootstrap layer (this engine) and the UE script bootstrap layer

## Case Studies

- [test-plugin](./case-studies/test-plugin.md) — Minimal reference implementation exercising core bootstrap operations
- [update01/bootstrap](./case-studies/update01-bootstrap.md) — Marketplace sync and plugin cache refresh
- [unreal-kit](./case-studies/unreal-kit.md) — Game development plugin with system tools, venv, config discovery, and external app dependencies
