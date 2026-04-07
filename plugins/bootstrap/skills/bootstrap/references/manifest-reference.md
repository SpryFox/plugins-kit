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
    {"ref": "plugins-kit:unreal-kit", "enabled": true}
  ],
  "project_venv": {
    "extras": ["dev"],
    "check_imports": ["pytest"]
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
