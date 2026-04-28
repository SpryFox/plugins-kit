---
_schema_version: 1
name: test-greeting
skill-type: technique-skill
description: Use when the user invokes /test-greeting to verify bootstrap config setup. Do NOT use for production work; this is a test fixture.
disable-model-invocation: true
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
