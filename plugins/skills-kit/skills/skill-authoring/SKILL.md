---
_schema_version: 1
name: skill-authoring
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
        keywords: [audit.py, classify.py, tag.py, schemas.py, scripts, deterministic checks, heuristic detectors, type inference, frontmatter tagging, mixed-type detection, judgment-required, idempotent, calibration, smoke-test, friction]
        summary: Audit, classify, tag script reference -- usage, output verdicts, gotchas, calibration history.
      - id: patterns_actions
        path: references/patterns-actions.md
        keywords: [actions pattern, multi-step recipe, YAML steps, capture, tell_user, facade script, narration, deterministic execution, ordered sequence, sub-domain action, capability action]
        summary: Actions pattern -- YAML step sequences for deterministic multi-step recipes, paired with facade scripts when batching 3+ tool calls.
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
