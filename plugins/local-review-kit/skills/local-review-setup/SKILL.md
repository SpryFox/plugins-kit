---
_schema_version: 1
name: local-review-setup
description: Interactive configuration setup for local-review-kit — guides through field collection and writes config
---

# Local Review Kit Setup

## Purpose

Guide the user through configuring local-review-kit by collecting required field values and writing them to the plugin's config file.

## Setup Flow

### 1. Describe available fields

Run the setup script to see what fields exist and their current values:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/setup.py --describe --data-dir ~/.claude/plugins/data/local-review-kit
```

### 2. Collect values from user

For each field shown by `--describe`, ask the user what value they want. Show the default and current value so they can accept defaults or customize.

Fields:
- **OPENAI_API_KEY** — OpenAI API key for OpenAI-based agents (set 'none' if not used)
- **OPENROUTER_API_KEY** — OpenRouter API key for OpenRouter-based agents (set 'none' if not used)
- **P4PORT** — Perforce server address (e.g., ssl:perforce.example.com:1666)
- **P4USER** — Perforce username
- **DEFAULT_AGENT** — Default agent for reviews (default: claude-opus)

### 3. Apply configuration

Write the collected values using `--apply`:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/setup.py --apply --data-dir ~/.claude/plugins/data/local-review-kit --set OPENAI_API_KEY=sk-... --set P4PORT=ssl:perforce:1666 --set P4USER=jdoe --set DEFAULT_AGENT=claude-haiku
```

Multiple `--set KEY=VALUE` pairs can be passed in one call.

### 4. Verify

Confirm the config is complete:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/setup.py --check --data-dir ~/.claude/plugins/data/local-review-kit
```

Exit code 0 means setup is complete.

## Alternative: Initialize with defaults

To accept all defaults without prompting:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/setup.py --init-defaults --data-dir ~/.claude/plugins/data/local-review-kit --source ${CLAUDE_PLUGIN_ROOT}/defaults
```

## Config Location

Config is stored at `~/.claude/plugins/data/local-review-kit/config.yaml` — a simple `KEY: "value"` YAML file.
