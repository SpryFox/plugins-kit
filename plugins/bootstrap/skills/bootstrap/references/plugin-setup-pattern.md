# Plugin Setup Pattern

How plugins declare and manage user-specific configuration (API keys, preferences, paths).

## Preferred: Declarative Config via `bootstrap.json`

Plugins that need configuration should declare a `config` section in their `bootstrap.json`. The bootstrap engine handles initialization, validation, and fix-all remediation automatically.

```json
{
  "config": {
    "file": "config.yaml",
    "defaults_source": "defaults/config.yaml",
    "required_fields": {
      "GREETING_NAME": {
        "default": "World",
        "user_msg": "Name to use in greeting",
        "agent_msg": "Set GREETING_NAME in {config_path}"
      },
      "API_KEY": {
        "user_msg": "Your API key",
        "agent_msg": "Ask the user for their API key and write it to {config_path}"
      }
    }
  }
}
```

### What the engine does

1. **Init**: Copies `defaults_source` to the data directory if config doesn't exist
2. **Autodetect** (optional): Runs a plugin script to discover values automatically
3. **Validate**: Checks required fields, applies defaults where declared
4. **Fix-all**: Fields without defaults that are still empty become fix-all items

### Autodetect

For fields that can be discovered programmatically (e.g. finding a `.uproject` file by scanning the filesystem), declare an autodetect script:

```json
"autodetect": "custom_bootstrap.py autodetect"
```

The function signature is `autodetect(config: dict, config_path: str)` and it can return either:
- `bool` — True if config was modified
- `dict` — `{"changed": bool, "actions": [...], "ok": [...]}` for structured logging

### Reference implementation

See `plugins/test-plugin/bootstrap.json` for a minimal example with two fields and defaults.

## Legacy: `scripts/setup.py` CLI Pattern

Some plugins (e.g. `local-review-kit`) still use a `scripts/setup.py` CLI for interactive setup driven by skills. This pattern predates the engine's config support and is being phased out for plugins that can use `bootstrap.json` config sections.

The CLI provides four modes:

| Mode | Purpose |
|------|---------|
| `--check --data-dir <path>` | Exit 0 if config valid, 1 if needs setup |
| `--describe --data-dir <path>` | Print field descriptions as YAML |
| `--apply --data-dir <path> --set K=V` | Write config values |
| `--init-defaults --data-dir <path> --source <path>` | Copy template config |

### When to use which

- **New plugins**: Use `bootstrap.json` config section. No `scripts/setup.py` needed.
- **Plugins with complex interactive setup** (e.g. API keys that need validation): May still benefit from `scripts/setup.py` alongside the config section, with skills driving the `--describe`/`--apply` flow.
- **Plugins with autodetect**: Use the `bootstrap.json` autodetect spec. The engine calls it automatically.
