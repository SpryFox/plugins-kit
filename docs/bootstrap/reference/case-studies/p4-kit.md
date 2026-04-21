# Case Study: p4-kit

P4/Swarm AI code review plugin with a mid-complexity bootstrap — system tools, venv, git dependency (sparse checkout), and config verification.

## Current Operations

### Automatable

| Category | Condition | Check Method | Remediation |
|----------|-----------|-------------|-------------|
| Tool | `p4` not installed | `command -v p4` | Platform-specific (`brew install --cask perforce` on macOS, manual download on Windows/Ubuntu) |
| Tool | `uv` not installed | `command -v uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Library/Data | Python venv missing or broken | Check dir -> binary -> packages importable | `uv sync` from `pyproject.toml` |
| Library/Data | Git dep not cloned or out of date | Check `code-review-research` exists | `git clone` (sparse checkout of `agents/` from `kitaekatt/code-review-research`) |

### Manual

| Condition | Check Method | Remediation |
|-----------|-------------|-------------|
| Config incomplete (API keys, P4PORT, P4USER, DEFAULT_AGENT) | `setup.py --check` fails | User invokes local-code-review-setup skill to configure interactively |

## Manifest (`bootstrap.json`)

Standard operations are declared in the manifest — the engine handles these without any script code:

```json
{
  "tools": [
    {
      "name": "p4",
      "install": {
        "macos": "brew install --cask perforce",
        "windows": "manual",
        "ubuntu": "manual"
      }
    },
    {
      "name": "uv",
      "install": "curl -LsSf https://astral.sh/uv/install.sh | sh"
    }
  ],
  "venv": {
    "check_imports": []
  },
  "git_deps": [
    {
      "url": "https://github.com/kitaekatt/code-review-research",
      "branch": "main",
      "sparse_paths": ["agents/"]
    }
  ]
}
```

## Bootstrap Script (Pseudocode)

The script handles only the custom config check — everything else is covered by the manifest:

```python
def bootstrap(ctx):
    """p4-kit bootstrap script — custom logic only.

    Standard operations (tools, venv, git dep) are handled
    by the manifest. This script only checks plugin-specific config.
    """

    result = run_config_check(ctx.plugin_path / "scripts" / "setup.py")
    if not result.success:
        ctx.add_fixall(
            agent_msg="Run the local-code-review-setup skill to configure this plugin interactively.",
            user_msg="p4-kit needs configuration. Type fix-all to set up."
        )
```

## Library Usage

| Source | Operation | Primitive |
|--------|-----------|-----------|
| Manifest | Verify `p4` is installed | `check_tool()` |
| Manifest | Verify `uv` is installed | `check_tool()` |
| Manifest | Create/validate venv | `ensure_venv()` |
| Manifest | Sparse clone of `kitaekatt/code-review-research` | `ensure_git_dep()` |
| Script | Check plugin config completion | Custom (runs `setup.py --check`) |

## Observations

- Mid-complexity bootstrap — two tools (one with platform-specific install), one venv, one git dep, one config check
- Good second target after test-plugin: exercises the same four categories but with real-world dependencies
- Four of five operations need zero code — just manifest entries
- The config check is the only custom logic, same hybrid pattern as test-plugin
- Platform-specific tool installs (`p4` uses `brew` on macOS, manual on Windows/Ubuntu) exercise the engine's per-OS install support already validated by test-plugin
- The `venv.check_imports` is empty because p4-kit's venv packages don't need import validation — presence of the venv itself is sufficient
- Current hand-rolled bootstrap is ~600 lines of bash across 5 sessionstart scripts, a stop hook, and a shared lib — all replaced by the manifest + a short script
