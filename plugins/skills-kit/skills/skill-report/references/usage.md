# skill-report usage

Full usage reference for `/skill-report` and its underlying script
`scripts/report.py`. Loaded when the agent needs the precise flag set,
location semantics, output-shape contract, or implication rules.

## Invocation

User-only slash command:

```
/skill-report                          # markdown to <project-root>/tmp/skill-report.md (default)
/skill-report tmp/skills.md            # markdown to that path
/skill-report -                        # markdown body printed to stdout (rendered in chat)
/skill-report --format html            # interactive HTML to <project-root>/tmp/skill-report.html
/skill-report --format html tmp/x.html # HTML to that path
/skill-report --format html -          # HTML printed to stdout
```

Direct script invocation (under the plugin's uv venv):

```
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/skill-report/scripts/report.py" \
    [--format markdown|html] [--out <path>|-] [--cwd <dir>]
```

The HTML backend (also runnable directly for dev iteration):

```
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/skill-report/scripts/skill_hierarchy_report.py" \
    [--project-root PATH] [--out PATH] [--installed-plugins PATH] [--user-skills PATH]
```

### Flags

- `--format markdown|html` -- output format. Default: `markdown`. HTML mode produces an interactive collapsible hierarchy with one column per frontmatter key and skill-type hover tooltips; markdown produces the location-then-type grouped roster described below.
- `--out <path>` -- write the report to `<path>`. Default: `<project-root>/tmp/skill-report.md` for markdown, `<project-root>/tmp/skill-report.html` for HTML. Pass `-` to write the body to stdout instead of a file.
- `--cwd <dir>` -- treat `<dir>` as the project root for the Project tier (default: process cwd). The `tmp/` default path is computed relative to this.

On every file-write invocation the script echoes the resolved absolute path so callers can relay it to the user.

Exit codes: `0` on success; non-zero on argument-parse errors. The script does not fail on per-file parse problems -- it skips unreadable or malformed SKILL.md files silently and reports what it could parse.

## HTML mode

`--format html` delegates to the `render_html(corpus)` function in the sibling `skill_hierarchy_report.py` module. Output is a single self-contained HTML file (no external assets, no JavaScript):

- A three-level `<details>`/`<summary>` hierarchy: All -> User/Project/Plugins -> per-marketplace plugin tables. The top-level `All` is open by default; everything below collapses.
- Each table's columns are the union of every frontmatter key in that section's skills, with `name` first and `description` last; ultra-wide-monitor friendly (no width cap).
- The `skill-type` cell carries a hover tooltip describing the type's purpose, audit criterion, prohibited patterns, required frontmatter, and required contract-block fields.
- Plugins with no skills are dropped; marketplaces with no skill-bearing plugins are dropped.

## Locations resolved

The report enumerates three sets of roots, in this fixed order:

1. **User**: `~/.claude/skills/**/SKILL.md`. Personal global skills installed under the user's home directory.
2. **Project**: `<cwd>/.claude/skills/**/SKILL.md`. Skills checked into the current project. Resolved against `--cwd` (default: process cwd). When invoked from outside a project tree this section is empty.
3. **Plugin: \<name\>** (one per active install). Source of truth: `~/.claude/plugins/installed_plugins.json`. For each plugin entry the script reads the active install's `installPath/skills/**/SKILL.md`. Multiple-version cache directories under `~/.claude/plugins/cache/` are NOT scanned directly; only the version listed as installed is reported, so stale on-disk versions do not pollute the roster.

The plugin section header is `Plugin: <plugin_name> (<marketplace>, v<version>)`. `<marketplace>` is taken from the manifest key suffix (`<plugin>@<marketplace>`).

## Grouping

Within each location:

- Skills are grouped by `skill-type`, with technique-skill further qualified as `(user-only)` or `(auto)`.
- Type ordering is alphabetical (`capability-skill`, `discipline-skill`, `domain-skill`, `pattern-skill`, `reference-skill`, `technique-skill (auto)`, `technique-skill (user-only)`).
- Within a type, skills are sorted alphabetically by frontmatter `name`.

## Skill-type detection

For each SKILL.md the script reads:

- The YAML frontmatter (delimited by `---` lines).
- The first ```` ```yaml ```` fenced block in the body, which carries the type contract per the skill-authoring framework.

The skill type is taken from frontmatter `skill-type:` if present; otherwise inferred from the contract block's root key (`technique_skill`, `domain_skill`, etc.). The technique-skill variant is taken from `technique_skill.trigger_model` in the body block: `user-only` -> user-only variant, anything else -> auto.

If neither source declares a type, the type is reported as `(unknown)`.

## Implied frontmatter -- the no-duplication contract

Each `(skill-type, variant)` group declares the frontmatter values implied by the contract once at the top of the group. Per-skill rows then suppress any flag whose actual value matches the implied value, and surface only flags that DIFFER.

Implication map:

| skill-type / variant         | disable-model-invocation | user-invocable |
|------------------------------|--------------------------|----------------|
| technique-skill (user-only)  | true (implied)           | true (implied) |
| technique-skill (auto)       | false                    | false          |
| reference-skill              | false                    | false          |
| pattern-skill                | false                    | false          |
| discipline-skill             | false                    | false          |
| domain-skill                 | false                    | false          |
| capability-skill             | false                    | false          |

Only entries marked "implied" are echoed in the group header. A user-only technique-skill therefore reads:

```
### technique-skill (user-only)

_Implied frontmatter: `disable-model-invocation: true`, `user-invocable: true`_
```

A skill row in that group will list `disable-model-invocation` only when it is set to false (overriding the contract), and likewise for `user-invocable`. A skill in a non-user-only group will list either flag only when it is set to true.

This is the "don't duplicate information" rule: the contract states the default; the per-skill row states only what departs from it.

## Per-skill row format

```
- **<name>** [author: <author>] -- <description>
  - <non-implied flag>, <non-implied flag>
```

- `[author: ...]` is omitted when the skill has no `author:` frontmatter line.
- The trailing `-- <description>` is omitted when frontmatter has no `description:` field.
- The flag-line beneath the row is omitted when no flags differ from the implied set.

## Worked example

A user-only technique-skill with a clean contract:

```
### technique-skill (user-only)

_Implied frontmatter: `disable-model-invocation: true`, `user-invocable: true`_

- **skill-audit** [author: christina] -- Use when the user invokes /skill-audit ...
- **skill-report** [author: christina] -- Use when the user invokes /skill-report ...
```

Same group with one skill that is unusually NOT user-invocable:

```
- **internal-only-tool** [author: bob] -- Internal tool, model-only
  - `user-invocable: false`
```

The flag is surfaced because it differs from the implied `user-invocable: true`.

## Gotchas

- The script reports based on `installed_plugins.json`. If a plugin was just edited on disk but the manifest has not been refreshed, the new version's SKILL.md may not appear under the Plugin tier. The plugin-version banner echoed before the report is the authoritative signal of which skills-kit version actually ran.
- `(unknown)` skill-type usually means the SKILL.md is missing both a frontmatter `skill-type:` line and a recognized contract root in its body YAML. Treat it as a hint to inspect the file with `/skill-audit`.
- Project tier honours `--cwd`. When this skill is invoked from a different working directory the report will reflect that directory's `.claude/skills/`, not the directory the agent typically runs in.
- The script reads files only. It does not edit SKILL.md frontmatter, does not call P4 or git, and does not write outside `--out` (when supplied).
