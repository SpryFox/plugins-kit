---
_schema_version: 1
name: skill-audit
author: christina
skill-type: technique-skill
description: Use when the user invokes /skill-audit to audit, inventory, or report on Claude Code skills -- single-file contract audits, corpus-wide markdown rosters, or interactive HTML hierarchies. Do NOT use for CLAUDE.md audits (use /claude-md-audit).
disable-model-invocation: true
user-invocable: true
argument-hint: "[ (none) | list | <path> | <numbers> | roster [path|-] | hierarchy [path|-] ]"
---

# Skill Audit

## Plugin version (always echo first)

!`uv run python "${CLAUDE_PLUGIN_ROOT}/scripts/print_version.py"`

The first line of your response MUST be the `Running ...` line printed above. This gives the user immediate confirmation of which plugin version actually executed (the slash registry can lag the on-disk cache; this is the only reliable signal).

`/skill-audit` is the umbrella for **skill analysis tooling** in skills-kit. It hosts three operations over the same skill corpus (User skills + Project skills + installed Plugin skills, discovered via the shared `_corpus.py` module):

- **Single-skill audit** -- per-file framework compliance verdict (the namesake operation).
- **Roster** -- corpus-wide markdown inventory grouped by location and type.
- **Hierarchy** -- corpus-wide interactive HTML browser with frontmatter columns and skill-type tooltips.

Future fix-up operations (auto-remediation of common findings) belong here too -- the audit namespace covers analysis, reporting, and fix as a single toolkit, matching the precedent set by `/audit-references` and `/cl`.

