# Skill Types Framework

This document defines the **contracts** that skills in this project must
satisfy. Per SSOT, vocabulary lives in `glossary.md` -- types,
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
cleanly. Future schema changes ship as v2 alongside v1; the validator dispatches by `_schema_version:` in each
skill's YAML root.

The structurally-repetitive framework content below is captured as YAML records. The "Type contracts" section retains markdown tables for human review; schemas.py is authoritative on divergence.

```yaml
framework:
  _schema_version: "1"
  scope:
    covers:
      - what every skill must satisfy regardless of type (description requirements, schemas-as-floors, content-form choice)
      - the framework's two design goals (auditability, robustness)
      - the conditional-requirement grammar
      - the audit procedure for an existing skill
      - open questions awaiting real-world friction signal
    excludes:
      - vocabulary (lives in glossary.md)
      - the 5 per-type contracts (kept as markdown tables below; canonical machine form in scripts/schemas.py)

  schemas_are_floors:
    keywords: [floors not ceilings, extras allowed, forbidden_keys, mixed-type drift, structure-friendly]
    summary: |
      The per-type YAML schemas validate the required minimum: which keys must be present, what their structure must be, and which prohibited keys signal cross-type drift. Authors may add load-bearing structured keys beyond what the schema enumerates -- e.g. an `exceptions:` list inside an anti-pattern entry, a `narration:` sub-block describing agent narration patterns inside a technique, a `false_positive_guardrails:` record inside a multi-agent review technique. The schema does not enumerate every key an author may use; it enumerates the floor that must be there.
      
      This matters because the framework biases toward structured data (see Content-form choice). Forbidding extras would push authors toward unstructured prose when they want to add legitimate structure the schema didn't anticipate. The schema is a contract on the floor, not a straitjacket on the ceiling.
      
      Mixed-type drift is detected via the explicit `forbidden_keys:` list on each schema (e.g. a `rules:` key inside `reference_skill:` is forbidden because rules belong to discipline-skills). Forbidden keys are deliberate cross-type signals; unknown keys not in the forbidden list are permitted.
    promoted_extensions:
      - field: anti_patterns
        applies_to: [technique_skill, discipline_skill]
        required: false
        record_shape: [id, name, keywords, why_it_seems_right, why_it_is_wrong, alternative]
        rationale: |
          Anti-patterns are the canonical example of "structure asserts." Containment in
          a list of records carrying these specific keys implicitly asserts every item
          is a real anti-pattern; a markdown bullet list carries no such assertion. A
          common-enough load-bearing extension was promoted to a first-class optional
          field on the two skill types whose surface (procedure or rule) frequently
          benefits from naming the lookalike-but-wrong moves an agent would reach for.
        keywords: [anti-pattern record, named anti-patterns, lookalike-but-wrong, structured assertion, technique-skill optional, discipline-skill optional]

  framework_goals:
    - id: auditability
      keywords: [auditable, contract, mechanical evaluation, deficiency, retroactive order]
      summary: "A skill is auditable when we can evaluate it against a defined contract and mechanically identify deficiencies."
      detail: |
        Without a contract, a skill is just markdown -- no objective standard exists. With one, we can flag missing required patterns, surface anti-patterns, and bring retroactive order to skills that grew organically.
    - id: robustness
      keywords: [robust, consistent across calls, organic decay, raise the floor]
      summary: "A skill is robust when it behaves consistently across calls and resists organic decay."
      detail: |
        Meeting a user's immediate goal in a skill is often fast and easy; producing a robust skill is a separate discipline. Robustness raises the floor -- if a skill deserves to be in this project, it deserves to be robust within the framework.

  conditional_requirements:
    keywords: [conditional requirement, testable criterion, IF-THEN, no recommended category]
    grammar: |
      A *conditionally required* row in a contract specifies a pattern or block that becomes mandatory when a stated condition holds. Every conditional requirement carries an explicit, testable criterion -- without one, the requirement is not auditable and doesn't belong in this framework.
      
      The structure:
      
      **IF** *condition* (testable by *criterion*) **THEN** *pattern or block is required*
    examples:
      - rule: progressive disclosure required when SKILL.md body exceeds 500 lines or 3000 tokens
        criterion: line/token count of the SKILL.md body
      - rule: workflow checklist required when a technique has more than three steps
        criterion: count `step` blocks in the technique definition
      - rule: sub-agent binding rule required when a paired sub-agent exists
        criterion: check for a matching <skill-name>-a agent definition
      - rule: vocabulary block required when reference files use canonical terms not defined in SKILL.md
        criterion: scan reference files for repeated terms; check whether each is defined inline
    no_recommended_category: |
      A conditional requirement without a testable criterion is a *recommendation*, not a requirement. The framework deliberately omits a "recommended" category -- patterns are either required (always or under a stated condition) or prohibited. If a real-world audit shows the strictness is wrong, the contract gets revised; the framework doesn't accumulate fuzzy middle ground.

  description_requirements:
    keywords: [description requirements, frontmatter, universal, cost-justified, clear condition]
    intro: |
      The frontmatter `description` is the only signal Claude uses to decide whether to load a skill. Every skill, regardless of type, must satisfy these:
    rules:
      - id: length
        keywords: [length budget, 160 chars, summarizing capability vs trigger]
        rule: "Length: <=160 characters."
        why: "A description that doesn't fit in 160 characters is summarizing capability rather than naming a trigger."
      - id: form
        keywords: [directive, use when, invoke when, capability summary anti-pattern]
        rule: "Form: directive."
        why: "Open with 'Use when...' or 'Invoke when...'. Capability summaries ('Enables...', 'Provides...', 'Manages...') cause Claude to follow the description as a workflow instead of reading the body."
      - id: condition
        keywords: [clear condition, unambiguous trigger, vague trigger anti-pattern]
        rule: "Condition: clear and unambiguous."
        why: "The trigger must name a specific situation when invocation is the right move. Vague conditions ('when you need help with X', 'for any X work') are evidence the skill is doing too much or doesn't have a real role."
      - id: cost_justified
        keywords: [cost-justified, tool-call boundary, topical adjacency, over-aggressive trigger]
        rule: "Cost-justified."
        why: "Every skill load is tokens and a tool-call boundary. A trigger that fires on topical adjacency ('...for any Python work...', '...whenever you read code...') violates the user's trust by burning tool calls without bringing value. Be specific about when the skill earns its load cost."
      - id: exclusion_clause
        keywords: [exclusion clause, do-not-use-for, bound activation surface]
        rule: "Exclusion clause: present."
        why: "Append a 'Do NOT use for...' clause that bounds the activation surface. Positive triggers alone do not bound activation; the exclusion is what keeps adjacent skills from triggering each other's loads."
    universal: |
      These requirements are universal -- they apply to every skill regardless of type contract. The auditing process checks them as the first step (after the mixed-type check).

  content_form_choice:
    keywords: [yaml default, prose exception, embedded not pure-yaml, structure-carries-assertions]
    intro: |
      The default for LLM-facing content is structured YAML. Skills are runtime context for Claude (Audience-Claude); structure aids Claude's comprehension and enables routing, keyword matching, and validation that prose cannot. **When in doubt, bias toward structured data.**
    rules:
      - id: use_yaml_by_default
        keywords: [yaml default, structured data, records, lookup tables, indexes]
        rule: "Use YAML by default for LLM-facing content"
        detail: |
          Records with the same shape (facts, rules, capabilities, steps, references, anti-patterns, gotchas), lookup tables, indexes, contract data, anything where keywords route per record. Structure carries assertions prose cannot -- an `anti_patterns:` list with each entry as a record asserts implicitly that every item is genuinely an anti-pattern; a markdown bullet list carries no such assertion.
      - id: use_prose_only_when
        keywords: [prose exception, naturally narrative, bar for prose, articulate why]
        rule: "Use prose only when the content is naturally narrative or hierarchy carries no meaning"
        detail: |
          (a) the content is naturally narrative -- an identity sentence, an orientation paragraph, a single-paragraph explanation that does not decompose into discrete records; or (b) the hierarchy carries no meaning over prose. The bar for prose is "I can articulate why this would be worse as YAML." If you cannot articulate that, default to YAML.
      - id: embedded_not_pure_yaml
        keywords: [embedded yaml, markdown wrapper, orientation surface, pure yaml anti-pattern]
        rule: "Embedded YAML in markdown, not pure-YAML SKILL.md"
        detail: |
          SKILL.md keeps a markdown wrapper -- title, identity sentence, brief orientation -- around fenced YAML blocks. Pure-YAML SKILL.md files are harder to skim during review and lose the orientation surface. The YAML carries the load-bearing contract; the markdown carries the priming.
    note_on_old_default: |
      The previous default ("if unclear, prose") was wrong-direction for an Audience-Claude framework. Structure is the default; prose is the documented exception.

  compositional_order:
    keywords: [dependency graph, bottom-up composition, atomic primitives, type order]
    intro: |
      Authoring follows the type dependency graph:
    steps:
      - n: 1
        types: [reference-skill, pattern-skill]
        guidance: "Atomic, no dependencies. Write these first."
      - n: 2
        types: [technique-skill]
        guidance: "Composes references and patterns into procedure."
      - n: 3
        types: [discipline-skill]
        guidance: "Wraps a target technique or pattern with rules + counters."
      - n: 4
        types: [domain-skill]
        guidance: "Assemble only after the leaf members exist."
    anti_pattern: |
      Top-down domain-skill authoring tends to produce a long monolithic SKILL.md that should have been five small files plus an index. The contract for domain-skill explicitly prohibits this.

  auditing_procedure:
    keywords: [audit procedure, mixed-type check, contract checklist, audit criterion]
    mixed_type_check:
      keywords: [mixed-type check, common audit finding, split along boundaries]
      detail: |
        Before classifying or running a contract, check whether the skill spans multiple types. A skill containing rule-and-counter material *plus* lookup tables, or how-to-procedure *plus* recognition criteria *plus* an aggregation index, is mixed-type. Mixed-type skills are the most common audit finding because skills tend to grow organically across type boundaries. The right remedy is splitting along those boundaries, not forcing the skill into one type's contract. Audit each type's content separately; the skill as currently written cannot pass any single type's contract while it remains mixed.
    steps:
      - n: 1
        action: identify the declared (or implicit) type
        detail: "If the skill claims none, infer from content shape."
      - n: 2
        action: run the contract checklist
        detail: "Required blocks present? Required patterns applied? Conditional requirements: do any conditions hold, and if so are the required patterns present? Any prohibited patterns?"
      - n: 3
        action: run the audit criterion
        detail: "This is the behavioral test, not a static check."
    worked_example_writing_skills: |
      Applied to the current `writing-skills`: it teaches discipline-skill authoring (RED/GREEN/REFACTOR with adversarial subagents) and presents that approach as universal. Under this framework that fits the discipline contract correctly but is the wrong shape for the other four types. A redraft should:
      
      1. Assume the glossary.
      2. Lead with this framework's contracts.
      3. Scope the existing TDD/pressure-testing content to the discipline-skill contract.
      4. Provide per-type contract checklists and audit criteria.

  open_questions:
    - id: q1_five_types_granularity
      keywords: [five types, granularity, technique-skill user-only attribute, script-skill collapse]
      question: "Are the five types the right granularity?"
      context: |
        Specifically, does collapsing the previous `script-skill` into `technique-skill` with a `trigger: user-only` attribute lose anything important about user-invoked workflows?
    - id: q2_harness_targeted_type_status
      keywords: [harness-targeted, type vs attribute, audit criterion change]
      question: "Does `harness-targeted` deserve type status?"
      context: |
        It changes the audit criterion (verify the harness reflects the change) more than other attributes do. Currently treated as an attribute.
    - id: q3_prohibited_patterns_strictness
      keywords: [prohibited patterns, discipline hedge prohibition, rule-with-exception]
      question: "Are the prohibited patterns per type too strict?"
      context: |
        Notably: discipline-skills currently prohibit hedging. Real rules often have legitimate exceptions; should the contract distinguish "rule" from "rule-with-exception"?
    - id: q4_index_block_machine_readable
      keywords: [index machine-readable, conditional loading, automated audit of index]
      question: "Should the `index` block in domain-skills be machine-readable?"
      context: |
        A YAML or table of `{name, trigger, file}` would enable automated audits.
```

