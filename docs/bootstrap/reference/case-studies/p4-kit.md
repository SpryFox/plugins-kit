# Case Study: p4-kit

P4 multi-agent code review plugin. The current bootstrap is **manifest-only with autodetect** — no venv, no git deps, no script-driven remediation. All review logic happens at runtime via Claude subagents launched by the skill prose.

## Current Operations

### Automatable

| Category | Condition | Check Method | Remediation |
|----------|-----------|-------------|-------------|
| Tool | `p4` not installed | `command -v p4` | Platform-specific (`brew install --cask perforce` on macOS, manual download on Windows/Ubuntu) |
| Tool | `uv` not installed | `command -v uv` | Platform install command |
| Tool | `claude` not installed | `command -v claude` | Manual (Claude Code CLI) |
| Project config | `P4PORT`/`P4USER` missing in `<project>/.claude/p4-kit.yaml` | `project_config` primitive | Run `custom_bootstrap.py autodetect` (reads `p4 set` and env vars). If autodetect finds the values, the engine writes them silently; otherwise the field becomes a fix-all item that asks the user. |

### Manual

None. Configuration is fully autodetected from the user's existing `p4 set` output or `$P4PORT`/`$P4USER` environment variables. Only if both sources are empty does the engine prompt the user via fix-all.

## Manifest (`bootstrap.json`)

The entire bootstrap is declarative — no script-driven `bootstrap()` function:

```json
{
  "tools": [
    { "name": "p4", "install": { "macos": "brew install --cask perforce", "windows": "manual", "ubuntu": "manual" } },
    { "name": "uv", "install": { "macos": "...", "windows": "...", "ubuntu": "..." } },
    { "name": "claude", "install": { "macos": "manual", "windows": "manual", "ubuntu": "manual" } }
  ],
  "project_config": {
    "file": ".claude/p4-kit.yaml",
    "required_fields": {
      "P4PORT": { "user_msg": "...", "agent_msg": "..." },
      "P4USER": { "user_msg": "...", "agent_msg": "..." }
    },
    "autodetect": "custom_bootstrap.py autodetect"
  }
}
```

## Autodetect (`custom_bootstrap.py`)

The only Python the bootstrap engine invokes:

```python
def autodetect():
    """Discover P4PORT/P4USER from `p4 set` (handling source annotations) or env vars."""
    # Returns {"P4PORT": ..., "P4USER": ...} or None
```

Used by the `project_config` primitive to fill in missing fields without asking the user.

## Library Usage

| Source | Operation | Primitive |
|--------|-----------|-----------|
| Manifest | Verify `p4`, `uv`, `claude` installed | `check_tool()` |
| Manifest | Verify per-project config has `P4PORT`/`P4USER` | `project_config` |
| Script | Discover `P4PORT`/`P4USER` for autodetect | `custom_bootstrap.py autodetect()` |

## Observations

- **Zero data-dir state** — no venv, no cloned git deps, no per-machine config under `~/.claude/plugins/data/plugins-kit/p4-kit/`. The plugin's only persistent state is the per-project `<project>/.claude/p4-kit.yaml`.
- **Runtime is in-conversation** — the skill (`local-code-review`) launches Claude subagents via the `Agent` tool with model overrides (`sonnet`, `opus`). No external Python orchestrator, no external LLM API keys.
- **The only Python in the plugin** is `custom_bootstrap.py` (autodetect, called by the engine) and `scripts/prepare_review.py` (called by the skill at runtime, stdlib-only, runs via `uv run --no-project python`).
- Earlier iterations had a venv, a `code-review-research` git dep, and a `run-review.py` orchestrator that called external LLMs (codex/gemini/openrouter). All removed in 0.7.0 — the multi-agent design subsumes them.
