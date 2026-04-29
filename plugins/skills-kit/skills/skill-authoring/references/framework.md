# Skill Types Framework

This document defines the **contracts** that skills in this project must
satisfy. Per SSOT, vocabulary lives in `skill-glossary.md` — types,
building blocks, patterns, principles, and attributes. Read the glossary
first; this document references entries by name without redefining them.

## Canonical contract surface (schema v1, locked 2026-04-28)

The **canonical** contract per skill type is the YAML schema declared in
`plugins/skills-kit/skills/skill-authoring/scripts/schemas.py`. Each
skill carries a `<type>:` YAML block in its SKILL.md body; the audit
script validates that block against the schema. A skill is well-formed
when its YAML contract block parses successfully against its type's
schema.

Schema v1 was locked after all six existing plugins-kit skills converted
cleanly (universal rows pass + schema-validation pass + single-root
deterministic mixed-type signal). Future schema changes ship as v2
alongside v1; the validator dispatches by `_schema_version:` in each
skill's YAML root.

The markdown tables in the **Type contracts** section below describe
the same contracts in human-readable form. They are kept for review
clarity and for skills not yet migrated, but the YAML schemas are
authoritative when the two diverge.

---

## Goals

Two properties skills should have. The framework's principles, patterns,
and contracts all derive from these.

**Auditability.** A skill is auditable when we can evaluate it against a
defined contract and mechanically identify deficiencies. Without a contract,
a skill is just markdown — no objective standard exists. With one, we can
flag missing required patterns, surface anti-patterns, and bring retroactive
order to skills that grew organically.

**Robustness.** A skill is robust when it behaves consistently across calls
and resists organic decay. Meeting a user's immediate goal in a skill is
often fast and easy; producing a robust skill is a separate discipline.
Robustness raises the floor — if a skill deserves to be in this project, it
deserves to be robust within the framework.

Pattern selection is guided by the principles defined in the glossary
(CRP, CCP, ADP, SSOT, bottom-up composition, concise is key). When this
document prohibits *monolithic content* in domain-skills, that's CCP. When
it requires *one hop deep* references, that's ADP. Patterns are the
concrete moves; principles are the reasoning that picks them.

---

## Conditional requirements

A *conditionally required* row in a contract specifies a pattern or block
that becomes mandatory when a stated condition holds. Every conditional
requirement carries an explicit, testable criterion — without one, the
requirement is not auditable and doesn't belong in this framework.

The structure:

> **IF** *condition* (testable by *criterion*) **THEN** *pattern or block is required*

Examples that follow this structure (used throughout the type contracts
below):

- *Progressive disclosure* required when SKILL.md body exceeds 500 lines
  or 3000 tokens. **Criterion:** line/token count of the SKILL.md body.
- *Workflow checklist* required when a technique has more than three
  steps. **Criterion:** count `step` blocks in the technique definition.
- *Sub-agent binding rule* required when a paired sub-agent exists.
  **Criterion:** check for a matching `<skill-name>-a` agent definition.
- *Vocabulary block* required when reference files use canonical terms not
  defined in SKILL.md. **Criterion:** scan reference files for repeated
  terms; check whether each is defined inline.

A conditional requirement without a testable criterion is a *recommendation*,
not a requirement. The framework deliberately omits a "recommended"
category — patterns are either required (always or under a stated
condition) or prohibited. If a real-world audit shows the strictness is
wrong, the contract gets revised; the framework doesn't accumulate fuzzy
middle ground.

---

## Description requirements

The frontmatter `description` is the only signal Claude uses to decide whether to load a skill. Every skill, regardless of type, must satisfy these:

- **Length: ≤160 characters.** A description that doesn't fit in 160 characters is summarizing capability rather than naming a trigger.
- **Form: directive.** Open with "Use when..." or "Invoke when...". Capability summaries ("Enables...", "Provides...", "Manages...") cause Claude to follow the description as a workflow instead of reading the body.
- **Condition: clear and unambiguous.** The trigger must name a specific situation when invocation is the right move. Vague conditions ("when you need help with X", "for any X work") are evidence the skill is doing too much or doesn't have a real role.
- **Cost-justified.** Every skill load is tokens and a tool-call boundary. A trigger that fires on topical adjacency ("...for any Python work...", "...whenever you read code...") violates the user's trust by burning tool calls without bringing value. Be specific about when the skill earns its load cost.
- **Exclusion clause: present.** Append a "Do NOT use for..." clause that bounds the activation surface. Positive triggers alone do not bound activation; the exclusion is what keeps adjacent skills from triggering each other's loads.

These requirements are universal -- they apply to every skill regardless of type contract. The auditing process checks them as the first step (after the mixed-type check).

## Content-form choice

YAML is the right shape for some content; prose is the right shape for other content. A skill chooses by asking "does this structure aid Claude's comprehension better than prose would?"

