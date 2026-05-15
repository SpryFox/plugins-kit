# Claude Explorer -- projections and layered personalization

The per-node rendering rules for the claude-explorer viewer. Read when implementing or extending the generator script.

Each container in the rendered HTML is an openable `<details>` block. The summary line shows the right level of detail for the node; opening it reveals direct children (and a button to drill further). Drill depth is unbounded; the viewer summarizes, never dumps source.

## Roots

| Root | Source | Summary line |
|---|---|---|
| Claude user dir | `~/.claude/` | "Claude user directory -- N marketplaces, M user skills, K projects-with-memory" |
| Project | CWD | Project name (from CWD basename or root `package.json` / `pyproject.toml` if present) + first line of root `CLAUDE.md` if present |

## Compositions

| Container | Summary projection | Children rendered on open |
|---|---|---|
| `claude_user_dir` | counts of marketplaces / user-skills / cached plugins | marketplaces; user `skills/`; `settings.json` summary; `installed_plugins.json` summary |
| `project` | name + first-line of `CLAUDE.md` (if present) + git remote (if discoverable) | root `CLAUDE.md`; `.claude/skills/` if present; in-tree `plugins/` if present; root `.claude-plugin/` if this is a marketplace |
| `marketplace` | `poster.yaml` subtitle (when present) or `marketplace.json` name + plugin count | each plugin |
| `plugin` | `plugin.json` description + razor + version + capability counts (skills / commands / agents / hooks) | each `SKILL.md`-rooted skill; `bootstrap.json` summary; root `CLAUDE.md` if present |
| `skill` | frontmatter name + description + skill-type + author + reference / script counts | SKILL.md frontmatter block; each reference doc; each script; in-skill `CLAUDE.md` if present |
| `directory` (fallback) | name + child counts | direct children only |

## Primitives

Every primitive has two renderings: a **summary projection** (what shows in the parent container's open state) and a **deep renderer** (what shows when the user clicks the primitive itself, opening it inline).

| Primitive | Summary projection | Deep renderer (on click) |
|---|---|---|
| `skill_md` | frontmatter (name, description, skill-type, author) + body line / token counts | full markdown rendered to HTML (headings, paragraphs, code fences, tables); contract YAML block syntax-highlighted |
| `claude_md` | scope.directory + scope.covers (when structured YAML is present); otherwise first heading + line count | full markdown rendered to HTML |
| `reference_doc` | filename + first H1/H2 + first 1-2 lines | full markdown rendered to HTML |
| `plain_md` | filename + first H1 + line count | full markdown rendered to HTML |
| `plugin_manifest` | name + version + description + razor (if present) | parsed JSON as key/value table |
| `marketplace_manifest` | name + plugin count | parsed JSON as key/value table |
| `bootstrap_manifest` | declared `venv.check_imports` + key tool checks (counts) | parsed JSON as key/value table |
| `script` | filename + leading docstring (first comment block) only | the full file body inside `<pre><code>` (no syntax highlighting in v1; stdlib-only) |

The deep renderer is inline (it opens within the same `<details>` element), not a navigation. The user stays on the same page; the rendering becomes more detailed when they ask for it.

## Markdown rendering

Markdown deep-rendering is the most common interaction. The generator ships a minimal CommonMark-subset renderer (headings, paragraphs, bold/italic, code fences, inline code, links, lists, tables, blockquotes) inline in the generator script. No external dependency. Anything outside the supported subset falls back to a `<pre>` block so the reader sees the source rather than mangled output.

## Layered personalization

Each composition supports an optional `claude-explorer.yaml` override file authored by the party that owns that level. The viewer reads sensible defaults from the primitives it discovers; the override only customizes what would otherwise default.

| Override file | Owner | What it overrides |
|---|---|---|
| `~/.claude/.local-data/awesome-kit/claude-explorer.yaml` | Viewer operator (you) | Top-level title, tagline, included/excluded roots, default open/closed state per composition kind |
| `<marketplace>/.claude-plugin/claude-explorer.yaml` | Marketplace maintainer | Marketplace card subtitle, opt-in display copy, per-plugin display overrides |
| `<plugin>/.claude-plugin/claude-explorer.yaml` | Plugin author | Plugin card razor, per-skill display overrides |
| `<skill>/claude-explorer.yaml` | Skill author | Per-reference / per-script display blurb overrides |

All fields in every override are optional. A missing field falls through to the next-most-specific override, then to the primitive default.

### Self-parameterizing behavior

When the viewer runs and an override YAML is missing for a composition that has at least one child, the viewer **generates a skeleton** at the canonical path with inferred defaults filled in. The skeleton is commented to explain each field. The next run reads the file the operator edited and applies any changes; fields the operator left at the default remain inert.

Pass `--regenerate-config` to force-regenerate skeletons (overwriting any existing override files with fresh skeletons). Without the flag, existing files are never modified -- only created when missing.
