# Plugin Setup Pattern

A standard mechanism for plugins that need user-specific configuration (API keys, preferences, paths). Instead of prompting during bootstrap, the pattern detects missing config and emits context that guides Claude through an interactive setup flow.

## Overview

The pattern adds **Step 5** to the existing 4-step bootstrap sequence. Step 5 runs a plugin's `setup.py` script to check whether configuration is complete, and if not, surfaces remediation guidance to Claude.

```
Steps 1-4 (environment bootstrap)
    |
    v
Step 5: Check config (check-config.sh)
    Run setup.py --check
    |-- Config valid --> emit success
    |-- Config missing --> emit context directing Claude to setup skill
```

## Interface Contract: `setup.py`

Every plugin that needs configuration provides a `scripts/setup.py` with four modes:

### `--check --data-dir <path>`
Check whether config exists and is complete.
- **Exit 0**: Config is valid, all required fields present
- **Exit 1**: Needs setup — prints JSON with `missing_fields` array
- **Exit 2**: Error (script bug, invalid args)

### `--describe --data-dir <path>`
Print human-readable field descriptions showing name, description, default, example, and current value. Output is YAML-formatted text.

### `--apply --data-dir <path> --set KEY=VALUE [--set KEY=VALUE ...]`
Validate and write config values. Merges with existing config. Prints JSON confirmation on success.

### `--init-defaults --data-dir <path> --source <path>`
Copy a template config from `<source>/config.yaml` to the data directory. Use this to accept all defaults without interactive setup.

### Constraints

- **Stdlib-only**: `setup.py` must not import any third-party packages. It runs before the venv exists and when the venv may be broken.
- **Simple YAML**: Config files use `KEY: "value"` format — parseable with string splitting, no YAML library needed.
- **Exit codes**: 0=success, 1=needs setup, 2=error.

## Bootstrap Integration

### `check-config.sh` (Step 5)

The bootstrap step script follows the same pattern as Steps 1-4:
- Sources shared helpers via `declare -f` guards
- Resolves Python (venv first, system fallback)
- Runs `setup.py --check`
- Emits structured JSON with `context_message` and `user_message` on failure

### Orchestrator changes

In `session-bootstrap.sh`:
1. Source `check-config.sh` alongside other step scripts
2. Step 5 runs **after** the cache write (Step 4)
3. Step 5 also runs on **cache hit** (config is user data, not environment state)
4. On failure: emit error context and `exit 0` (same as Step 1 — session starts with remediation guidance)

### Config is NOT cached

`validate-cache.sh` hashes environment manifests (`system-tools.yaml`, `pyproject.toml`, `git-dependencies.yaml`). Config is user data that changes independently, so Step 5 checks it every session regardless of cache state.

### Stop hook

The Stop hook (`hooks/stop/bootstrap-check.py`) adds a config check after the system tools check. If config is missing, it blocks with the same severity as a missing tool.

## Setup Skill Pattern

The setup skill (`skills/test-setup/SKILL.md`) follows this flow:

1. Run `setup.py --describe` to learn available fields and their current values
2. Ask the user for each value, showing defaults
3. Run `setup.py --apply --set KEY=VALUE` with gathered values
4. Verify with `setup.py --check` (exit 0 = done)

### Alternative: Silent defaults

For non-interactive setup (CI, automation):
```bash
python setup.py --init-defaults --data-dir <data-dir> --source <plugin-root>/defaults
```

## How to Adopt This Pattern

1. Create `scripts/setup.py` implementing the 4-mode interface
2. Create `defaults/config.yaml` with template values
3. Copy `check-config.sh` to `hooks/sessionstart/`
4. Source it in your `session-bootstrap.sh` and add Step 5
5. Add config check to your Stop hook
6. Create a setup skill that runs `--describe` -> collect -> `--apply` -> `--check`

## Reference Implementation

See `plugins/test-plugin/` for a complete working example exercising all 5 bootstrap steps.
