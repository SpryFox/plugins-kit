---
_schema_version: 1
name: test-setup
description: Interactive configuration setup for test-plugin — guides through field collection and writes config
---

# Test Plugin Setup

## Purpose

Guide the user through configuring test-plugin by collecting required field values and writing them to the plugin's config file.

## Setup Flow

### 1. Describe available fields

Run the setup script to see what fields exist and their current values:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/setup.py --describe --data-dir ~/.claude/plugins/data/test-plugin
```

### 2. Collect values from user

For each field shown by `--describe`, ask the user what value they want. Show the default and current value so they can accept defaults or customize.

Fields:
- **GREETING_NAME** — Name to use in the greeting (default: "World")
- **FAVORITE_COLOR** — Your favorite color (default: "blue")

### 3. Apply configuration

Write the collected values using `--apply`:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/setup.py --apply --data-dir ~/.claude/plugins/data/test-plugin --set GREETING_NAME=Alice --set FAVORITE_COLOR=green
```

### 4. Verify

Confirm the config is complete:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/setup.py --check --data-dir ~/.claude/plugins/data/test-plugin
```

Exit code 0 means setup is complete.

## Alternative: Initialize with defaults

To accept all defaults without prompting:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/setup.py --init-defaults --data-dir ~/.claude/plugins/data/test-plugin --source ${CLAUDE_PLUGIN_ROOT}/defaults
```

## Config Location

Config is stored at `~/.claude/plugins/data/test-plugin/config.yaml` — a simple `KEY: "value"` YAML file.
