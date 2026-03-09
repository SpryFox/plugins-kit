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

If `~/.claude/plugins/data/test-plugin/config.yaml` does not exist or is incomplete, the bootstrap engine will create it automatically with default values on the next session start.
