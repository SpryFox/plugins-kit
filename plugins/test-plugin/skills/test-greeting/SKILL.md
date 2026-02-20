---
_schema_version: 1
name: test-greeting
description: Generate a personalized greeting using test-plugin configuration
---

# Test Greeting

## Purpose

Demonstrate consuming plugin configuration by generating a personalized greeting.

## Usage

Read the config file at `~/.claude/plugins/data/test-plugin/config.yaml` and produce:

> Hello, {GREETING_NAME}! Your favorite color is {FAVORITE_COLOR}.

## Config Format

The config file is simple `KEY: "value"` YAML:

```yaml
GREETING_NAME: "Alice"
FAVORITE_COLOR: "green"
```

## If Config Is Missing

If `~/.claude/plugins/data/test-plugin/config.yaml` does not exist or is incomplete, suggest invoking the **test-setup** skill to configure the plugin first.

Check config status:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/setup.py --check --data-dir ~/.claude/plugins/data/test-plugin
```
