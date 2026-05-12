---
_schema_version: 1
name: audit-references
author: christina
skill-type: technique-skill
description: Use when the user invokes /audit-references to scan SKILL.md, reference docs, or arbitrary .md files for broken skill cross-references, then categorize and remediate the findings. Do NOT use for single-skill validation (use /skill-audit).
disable-model-invocation: true
user-invocable: true
argument-hint: "[--scope skills|references|md|all] [--path FILE] [--ignore-dir GLOB] [--ignore-file GLOB] [--verbose] [--json]"
---

# Audit References

## Plugin version (always echo first)

!`uv run python "${CLAUDE_PLUGIN_ROOT}/scripts/print_version.py"`

The first line of your response MUST be the `Running ...` line printed above. This gives the user immediate confirmation of which plugin version actually executed (the slash registry can lag the on-disk cache; this is the only reliable signal).

## What this skill does

Scan one or more sets of markdown files for broken Claude Code skill references and report them. The default scope (`skills`) is the original `skill-deps` behavior — scan every `SKILL.md` and check that each `/example:skill-name` or `skill:"example:skill-name"` reference points to a real skill. Other scopes extend the scan to additional file types so reference files and standalone docs (e.g. `references/*.md`, `CLAUDE.md`) can be audited too.

Plugin skills are discovered from `~/.claude/plugins/installed_plugins.json` and resolved by both their bare name (e.g. `/example:skill-name`) and their plugin-qualified name (e.g. `/example:plugin-skill-name`).

## Invocation

This skill can be invoked three ways:

- **Slash command (project-scoped):** `/audit-references [args]`
- **Slash command (plugin-qualified):** `/skills-kit:audit-references [args]`
- **Skill tool (from another skill):** `Skill: "audit-references"` with `args` containing the desired flags. Pass scope decisions through `args` rather than hardcoding them at the call site so the caller stays generic.

All three resolve to the same SKILL.md and run the same `audit_references.py` script.

## Documentation Convention

When showing example skill-reference syntax in prose, use `/example:` or `/proposed:` prefixes (e.g. `/example:skill-name`, `/proposed:run-bot`). The scanner ignores any reference with one of these prefixes and never reports it as broken.

For **historical artifacts** (rollout summaries, design plans whose proposed names were later renamed or never built, postmortem docs that record past state), a per-file allowlist in YAML frontmatter declares which legacy names are expected to no longer resolve:

```yaml
---
audit-references-allow-stale: plan, designer-plan, rollback-to-preflight
---
```

Listed bare names are silenced inside that file only, for both soft refs and hard deps. Any *new* broken reference in the same file still fires — the allowlist is an explicit exception list, not a file-level bypass. Prefer this over rewriting historical refs to backticks or `/proposed:` prefixes when the doc's value is the historical record itself. The allowlist is documented in the editor's note inside the doc, so a reader sees both the declared exceptions and the reason for them.

## Step 1: Pick the Scope

The scope tells the script which files to audit. The agent picks based on what the user asked for; if the user did not specify, use the default `skills`.

| User said... | Pass | Effect |
|---|---|---|
| (nothing specific, or "audit my skills") | `--scope skills` (default) | Scan every `SKILL.md` (project + user + plugin). |
| "audit my reference docs" / "check references/ files" | `--scope references` | Scan every `*.md` file that sits inside a skill directory but is NOT `SKILL.md` (i.e. `references/*.md`, `CLAUDE.md` inside a skill dir, etc.). The skill pool itself is still loaded from SKILL.md files so refs can resolve. |
| "audit every markdown file" / "check all .md" | `--scope md` | Scan every `*.md` file under the scan roots, including SKILL.md, references, and standalone docs. |
| "audit everything" | `--scope all` | Alias for `--scope md`. |
| "audit this one file: PATH" | `--path PATH` (combine with `--scope` if the skill-pool scope matters) | Scan only the file at PATH; refs still resolve against the full skill pool. May be repeated. |

Scopes can also be combined with commas: `--scope skills,references` audits SKILL.md and reference files but skips standalone docs.

## Step 2: Run the Analysis

```
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/audit-references/scripts/audit_references.py" \
  --project-dir .claude/skills \
  --user-dir $HOME/.claude/skills \
  $ARGUMENTS
```

If `uv` isn't available in the host environment, fall back to whatever Python entry point fits (e.g. `python`, `python3`, `py`, or a project-bundled `python.bat`). The script depends only on the Python standard library.

Pass through any of these flags from `$ARGUMENTS`:

