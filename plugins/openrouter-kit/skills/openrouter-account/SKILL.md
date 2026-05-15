---
_schema_version: 1
name: openrouter-account
author: christina
skill-type: technique-skill
description: Use when checking, setting, or troubleshooting the OpenRouter API key managed by openrouter-kit -- account status, credit balance, key rotation, 401/402 errors. Do NOT use for general LLM/translation work; this only covers credential management.
---

# OpenRouter Account

Manage the shared OpenRouter API key that other plugins and project scripts depend on. The key is stored in a user-scoped `.env` file at `~/.claude/plugins/data/plugins-kit/openrouter-kit/.env` and consulted by anything that imports `openrouter_kit` (today: loc-ops; future: any plugin that calls OpenRouter).

## When to invoke

- The user wants to check whether their OpenRouter key is set up and working.
- The user wants to set or rotate the key.
- A bootstrap fix-all entry says `openrouter_credential` is missing or rejected.
- A consumer (loc-ops, etc.) failed with HTTP 401 / 402 and the user needs to know whether the key or the account balance is the problem.

Do NOT use for translating strings, choosing models, debugging chunk failures, or any other LLM work that happens *after* the key is verified -- that is the consumer's responsibility.

## The CLI

The plugin ships a single CLI script at `${CLAUDE_PLUGIN_ROOT}/scripts/openrouter_kit_cli.py` with three subcommands.

| Command | What it does |
|---------|--------------|
| `status` | Resolves the key from env / project / user .env (in that order), calls `GET /auth/key`, prints account label, usage, limit, free-tier flag, rate limit. Exit 0 = OK; non-zero = missing or rejected. |
| `set-key [--key VALUE] [--no-validate]` | Writes a new key to the user-scoped .env. With no `--key`, prompts via `getpass` (input hidden). Validates the key against `/auth/key` before writing unless `--no-validate` is passed. |
| `which` | Prints the source path of the resolved key (`env`, `project: <path>`, `user: <path>`, or `missing`). Useful when the user is confused about which file is being read. |

### Invocation

Use the bootstrap-installed venv path so cwd does not matter:

```bash
# Windows
~/.claude/plugins/data/plugins-kit/openrouter-kit/.venv/Scripts/python.exe \
    ~/.claude/plugins/cache/plugins-kit/openrouter-kit/<version>/scripts/openrouter_kit_cli.py status

# macOS / Linux
~/.claude/plugins/data/plugins-kit/openrouter-kit/.venv/bin/python \
    ~/.claude/plugins/cache/plugins-kit/openrouter-kit/<version>/scripts/openrouter_kit_cli.py status
```

When the plugin is being developed locally via `--plugin-dir`, swap the cache path for the working-copy path:

```bash
uv run python <plugin-dir>/scripts/openrouter_kit_cli.py status
```

The script is stdlib-only; any Python 3.10+ interpreter works.

## Common scenarios

**No key is set yet** -- run `set-key` and paste the key from <https://openrouter.ai/keys> at the prompt. The script validates against `/auth/key` before writing, so a typo never silently lands on disk. After it returns, `status` should show `OK` with the key's label.

**Key was rejected (HTTP 401)** -- the key was revoked or rotated on the OpenRouter side. Generate a new one at <https://openrouter.ai/keys> and re-run `set-key`. Old key value is overwritten.

**Account out of credit (HTTP 402)** -- the key is valid but the account has no balance. Top up at <https://openrouter.ai/credits>. The next bootstrap session-start automatically clears the cached `last_validated.sha256` once a successful `/auth/key` call happens, so no manual cache reset is needed.

**Key loaded from the wrong place** -- run `which` to see which file Wins the precedence resolution (env var > project `.env` > user `.env`). If the user wants the user-scoped file to win but a project file is shadowing it, delete `<project>/.local-data/openrouter-kit/.env`.

## What lives where

| Path | Purpose |
|------|---------|
| `~/.claude/plugins/data/plugins-kit/openrouter-kit/.env` | Canonical user-scoped credential file. 0600 perms on Unix. |
| `<project>/.local-data/openrouter-kit/.env` | Optional per-project override. Wins over the user file when present. |
| `OPENROUTER_API_KEY` env var | Highest priority. Useful for CI / one-shot overrides. |
| `~/.claude/plugins/data/plugins-kit/openrouter-kit/last_validated.sha256` | Cache marker. Contains the SHA-256 of the last key that successfully validated, so subsequent sessions skip the network call when nothing changed. Safe to delete -- the next bootstrap re-validates. |

## What this skill does NOT do

- Choose models, set temperature, or shape requests. That is the consumer's job (loc-ops's `translate_*` functions, etc.).
- Manage Anthropic, OpenAI, or any other provider's credentials. Those would live in their own `<provider>-kit` plugin.
- Inspect or modify the bootstrap engine itself -- see `/bootstrap` for that.
