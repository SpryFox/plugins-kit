---
name: cohesion-audit
author: christina
skill-type: domain-skill
description: Use when auditing a CLAUDE.md, SKILL.md, or skill cross-references against the cohesion framework. Do NOT use to author skills (use skill-authoring).
---

# Cohesion Audit

The domain for auditing LLM-facing artifacts against the cohesion framework (CCP / CRP / ADP). Say what you
want in natural language — "audit this CLAUDE.md", "check my SKILL.md", "find broken skill references",
"inventory the skills" — and this domain interprets the target and routes to the right audit. Each audit is
**also** directly invocable by its own slash command (below); this domain is the natural-language front door,
not a replacement for those commands.

The audits share one framework (vocabulary + data model). It currently lives in `skill-audit`'s `references/`
as the shared substrate; this domain references it there and routes among the members. The placement
principles every audit judges against live in the `cohesion-principles` skill (the spine).

## Routing

Pick the member by the artifact under audit. Each is an independent, self-contained skill that keeps its
own slash command — this table is the map, not a wrapper.

| You want to audit… | Member skill | Slash command | What it does |
|---|---|---|---|
| a **CLAUDE.md** (multi-file capable) | `claude-md-audit` | `/claude-md-audit` | CCP/CRP/ADP + hygiene + optional `claude_md:` schema; fans multi-file runs via the Workflow tool |
| a **CLAUDE.md** (single-loop, no fan-out) | `claude-md-audit-noworkflow` | `/claude-md-audit-noworkflow` | the preserved inline variant of the above |
| a **SKILL.md** (contract + cohesion) | `skill-audit` | `/skill-audit` | per-skill contract + CCP/CRP/ADP; also `roster` / `hierarchy` corpus inventory |
| **broken skill cross-references** | `references-audit` | `/references-audit` | scans markdown for dangling `/skill` refs and unresolved `skill:` hard deps |

## Domain contract

```yaml
domain_skill:
  _schema_version: "1"
  identity: The domain for auditing LLM-facing artifacts (CLAUDE.md, SKILL.md, skill cross-references) against the cohesion framework (CCP / CRP / ADP), routing natural-language audit intent to the right member skill.
  companions:
    siblings: []
    note: |
      No sibling domains in the audit area. Adjacent (non-sibling) skills the agent should know:
      skill-authoring (authoring the skills this domain audits) and cohesion-principles (the placement
      spine the audits judge against). This domain consumes those; it does not duplicate them.
  scope:
    covers:
      - interpreting natural-language audit intent and routing to the right member audit
      - orienting a fresh agent on which audit applies to which artifact
      - naming the members and the shared framework they operate under
    excludes:
      - authoring or refining skills (use skill-authoring)
      - deciding where content should live -- the placement question (use cohesion-principles)
      - the deep per-audit procedures, taxonomies, and remediation flows (they live in the member skills)
  orientation:
    summary: |
      Four member audits share one subject -- auditing LLM-facing artifacts against the cohesion
      framework -- and one shared framework (the audit-framework glossary + data model, which lives in
      skill-audit as the shared substrate). They differ by artifact: claude-md-audit (+ its noworkflow
      variant) for CLAUDE.md, skill-audit for SKILL.md, references-audit for cross-references. Route by
      the artifact under audit (see the Routing table). The members are independent skills with their own
      slash commands; this domain adds the natural-language entry and the map among them.
    behavioral_guardrails:
      - Route by artifact -- do not run a SKILL.md audit on a CLAUDE.md (or vice-versa); each member's contract is artifact-specific.
      - Detection and remediation are separate phases. The audit pass produces a verdict; it does not silently mutate the subject. Remediation is dispatched after, as its own work.
      - Size is a SIGNAL, not a verdict. An over-threshold file prompts a CRP evaluation (do sections serve different reading tasks?), never an automatic split. Defer to cohesion-principles and the CRP test.
      - This domain is the natural-language front door; the member slash commands remain the explicit entry points and are unchanged.
  index:
    references:
      - id: audit_framework
        path: skills-kit:skill-audit/references/audit-framework.md
        keywords: [audit framework, glossary, subject, primitive, composition, audit-kind, rule, finding, severity, taxonomy, bucket, corpus]
        summary: Canonical glossary for the audit family -- the vocabulary (subject / primitive / composition / discovery / audit-kind / rule / finding / severity / taxonomy / bucket / corpus / scaffolding) every member audit declares its subject and rules in terms of. Shared substrate; currently housed in skill-audit.
      - id: audit_framework_data
        path: skills-kit:skill-audit/references/audit-framework.yaml
        keywords: [audit framework data, primitives, compositions, audit-kind registry, rules per composition, machine-readable]
        summary: The machine-readable data side of the framework -- primitives, compositions, and the audit-kind registry (which rule ids bind to which compositions per audit-kind). Authoritative on divergence with the markdown tables.
    members:
      - name: claude-md-audit
        type: audit-skill
        ref: /claude-md-audit
        keywords: [claude.md audit, cohesion, ccp crp adp, workflow fan-out, multi-file]
      - name: claude-md-audit-noworkflow
        type: audit-skill
        ref: /claude-md-audit-noworkflow
        keywords: [claude.md audit, single-loop, no workflow, inline variant]
      - name: skill-audit
        type: audit-skill
        ref: /skill-audit
        keywords: [skill.md audit, contract, roster, hierarchy, inventory]
      - name: references-audit
        type: audit-skill
        ref: /references-audit
        keywords: [broken references, cross-reference scan, soft ref, hard dep]
```

## Cross-references

- **Placement spine (what the audits judge against)** — `cohesion-principles` (in skills-kit).
- **Authoring the skills this domain audits** — `/skill-authoring` (in skills-kit).
- **Members** — `/claude-md-audit`, `/claude-md-audit-noworkflow`, `/skill-audit`, `/references-audit`.
