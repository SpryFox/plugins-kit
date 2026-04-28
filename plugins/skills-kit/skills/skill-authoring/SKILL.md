---
_schema_version: 1
name: skill-authoring
skill-type: domain-skill
description: Use when authoring, auditing, or refining a Claude Code skill -- covers vocabulary, the five-type contract framework, principles, patterns, and a worked audit example. Do NOT use for invoking an existing skill or for general writing tasks unrelated to skill design.
---

# Skill Authoring

Skill authoring is the discipline of designing Claude Code skills that are auditable and robust. This domain owns the vocabulary, type contracts, and audit process for that work.

## Companion declaration

No sibling domains. The skill-authoring domain stands alone within plugins-kit. Future related domains (e.g. an authoring-rules discipline-skill, a per-type pattern-skill) would slot under this container.

## What this domain teaches

A skill is one of five types: **reference**, **pattern**, **technique**, **discipline**, **domain**. Each type has a contract that names its required blocks, required patterns, conditionally required patterns (with explicit testable criteria), and prohibited patterns. A skill is well-formed when it satisfies its type's contract. A skill spanning more than one type's content is **mixed-type** and needs to be split, not forced into a single contract.

The vocabulary (glossary) and the type contracts (framework) are the two halves of this domain. The glossary names primitives -- files, conventions, principles, patterns, types, attributes, sources. The framework binds those primitives into the contracts. Read glossary first, framework second.

## Authoring order

When building a new skill, follow the type-dependency graph from the framework's compositional-order section:

1. Reference-skill and pattern-skill -- atomic, no dependencies. Write these first.
2. Technique-skill -- composes references and patterns into procedure.
3. Discipline-skill -- wraps a target technique or pattern with rules + counters.
4. Domain-skill -- assemble only after the leaf members exist.

Top-down domain authoring tends to produce a long monolithic SKILL.md that should have been five small files plus an index. The domain-skill contract prohibits that shape.

## Auditing process

Run an audit in this order:

1. **Mixed-type check first.** Skills tend to grow organically across type boundaries; this is the most common audit finding. If the skill spans multiple types, the remedy is splitting along those boundaries -- not forcing the skill into a single type's contract.
2. **Identify the declared (or implicit) type.** If the skill claims none, infer from content shape.
3. **Run the contract checklist** for that type. Required blocks present? Required patterns applied? Any conditionally required pattern whose condition holds is present? Any prohibited pattern present?
4. **Run the audit's behavioral test.** Each contract names one (e.g. for technique-skill: can the agent apply the method to a novel scenario?).

See `references/example-audit.md` for a worked audit of a real skill, including the friction the audit surfaced about the framework itself.

## Behavioral guardrails

- **Do not declare a "recommended" pattern.** The framework has only required, conditionally required, and prohibited. Conditional requirements must carry an explicit, testable criterion. Fuzzy recommendations are a strictness leak.
- **Do not silently expand a skill across type boundaries.** When a reference-skill grows a workflow, or a discipline-skill grows a vocabulary block, the skill is becoming mixed-type. Recognize and split.
- **Do not invent frontmatter.** A SKILL.md without YAML frontmatter is flagged, not patched.
- **Do not rely on the description to summarize the workflow.** The description is a trigger, not a summary. Workflow lives in the body.
- **Do not assume Claude needs explanatory prose.** Every loaded paragraph justifies its tokens; remove content the agent doesn't need.

## Capabilities

Three scripts in `scripts/` support the audit / classify / tag operations. Full mechanics in `references/scripts.md`.

- **audit** -- run the deterministic contract checks against a SKILL.md.
  - Operation: `python scripts/audit.py <path>` (add `--json` for machine output).
  - Scope: per-row verdict against the declared skill-type's contract; flags judgment-required rows for the agent.
  - Reference: `references/scripts.md` (audit.py section).
- **classify** -- infer a SKILL.md's type from content shape.
  - Operation: `python scripts/classify.py <path>` (add `--json`).
  - Scope: scores all five canonical types and suggests one; flags mixed-type / ambiguous / indeterminate cases.
  - Reference: `references/scripts.md` (classify.py section).
- **tag** -- write a `skill-type:` value into a SKILL.md's frontmatter.
  - Operation: `python scripts/tag.py <path> <skill-type>` (add `--check` for dry-run, `--force` to overwrite).
  - Scope: idempotent in-place edit of frontmatter only; refuses to invent frontmatter.
  - Reference: `references/scripts.md` (tag.py section).

## Conditional Loading

Read the references when their keywords match your task:

- **Glossary** -> `references/glossary.md`
  Keywords: vocabulary, term, definition, files, conventions, patterns, principles, skill types, attributes, sources, glossary, CRP, CCP, ADP, SSOT, context efficiency, tool-call efficiency, inference efficiency, bottom-up composition, frontmatter, trigger, exclusion, rule, counter, step, checklist, example, gotcha, index, sub-agent binding, technique, capability.
- **Type contracts framework** -> `references/framework.md`
  Keywords: contract, type, required, conditionally required, prohibited, audit, reference-skill, pattern-skill, technique-skill, discipline-skill, domain-skill, IF THEN criterion, mixed-type, auditing process, compositional order, goals, auditability, robustness.
- **Worked audit example** -> `references/example-audit.md`
  Keywords: example audit, contract checklist applied, framework friction, real-world audit output, discipline-skill audit, mixed-type case study, verdict, friction observed.
- **Audit / classify / tag scripts** -> `references/scripts.md`
  Keywords: audit.py, classify.py, tag.py, scripts, deterministic checks, heuristic detectors, type inference, frontmatter tagging, mixed-type detection, judgment-required, idempotent, calibration, smoke-test, friction.