- `--verbose` / `-v` — full soft-reference graph and per-source-file table.
- `--ignore-dir GLOB` (repeatable) — skip files whose path contains a matching ancestor directory. Use for harness transcript dirs (e.g. `--ignore-dir 'ClaudeFeedback'`) and vendored third-party doc trees.
- `--ignore-file GLOB` (repeatable) — skip files matching the glob.
- `--json` — emit a structured JSON report instead of markdown. Use when downstream tooling (or the remediation step below) needs to consume findings programmatically.

## Step 3: Display Results

Show the script's markdown output directly to the user when remediation will be conversational. When remediation is in scope (Step 5 below), prefer `--json` and synthesize a short human summary for the user — the JSON feeds the classification step.

The output (markdown form) includes:

- **Scope summary**: which scopes ran and how many source files were scanned for each.
- **Skills discovered**: counts of project, user, and plugin skills (the resolvable name pool).
- **Issues**: each finding includes the file path, line number, and the missing ref. ERRORs (broken hard deps), WARNINGs (broken soft refs, name mismatches), INFOs (shadowed skills).
- **Hard Dependencies**: the Skill-tool invocation graph (edges across scanned source files), with line numbers.
- **Summary**: counts of each issue type.

If `--verbose` was used, also shows the full soft-reference graph (with line numbers) and a table of every scanned source file.

## Step 4: Interpret

This level only classifies the *scanner's* output type. For the **semantic categories** of broken references (renamed, retired, merged, scope-violating, false positive, illustrative, proposed, etc.) and the default fix for each, load `references/finding-taxonomy.md` in Step 5.

| Issue type | Meaning |
|------------|---------|
| ERROR | A Skill-tool call (e.g. `skill: "X"`) in a scanned source targets a skill that does not exist. This **will fail at runtime** when that path fires. |
| WARNING (broken ref) | A `/example:skill-name` reference in scanned prose targets a skill that does not exist. Misleading but not a runtime failure on its own. |
| WARNING (name mismatch) | The YAML frontmatter `name:` on a SKILL.md does not match what the directory structure suggests. May cause confusion. |
| INFO (shadowed) | A user-level skill has the same name as a project skill and overrides it at runtime. |

Exit code 0 = no ERRORs (warnings and infos are OK). Exit code 1 = broken hard dependencies exist.

## Step 5: Categorize and Remediate

Only run this step when the user asks to fix the findings (or it is otherwise in scope). Don't volunteer remediation if the user only wanted to see the report.

The flow:

1. Re-run the script with `--json` if you didn't already.
2. For each finding, classify into one of the categories in `references/finding-taxonomy.md` (A–J, plus K for special cases).
3. Bucket findings into **AUTO** / **DISCUSS** / **SPECIAL** per the taxonomy doc.
4. **In parallel**: launch a single background agent for the AUTO bucket with the brief template from the taxonomy doc, and open a foreground Q&A round for DISCUSS + SPECIAL.
5. After both return, merge changes, re-run the audit, iterate only on newly-surfaced findings.

The taxonomy doc is the authoritative reference for detection signals, default remediation per category, and the background-agent brief template. Do not improvise — load it.

## Scope Definitions in Detail

- **skills**: every `SKILL.md` under the scan roots (project, user, installed plugins). Backward-compatible with the original `skill-deps` behavior.
- **references**: every `*.md` file that lives inside a skill directory but is not the `SKILL.md` itself. Typically `references/*.md`, but also picks up any other markdown shipped alongside a skill (a per-skill `CLAUDE.md`, design notes, etc.). The skill pool is still populated from SKILL.md frontmatter; reference files contribute references, not skill identities.
- **md**: every `*.md` file under the scan roots, including SKILL.md, references, and any standalone docs.
- **all**: alias for **md**.

## Known Limitations

- **Prose-form hard deps** like "invoke `/example:review-read-comments` using the Skill tool" are classified as soft refs, not hard deps. The slash reference is still caught, just at WARNING level instead of ERROR.
- **Frontmatter parsing is regex-based** — handles the simple `key: value` shape used by SKILL.md files but does not parse the YAML contract block inside the body. The skill pool is built from frontmatter `name:` values only.
- **NON_SKILL_WORDS exclusion list** may occasionally filter a real skill name that collides with a common path segment (e.g. if someone creates a skill named "build"). Check the exclusion list in `audit_references.py` if a reference seems missing.
- **`settings.json`, `*.py`, and other non-markdown files** are not scanned at any scope.
- **Compound-adjective prose** like `X-/Y-foo` will match the trailing token (here, `Y-foo`) as a slash reference and produce a false positive. Category E in the taxonomy doc covers the remediation: reword the prose.
