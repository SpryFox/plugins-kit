# Plan: Create dippy-kit Plugin

## Context

Dippy (https://github.com/ldayton/Dippy) is an approval autopilot for Claude Code — a PreToolUse hook that auto-approves safe shell commands while blocking destructive ones. It's pure Python with zero dependencies and works from any install location.

We want to integrate Dippy into the plugins-kit marketplace so that:
- Installing the plugin installs Dippy (via bootstrap `git_deps`)
- The hook is only active when the plugin is enabled (via `hooks/hooks.json`)
- No copy of Dippy source lives in our repo — it's cloned to the data directory at runtime

## Files to Create

### 1. `plugins/dippy-kit/.claude-plugin/plugin.json`

```json
{
  "name": "dippy-kit",
  "version": "0.1.0",
  "description": "Approval autopilot for Claude Code - auto-approves safe commands, blocks destructive ones",
  "author": {
    "name": "Christina"
  },
  "keywords": ["approval", "safety", "hooks", "bash", "permissions", "auto-approve"]
}
```

### 2. `plugins/dippy-kit/bootstrap.json`

```json
{
  "git_deps": [
    {
      "url": "https://github.com/ldayton/Dippy.git",
      "branch": "main"
    }
  ]
}
```

No `tools`, `venv`, or `config` needed — Dippy has zero deps and uses its own `~/.dippy/config` discovery.

### 3. `plugins/dippy-kit/hooks/hooks.json`

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/pretooluse/dippy-hook.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/posttooluse/dippy-hook.sh"
          }
        ]
      }
    ]
  }
}
```

No `matcher` — Dippy handles Bash, MCP tools, and returns `{}` for everything else internally.

### 4. `plugins/dippy-kit/hooks/pretooluse/dippy-hook.sh`

Wrapper script that:
- Derives data directory path (same pattern as `bootstrap-display.sh`)
- Checks if Dippy clone exists; outputs `{}` if not (graceful fallback)
- Invokes `uv run python <dippy>/bin/dippy-hook` via `exec`

### 5. `plugins/dippy-kit/hooks/posttooluse/dippy-hook.sh`

Same wrapper logic. Fallback: silent `exit 0` (PostToolUse doesn't need a permission decision).

### 6. Edit `.claude-plugin/marketplace.json`

Add dippy-kit entry after the p4-kit entry (line 59):

```json
,
{
  "name": "dippy-kit",
  "description": "Approval autopilot for Claude Code - auto-approves safe commands, blocks destructive ones",
  "version": "0.1.0",
  "author": {
    "name": "Christina"
  },
  "source": "./plugins/dippy-kit",
  "category": "development"
}
```

## Key Design Decisions

1. **Git clone via `git_deps`** — Dippy repo clones to `~/.claude/plugins/data/<marketplace>/dippy-kit/github/Dippy/`. No source copy in our repo.

2. **Plugin-scoped hooks** — Hooks declared in `hooks/hooks.json` are only active when plugin is installed+enabled. Disable plugin = hooks disappear.

3. **No matcher on PreToolUse** — Dippy handles Bash + MCP tools internally, returns `{}` for non-matching tools. Slight overhead (~100ms) per non-Bash tool call but preserves full MCP rule support.

4. **Two separate wrapper scripts** — PreToolUse fallback outputs `{}` (don't block), PostToolUse fallback exits silently. Different fallback behavior justifies separate scripts.

5. **Branch tracking, no commit pin** — Track `main` for latest Dippy improvements. Can pin a commit later for stability.

## Verification

1. **Pre-commit hook**: Verify version match between `plugin.json` (0.1.0) and `marketplace.json` (0.1.0)
2. **Local test**: `claude --plugin-dir D:/Dev/plugins-kit/plugins/dippy-kit` — verify hooks load
3. **Bootstrap test**: Run engine in console mode, verify Dippy appears as git dep
4. **Graceful fallback**: Delete the Dippy clone dir, verify hook outputs `{}` and doesn't block
5. **End-to-end**: With Dippy cloned, verify `ls` gets auto-approved and `rm -rf /` gets blocked