## Type contracts

A skill claiming a type must satisfy the **required** rows and the
**conditionally required** rows whose conditions hold. Glossary terms are
referenced by name; consult `glossary.md` for definitions.

Tables are kept for human review; the canonical machine-readable contract is in `plugins/skills-kit/skills/skill-authoring/scripts/schemas.py`. When the two diverge, schemas.py wins; the table gets updated to match.

### reference-skill

| Contract | Items |
|---|---|
| **Required blocks** | SKILL.md file with frontmatter and trigger; >=1 example; >=1 gotcha |
| **Required patterns** | activation metadata, exclusion clause, in-skill examples, known gotchas, context efficiency |
| **Conditionally required patterns** | progressive disclosure -- IF SKILL.md body exceeds 500 lines or 3000 tokens (criterion: line/token count); domain-specific organization -- IF reference content covers more than one mutually-exclusive sub-domain (criterion: are sub-domains independently loadable without cross-references) |
| **Prohibited patterns** | adversarial pressure testing, rule + counter pairs, workflow checklists |
| **Audit** | Drop a fresh agent into a topic the skill covers. Does it retrieve and apply the right fact? Are gotchas current? |

Examples: `/bootstrap` (plugins-kit) -- engine behavior reference, config schemas, remediation lookup tables. Generally: any skill that primarily collects facts, conventions, or syntax for retrieval.

