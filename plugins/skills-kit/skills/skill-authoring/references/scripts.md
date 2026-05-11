# Skill-authoring scripts

The skill-authoring domain ships three deterministic-or-heuristic scripts in `scripts/`. They support the audit / classify / tag operations the agent applies during authoring and refinement. All three are stdlib-only Python and share a `_shared.py` helper module for SKILL.md parsing and structural detectors.

The scripts surface candidates and structural facts; the agent weighs them. They never make semantic judgments on whether a rule has a real counter, whether a hedge softens vs. carves a bounded exception, or whether content is meaningfully complete. Those rows return `judgment-required` and the agent runs them by hand against the contract in `framework.md`.

## audit.py

**Purpose.** Run the deterministic contract checks against a SKILL.md. Each row of the contract for the declared skill-type emits a verdict; the agent extends the report with the judgment-required rows.

**Usage.**

```
python scripts/audit.py <path-to-SKILL.md>
python scripts/audit.py <path-to-SKILL.md> --json
```

**Output.** Three sections: universal (frontmatter, line/token counts, reference integrity), type-specific (per the declared `skill-type` frontmatter value), and mixed-type signal. Each row emits one of:

- `pass` -- the check confirms the row is satisfied.
- `fail` -- the check confirms the row is not satisfied.
- `judgment-required` -- the row is not deterministic at the script level; the agent runs it by hand against `framework.md`.
- `n/a` -- a conditional row whose IF clause does not fire.

**Gotchas.**

- Heuristic detectors fire on structural markers (headings, ordered lists, tables, specific phrases). False positives are possible: a paragraph mentioning "rationalization" in passing will register as a discipline-content signal. The agent reads the verdict in context, not in isolation.
- The token count is approximated as `word_count * 1.3`. It is calibrated for the progressive-disclosure threshold (3000 tokens) at the order-of-magnitude level; for precise budgeting, use a real tokenizer.
- The mixed-type signal score is a count of distinct typed-marker categories detected. Score `>= 2` is flagged for agent judgment because organic skills often grow across boundaries; per the SSOT extension in `glossary.md`, orientation summaries that name a canonical reference and stay short do not count as cross-type drift even when their structural markers fire.

## classify.py

**Purpose.** Infer a SKILL.md's type from its content shape. Useful for organic skills that haven't adopted the `skill-type:` frontmatter convention, or for cross-checking whether a declared type matches the actual content.

**Usage.**

```
python scripts/classify.py <path-to-SKILL.md>
python scripts/classify.py <path-to-SKILL.md> --json
```

**Output.** A score per canonical type (reference / pattern / technique / discipline / domain), a suggested type, and a verdict.

**Verdict values.**

- `single-type` -- one type scores strictly higher than the others; suggestion is that type.
- `ambiguous` -- the top types tie; the agent picks based on intent.
- `mixed-type` -- two or more types score at or above the mixed threshold (default `2`); agent must split the skill or reclassify.
- `indeterminate` -- no canonical signals fire; either the skill is too small to classify or the heuristics need extension.

**Gotchas.**

- Scoring is heuristic. A domain-skill with orientation sections that include ordered steps will score on technique-content; treat the verdict as a starting point, not a verdict.
- A SKILL.md without canonical signals at all (no headings matching the heuristic vocabulary, no tables, no ordered lists) returns `indeterminate`. This is a real signal: the skill may be too thin to classify, or it may use vocabulary the heuristics don't recognize. Either way, the agent inspects directly.
- The mixed-type threshold is constant `MIXED_THRESHOLD = 2` at top of the file. Tuning it changes how aggressive the classifier is about flagging cross-type drift.

## tag.py

**Purpose.** Write a `skill-type:` value into the SKILL.md frontmatter. Idempotent. Refuses to overwrite an existing value without `--force`.

**Usage.**

```
python scripts/tag.py <path-to-SKILL.md> <skill-type>
python scripts/tag.py <path-to-SKILL.md> <skill-type> --check
python scripts/tag.py <path-to-SKILL.md> <skill-type> --force
```

**Behavior.**

- If the file has no frontmatter, the script flags the file and refuses. It never invents frontmatter; that would silently regularize a SKILL.md the framework expects to surface as flagged.
- If the file's frontmatter has the requested `skill-type:` value, the script is a no-op.
- If the file's frontmatter has a different `skill-type:` value, the script refuses unless `--force` is passed.
- `--check` reports what would happen without writing.

**Gotchas.**

- `tag.py` modifies the file in place. For bulk-tagging operations, run on a clean working tree so changes are reviewable per-file.
- The valid type values are the five canonical types from `glossary.md`. Passing any other value errors out before touching the file.
- The frontmatter parser is regex-based and handles the simple `key: value` shape used throughout this project. Frontmatter using YAML features beyond simple flat keys (lists, nested mappings) is not preserved verbatim by tag.py and should be hand-edited instead.

## skill_hierarchy_report.py

**Purpose.** Emit an HTML hierarchy report of every SKILL.md discoverable under user, project, and installed-plugin roots. Unlike `audit.py` / `classify.py` (which inspect one skill at a time), this script enumerates the agent's available-skill surface and renders it as an interactive document the user can browse.

The hierarchy is three levels deep:

