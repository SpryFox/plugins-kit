---
_schema_version: 1
name: skill-report
author: christina
skill-type: technique-skill
description: Use when the user invokes /skill-report to list all skills by location and type. Do NOT use for auditing a SKILL.md (use /skill-audit).
disable-model-invocation: true
user-invocable: true
argument-hint: "[output path]"
---

# Skill Report

## Plugin version (always echo first)

!`uv run python "${CLAUDE_PLUGIN_ROOT}/scripts/print_version.py"`

The first line of your response MUST be the `Running ...` line printed above. This gives the user immediate confirmation of which plugin version actually executed (the slash registry can lag the on-disk cache; this is the only reliable signal).

Produce a roster of every SKILL.md visible from the session: User skills, Project skills, and all installed Plugin skills. Group by location, then by skill-type, with the per-type implied frontmatter declared once so per-skill rows do not duplicate the contract. Authors (when declared in frontmatter) are surfaced inline.

```yaml
technique_skill:
  _schema_version: "1"
  trigger_model: user-only
  identity: Generate an organized roster of all skills visible from the session.
  scope:
    covers:
      - listing User / Project / Plugin skills with location, type, name, description, and author
      - declaring per-type implied frontmatter once so per-skill rows do not repeat it
      - writing the report to stdout or to a file via --out
    excludes:
      - auditing a single SKILL.md against framework rules (use /skill-audit)
      - editing SKILL.md frontmatter or body content
      - reporting on CLAUDE.md files (out of scope; this skill is skill-only)
  techniques:
    - id: generate_skill_report
      name: Generate the skill report
      keywords: [skill report, skill roster, skill inventory, list skills, skills by location, skills by type, /skill-report]
      goal: Produce a markdown report grouping every visible SKILL.md by location and skill-type.
      arguments:
        - name: OUT_PATH
          required: false
          description: |
            If provided, write the report to this path; otherwise print to stdout.
            Mapped to the script's --out flag.
      preconditions:
        - The skills-kit plugin is installed (this skill ships with it).
        - PyYAML is available (skills-kit declares it as a dependency).
      steps:
        - n: 1
          action: Resolve OUT_PATH from $ARGUMENTS; pass through to the script's --out flag if present.
          tool: argument parsing
          input: $ARGUMENTS
          expected: A list of script flags (empty or a single --out value).
        - n: 2
          action: Run the report script via the plugin venv.
          tool: report.py
          input: |
            uv run python "${CLAUDE_PLUGIN_ROOT}/skills/skill-report/scripts/report.py" [--out <path>]
          expected: Markdown report on stdout (or written to OUT_PATH).
        - n: 3
          action: If --out was used, surface the resolved path so the user can open it; otherwise the report is already in chat.
          expected: User can read or open the report.
      gotchas:
        - "The Plugin: skills-kit row reads from ~/.claude/plugins/installed_plugins.json and shows the active version, which can lag the on-disk cache. The plugin-version banner above is the authoritative signal of which version actually ran."
        - "Implied frontmatter is per (skill-type, variant). User-only technique-skills imply both disable-model-invocation true and user-invocable true; other types imply neither. Per-skill rows show only flags that DIFFER from the implied set."
        - "Project skills resolve relative to cwd (<cwd>/.claude/skills). If invoked from outside a project tree the Project section will be empty; this is expected, not a bug."
        - "The script reads only files. It does not modify SKILL.md frontmatter and does not call any P4 / git commands."
      reference_section: usage.md
  reference_index:
    - id: usage
      path: references/usage.md
      keywords: [usage doc, skill-report flags, output shape, location semantics, examples, implied flags]
      summary: Full usage and output-shape reference for /skill-report -- flags, exit codes, what each location resolves to, how implied flags are computed, and worked examples.
```

## Argument grammar

- `(none)` -- write the report to stdout (rendered in chat).
- `<path>` -- write the report to that file path instead of stdout.

## Output shape (summary)

The report has three location tiers in order:

1. `User (~/.claude/skills)`
2. `Project (<cwd>/.claude/skills)`
3. `Plugin: <name> (<marketplace>, v<version>)` -- one section per actively installed plugin, in registration order from `installed_plugins.json`.

Inside each location, skills are grouped by `skill-type` (with `(user-only)` / `(auto)` qualifier on technique-skill). The first line under each type heading declares the implied frontmatter for that type so per-skill rows do not duplicate it. See `references/usage.md` for full details.

## Cross-references

- Full usage doc: `references/usage.md`.
- The frontmatter type system: `framework.md (in skills-kit:skill-authoring)`.
- The schemas this script's type detection mirrors: `plugins/skills-kit/skills/skill-authoring/scripts/schemas.py`.
- Sibling auditing skill: `/skill-audit` (audits a single SKILL.md against the framework).