```yaml
technique_skill:
  _schema_version: "1"
  trigger_model: user-only
  identity: Audit, inventory, and report on Claude Code skills -- single-file contract verdicts plus corpus-wide markdown/HTML views.
  scope:
    covers:
      - auditing a SKILL.md against its declared type contract (schema validation)
      - auditing a SKILL.md against CRP / CCP / ADP placement rules
      - listing all SKILL.md files visible from cwd
      - producing a per-file compliance report and an overall summary
      - generating a corpus-wide markdown roster grouped by location and type (the `roster` subcommand)
      - generating an interactive HTML hierarchy of the corpus with one column per frontmatter key and skill-type hover tooltips (the `hierarchy` subcommand)
    excludes:
      - auditing CLAUDE.md files (use /claude-md-audit)
      - auditing reference docs in isolation (audited transitively via the SKILL.md they belong to)
  techniques:
    - id: audit_skill_md
      name: Audit SKILL.md against framework + cohesion principles
      keywords: [audit skill.md, skill audit, contract validation, schema check, cohesion principles audit, CRP CCP ADP applied to skill, framework compliance, single-file audit]
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
          action: Inspect $ARGUMENTS. If the first token is `roster` or `hierarchy`, dispatch to the corresponding technique (generate_roster or generate_hierarchy) and stop processing here. Otherwise resolve the audit target.
          tool: argument parsing
          input: $ARGUMENTS
          expected: Either a dispatch to a sibling technique, or a resolved SKILL.md target set.
        - n: 2
          action: Resolve the audit target set.
          tool: discover.py
          input: |
            If TARGET is 'list', run discover.py and emit the numbered list to the user; STOP.
            If TARGET is integer(s), run discover.py --json, map indices to paths, proceed.
            If TARGET is a path, use it directly.
            If TARGET is empty, use <cwd>/SKILL.md if it exists, else surface the cwd and stop.
          expected: A list of SKILL.md paths.
          on_failure: If no SKILL.md is found at the resolved location, surface the cwd and stop. Do not improvise a target.
        - n: 3
          action: Load the placement framework into context.
          tool: Read
          input: |
            content-allocation.md (in skills-kit:skill-authoring)
            (resolved via the skills-kit install path)
          expected: The CCP / CRP / ADP rules and per-artifact audit criteria are now loaded.
        - n: 4
          action: For each target SKILL.md, run skill-authoring's audit.py for schema and contract validation. Capture the structured output.
          tool: audit.py
          input: <path-to-SKILL.md> --json
          expected: JSON with per-row PASS / FAIL / JUDGMENT-REQUIRED verdicts for the universal description rules, the YAML contract validation, the type-specific contract rows, and the mixed-type signal.
          on_failure: If audit.py is unavailable (e.g. plugin venv missing), surface the limitation and proceed with the cohesion-principle audit only -- mark the Schema group as 'unavailable, agent should manually review the contract'.
        - n: 5
          action: For each target, read the SKILL.md and apply cohesion-principle judgment from content-allocation.md per_artifact_role.skill_md.audit_rules.
          expected: A finding list under CRP / CCP / ADP / Hygiene groups.
        - n: 6
          action: Where applicable, also audit the references/ directory ADP property -- one-hop-deep, no cross-cycles, no SKILL.md back-references. (audit.py covers some of this mechanically; surface any judgment-required cases for the agent to evaluate.)
          tool: Read
          input: each references/*.md path
          expected: ADP findings about the reference graph integrity.
        - n: 7
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

    - id: generate_roster
      name: Generate corpus-wide markdown roster
      keywords: [skill roster, skill inventory, list skills, skills by location, skills by type, markdown report, corpus listing]
      goal: Produce a markdown report grouping every visible SKILL.md by location and skill-type, with per-type implied frontmatter declared once so per-skill rows don't repeat it.
      arguments:
        - name: OUT_PATH
          required: false
          description: |
            Where to write the roster. Default: <project-root>/tmp/skill-roster.md.
            Pass the literal `-` to write the markdown body to stdout instead.
      preconditions:
        - The skills-kit plugin is installed (this skill ships with it).
        - PyYAML is available (skills-kit declares it as a dependency).
      steps:
        - n: 1
          action: Run report.py with the `roster` subcommand and the optional out arg.
          tool: report.py
          input: |
            uv run python "${CLAUDE_PLUGIN_ROOT}/skills/skill-audit/scripts/report.py" roster [out]
          expected: |
            With no out, the script writes to <project-root>/tmp/skill-roster.md and
            echoes the resolved path. With `-`, the markdown body is written to stdout.
        - n: 2
          action: Surface the script's stdout to the user verbatim -- the resolved output path or the report body.
          expected: User sees the absolute path and can open it (or the body, when stdout).
      gotchas:
        - "Implied frontmatter is per (skill-type, variant). User-only technique-skills imply both disable-model-invocation true and user-invocable true; other types imply neither. Per-skill rows show only flags that DIFFER from the implied set."
        - "Project skills resolve relative to cwd (<cwd>/.claude/skills). If invoked from outside a project tree the Project section will be empty; this is expected, not a bug."
        - "The script reads files only -- no edits, no P4 / git calls."
      reference_section: usage.md

    - id: generate_hierarchy
      name: Generate corpus-wide interactive HTML hierarchy
      keywords: [skill hierarchy, HTML report, interactive skill browser, frontmatter columns, skill-type tooltips, marketplace grouping, corpus browser]
      goal: Produce a self-contained HTML hierarchy of the corpus -- collapsible <details> sections, one column per frontmatter key, skill-type hover tooltips.
      arguments:
        - name: OUT_PATH
          required: false
          description: |
            Where to write the HTML. Default: <project-root>/tmp/skill-hierarchy.html.
            Pass the literal `-` to write the HTML body to stdout instead.
      preconditions:
        - The skills-kit plugin is installed.
        - PyYAML is available.
      steps:
        - n: 1
          action: Run report.py with the `hierarchy` subcommand and the optional out arg.
          tool: report.py
          input: |
            uv run python "${CLAUDE_PLUGIN_ROOT}/skills/skill-audit/scripts/report.py" hierarchy [out]
          expected: |
            With no out, the script writes to <project-root>/tmp/skill-hierarchy.html and
            echoes the resolved path. With `-`, the HTML body is written to stdout.
        - n: 2
          action: Surface the script's stdout to the user verbatim -- the resolved output path or the HTML body.
          expected: User sees the absolute path and can open the file in a browser.
      gotchas:
        - "Plugins with no skills are dropped from the hierarchy; marketplaces with no skill-bearing plugins are dropped from the marketplace list."
        - "Column union is per-section, not corpus-wide. A frontmatter key used by only one project skill (e.g. `allowed-tools`) appears as a column in the Project-skills table and is absent from the User-skills table. Same column may sit in different positions across tables."
        - "Built-in slash-command 'skills' (the ones bundled with Claude Code itself -- `loop`, `init`, `review`, `simplify`, etc.) have no on-disk SKILL.md and will not appear. This is correct -- they are not authored skills under any of the three discovery roots."
        - "The hierarchy does NOT use the per-type implied-frontmatter convention from the roster. Every frontmatter key is shown as its own column."
      reference_section: usage.md

  reference_index:
    - id: content_allocation
      path: sibling skill-authoring -- content-allocation.md
      keywords: [content allocation rules, CRP CCP ADP placement, per-artifact audit rules, load graph DAG, skill md role audit rules]
      summary: The cohesion-principles placement framework. Loaded for the audit_skill_md technique; rules under per_artifact_role.skill_md.audit_rules apply.
    - id: framework
      path: sibling skill-authoring -- framework.md
      keywords: [type contracts, description requirements, mixed-type, conditional requirements, audit procedure]
      summary: The type contracts. audit.py validates against schemas.py which is canonical for these contracts.
    - id: usage
      path: references/usage.md
      keywords: [usage doc, skill-audit subcommands, roster, hierarchy, output shape, location semantics, implied flags, examples]
      summary: Full usage and output-shape reference for /skill-audit's report subcommands -- arguments, exit codes, location semantics, implied-frontmatter rules for the roster, and the HTML hierarchy structure.
```

