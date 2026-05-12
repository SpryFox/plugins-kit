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

## HTML hierarchy report

The interactive HTML hierarchy report ships with the `/skill-audit` skill (the umbrella for skill analysis, reports, and fixes). Since v0.7.0 the renderer (`render_html(corpus)`) sits in `skills-kit/skills/skill-audit/scripts/skill_hierarchy_report.py` and is invoked via the `hierarchy` subcommand:

- `/skill-audit hierarchy` -- write `<project-root>/tmp/skill-hierarchy.html` and echo the path.
- `/skill-audit hierarchy <path>` / `/skill-audit hierarchy -` -- explicit path / stdout.
- `python skills/skill-audit/scripts/skill_hierarchy_report.py [...flags]` -- direct invocation for dev iteration (default output `<project-root>/tmp/skill-hierarchy.html`).

See `/skill-audit`'s `references/usage.md` for the full reference, including the companion `roster` subcommand for the markdown view.

The `/skill-report` slash command from 0.6.x has been retired -- both reports moved under `/skill-audit` because the namespace covers analysis broadly (single-skill audits, corpus-wide reports, future auto-fixes), matching the precedent set by `/references-audit` and `/cl`.

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

Sections are HTML `<details>`/`<summary>` -- expand and collapse interactively, no JavaScript required. The `skill-type` cell carries a hover tooltip describing the type's purpose, audit criterion, prohibited patterns, required frontmatter, and required contract-block fields. Tooltip content is authored from `schemas.py` and `framework.md`; the static table in the script body is the source of truth.

Corpus discovery is delegated to `skills-kit/scripts/_corpus.py` (see the "Shared discovery" section below), so the HTML and markdown views enumerate the same set of skills.

## Shared discovery: scripts/_corpus.py

The plugin-level `skills-kit/scripts/_corpus.py` module is the single source of truth for "what skills exist in this session's universe?" Both `skill_hierarchy_report.py` (HTML) and `skill-audit/scripts/report.py` (markdown roster dispatcher) consume it, so their corpora cannot diverge.

What `_corpus.discover_corpus()` returns:

- `SkillCorpus.user` -- list of `SkillRecord` from `~/.claude/skills/`.
- `SkillCorpus.project` -- list of `SkillRecord` from `<project-root>/.claude/skills/` (only when `project_root=` is supplied).
- `SkillCorpus.plugins` -- list of `PluginEntry`, one per active install per `installed_plugins.json`. Each `PluginEntry` has `name`, `marketplace`, `version`, `install_path`, and a `skills` list.

Each `SkillRecord` carries the parsed YAML frontmatter and (when present) the first fenced YAML block in the body, which is the type contract. `detect_skill_type(record)` returns `(skill_type, variant)` using the same rules both renderers apply.

The helper does not read CLAUDE.md, does not walk cwd-downward (the audit-flow `discover.py` scripts handle that, separately, with their own scope), and does not edit anything.

## Shared structural detectors: _shared.py

`_shared.py` exports the stdlib-only parsing primitives (`parse_frontmatter`, `parse_body`) and the structural detectors (`has_excuse_reality_table`, `count_ordered_steps`, `has_conditional_loading`, etc.) plus the `type_signals()` scoring function used by `audit.py` and `classify.py`. Per SSOT, the detectors live there exactly once.

`_shared.py` is intentionally narrower than `_corpus.py`: the audit / classify scripts work on a single SKILL.md path supplied by the user and don't need corpus-wide discovery. Likewise, `_corpus.py` does not implement structural detectors -- it stops at "find SKILL.md files and parse their frontmatter + first body YAML block."

When extending the heuristics (new structural marker, new type signal), modify `_shared.py` first, then add the row to whichever script consumes the new signal.

## Calibration history

The scripts are v1. Friction surfaced during smoke-testing on existing plugins-kit skills will feed Phase 4 calibration:

- The skill-authoring SKILL.md itself classifies as mixed-type because its orientation sections include ordered steps and a "recognize and split" callout. This is the SSOT-extension orientation-summary case in action -- the script flags for judgment, not for failure.
- The cache-report SKILL.md classifies as `indeterminate` because its content uses formatting the heuristics don't yet recognize (e.g. user-objective descriptions without ordered-list steps). Phase 4 audits will surface whether this is a heuristic gap or a genuine gap in the skill's structure.
- The bootstrap SKILL.md scores tied between technique-content and reference-content. It declares reference-skill but contains both shapes. This is a real mixed-type finding, separate from script calibration.
