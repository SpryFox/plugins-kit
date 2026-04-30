# Bootstrap Manifest Reference (`bootstrap.json`)

A declarative configuration file covering automatable operations. The engine reads the manifest and calls library primitives directly — no plugin code needed.

## Schema

```json
{
  "tools": [
    {"name": "git"},
    {"name": "uv", "install": {"darwin": "curl -LsSf https://astral.sh/uv/install.sh | sh", "linux": "curl -LsSf https://astral.sh/uv/install.sh | sh", "windows": "powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\""}},
    {"name": "node", "installPath": "~/.local/share/node", "install": {"macos": "brew install node"}}
  ],
  "path_entries": ["~/.local/bin"],
  "python_stub_check": {
    "good_python_dir": "~/.local/share/python-standalone/python",
    "stub_markers": ["WindowsApps"],
    "script_output_dir": "~/Desktop"
  },
  "venv": {
    "check_imports": ["yaml", "upyrc"]
  },
  "git_deps": [
    {
      "url": "https://github.com/octocat/Hello-World",
      "branch": "master",
      "sparse_paths": ["README"],
      "commit": "abc1234567890abcdef1234567890abcdef123456"
    }
  ],
  "sync_to_data": [
    {"src": "lib", "dst": "lib"}
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
    {"ref": "plugins-kit:unreal-kit", "enabled": true},
    {"ref": "plugins-kit:bootstrap", "min_version": "0.9.1"}
  ],
  "project_venv": {
    "extras": ["dev"],
    "check_imports": ["pytest"]
  },
  "project_config": {
    "file": ".local-data/p4-kit/config.yaml",
    "legacy_file": ".claude/p4-kit.yaml",
    "required_fields": {
      "P4PORT": {"user_msg": "Perforce server address", "agent_msg": "Ask the user for P4PORT and write it to {config_path}"},
      "P4USER": {"user_msg": "Perforce username", "agent_msg": "Ask the user for P4USER and write it to {config_path}"},
      "DEFAULT_AGENT": {"user_msg": "Default review agent", "agent_msg": "Ask the user for DEFAULT_AGENT", "default": "claude-opus"}
    },
    "autodetect": "custom_bootstrap.py autodetect"
  },
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

Every field is optional — include only what the plugin needs.

## `venv` — Per-Plugin Python Environment

A plugin declares a `venv` section to request a bootstrap-managed Python environment. The engine creates and syncs `<plugin_data_dir>/.venv` from the plugin's `pyproject.toml` (via `uv sync --project <plugin_root>`), then verifies each listed import works.

```json
{
  "venv": {
    "check_imports": ["yaml", "upyrc"]
  }
}
```

### `<PLUGIN>_VENV` environment variable export

When `CLAUDE_ENV_FILE` is set (always true under SessionStart hooks), a successful venv check also appends an export line of the form:

```sh
export <PLUGIN_NAME_UPPER>_VENV=<absolute path to venv python>
```

`<PLUGIN_NAME_UPPER>` is the plugin manifest name uppercased with hyphens replaced by underscores. Examples:

```sh
export UNREAL_KIT_VENV=/Users/christina/.claude/plugins/data/plugins-kit/unreal-kit/.venv/bin/python
export BOOTSTRAP_VENV=/Users/christina/.claude/plugins/data/plugins-kit/bootstrap/.venv/bin/python
```

**Consumer pattern** — scripts re-exec themselves under the plugin's venv without reconstructing bootstrap's data-dir layout:

```python
import os, sys
from pathlib import Path

_venv = os.environ.get("UNREAL_KIT_VENV")
if not _venv:
    sys.stderr.write("ERROR: UNREAL_KIT_VENV not set. Is bootstrap running?\n")
    sys.exit(1)
if Path(sys.executable).resolve() != Path(_venv).resolve():
    os.execv(_venv, [_venv] + sys.argv)