```
All (N skills)
  |- User skills (N)         -- ~/.claude/skills/
  |- Project skills (N)      -- <project>/.claude/skills/
  `- Plugins (N)             -- enumerated from installed_plugins.json
        |- <marketplace-1>
        |    |- <marketplace-1>:<plugin-a> (N)
        |    `- <marketplace-1>:<plugin-b> (N)
        `- <marketplace-2>
             `- ...
```

Sections are HTML `<details>`/`<summary>` -- expand and collapse interactively, no JavaScript required. Plugin sections are grouped first by marketplace, then by plugin; each plugin's display name uses the `marketplace:plugin-name` form, and the skill name inside each table renders as `marketplace:plugin-name:skill-name`.

**Usage.**

```
python scripts/skill_hierarchy_report.py [--project-root PATH]
                                         [--user-skills PATH]
                                         [--installed-plugins PATH]
                                         [--out PATH]
```

All flags are optional. Defaults:

- `--project-root` -- the current working directory (typically the project root the user is in)
- `--user-skills` -- `~/.claude/skills/`
- `--installed-plugins` -- `~/.claude/plugins/installed_plugins.json`
- `--out` -- `<project-root>/tmp/skill-hierarchy.html`

Run from any directory; the script resolves `_shared.py` via `__file__` and does not depend on cwd.

**Output.** A single self-contained HTML file with embedded CSS (no external assets, no JavaScript). Layout:

- Top-level `All` count is open by default; the three groups below it are collapsed.
- Each expanded section shows a table whose columns are the **union** of every frontmatter key present in that section's skills. Column order is `name` first, alphabetical middle, `description` last. Width is intentionally unconstrained (assumes wide-monitor viewing).
- The `skill-type` cell carries a hover tooltip describing the type's purpose, audit criterion, prohibited patterns, required frontmatter, and required contract-block fields. Tooltip content is authored from `schemas.py` and `framework.md`; the static table in the script body is the source of truth.

**Discovery behavior.**

- User skills come from a flat `~/.claude/skills/<skill>/SKILL.md` layout; if no flat children are found the script falls back to a bounded `rglob`.
- Project skills follow the same shape under `<project-root>/.claude/skills/`.
- Plugin skills are enumerated by reading `installed_plugins.json` (the canonical record of which version is active per plugin). Each plugin's `installPath` plus `/skills/` is scanned with the same flat-then-rglob strategy. Plugins with no skills are dropped from the report; marketplaces with no skill-bearing plugins are dropped from the marketplace list.

**Gotchas.**

- The discovery enumerates **on-disk** skills, not the skills surfaced in the current session's available-skills system reminder. The two sets can differ -- the session listing reflects harness filtering (e.g. built-in slash commands without SKILL.md files, plugins the harness suppressed). If the user wants exactly the session list, they need to supply it separately; there is no on-disk source of truth for it.
- Column union is per-section, not corpus-wide. A frontmatter key that only one project skill uses (e.g. `allowed-tools`) appears as a column in the Project-skills table and is absent from the User-skills table. This keeps each section's table narrow and relevant; it also means the same column can have different positions in different tables.
- Built-in slash-command "skills" (the ones bundled with Claude Code itself -- `loop`, `init`, `review`, `simplify`, etc.) have no on-disk SKILL.md and will not appear in the report. This is correct -- they are not authored skills under any of the three discovery roots.
- The script reads `installed_plugins.json` for the active version per plugin. If a plugin has multiple cached versions on disk under `~/.claude/plugins/cache/`, the report only shows the version currently pinned by `installed_plugins.json`.

**Iterating without publishing.** The script lives in `skills-kit/skills/skill-authoring/scripts/skill_hierarchy_report.py`. It can be invoked directly from a dev clone (e.g. `D:/Dev/plugins-kit/plugins/skills-kit/...`) -- the only dependency it borrows from the installed plugin is the venv interpreter at `~/.claude/plugins/data/plugins-kit/skills-kit/.venv/Scripts/python.exe` (which has PyYAML available for the underlying `_shared.parse_frontmatter` call). Iterate on the dev path, re-run the same command, no version bump or marketplace push required until the output format is settled.

## Shared module: _shared.py

`_shared.py` exports the parsing primitives (`parse_frontmatter`, `parse_body`) and the structural detectors (`has_excuse_reality_table`, `count_ordered_steps`, `has_conditional_loading`, etc.) plus the `type_signals()` scoring function. Per SSOT, the detectors live there exactly once; audit.py and classify.py import the same definitions.

When extending the heuristics (new structural marker, new type signal), modify `_shared.py` first, then add the row to whichever script consumes the new signal.

## Calibration history

The scripts are v1. Friction surfaced during smoke-testing on existing plugins-kit skills will feed Phase 4 calibration:

- The skill-authoring SKILL.md itself classifies as mixed-type because its orientation sections include ordered steps and a "recognize and split" callout. This is the SSOT-extension orientation-summary case in action -- the script flags for judgment, not for failure.
- The cache-report SKILL.md classifies as `indeterminate` because its content uses formatting the heuristics don't yet recognize (e.g. user-objective descriptions without ordered-list steps). Phase 4 audits will surface whether this is a heuristic gap or a genuine gap in the skill's structure.
- The bootstrap SKILL.md scores tied between technique-content and reference-content. It declares reference-skill but contains both shapes. This is a real mixed-type finding, separate from script calibration.