- **Use YAML** when the information is structurally repetitive: records with the same shape (facts, rules, capabilities, steps, references), lookup tables, indexes, contract data, anything with keywords routing per record. The chat-term relevance hint pattern only works when records have a discrete YAML shape carrying their own keywords.
- **Use prose** when the information is naturally narrative: an identity sentence, an orientation paragraph, a single-paragraph explanation that does not decompose into discrete records. Prose is the right shape for content that reads as one continuous thought rather than as a collection of routable items.
- **Embedded, not pure-YAML.** SKILL.md keeps a markdown wrapper -- title, identity sentence, brief orientation -- around fenced YAML blocks. Pure-YAML SKILL.md files are harder to skim during review and lose the orientation surface. The YAML carries the load-bearing contract; the markdown carries the priming.

YAML for the sake of YAML obscures content. If you cannot articulate why a piece of information is better as YAML than as prose, leave it as prose.

---

## Type contracts

A skill claiming a type must satisfy the **required** rows and the
**conditionally required** rows whose conditions hold. Glossary terms are
referenced by name; consult `skill-glossary.md` for definitions.

### reference-skill

| Contract | Items |
|---|---|
| **Required blocks** | SKILL.md file with frontmatter and trigger; ≥1 example; ≥1 gotcha |
| **Required patterns** | activation metadata, exclusion clause, in-skill examples, known gotchas, context efficiency |
| **Conditionally required patterns** | progressive disclosure — IF SKILL.md body exceeds 500 lines or 3000 tokens (criterion: line/token count); domain-specific organization — IF reference content covers more than one mutually-exclusive sub-domain (criterion: are sub-domains independently loadable without cross-references) |
| **Prohibited patterns** | adversarial pressure testing, rule + counter pairs, workflow checklists |
| **Audit** | Drop a fresh agent into a topic the skill covers. Does it retrieve and apply the right fact? Are gotchas current? |

Examples: `/bootstrap` (plugins-kit) — engine behavior reference, config schemas, remediation lookup tables. Generally: any skill that primarily collects facts, conventions, or syntax for retrieval.

### pattern-skill

| Contract | Items |
|---|---|
| **Required blocks** | SKILL.md file with frontmatter and trigger; recognition criteria; counter-example(s); ≥1 example |
| **Required patterns** | activation metadata, exclusion clause, explain-the-why, in-skill examples |
| **Prohibited patterns** | utility bundle, workflow checklist, rule + counter pairs |
| **Audit** | Does the agent recognize when to apply *and* when not? Counter-examples must be exercised. |

Examples: `flatten-with-flags`, `test-invariants`, `reducing-complexity` (from the obra/superpowers public skill set). The plugins-kit ecosystem currently has no pattern-skill — see the audit-gap note in this directory's audit reports.

### technique-skill

| Contract | Items |
|---|---|
| **Required blocks** | SKILL.md file with frontmatter and trigger; ≥1 technique with body content (ordered steps for agent-invoked techniques; behavior + examples for user-only / `disable-model-invocation: true` techniques where the technique IS the slash-command); ≥1 gotcha |
| **Required patterns** | activation metadata, exclusion clause, technique, known gotchas |
| **Conditionally required patterns** | ordered-step body — IF the skill is not user-only (criterion: frontmatter does not set `disable-model-invocation: true`); workflow checklist — IF the technique has more than 3 steps (criterion: count `step` blocks); utility bundle — IF the procedure has deterministic steps that would otherwise be regenerated each call (criterion: any step where output depends only on input); self-correcting loop — IF the procedure produces output that can be programmatically validated (criterion: a validator script or rubric exists); plan-validate-execute — IF the procedure has batch operations or irreversible side effects (criterion: any step that modifies external state at scale or is hard to undo) |
| **Prohibited patterns** | adversarial pressure testing |
| **Audit** | Can the agent apply the method to a novel scenario? Try variation and missing-information tests. |

Examples: `condition-based-waiting`, `root-cause-tracing` (from obra/superpowers); `/test-greeting`, `/cache-report`, `/local-code-review` (plugins-kit, all `trigger: user-only`).

### discipline-skill