```

**Reach**: Exports in `CLAUDE_ENV_FILE` are sourced by Claude Code before every subsequent Bash tool invocation. They do NOT automatically propagate to hook script invocations — hook scripts that need the venv must either re-derive the path or source `$CLAUDE_ENV_FILE` themselves. For the common case (scripts called via Bash or re-exec'd via `os.execv`), the variable is always set.

**Fail-fast semantics**: if bootstrap cannot create the venv, no export line is written. Consumer scripts then error out on the unset var rather than re-exec'ing an invalid interpreter path.

## Variable Expansion

Variable references are expanded by the engine from plugin context and config:

| Variable | Source |
|----------|--------|
| `${plugin_root}` | Plugin's install path |
| `${data_dir}` | Plugin's data directory |
| `${uproject_dir}` | From plugin config (if applicable) |

## Tool `installPath`

The optional `installPath` field on a tool entry tells the engine where the tool binary lives (or will live after install). This solves the chicken-and-egg problem where a tool is installed to a known directory that isn't in PATH yet at check time.

```json
{"name": "node", "installPath": "~/.local/share/node", "install": {"windows": "..."}}
```

- Supports `~` expansion
- The engine checks `<installPath>/<name>` (and `<installPath>/<name>.exe` on Windows) before falling back to `shutil.which()`
- The same `installPath` is used for the recheck after install

## `self_setup.python_stub_check`

A Windows-only check that detects Microsoft Store Python stubs (or any other shadowing `python.exe`) sitting in front of the bootstrap-installed standalone Python on PATH. When a stub is detected, bootstrap writes a self-elevating `fix_python_path.bat` script to the user's Desktop and surfaces a friendly fix-all message instructing the user to run it as administrator. The check is a no-op on non-Windows and on Windows machines whose first `python.exe` is already the standalone one.

This field lives only under `self_setup` (in `defaults/config.json` for the bootstrap plugin) — it is not a per-plugin manifest entry.

| Key | Default | Description |
|-----|---------|-------------|
| `good_python_dir` | `~/.local/share/python-standalone/python` | Directory that should win on PATH. The check passes when the first `python.exe` resolved by `shutil.which` lives here. |
| `stub_markers` | `["WindowsApps"]` | Substrings that identify a shadowing stub. If the first `python.exe` on PATH contains any of these (case-insensitive), the check fails and a remediation script is written. |
| `script_output_dir` | `~/Desktop` | Where to write `fix_python_path.bat`. Created if missing. The script is overwritten on every run so template updates land. |

The fix script self-elevates via UAC (`powershell Start-Process -Verb RunAs`), prepends `good_python_dir` to the **System** PATH (HKLM Environment), and is idempotent — re-running it after the fix is in place is a no-op. Modifying System PATH requires administrator privileges, which is why the engine cannot do this itself.

## `project_config` Section

A per-project config file (under `<cwd>/.local-data/<plugin>/config.yaml`) discovered or populated by an autodetect script. Runs before the `config` section so discovered values can be synced into the data-dir config. If autodetect returns `None` and the file is absent, downstream project-scoped phases (e.g. `ini_settings`) are skipped for that plugin.

```json
{
  "project_config": {
    "file": ".local-data/p4-kit/config.yaml",
    "legacy_file": ".claude/p4-kit.yaml",
    "required_fields": {
      "P4PORT": {"user_msg": "Perforce server", "agent_msg": "Ask for P4PORT, write to {config_path}"},
      "DEFAULT_AGENT": {"user_msg": "Review agent", "agent_msg": "Ask for DEFAULT_AGENT", "default": "claude-opus"}
    },
    "autodetect": "custom_bootstrap.py autodetect"
  }
}
```

### `legacy_file` — one-shot path migration

If the manifest declares `legacy_file`, the engine checks whether `<cwd>/<legacy_file>` exists at session start. If it does and `<cwd>/<file>` does not, the engine moves the file to the new path (creating parent dirs as needed) and emits a `project config: migrated <old> -> <new>` action entry. The downstream load/autodetect/required-fields flow then runs against the new path. The migration is idempotent — once the file lives at the new path, subsequent sessions see the legacy file as absent and skip the move.

Use `legacy_file` only when an existing path is being relocated (e.g. moving project config out of `.claude/` and into `.local-data/`); it is not a general-purpose alias.

### `required_fields` — two forms

Both forms are supported; the dict form is preferred for new plugins.

**Dict form** (preferred) — mirrors `config.required_fields`:

| Key | Required? | Description |
|-----|-----------|-------------|
| `user_msg` | Yes (for fix-all) | User-facing description shown when the field is missing |
| `agent_msg` | Yes (for fix-all) | Instructions to the agent. `{config_path}` is expanded to the absolute per-project file path |
| `default` | No | If set, used when the field is absent from both the file and autodetect output. Never overrides an already-populated value |

**String-list form** (legacy) — a flat list of field names. Fields populated by autodetect are synced to the data-dir config; missing fields are left to the separate `config` section for fix-all handling.

### Defaulting behavior (dict form)

1. Autodetect runs (if declared) and contributes any fields it discovers.
2. For any declared field still missing, if a `default` is set, the engine writes it to the project file and logs a `project config: applied defaults [...]` action entry (never silent — see "Every check must log its outcome" in engine-internals).
3. Any field that is still missing **and** has no default becomes a fix-all entry using its `user_msg`/`agent_msg`. The `type` on the failure record is `project_config`.
4. Final values are synced to the plugin's data-dir `config.yaml` so host-side tools can read a single location.

### When to use `project_config` vs `config`

- **`project_config`** holds per-project values that are machine- or developer-specific (the `.uproject` path on this developer's box, this developer's Perforce username), so they live under `<project>/.local-data/<plugin>/config.yaml` and are gitignored. Good for: project-scoped identifiers each developer fills in for themselves, and any per-project default the user may want to override (e.g. `DEFAULT_AGENT`).
- **`config`** holds machine-global values that don't belong in version control (API keys, local install paths). Lives in `~/.claude/plugins/data/<plugin>/config.yaml`.
- The razor: if it should be checked into source control, it goes in `<project>/.claude/`. If it shouldn't, it goes in `<project>/.local-data/<plugin>/` (project-scoped) or `~/.claude/plugins/data/<plugin>/` (user-scoped).

Values set in `project_config` are automatically mirrored into the data-dir config after the project_config phase, so downstream code that reads the data-dir config (e.g. for simple getenv-style lookups) works unchanged.

## `plugins` Entry Fields

Each entry in the `plugins` array declares a plugin the engine should ensure is installed and enabled.

| Field | Required? | Description |
|-------|-----------|-------------|
| `ref` | Yes | Plugin reference in `marketplace:plugin` format |
| `enabled` | No (default `true`) | If `false`, the engine disables the plugin |
| `scope` | No (default `"user"`) | Installation scope (`user` or `project`) |
| `min_version` | No | Minimum required installed version — see below |

### `min_version`

Declares that the installed plugin must be at least this version. When the constraint is not satisfied, the engine runs `claude plugin update <ref>` and rechecks. If the update succeeds and the installed version now satisfies the constraint, processing continues. If the constraint remains unsatisfied (e.g. the marketplace does not yet have a version new enough), the engine records a failure that surfaces as a fix-all item.

**Output examples**:
```
plugin plugins-kit:bootstrap: installed 0.8.3 < required 0.9.1, running `claude plugin update bootstrap@plugins-kit`
plugin plugins-kit:bootstrap: updated to 0.9.1 (satisfies >= 0.9.1)
```
```
plugin plugins-kit:bootstrap: installed 0.8.3 < required 0.9.1, update failed - <reason>
```

**Comparison semantics**: Numeric dotted versions only (e.g. `0.9.1`, `1.2.3`). Non-numeric parts coerce to 0, so pre-release suffixes like `0.9.1-rc1` are not handled reliably. If you need full specifier grammar (`~=`, `<`), file an issue — this starts as minimum-only.

**Chicken-and-egg for bootstrap itself**: A plugin may declare `plugins-kit:bootstrap` with a `min_version`. This only takes effect once an engine new enough to read the `min_version` field is already running. Older bootstrap engines ignore the field (forward-compatible). If bootstrap itself is too old to recognize the field, the constraint is silently not enforced — consumers should treat the field as advisory in that scenario.

**Layering**: `min_version` participates in the standard merge-by-identity rule (identity key `ref`). If the same plugin ref appears in multiple layers with different `min_version` values, the highest-priority layer wins (it is a scalar field, not a list).

## Script Section

The `script` field declares an optional Python module that runs after manifest processing:

```json
{
  "script": {
    "path": "scripts/bootstrap.py",
    "entry_point": "bootstrap"
  }
}
```

The engine imports the module and calls the entry point function. The script runs in-process within a try/except. See [engine-internals.md](./engine-internals.md) for details on script execution.

## Layered Config Model

The engine supports a 4-layer `bootstrap.json` model — following the same pattern as Claude Code's `settings.json` / `settings.local.json`. This lets users and projects declare bootstrap requirements without creating a plugin.

### Layer Priority

| Priority | File | Scope | Checked in? |
|----------|------|-------|-------------|
| 4 (highest) | `<project>/.claude/bootstrap.local.json` | Project-local | No (gitignored) |
| 3 | `<project>/.claude/bootstrap.json` | Project | Yes |
| 2 | `~/.claude/bootstrap.local.json` | User-local | N/A |
| 1 (lowest) | `~/.claude/bootstrap.json` | User | N/A |

### Merge Semantics

- **Arrays** (plugins, marketplaces, tools, etc.): Unioned by identity key (`ref` for plugins, `name` for marketplaces/tools). When the same identity appears in multiple layers, higher-priority layer's fields win.
- **Objects** (venv, config, project_venv, etc.): Deep-merged, higher priority wins for conflicting keys.
- **path_entries**: Simple string list union (deduplicated, order preserved).
- **Scalars**: Higher priority wins.

### Identity Keys

Each array type has an identity key used for deduplication during merge:

| Array | Identity key |
|-------|-------------|
| `tools` | `name` |
| `marketplaces` | `name` |
| `plugins` | `ref` |
| `git_deps` | `url` |
| `json_entries` | `target` |
| `ini_settings` | `file` + `section` |
| `sync_to_data` | `src` + `dst` |
| `pypi_packages` | `package` |

### Example

User-level `~/.claude/bootstrap.json` — personal tools across all projects:
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

Project-level `<project>/.claude/bootstrap.json` — project-specific requirements:
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

The engine merges these layers before processing plugin `bootstrap.json` files (step 4). Layered configs set up the ecosystem (what marketplaces and plugins to use); plugin bootstrap.json files configure individual plugins.

### Migration from user-bootstrap.json

The legacy `user-bootstrap.json` in the data dir is still processed (lowest priority) but emits a deprecation notice. Move its contents to `~/.claude/bootstrap.json`.
