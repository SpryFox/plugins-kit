---
_schema_version: 1
name: statusline
skill-type: technique-skill
description: Use when the user invokes /statusline or asks to inspect, customize, or reset their Claude Code status line. Do NOT volunteer styling concepts the user hasn't mentioned.
disable-model-invocation: true
---

# Statusline

Inspect and customize the Claude Code status line. The plugin ships an opinionated default; this skill helps the user change it without forcing a vocabulary on them.

## Behavior on /statusline (no arguments)

1. **Identify the active statusLine.** Read settings.json layers in precedence order (highest first):
   - `<project>/.claude/settings.local.json`
   - `<project>/.claude/settings.json`
   - `~/.claude/settings.json`

   The first one with a `statusLine.command` is the active script. If none, tell the user there is no statusLine configured and offer to install claude-ui-kit's default.

2. **Read the script** at that command path. Identify what it displays (components) and how (colors, thresholds, separators). Summarize for the user in plain language. Example:
   > Your current status line shows **directory**, **context %**, **5-hour usage**, and **7-day usage**, separated by `│`. The context number turns orange at 30% and red at 70%; the 5-hour number turns orange at 70% and red at 90%.

3. **Ask if they want to change anything.** Don't suggest specific changes ("would you like a gradient?"). Just: "Want to customize anything?"

4. **Wait for the user.** If they ask for a specific change, apply it (see Editing rules below). If they decline, stop.

## Editing rules

When the user requests a change:

- **If the active script lives inside the plugin's data dir** (path contains `/claude-ui-kit/scripts/`), do NOT edit it in place — bootstrap will overwrite it on the next session. Instead:
  1. Copy it to `~/.claude/statusline.sh` (or `<project>/.claude/statusline.sh` if the user wants a project-scoped version).
  2. Update the relevant settings.json's `statusLine.command` to the new path.
  3. Touch `<plugin_data_dir>/customized.flag` so bootstrap stops trying to manage it. The data dir is `~/.claude/plugins/data/plugins-kit/claude-ui-kit/`.
  4. Apply the requested edit to the copied script.
- **If the active script is already user-owned**, edit it directly.
- **Preserve the script's input contract** (`DATA=$(cat)`, jq parses session JSON from stdin) and the basic output discipline (single line, ANSI escapes, `echo -e`).
- After any edit, verify by piping a small fake JSON payload through the script and showing the user the rendered output.

## Stay grounded

The user's request is the source of truth for what to change. Don't invent extra features. Examples of good behavior:

| User says | Do |
|-----------|----|
| "Make the context bar a yellow progress bar" | Replace the `🧠 NN%` text with a 10-cell filled-block bar in yellow (ANSI 226). Keep everything else. |
| "Drop the 7-day percentage" | Remove the `📅` block. Don't ask if they also want to reformat the others. |
| "Use a powerline arrow instead of the pipe" | Swap `│` for ` ` (powerline arrow) wherever it appears. Don't redesign. |
| "Reset to default" | Delete the user-owned script and the `customized.flag`, point settings.json back at `<data_dir>/scripts/statusline.sh` (claude-ui-kit's data dir). |

Don't ask about themes, gradients, or other concepts the user hasn't mentioned. The reference docs below list common patterns — load them only when the user's request is specific enough to need them.

```yaml
technique_skill:
  _schema_version: "1"
  trigger_model: user-only
  identity: Help the user inspect and customize their Claude Code status line script.
  scope:
    covers:
      - explaining what the current statusline displays
      - applying user-requested edits to the script (components, colors, thresholds, separators)
      - resetting back to claude-ui-kit's default
      - copying the plugin default into a user-owned location for editing
    excludes:
      - volunteering styling concepts the user hasn't mentioned
      - editing the script in the plugin data dir (bootstrap overwrites it)
      - changing settings.json layers other than the one holding the active statusLine
  techniques:
    - id: inspect
      name: Inspect current statusline
      keywords: [/statusline, what is my statusline, current statusline, explain my statusline]
    - id: edit
      name: Apply a user-requested edit
      keywords: [change, customize, edit, swap, replace, drop, add, color, threshold, progress bar, separator]
    - id: reset
      name: Reset to claude-ui-kit default
      keywords: [reset, restore default, undo customization, default statusline]
```

```yaml
conditional_loading:
  components_keywords:
    keywords: [component, field, segment, what can i show, available data, model, branch, git, cost, tokens, time, duration, memory, working directory, context window, rate limit]
    load_references:
      - references/components.md

  styling_keywords:
    keywords: [color, theme, gradient, progress bar, threshold, ansi, hex, truecolor, separator, powerline, icon, emoji, nerd font, bold, italic, dim]
    load_references:
      - references/styling.md
```
