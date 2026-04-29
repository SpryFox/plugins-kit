---
_schema_version: 1
name: test-greeting
skill-type: technique-skill
description: Use when the user invokes /test-greeting to verify bootstrap config setup. Do NOT use for production work; this is a test fixture.
disable-model-invocation: true
---

# Test Greeting

A bootstrap-config test fixture. Reads two values from
`~/.claude/plugins/data/test-plugin/config.yaml` and renders a one-line
greeting.

```yaml
technique_skill:
  _schema_version: "1"
  trigger_model: user-only
  identity: Test fixture for verifying bootstrap config setup; produces a personalized greeting.
  scope:
    covers:
      - verifying that bootstrap config setup works end-to-end
      - the /test-greeting slash command
    excludes:
      - production work; this is a test fixture
  techniques:
    - id: greet
      name: Personalized greeting
      keywords: [test greeting, bootstrap config test, hello world skill, plugin config demo, test-greeting slash command]
      goal: Read GREETING_NAME and FAVORITE_COLOR from the config file and render a one-line greeting.
      arguments:
        - name: GREETING_NAME
          required: true
          description: Sourced from ~/.claude/plugins/data/test-plugin/config.yaml.
        - name: FAVORITE_COLOR
          required: true
          description: Sourced from ~/.claude/plugins/data/test-plugin/config.yaml.
      steps:
        - n: 1
          action: Read GREETING_NAME and FAVORITE_COLOR from ~/.claude/plugins/data/test-plugin/config.yaml.
          tool: Read
          expected: Two values resolved from the config file.
          on_failure: If the config file is missing or incomplete, tell the user to restart their session so the bootstrap engine can create it with defaults. Do not improvise values.
        - n: 2
          action: Render the output_template with the resolved values substituted in for {GREETING_NAME} and {FAVORITE_COLOR}.
          expected: A one-line greeting in the user's chat.
      output_template: |
        Hello, {GREETING_NAME}! Your favorite color is {FAVORITE_COLOR}.
      gotchas:
        - If the config file is missing or incomplete, the bootstrap engine creates it with defaults on the next session start. Tell the user to restart their session in that case; do not improvise values.
```

## Config format reference

The config file is simple `KEY: "value"` YAML:

```yaml
GREETING_NAME: "Alice"
FAVORITE_COLOR: "green"
```