### pattern-skill

| Contract | Items |
|---|---|
| **Required blocks** | SKILL.md file with frontmatter and trigger; recognition criteria; counter-example(s); >=1 example |
| **Required patterns** | activation metadata, exclusion clause, explain-the-why, in-skill examples |
| **Prohibited patterns** | utility bundle, workflow checklist, rule + counter pairs |
| **Audit** | Does the agent recognize when to apply *and* when not? Counter-examples must be exercised. |

Examples: `flatten-with-flags`, `test-invariants`, `reducing-complexity` (from the obra/superpowers public skill set). The plugins-kit ecosystem currently has no pattern-skill -- see the audit-gap note in this directory's audit reports.

### technique-skill

| Contract | Items |
|---|---|
| **Required blocks** | SKILL.md file with frontmatter and trigger; >=1 technique with ordered-step body (`steps:` list, min 1 step); >=1 gotcha. `output_template:` is an optional companion to `steps:` carrying the output-shape contract for the agent's reply -- not a substitute for steps. Even user-only slash-command skills reduce to a 1-step procedure ("invoke command; render output") and write that step explicitly. |
| **Required patterns** | activation metadata, exclusion clause, technique, known gotchas |
| **Conditionally required patterns** | workflow checklist -- IF the technique has more than 3 steps (criterion: count `step` blocks); utility bundle -- IF the procedure has deterministic steps that would otherwise be regenerated each call (criterion: any step where output depends only on input); self-correcting loop -- IF the procedure produces output that can be programmatically validated (criterion: a validator script or rubric exists); plan-validate-execute -- IF the procedure has batch operations or irreversible side effects (criterion: any step that modifies external state at scale or is hard to undo) |
| **Prohibited patterns** | adversarial pressure testing |
| **Audit** | Can the agent apply the method to a novel scenario? Try variation and missing-information tests. |

