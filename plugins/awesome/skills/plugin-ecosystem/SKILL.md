---
_schema_version: 1
name: plugin-ecosystem
author: christina
description: Use when generating, refreshing, or customizing the Claude Code plugin ecosystem poster (an interactive 16:9 HTML browser of installed marketplaces and plugins, with a click-to-expand skill-list panel). Do NOT use for skill authoring or single-plugin inspection.
---

## Skill Purpose

Generate `~/.claude/plugin-ecosystem.html` -- a self-contained 16:9 poster that visualizes the user's installed Claude Code plugin ecosystem. Each marketplace gets a column; each plugin a clickable card; clicking opens a side panel with the plugin's value-prop and skill list. The script overwrites the same file on every run and opens it in the browser.

## When to Use

- "Show me the plugin ecosystem"
- "Regenerate / refresh the plugin poster"
- "Make the poster reflect SpryFox defaults" (use the `states:` override block in the user config)
- "Set the poster title to X" / "set the tagline to Y" (edit the user config)
- "Add `<marketplace>` to the poster" (author a `.claude-plugin/poster.yaml` in that marketplace's repo)

## How to Invoke

```bash
powershell -NoProfile -Command "& SpiritCrossing\Scripts\python.bat \
  D:/dev/plugins-kit/plugins/awesome/skills/plugin-ecosystem/scripts/generate.py"
```

Optional flags:
- `--project PATH` -- project root (defaults to cwd). Determines which `bootstrap.json` and `settings.json` are read for live state.
- `--config PATH` -- user-level config YAML (default: `~/.claude/.local-data/awesome/plugin-ecosystem-poster.yaml`).
- `--output PATH` -- HTML output path (default: `~/.claude/plugin-ecosystem.html`).
- `--title TEXT` -- one-shot title override (the config YAML is the persistent home).
- `--no-open` -- write the file without opening it in the browser.

Stdlib only; the generated HTML is a single self-contained file.

## Data Model

The poster pulls from four sources, each owned by a different party:

| Layer | Owner | Where it lives |
|-------|-------|----------------|
| Marketplace column subtitle + opt-in | Marketplace maintainer | `<marketplace-repo>/.claude-plugin/poster.yaml`, read locally from `~/.claude/plugins/marketplaces/<name>/.claude-plugin/poster.yaml` |
| Plugin name / description / razor | Plugin author | `<plugin>/.claude-plugin/plugin.json` (the optional `razor` field is the side-panel blurb) |
| Skill name / description / author | Skill author | `<skill>/SKILL.md` YAML frontmatter (`author:` renders as "by {author}" beside the skill name) |
| Title / tagline / per-plugin state overrides | Poster author | `~/.claude/.local-data/awesome/plugin-ecosystem-poster.yaml` |
| Live on/off state | Project / user | `enabledPlugins` merged across project + user `settings.json`, falling back to project `bootstrap.json` |

### Marketplace opt-in (the gate)

A marketplace appears in the poster **only** if its repo ships `.claude-plugin/poster.yaml`. Marketplaces without one are excluded entirely, even if their plugins are installed. This keeps random third-party marketplaces from polluting the poster -- only marketplaces that have authored their poster identity participate.

The `poster.yaml` schema (all fields optional):

```yaml
subtitle: "Christina's open source plugin repository"
```

To add a marketplace: create that file in the marketplace repo, commit + push, then on the user's machine the next bootstrap pull syncs it into `~/.claude/plugins/marketplaces/`.

### State precedence

For each plugin, the badge is computed in this order (first match wins):

1. `states:` map in the user config YAML, keyed by `<marketplace>:<plugin>` or just `<plugin>`. Values: `on`, `off`, `opt-in`.
2. `enabledPlugins` in project `<cwd>/.claude/settings.local.json`, then `<cwd>/.claude/settings.json`, then `~/.claude/settings.json`. `true` -> on, `false` -> off.
3. Project `<cwd>/.claude/bootstrap.json` declaration. `enabled: true` -> on, `install: manual` -> opt-in, anything else declared -> off.
4. Default -> "unmanaged" (installed but neither enabled nor declared).

**SpryFox-defaults poster recipe**: drop a `states:` map into the user config that mirrors what the SpryFox `bootstrap.json` declares. Re-run -- the badges reflect SpryFox defaults regardless of the user's personal overrides.

### User config YAML

`~/.claude/.local-data/awesome/plugin-ecosystem-poster.yaml`:

```yaml
title: "Spirit Crossing Claude Plugin Ecosystem"
tagline: "Use /plugin to change your claude-code plugins, you decide what's active!"
states:
  spryfox-plugins:designer: on
  spryfox-plugins:claude-admin: opt-in
```

All keys optional. Defaults: title = "Claude Plugin Ecosystem", tagline = "" (no text), states = {} (use live values).

## When the User Asks To Customize

| User asks... | What to do |
|--------------|-----------|
| "Change the title to X" | Edit `title:` in the user config YAML, re-run skill |
| "Add a tagline that says Y" | Edit `tagline:` in the user config YAML, re-run skill |
| "Show this plugin as on/off" | Add `<marketplace>:<plugin>: on` (or off / opt-in) to `states:` in the user config |
| "Add `<marketplace>` to the poster" | Create `.claude-plugin/poster.yaml` in that marketplace's repo with at least a `subtitle:`, then commit + push |
| "Change the subtitle for `<marketplace>`" | Edit `.claude-plugin/poster.yaml` in that marketplace's repo (NOT the user config) |
| "Make the poster reflect SpryFox defaults" | Populate `states:` in the user config to match what SpryFox `bootstrap.json` declares for each plugin |

User config = poster author's knobs. Marketplace `poster.yaml` = marketplace maintainer's knobs. Don't conflate.

## Anti-Patterns

- **Hand-editing the generated HTML** -- it is overwritten on every run.
- **Hard-coding marketplace subtitles in `generate.py`** -- always live in the marketplace's `poster.yaml`.
- **Putting per-marketplace knobs in the user config** -- those belong to the marketplace owner, not the poster author.
- **Using `states:` to mask incorrect live state** -- if `enabledPlugins` says the wrong thing, fix `settings.json`, not the override map. Use overrides for "what would this look like under a different config" exploration.
