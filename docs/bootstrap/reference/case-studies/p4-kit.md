# Case Study: p4-kit

P4 multi-agent code review plugin. The current bootstrap is **tool-checks plus a legacy-cleanup script** — no venv, no git deps, no per-project config, no autodetect. All review logic happens at runtime via Claude subagents launched by the skill prose; `p4` itself resolves P4PORT/P4USER from its own registry/P4CONFIG/P4ENVIRO cascade, so the plugin never needs to persist or read those values.

## Current Operations

### Automatable

| Category | Condition | Check Method | Remediation |
|----------|-----------|-------------|-------------|
| Tool | `p4` not installed | `command -v p4` | Platform-specific (`brew install --cask perforce` on macOS, manual download on Windows/Ubuntu) |
| Tool | `uv` not installed | `command -v uv` | Platform install command |
| Tool | `claude` not installed | `command -v claude` | Manual (Claude Code CLI) |
| Legacy cleanup | `<project>/.local-data/p4-kit/config.yaml` or `<project>/.claude/p4-kit.yaml` left over from pre-0.9.2 releases | `script` primitive | `scripts/cleanup_legacy_config.py:cleanup` deletes the file and prunes the now-empty parent dir, silent no-op when nothing is present. |

### Manual

None. The plugin no longer asks for P4PORT/P4USER — when a `p4` command run by `prepare_review.py` can't reach the server, the native p4 error surfaces verbatim and the user resolves it through standard p4 mechanisms (`p4 set`, `p4 login`, etc.).

## Manifest (`bootstrap.json`)

Declarative tool checks plus a single cleanup script:

```json
{
  "tools": [
    { "name": "p4", "install": { "macos": "brew install --cask perforce", "windows": "manual", "ubuntu": "manual" } },
    { "name": "uv", "install": { "macos": "...", "windows": "...", "ubuntu": "..." } },
    { "name": "claude", "install": { "macos": "manual", "windows": "manual", "ubuntu": "manual" } }
  ],
  "script": {
    "path": "scripts/cleanup_legacy_config.py",
    "entry_point": "cleanup"
  }
}
```

## Library Usage

| Source | Operation | Primitive |
|--------|-----------|-----------|
| Manifest | Verify `p4`, `uv`, `claude` installed | `check_tool()` |
| Manifest | Remove legacy per-project p4-kit config files | `script` |

## Observations

- **Zero persistent state** — no venv, no cloned git deps, no per-machine config under `~/.claude/plugins/data/plugins-kit/p4-kit/`, no per-project config file. The plugin runs entirely off `p4`'s own configuration and the CLAUDE.md files the skill walks at review time.
- **Runtime is in-conversation** — the skill (`local-code-review`) launches Claude subagents via the `Agent` tool with model overrides (`sonnet`, `opus`). No external Python orchestrator, no external LLM API keys.
- **The only Python in the plugin** is `scripts/prepare_review.py` (called by the skill at runtime, stdlib-only, runs via `uv run --no-project python`) and `scripts/cleanup_legacy_config.py` (one-shot legacy cleanup, called by the bootstrap engine).
- Earlier iterations had a venv, a `code-review-research` git dep, and a `run-review.py` orchestrator that called external LLMs (codex/gemini/openrouter). All removed in 0.7.0. The `project_config` autodetect that wrote `<project>/.local-data/p4-kit/config.yaml` (and the pre-migration `<project>/.claude/p4-kit.yaml`) was removed in 0.9.2 — nothing ever consumed those files and they polluted every cwd Claude was launched in, including ephemeral eval tmp dirs.
