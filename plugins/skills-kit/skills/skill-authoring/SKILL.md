---
_schema_version: 1
name: skill-authoring
author: christina
skill-type: domain-skill
description: Use when authoring, auditing, or refining a Claude Code skill. Do NOT use for invoking existing skills or for general writing tasks.
---

# Skill Authoring

Skill authoring is the discipline of designing Claude Code skills that are auditable and robust. This domain owns the vocabulary, type contracts, and audit process for that work.

The contract data below is the load-bearing surface; the markdown text above is orientation. To reach a specific record, match user-language phrasing against the `keywords:` clusters in the YAML.

```yaml
domain_skill:
  _schema_version: "1"
  identity: Skill authoring is the discipline of designing Claude Code skills that are auditable and robust.
  companions:
    siblings: []
    note: No siblings within plugins-kit. Future related domains (an authoring-rules discipline-skill, a per-type pattern-skill) would slot under this container.
  scope:
    covers:
      - authoring a new skill of any of the five canonical types
      - auditing an existing skill against its declared type contract
      - tagging a skill's frontmatter with a skill-type value
      - validating a skill's YAML contract block against the type schema
    excludes:
      - invoking existing skills (use the skill itself)
      - general writing tasks unrelated to skill design
  orientation:
    summary: |
      Five skill types: reference, pattern, technique, discipline, domain. Each has a contract.
      A skill is well-formed when its YAML contract block parses against its type's schema. A
      skill containing more than one type's contract data is mixed-type; the remedy is splitting
      along those boundaries, not forcing the skill into a single type. Read glossary first
      (vocabulary), framework second (contracts), example-audit third (worked example).
    behavioral_guardrails:
      - 'Do not declare a "recommended" pattern. Only required, conditionally required, prohibited.'
      - Do not silently expand a skill across type boundaries. Recognize and split.
      - Do not invent frontmatter. A SKILL.md without YAML frontmatter is flagged, not patched.
      - Do not rely on the description to summarize the workflow. The description is a trigger, not a summary.
      - Do not assume Claude needs explanatory prose. Every loaded paragraph justifies its tokens.
      - 'Do not YAML content that does not benefit from structure. YAML is the right shape for records, tables, indexes, contract data; prose is the right shape for identity sentences, orientation paragraphs, and narrative explanations. Test "does this structure aid Claude''s comprehension better than prose would?" If the answer is unclear, prose is the default.'
      - 'Do not leave multi-tool-call operations or inference-based decision trees unscripted. Skills replace inference with deterministic Python scaffolding wherever the operation is repeatable. A skill whose body says "for each X, check Y, then decide Z" is a script waiting to be written; the body should describe when to run the scaffolding and how to interpret its output, not re-derive the decision tree per session.'
  index:
    references:
      - id: glossary
        path: references/glossary.md
        keywords: [vocabulary, term, definition, files, conventions, patterns, principles, skill types, attributes, sources, glossary, CRP, CCP, ADP, SSOT, audience-claude, chat-term relevance hints, context efficiency, tool-call efficiency, inference efficiency, bottom-up composition, frontmatter, trigger, exclusion, rule, counter, step, checklist, example, gotcha, index, sub-agent binding, technique, capability]
        summary: Canonical terms; read first. Defines the primitives every other reference assumes.
      - id: framework
        path: references/framework.md
        keywords: [contract, type, required, conditionally required, prohibited, audit, reference-skill, pattern-skill, technique-skill, discipline-skill, domain-skill, IF THEN criterion, mixed-type, auditing process, compositional order, goals, auditability, robustness, description requirements]
        summary: Type contracts; read after glossary. Names what each type must, may, and must not contain.
      - id: example_audit
        path: references/example-audit.md
        keywords: [example audit, contract checklist applied, framework friction, real-world audit output, discipline-skill audit, mixed-type case study, verdict, friction observed]
        summary: Worked audit of a real skill, with the friction the framework surfaces about itself.
      - id: scripts
        path: references/scripts.md
        keywords: [audit.py, classify.py, tag.py, schemas.py, skill_hierarchy_report.py, _corpus.py, _shared.py, scripts, deterministic checks, heuristic detectors, type inference, frontmatter tagging, mixed-type detection, judgment-required, idempotent, calibration, smoke-test, friction, hierarchy report, HTML report, shared discovery, skill enumeration, marketplace grouping, available-skills surface, installed_plugins.json, skill-type tooltip]
        summary: Audit, classify, tag, and hierarchy-report script reference -- usage, output verdicts, gotchas, calibration history, plus the plugin-level _corpus.py shared discovery module.
      - id: patterns_actions
        path: references/patterns-actions.md
        keywords: [actions pattern, multi-step recipe, YAML steps, capture, tell_user, facade script, narration, deterministic execution, ordered sequence, sub-domain action, capability action]
        summary: Actions pattern -- YAML step sequences for deterministic multi-step recipes, paired with facade scripts when batching 3+ tool calls.
      - id: domain_layering
        path: references/domain-layering.md
        keywords: [sub-domain layering, greeting menu, argument dispatch, overview request detection, sub-domain registration, sub-agent dispatch, agent-bundled, bare invocation, capability menu, multi-area domain]
        summary: Domain layering -- bare-invocation greeting, argument dispatch, overview-vs-action detection, sub-domain registration, and sub-agent dispatch convention for domain-skills with 2+ sub-areas.
      - id: subdomain_schema
        path: references/subdomain-schema.md
        keywords: [subdomain config schema, state terms, operations, scope axes, canonical phrasing, llm-dependent content, dependency order, sub-area record, capability-skill subdomain config, vocabulary contract]
        summary: Sub-domain config schema -- per-sub-area structural fields (state_terms / operations / scope_axes / canonical_phrasing / llm_dependent_content / dependency_order) for capability-skills with 2+ sub-areas.
      - id: query_tool_pattern
        path: references/query-tool-pattern.md
        keywords: [query tool facade, lookup tool, gazetteer, did-you-mean, YAML output, spelling discovery, exact match modes, substring enumeration, canonical spelling]
        summary: Query-tool facade pattern -- single CLI with multiple lookup modes, did-you-mean on miss, YAML output, spelling-discovery discipline; replaces ad-hoc greps and spelling-from-memory.
  capabilities:
    - id: audit
      keywords: [audit, contract check, validate skill, run audit, schema validation]
      description: Run deterministic contract checks against a SKILL.md.
      operation: python scripts/audit.py <path>
      tool: scripts/audit.py
      scope_axes: [single-skill]
      reference_section: scripts.md (audit.py)
    - id: classify
      keywords: [classify, infer type, type detection, mixed-type detection, suggest type]
      description: Infer a SKILL.md's type from content shape and YAML root.
      operation: python scripts/classify.py <path>
      tool: scripts/classify.py
      scope_axes: [single-skill]
      reference_section: scripts.md (classify.py)
    - id: tag
      keywords: [tag, write skill-type, frontmatter tagging, idempotent skill-type write]
      description: Write a skill-type value into a SKILL.md's frontmatter idempotently.
      operation: python scripts/tag.py <path> <skill-type>
      tool: scripts/tag.py
      scope_axes: [single-skill]
      reference_section: scripts.md (tag.py)
  tools:
    - name: audit
      command: python scripts/audit.py
      description: YAML-first schema validator with markdown-heuristic fallback for legacy skills.
    - name: classify
      command: python scripts/classify.py
      description: Type inference across the five canonical skill types.
    - name: tag
      command: python scripts/tag.py
      description: Idempotent frontmatter tagger; refuses to invent or overwrite without --force.
```

The corpus-wide hierarchy report lives in the sibling `/skill-audit` skill: invoke `/skill-audit hierarchy` for the interactive HTML browser, `/skill-audit roster` for the markdown roster.
