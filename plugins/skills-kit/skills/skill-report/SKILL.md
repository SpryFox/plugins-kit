---
_schema_version: 1
name: skill-report
author: christina
skill-type: technique-skill
description: Use when the user invokes /skill-report to list all skills by location and type, in markdown (default) or interactive HTML (--format html). Do NOT use for auditing a SKILL.md (use /skill-audit).
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
      - rendering as markdown (default) or interactive HTML via --format html
      - declaring per-type implied frontmatter once in the markdown output so per-skill rows do not repeat it
      - writing the report to <project-root>/tmp/skill-report.{md,html} by default, or a caller-supplied path, or stdout via --out -
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
            Where to write the report. If omitted, defaults to
            <project-root>/tmp/skill-report.md (or .html when --format html is set).
            Pass the literal `-` to write to stdout instead. Mapped to --out.
        - name: FORMAT
          required: false
          description: |
            Output format flag: `--format markdown` (default) or `--format html`.
            HTML mode renders an interactive collapsible hierarchy with one column
            per frontmatter key and skill-type hover tooltips.
      preconditions:
        - The skills-kit plugin is installed (this skill ships with it).
        - PyYAML is available (skills-kit declares it as a dependency).
      steps:
        - n: 1
          action: Resolve OUT_PATH and FORMAT from $ARGUMENTS; pass through to the script's --out and --format flags.
          tool: argument parsing
          input: $ARGUMENTS
          expected: A list of script flags (path / '-' / --format html, in any combination).
        - n: 2
          action: Run the report script via the plugin venv.
          tool: report.py
          input: |
            uv run python "${CLAUDE_PLUGIN_ROOT}/skills/skill-report/scripts/report.py" [--format markdown|html] [--out <path>|-]
          expected: |
            With no args or an explicit path, the script writes the report to disk and
            echoes the resolved path to stdout. With `--out -`, the report body is
            written to stdout in the chosen format.
        - n: 3
          action: Always surface the resolved output path to the user (the script echoes it; relay it verbatim).
          expected: User sees the absolute path and can open it.
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

Markdown (default):

- `(none)` -- write to `<project-root>/tmp/skill-report.md`.
- `<path>` -- write to that file path.
- `-` -- write the markdown body to stdout (renders in chat).

HTML (interactive hierarchy with hover tooltips):

- `--format html` -- write to `<project-root>/tmp/skill-report.html`.
- `--format html <path>` -- write HTML to that path.
- `--format html -` -- write HTML to stdout.

In every file-write case, the script echoes the resolved output path; that path must always be surfaced to the user.

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
