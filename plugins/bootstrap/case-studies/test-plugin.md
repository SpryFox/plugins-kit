# Case Study: test-plugin

Minimal reference implementation. Exercises system tool checks, venv creation, git dependency fetching, and config verification — the core bootstrap operations.

## Current Operations

### Automatable

| Category | Condition | Check Method | Remediation |
|----------|-----------|-------------|-------------|
| Tool | `git` not installed | `command -v git` | Platform-specific install command |
| Library/Data | Python venv missing or broken | Check dir → binary → `import yaml` | `uv sync` from `pyproject.toml` |
| Library/Data | Git dependency not cloned or out of date | Check `~/.claude/plugins/data/test-plugin/github/Hello-World` exists | `git clone` (sparse checkout of `README` from `octocat/Hello-World`) |

### Manual

| Condition | Check Method | Remediation |
|-----------|-------------|-------------|
| Plugin config incomplete | `setup.py --check` fails | User invokes test-setup skill to configure interactively |

## Manifest (`bootstrap.json`)

The three automatable operations are fully expressed as manifest entries — no script code needed for these:

```json
{
  "tools": [
    {"name": "git"}
  ],
  "venv": {
    "check_imports": ["yaml"]
  },
  "git_deps": [
    {
      "url": "https://github.com/octocat/Hello-World",
      "branch": "master",
      "sparse_paths": ["README"]
    }
  ]
}
```

## Bootstrap Script (Pseudocode)

The script handles only the custom config check — everything else is covered by the manifest:

```python
def bootstrap(ctx):
    """test-plugin bootstrap script — custom logic only.

    Standard operations (git tool, venv, git dep) are handled
    by the manifest. This script only checks plugin-specific config.
    """

    config = ctx.read_config()  # reads data_dir/bootstrap-config.json
    if not config.get("setup_complete"):
        ctx.add_fixall(
            agent_msg="Run the test-setup skill to configure this plugin interactively.",
            user_msg="test-plugin needs configuration. Type fix-all to set up."
        )
```

## Library Usage

| Source | Operation | Primitive |
|--------|-----------|-----------|
| Manifest | Verify `git` is installed | `check_tool()` |
| Manifest | Create/validate venv with `yaml` package | `ensure_venv()` |
| Manifest | Sparse clone of `octocat/Hello-World` | `ensure_git_dep()` |
| Script | Check plugin config completion | Custom (reads JSON field) |

## Observations

- Simplest possible bootstrap — one tool, one venv, one git dep, one config check
- Good first target for implementation since it exercises all four library categories
- Three of four operations need zero code — just manifest entries
- The config check is the only custom logic, demonstrating the hybrid model: manifest for standard ops, script for the rest
- If a `config_required` manifest field were added later, this plugin could become pure manifest with no script at all