## Argument grammar

Single-skill audit (the namesake operation):

- `(none)` -- audit `<cwd>/SKILL.md` if present.
- `list` -- show numbered list of SKILL.md files under cwd; do not audit.
- `<path>` -- audit a specific SKILL.md.
- `<numbers>` -- audit files by index from the most recent `list` output (e.g. `3 7`).

Corpus-wide reports:

- `roster` -- markdown roster to `<project-root>/tmp/skill-roster.md`.
- `roster <path>` -- markdown roster to `<path>`.
- `roster -` -- markdown roster body to stdout.
- `hierarchy` -- interactive HTML to `<project-root>/tmp/skill-hierarchy.html`.
- `hierarchy <path>` -- HTML to `<path>`.
- `hierarchy -` -- HTML body to stdout.

Typical workflows:

- *Audit one skill*: `/skill-audit list` to see what's nearby, then `/skill-audit 3` to audit by index.
- *Inventory all skills*: `/skill-audit roster` -- scan the markdown to spot odd entries.
- *Browse with detail*: `/skill-audit hierarchy` -- open the HTML to see every frontmatter key per skill.

## Decision rules (single-skill audit)

- Any FAIL finding -> file is NON-COMPLIANT.
- Only PASS, INFO, JUDGMENT-REQUIRED findings -> file is COMPLIANT (with judgment-required calls noted).
- INFO findings are advisory improvements, not compliance failures.
- INFO findings do not escalate to FAIL on subsequent runs.

## Cross-references

- Canonical placement framework: `content-allocation.md (in skills-kit:skill-authoring)`.
- Canonical type contracts: `framework.md (in skills-kit:skill-authoring)` and `plugins/skills-kit/skills/skill-authoring/scripts/schemas.py`.
- Mechanical validator: `plugins/skills-kit/skills/skill-authoring/scripts/audit.py`.
- Shared corpus discovery: `plugins/skills-kit/scripts/_corpus.py` (used by the roster and hierarchy subcommands).
- Sibling audit skill: `/claude-md-audit` for CLAUDE.md files.
- Sibling cross-reference scan/fix: `/audit-references` for broken `(in skills-kit:...)` cross-reference cleanup.
