---
_schema_version: 1
name: claude-md-audit
skill-type: technique-skill
description: Use when the user invokes /claude-md-audit to audit a CLAUDE.md against the cohesion-principles content-allocation framework. Do NOT use for SKILL.md files (use /skill-audit).
user-invocable: true
argument-hint: "[file path, number(s) from list, or 'list']"
---

# CLAUDE.md Audit

Audit a CLAUDE.md (root, subsystem, directory, or `.local`) against the cohesion-principles content-allocation framework. Findings are grouped by principle: CCP (write-together / change cadence), CRP (read-together / smallest correct scope), ADP (link-forward-only / DAG), plus universal hygiene rules.

The audit is idempotent: same input produces the same findings; addressing all FAIL findings produces a COMPLIANT verdict on the next run.

```yaml
technique_skill:
  _schema_version: "1"
  trigger_model: user-only
  identity: Audit a CLAUDE.md against the cohesion-principles content-allocation framework.
  scope:
    covers:
      - auditing a CLAUDE.md / CLAUDE.local.md against CRP / CCP / ADP placement rules
      - listing all CLAUDE.md files visible from the current working directory
      - producing a per-file compliance report and an overall summary
    excludes:
      - auditing SKILL.md files (use /skill-audit)
      - auditing reference docs (audited transitively via the SKILL.md they belong to)
      - making fixes; this skill reports, it does not edit
  techniques:
    - id: audit_claude_md
      name: Audit CLAUDE.md against cohesion principles
      keywords: [audit claude.md, claude.md compliance, cohesion principles audit, CRP CCP ADP audit, content allocation audit, claude.md placement, claude.md hierarchy review, claude-md-audit slash command]
      goal: Produce a per-file compliance report grouped by CCP / CRP / ADP / hygiene findings, with a COMPLIANT or NON-COMPLIANT verdict per file.
      arguments:
        - name: TARGET
          required: false
          description: |
            One of:
              - (omitted)  -> audit <cwd>/CLAUDE.md
              - 'list'     -> show numbered list of CLAUDE.md files visible from cwd; do not audit
              - <path>     -> audit a specific CLAUDE.md or CLAUDE.local.md
              - <numbers>  -> audit files by index from the most recent 'list' output (e.g. '3 7 9')
      preconditions:
        - The target file exists and is readable.
        - The user is in a project directory (cwd) so role classification works.
      steps:
        - n: 1
          action: Resolve the target file set from $ARGUMENTS.
          tool: discover.py
          input: |
            If TARGET is 'list', run discover.py and emit the numbered list to the user; STOP.
            If TARGET is integer(s), run discover.py --json, map indices to paths, proceed.
            If TARGET is a path, use it directly.
            If TARGET is empty, use <cwd>/CLAUDE.md.
          expected: A list of (path, role) tuples where role is one of root / ancestor / child / local.
          on_failure: If no CLAUDE.md is found at the resolved location, surface the cwd and stop. Do not improvise a target.
        - n: 2
          action: Load the audit criteria reference into context.
          tool: Read
          input: references/audit-criteria.md (relative to this skill's install path)
          expected: The CCP / CRP / ADP / hygiene criteria are now loaded.
        - n: 3
          action: For each target file, read it and (if its role is child / directory) read the relevant parent CLAUDE.md as well.
          tool: Read
          expected: The file content is in context, plus any ancestor needed for CCP cross-file duplication checks.
        - n: 4
          action: For each target file, apply the criteria from references/audit-criteria.md according to the role-to-criteria map. Produce findings tagged with their group (CCP / CRP / ADP / Hygiene) and severity (FAIL / INFO / PASS).
          expected: A finding list per file.
        - n: 5
          action: For files carrying a `claude_md:` YAML contract block, additionally invoke skill-authoring's audit.py for schema validation. Merge those results into the per-file finding list under a 'Schema validation' group.
          tool: audit.py
          input: <path-to-CLAUDE.md>
          expected: Schema validation findings appended.
          on_failure: If audit.py is unavailable (e.g. plugin venv missing), surface the limitation and continue with the cohesion-principle audit only.
        - n: 6
          action: Render the per-file report (see output_template), then the overall audit summary if multiple files were audited.
          expected: Markdown report in the user's chat.
      output_template: |
        ## <file path> (<role>)

        Lines: <N> (<size assessment>)

        ### CCP findings (write-together / change cadence)
        [PASS|FAIL|INFO] <criterion-id>: <message>

        ### CRP findings (read-together / smallest reader-set)
        [PASS|FAIL|INFO] <criterion-id>: <message>

        ### ADP findings (link-forward-only / DAG)
        [PASS|FAIL|INFO] <criterion-id>: <message>

        ### Hygiene findings (universal)
        [PASS|FAIL|INFO] <criterion-id>: <message>

        ### Schema validation (if claude_md: YAML block present)
        [PASS|FAIL] <yaml: ...>

        ### Compliance

        <P> PASS | <F> FAIL | <I> INFO
        COMPLIANT | NON-COMPLIANT
      gotchas:
        - Idempotency requires the same input produces the same output. The criteria are fixed (see references/audit-criteria.md); do not re-rank or re-order findings session-to-session.
        - Role classification depends on cwd. A CLAUDE.md at the user's cwd is `root` from the audit's perspective, even if the broader project has a CLAUDE.md higher up. The audit reports the cwd-relative role and notes any ancestor CLAUDE.md it walked.
        - INFO findings are advisory (migration opportunities, size signals). They do NOT escalate to FAIL on subsequent runs even if unaddressed.
        - When auditing a child CLAUDE.md, the parent must be read for CCP duplication checks. If the parent cannot be located (e.g. user audits a standalone file with no project context), report 'parent unavailable' for parent-relative criteria rather than failing them silently.
        - For role=local (CLAUDE.local.md), only D-group criteria apply (see role-to-criteria map). Hygiene and ADP rules are skipped because the file is by design personal-scoped.
      reference_section: references/audit-criteria.md (criteria) and references/audit-criteria.md (output format)
  reference_index:
    - id: audit_criteria
      path: references/audit-criteria.md
      keywords: [criteria, CCP rules, CRP rules, ADP rules, hygiene rules, role-to-criteria map, output format, decision rules, severity levels]
      summary: The auditable criteria, grouped by cohesion principle, with role-to-criteria map and output format. Loaded in step 2.
```

## Argument grammar

- `(none)` -- audit `<cwd>/CLAUDE.md`.
- `list` -- show numbered list of CLAUDE.md files visible from cwd; do not audit.
- `<path>` -- audit a specific CLAUDE.md or CLAUDE.local.md.
- `<numbers>` -- audit files by index from the most recent `list` output (e.g. `3 7 9`).

Typical workflow: `/claude-md-audit list` to see what's available, then `/claude-md-audit 3 7` to audit specific files.

## Decision rules

- Any FAIL finding -> file is NON-COMPLIANT.
- Only PASS and INFO findings -> file is COMPLIANT.
- INFO findings are advisory improvements, not compliance failures, and do not escalate to FAIL on subsequent runs.

## Cross-references

- Canonical placement framework: `content-allocation.md` in skills-kit:skill-authoring. The criteria in this skill's `references/audit-criteria.md` derive directly from that doc; when the two diverge, the canonical doc wins.
- Schema validation tooling: `plugins/skills-kit/skills/skill-authoring/scripts/audit.py` (validates `claude_md:` YAML blocks against `CLAUDE_MD_SCHEMA` in schemas.py).
- Sibling audit skill: `/skill-audit` for SKILL.md files.
