# Case Study: unreal-kit

Game development plugin with the most complex bootstrap — system tools, venv, config discovery, external app dependencies, and PyPI package extraction.

## Current Operations

### Automatable

| Category | Condition | Check Method | Remediation |
|----------|-----------|-------------|-------------|
| Configuration | `~/.local/bin` not in PATH | Read shell RC files / query OS env var | Modify persistent PATH (platform-specific) |
| Configuration | UE `bRemoteExecution` not enabled | Read `DefaultEngine.ini` and `UserEngine.ini` | Write `bRemoteExecution=True` to `UserEngine.ini` |
| Configuration | UE `bIsDeveloperMode` not enabled | Read `DefaultEngine.ini` and `UserEngine.ini` | Write `bIsDeveloperMode=True` to `UserEngine.ini` |
| Tool | `uv` not installed | `command -v uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Tool | `git` not installed | `command -v git` | Platform-specific install command |
| Tool | `curl` not installed (Windows/Ubuntu) | `command -v curl` | `winget install cURL.cURL` / `sudo apt install -y curl` |
| Library/Data | Python venv missing or broken | Check dir → binary → `import upyrc; import yaml` | `uv sync` from `pyproject.toml` |
| Library/Data | PyPI package missing (UE stubs) | Check `stubs/unreal.py` exists | Download `unreal-stub` from PyPI, extract from wheel |

### Manual

| Condition | Check Method | Remediation |
|-----------|-------------|-------------|
| UE project path unknown (auto-detect failed) | Config check + auto-detect from CWD both fail | Ask user for `.uproject` path, write to config |
| UE Editor settings written but not active | Settings just written to `UserEngine.ini` | User restarts UE Editor, types `fixed` |
| Project-specific stubs unavailable | `<project>/Intermediate/PythonStub/unreal.py` doesn't exist | User enables Developer Mode, restarts editor, types `fixed` |

## Manifest (`bootstrap.json`)

Standard operations are declared in the manifest — the engine handles these without any script code:

```json
{
  "path_entries": ["~/.local/bin"],
  "tools": [
    {"name": "uv", "install": "curl -LsSf https://astral.sh/uv/install.sh | sh"},
    {"name": "git"},
    {"name": "curl", "platforms": ["windows", "linux"]}
  ],
  "venv": {
    "check_imports": ["upyrc", "yaml"]
  },
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
  ]
}
```

Note: `ini_settings` uses `${uproject_dir}` which the engine resolves from the plugin's config. If the config doesn't have this value yet (first run), the engine skips ini_settings and the script handles discovery.

## Bootstrap Script (Pseudocode)

The script handles only UE-specific custom logic — everything standard is in the manifest:

```python
def bootstrap(ctx):
    """unreal-kit bootstrap script — custom logic only.

    Standard operations (tools, PATH, venv, ini settings, PyPI stubs)
    are handled by the manifest. This script handles:
    - UE project discovery (domain-specific heuristic)
    - Project-specific stub copy (conditional on project state)
    """

    # --- UE project discovery (custom) ---
    config = ctx.read_config()
    uproject = config.get("uproject")

    if not uproject:
        # Try auto-detection from CWD
        uproject = discover_uproject(Path.cwd())
        if uproject:
            config["uproject"] = str(uproject)
            config["engine_dir"] = str(discover_engine(uproject))
            ctx.write_config(config)
        else:
            ctx.add_fixall(
                agent_msg=(
                    f"Ask the user where the .uproject file is, "
                    f"then write that information to {ctx.data_dir / 'bootstrap-config.json'} "
                    f"as the value of the 'uproject' field. "
                    f"Also discover the engine directory and write it as 'engine_dir'."
                ),
                user_msg="No UE project detected. Type fix-all to configure."
            )
            return  # can't proceed without project path

    # --- Project-specific stubs (optional upgrade) ---
    project_stubs = Path(uproject).parent / "Intermediate" / "PythonStub" / "unreal.py"
    stubs_path = ctx.plugin_path / "skills" / "ue-python-api" / "stubs" / "unreal.py"
    if project_stubs.exists():
        import shutil
        shutil.copy2(project_stubs, stubs_path)
        ctx.add_info("Copied project-specific UE stubs (richer than PyPI stubs)")
```

## Library Usage

| Source | Operation | Primitive |
|--------|-----------|-----------|
| Manifest | Add `~/.local/bin` to PATH | `ensure_path_entry()` |
| Manifest | Verify `uv`, `git`, `curl` installed | `check_tool()` |
| Manifest | Create/validate venv with `upyrc`, `yaml` | `ensure_venv()` |
| Manifest | Write UE editor settings to `UserEngine.ini` | `ensure_ini_setting()` |
| Manifest | Download and extract `unreal-stub` wheel | `ensure_pypi_package()` |
| Script | Discover `.uproject` from CWD | Custom (`discover_uproject()`) |
| Script | Discover engine directory | Custom (`discover_engine()`) |
| Script | Copy project-specific stubs | Custom (`shutil.copy2`) |

## Observations

- Most complex bootstrap of the three — but the manifest handles the bulk of operations, leaving the script focused on domain-specific discovery
- The hybrid split is clean: manifest for "ensure X exists," script for "figure out where X is"
- Custom logic is limited to UE-specific discovery (2 functions) and a conditional file copy
- Three distinct fix-all/fixed scenarios:
  1. **fix-all**: Missing tools → install commands (manifest-driven)
  2. **fix-all**: Unknown project path → ask user (script-driven)
  3. **fixed**: Editor settings written → user restarts editor (manifest-driven, with fixed directive)
- The `ini_settings` manifest entry depends on `${uproject_dir}` — the engine gracefully skips entries with unresolved variables, so the manifest and script cooperate: first run discovers the project (script), subsequent runs apply ini settings (manifest)
- Stubs have two tiers: PyPI (manifest, automatic) and project-specific (script, conditional). The bootstrap handles both, preferring project-specific when available
