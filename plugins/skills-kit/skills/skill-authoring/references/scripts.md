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

## Shared module: _shared.py

`_shared.py` exports the parsing primitives (`parse_frontmatter`, `parse_body`) and the structural detectors (`has_excuse_reality_table`, `count_ordered_steps`, `has_conditional_loading`, etc.) plus the `type_signals()` scoring function. Per SSOT, the detectors live there exactly once; audit.py and classify.py import the same definitions.

When extending the heuristics (new structural marker, new type signal), modify `_shared.py` first, then add the row to whichever script consumes the new signal.

## Calibration history

The scripts are v1. Friction surfaced during smoke-testing on existing plugins-kit skills will feed Phase 4 calibration:

- The skill-authoring SKILL.md itself classifies as mixed-type because its orientation sections include ordered steps and a "recognize and split" callout. This is the SSOT-extension orientation-summary case in action -- the script flags for judgment, not for failure.
- The cache-report SKILL.md classifies as `indeterminate` because its content uses formatting the heuristics don't yet recognize (e.g. user-objective descriptions without ordered-list steps). Phase 4 audits will surface whether this is a heuristic gap or a genuine gap in the skill's structure.
- The bootstrap SKILL.md scores tied between technique-content and reference-content. It declares reference-skill but contains both shapes. This is a real mixed-type finding, separate from script calibration.