| Contract | Items |
|---|---|
| **Required blocks** | SKILL.md file with frontmatter and trigger; ≥1 rule + counter pair; rationalization counter table |
| **Required patterns** | activation metadata, exclusion clause, adversarial pressure testing (applied to this skill's own rules — the rationalization counter table must reflect observed agent failures, not hypothetical ones), rationalization counter table, red flags list, control tuning (low freedom), explain-the-why on rules |
| **Conditionally required patterns** | autonomy calibration — IF the skill invokes specific tools whose autonomy scope matters (criterion: any `Bash` or external-tool invocation that should be pre-approved or restricted) |
| **Prohibited patterns** | high-freedom phrasing in rule statements; softening hedges that weaken a rule's core. Note: an exception clause that names a specific known legitimate case (e.g. "delete the user copy unless it intentionally diverges from the project version") is permitted — the rule's core stays sharp and the exception is bounded. |
| **Audit** | Does the rule hold under combined pressures (time + sunk cost + fatigue)? Run an adversarial subagent. |

Examples: TDD discipline (write test first; rationalization counters for "too simple to test", "tests after achieve the same purpose", etc.) is the canonical reference shape for this type. The plugins-kit ecosystem currently has no discipline-skill.

### domain-skill (container)

A skill claiming this type must satisfy all five required-floor blocks. A
skill missing any of them is not a domain-skill — it's a reference-skill
folder with friends.

| Contract | Items |
|---|---|
| **Required blocks (floor)** | SKILL.md file with frontmatter and trigger; identity sentence (one sentence stating what knowledge area this domain owns); companion declaration (explicit cross-references to sibling domains, or an explicit "no siblings"); orientation content (≥1 substantive section beyond the index — vocabulary, pipeline overview, behavioral guardrails, or capability menu); reference index (Conditional Loading section listing every reference file with a keyword cluster) |
| **Conditionally required blocks** | sub-agent binding rule — IF a paired `<skill-name>-a` agent exists (criterion: agent definition file present); tool inventory — IF the domain ships scripts (criterion: `scripts/` subdirectory present, or external tools cited in the SKILL.md); capability surface — IF the domain has procedural operations the agent is expected to execute (criterion: any operation named in the SKILL.md that the agent invokes); vocabulary block — IF reference files use canonical terms not defined in SKILL.md (criterion: scan reference files for repeated terms and check inline definition); output conventions — IF the domain has format expectations for agent output (criterion: any consistent expected format like clickable links, YAML, etc.); behavioral guardrails — IF the domain has known anti-patterns that have caused real failures (criterion: documented past failure modes); menu mechanic — IF the domain has multiple sub-domains (criterion: count of distinct sub-areas) |
| **Required patterns** | activation metadata, exclusion clause, domain-specific organization, conditional details |
| **Conditionally required patterns** | sub-agent binding (the `agent-bundled` attribute) — IF a paired sub-agent exists (same criterion as the binding-rule block); capability — IF the domain has procedural operations (same criterion as the capability-surface block) |
| **Prohibited** | monolithic prose content — meaty workflows, full reference text, or rules-with-counters belong in member skills (or in structured capability blocks), not in the container's prose; index without orientation — a SKILL.md that contains only a conditional-loading list is routing without priming, not aggregating |
| **Audit** | Does a fresh agent dropped into the domain (a) operate fluently in vocabulary and conventions without re-orientation, (b) find and load the right member skill when a specific trigger fires, (c) recognize the boundary between this domain and its declared companions? Is the index complete relative to the actual member set on disk? |

Examples: `/ue-python-api` (plugins-kit) — Unreal Editor automation domain with its own vocabulary, scripts, and reference set, paired with the `unreal-kit-a` agent.

---

## Compositional order

Authoring follows the type dependency graph:

1. **reference-skill** and **pattern-skill** — atomic, no dependencies. Write
   these first.
2. **technique-skill** — composes references and patterns into procedure.
3. **discipline-skill** — wraps a target technique or pattern with rules +
   counters.
4. **domain-skill** — assemble only after the leaf members exist.

Top-down domain-skill authoring tends to produce a long monolithic SKILL.md
that should have been five small files plus an index. The contract for
domain-skill explicitly prohibits this.

---

## Auditing an existing skill

**Mixed-type check first.** Before classifying or running a contract, check
whether the skill spans multiple types. A skill containing rule-and-counter
material *plus* lookup tables, or how-to-procedure *plus* recognition
criteria *plus* an aggregation index, is mixed-type. Mixed-type skills are
the most common audit finding because skills tend to grow organically
across type boundaries. The right remedy is splitting along those
boundaries, not forcing the skill into one type's contract. Audit each
type's content separately; the skill as currently written cannot pass any
single type's contract while it remains mixed.

If the skill is single-type, proceed:

1. **Identify the declared (or implicit) type.** If the skill claims none,
   infer from content shape.
2. **Run the contract checklist.** Required blocks present? Required
   patterns applied? Conditional requirements: do any conditions hold,
   and if so are the required patterns present? Any prohibited patterns?
3. **Run the audit criterion.** This is the behavioral test, not a static
   check.

Applied to the current `writing-skills`: it teaches discipline-skill
authoring (RED/GREEN/REFACTOR with adversarial subagents) and presents that
approach as universal. Under this framework that fits the discipline
contract correctly but is the wrong shape for the other four types. A
redraft should:

1. Assume the glossary.
2. Lead with this framework's contracts.
3. Scope the existing TDD/pressure-testing content to the discipline-skill
   contract.
4. Provide per-type contract checklists and audit criteria.

---

## Open questions

1. **Are the five types the right granularity?** Specifically, does
   collapsing the previous `script-skill` into `technique-skill` with a
   `trigger: user-only` attribute lose anything important about user-invoked
   workflows?
2. **Does `harness-targeted` deserve type status?** It changes the audit
   criterion (verify the harness reflects the change) more than other
   attributes do. Currently treated as an attribute.
3. **Are the prohibited patterns per type too strict?** Notably:
   discipline-skills currently prohibit hedging. Real rules often have
   legitimate exceptions; should the contract distinguish "rule" from
   "rule-with-exception"?
4. **Should the `index` block in domain-skills be machine-readable?** A YAML
   or table of `{name, trigger, file}` would enable automated audits.
