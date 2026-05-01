---
_schema_version: 1
name: skill-audit
skill-type: technique-skill
description: Use when the user invokes /skill-audit to audit a SKILL.md against the framework's type contract and the content-allocation rules. Do NOT use for CLAUDE.md (use /claude-md-audit).
disable-model-invocation: true
user-invocable: true
argument-hint: "[file path, number(s) from list, or 'list']"
---

# Skill Audit

Audit a SKILL.md against the skill-authoring framework: the type contract from `framework.md` (validated mechanically by `audit.py`) and the cohesion-principles content-allocation rules from `content-allocation.md` (judged by the agent against the rules' testable criteria). Findings are grouped by Schema, CRP, CCP, ADP, and Hygiene.

The audit is idempotent: same input produces the same findings; addressing all FAIL findings produces a COMPLIANT verdict on the next run.

```yaml
technique_skill:
  _schema_version: "1"
  trigger_model: user-only
  identity: Audit a SKILL.md against the framework's type contract and the content-allocation rules.
  scope:
    covers:
      - auditing a SKILL.md against its declared type contract (schema validation)
      - auditing a SKILL.md against CRP / CCP / ADP placement rules
      - listing all SKILL.md files visible from cwd
      - producing a per-file compliance report and an overall summary
    excludes:
      - auditing CLAUDE.md files (use /claude-md-audit)
      - auditing reference docs in isolation (audited transitively via the SKILL.md they belong to)
      - making fixes; this skill reports, it does not edit
  techniques:
    - id: audit_skill_md
      name: Audit SKILL.md against framework + cohesion principles
      keywords: [audit skill.md, skill audit, contract validation, schema check, cohesion principles audit, CRP CCP ADP applied to skill, framework compliance, /skill-audit slash command]
      goal: Produce a per-file compliance report grouped by Schema / CCP / CRP / ADP / Hygiene findings, with a COMPLIANT or NON-COMPLIANT verdict per file.
      arguments:
        - name: TARGET
          required: false
          description: |
            One of:
              - (omitted)  -> audit <cwd>/SKILL.md (or fail with the cwd if none)
              - 'list'     -> show numbered list of SKILL.md files visible under cwd; do not audit
              - <path>     -> audit a specific SKILL.md
              - <numbers>  -> audit files by index from the most recent 'list' output (e.g. '3 7')
      preconditions:
        - The target SKILL.md exists and is readable.
        - The skills-kit plugin is installed (audit.py is reachable for schema validation; the cohesion-principle reference docs exist).
      steps:
        - n: 1
          action: Resolve the target SKILL.md set from $ARGUMENTS.
          tool: discover.py
          input: |
            If TARGET is 'list', run discover.py and emit the numbered list to the user; STOP.
            If TARGET is integer(s), run discover.py --json, map indices to paths, proceed.
            If TARGET is a path, use it directly.
            If TARGET is empty, use <cwd>/SKILL.md if it exists, else surface the cwd and stop.
          expected: A list of SKILL.md paths.
          on_failure: If no SKILL.md is found at the resolved location, surface the cwd and stop. Do not improvise a target.
        - n: 2
          action: Load the placement framework into context.
          tool: Read
          input: |
            content-allocation.md (in skills-kit:skill-authoring)
            (resolved via the skills-kit install path)
          expected: The CCP / CRP / ADP rules and per-artifact audit criteria are now loaded.
        - n: 3
          action: For each target SKILL.md, run skill-authoring's audit.py for schema and contract validation. Capture the structured output.
          tool: audit.py
          input: <path-to-SKILL.md> --json
          expected: JSON with per-row PASS / FAIL / JUDGMENT-REQUIRED verdicts for the universal description rules, the YAML contract validation, the type-specific contract rows, and the mixed-type signal.
          on_failure: If audit.py is unavailable (e.g. plugin venv missing), surface the limitation and proceed with the cohesion-principle audit only -- mark the Schema group as 'unavailable, agent should manually review the contract'.
        - n: 4
          action: For each target, read the SKILL.md and apply cohesion-principle judgment from content-allocation.md per_artifact_role.skill_md.audit_rules.
          expected: A finding list under CRP / CCP / ADP / Hygiene groups.
        - n: 5
          action: Where applicable, also audit the references/ directory ADP property -- one-hop-deep, no cross-cycles, no SKILL.md back-references. (audit.py covers some of this mechanically; surface any judgment-required cases for the agent to evaluate.)
          tool: Read
          input: each references/*.md path
          expected: ADP findings about the reference graph integrity.
        - n: 6
          action: Render the per-file report (see output_template), then the overall audit summary if multiple files were audited.
          expected: Markdown report in the user's chat.
      output_template: |
        ## <skill name> (<skill-type>) -- <file path>

        Lines: <N>

        ### Schema validation (audit.py output)
        [PASS|FAIL|JUDGMENT] <row>: <message>

        ### CCP findings (write-together / change cadence)
        [PASS|FAIL|INFO] <criterion>: <message>

        ### CRP findings (read-together / smallest reader-set)
        [PASS|FAIL|INFO] <criterion>: <message>

        ### ADP findings (link-forward-only / DAG)
        [PASS|FAIL|INFO] <criterion>: <message>

        ### Hygiene findings (universal: description requirements, exclusion clause, etc.)
        [PASS|FAIL|INFO] <criterion>: <message>

        ### Compliance

        <P> PASS | <F> FAIL | <I> INFO | <J> JUDGMENT-REQUIRED
        COMPLIANT | NON-COMPLIANT
      gotchas:
        - audit.py is the canonical mechanical validator for schema and type contracts. Do not re-implement its checks here; consume its JSON output and present it under the Schema group. The cohesion-principle judgment is what this skill adds.
        - "Cohesion-principle findings are judgment calls, not regex matches. CCP for SKILL.md asks: does this content change with the skill's contract, or with project conventions? Project-convention content bleeding into SKILL.md is a CCP-fail; the content belongs in CLAUDE.md."
        - "Decision provenance (Dec-N entries, audit-finding logs) does NOT belong in SKILL.md. If found, it is a CCP-fail -- decision history changes with audits, not with the skill's contract; the right home is the co-located CLAUDE.md."
        - The 500-line / 3000-token threshold for SKILL.md is a CRP-evaluation signal, not a verdict. Do not flag size alone as FAIL. Apply the CRP test from content-allocation.md "CRP is the test for L2 -> L3 splits."
        - audit.py's one-hop-deep references/ check is mechanical (ADP-A1). The agent need only confirm that mechanical pass and add judgment-level findings about cross-reference patterns the script cannot detect (e.g. a reference cited from SKILL.md that itself cites SKILL.md sections).
        - Idempotency: criteria are fixed; same input produces same output. Do not re-rank or re-order findings session-to-session.
      reference_section: content-allocation.md (in skills-kit:skill-authoring) (placement rules) and framework.md (in skills-kit:skill-authoring) (type contracts)
  reference_index:
    - id: content_allocation
      path: sibling skill-authoring -- content-allocation.md
      keywords: [content allocation rules, CRP CCP ADP placement, per-artifact audit rules, load graph DAG, skill md role audit rules]
      summary: The cohesion-principles placement framework. Loaded in step 2; rules under per_artifact_role.skill_md.audit_rules apply.
    - id: framework
      path: sibling skill-authoring -- framework.md
      keywords: [type contracts, description requirements, mixed-type, conditional requirements, audit procedure]
      summary: The type contracts. The audit.py invocation in step 3 validates against schemas.py which is canonical for these contracts.
```

## Argument grammar

- `(none)` -- audit `<cwd>/SKILL.md` if present.
- `list` -- show numbered list of SKILL.md files under cwd; do not audit.
- `<path>` -- audit a specific SKILL.md.
- `<numbers>` -- audit files by index from the most recent `list` output (e.g. `3 7`).

Typical workflow: `/skill-audit list` to see what's available, then `/skill-audit 3` to audit a specific skill.

## Decision rules

- Any FAIL finding -> file is NON-COMPLIANT.
- Only PASS, INFO, JUDGMENT-REQUIRED findings -> file is COMPLIANT (with judgment-required calls noted).
- INFO findings are advisory improvements, not compliance failures.
- INFO findings do not escalate to FAIL on subsequent runs.

## Cross-references

- Canonical placement framework: `content-allocation.md (in skills-kit:skill-authoring)`.
- Canonical type contracts: `framework.md (in skills-kit:skill-authoring)` and `plugins/skills-kit/skills/skill-authoring/scripts/schemas.py`.
- Mechanical validator: `plugins/skills-kit/skills/skill-authoring/scripts/audit.py`.
- Sibling audit skill: `/claude-md-audit` for CLAUDE.md files.