Examples: `condition-based-waiting`, `root-cause-tracing` (from obra/superpowers); `/test-greeting`, `/cache-report`, `/local-code-review` (plugins-kit, all `trigger: user-only`).

### discipline-skill

| Contract | Items |
|---|---|
| **Required blocks** | SKILL.md file with frontmatter and trigger; >=1 rule + counter pair; rationalization counter table |
| **Required patterns** | activation metadata, exclusion clause, adversarial pressure testing (applied to this skill's own rules -- the rationalization counter table must reflect observed agent failures, not hypothetical ones), rationalization counter table, red flags list, control tuning (low freedom), explain-the-why on rules |
| **Conditionally required patterns** | autonomy calibration -- IF the skill invokes specific tools whose autonomy scope matters (criterion: any `Bash` or external-tool invocation that should be pre-approved or restricted) |
| **Prohibited patterns** | high-freedom phrasing in rule statements; softening hedges that weaken a rule's core. Note: an exception clause that names a specific known legitimate case (e.g. "delete the user copy unless it intentionally diverges from the project version") is permitted -- the rule's core stays sharp and the exception is bounded. |
| **Audit** | Does the rule hold under combined pressures (time + sunk cost + fatigue)? Run an adversarial subagent. |

Examples: TDD discipline (write test first; rationalization counters for "too simple to test", "tests after achieve the same purpose", etc.) is the canonical reference shape for this type. The plugins-kit ecosystem currently has no discipline-skill.

### domain-skill (container)

A skill claiming this type must satisfy all five required-floor blocks. A
skill missing any of them is not a domain-skill -- it's a reference-skill
folder with friends.

| Contract | Items |
|---|---|
| **Required blocks (floor)** | SKILL.md file with frontmatter and trigger; identity sentence (one sentence stating what knowledge area this domain owns); companion declaration (explicit cross-references to sibling domains, or an explicit "no siblings"); orientation content (>=1 substantive section beyond the index -- vocabulary, pipeline overview, behavioral guardrails, or capability menu); reference index (Conditional Loading section listing every reference file with a keyword cluster) |
| **Conditionally required blocks** | sub-agent binding rule -- IF a paired `<skill-name>-a` agent exists (criterion: agent definition file present); tool inventory -- IF the domain ships scripts (criterion: `scripts/` subdirectory present, or external tools cited in the SKILL.md); capability surface -- IF the domain has procedural operations the agent is expected to execute (criterion: any operation named in the SKILL.md that the agent invokes); vocabulary block -- IF reference files use canonical terms not defined in SKILL.md (criterion: scan reference files for repeated terms and check inline definition); output conventions -- IF the domain has format expectations for agent output (criterion: any consistent expected format like clickable links, YAML, etc.); behavioral guardrails -- IF the domain has known anti-patterns that have caused real failures (criterion: documented past failure modes); menu mechanic -- IF the domain has multiple sub-domains (criterion: count of distinct sub-areas) |
| **Required patterns** | activation metadata, exclusion clause, domain-specific organization, conditional details |
| **Conditionally required patterns** | sub-agent binding (the `agent-bundled` attribute) -- IF a paired sub-agent exists (same criterion as the binding-rule block); capability -- IF the domain has procedural operations (same criterion as the capability-surface block) |
| **Prohibited** | monolithic prose content -- meaty workflows, full reference text, or rules-with-counters belong in member skills (or in structured capability blocks), not in the container's prose; index without orientation -- a SKILL.md that contains only a conditional-loading list is routing without priming, not aggregating |
| **Audit** | Does a fresh agent dropped into the domain (a) operate fluently in vocabulary and conventions without re-orientation, (b) find and load the right member skill when a specific trigger fires, (c) recognize the boundary between this domain and its declared companions? Is the index complete relative to the actual member set on disk? |

Examples: `/ue-python-api` (plugins-kit) -- Unreal Editor automation domain with its own vocabulary, scripts, and reference set, paired with the `unreal-kit-a` agent.
