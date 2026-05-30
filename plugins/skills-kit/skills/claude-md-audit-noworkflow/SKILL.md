---
_schema_version: 1
name: claude-md-audit-noworkflow
author: christina
skill-type: audit-skill
description: Use when invoking /claude-md-audit-noworkflow -- the preserved single-loop CLAUDE.md audit (no Workflow fan-out). Do NOT use for SKILL.md (use /skill-audit).
disable-model-invocation: true
user-invocable: true
argument-hint: "[file path, number(s) from list, or 'list']"
---

# CLAUDE.md Audit

## Plugin version (always echo first)

!`uv run python "${CLAUDE_PLUGIN_ROOT}/scripts/print_version.py"`

The first line of your response MUST be the `Running ...` line printed above. This gives the user immediate confirmation of which plugin version actually executed (the slash registry can lag the on-disk cache; this is the only reliable signal).

Audit a CLAUDE.md (root, ancestor, child, or `.local`) against the cohesion-principles content-allocation framework. Findings are grouped by principle: CCP (write-together / change cadence), CRP (read-together / smallest correct scope), ADP (link-forward-only / DAG), plus universal hygiene rules and optional schema validation when a `claude_md:` YAML contract block is present.

The audit is idempotent: same input produces the same findings; addressing all FAIL findings produces a COMPLIANT verdict on the next run.

```yaml
audit_skill:
  _schema_version: "1"
  identity: "Audit CLAUDE.md files against the cohesion-principles content-allocation framework (CCP / CRP / ADP), plus universal hygiene and optional claude_md schema validation. Classify findings into a taxonomy and dispatch remediations by bucket."
  scope:
    covers:
      - "auditing a CLAUDE.md or CLAUDE.local.md against CCP / CRP / ADP placement rules (judgment-based from content-allocation.md)"
      - "applying the role-to-criteria map (root / ancestor / child / local roles have different applicable rules)"
      - "schema validation when a `claude_md:` YAML contract block is present in the file"
      - "categorizing findings into remediation buckets (AUTO / DISCUSS / SPECIAL)"
      - "listing CLAUDE.md files visible from cwd (the cwd-relative discover.py helper for index-based selection)"
    excludes:
      - "auditing SKILL.md files (use /skill-audit)"
      - "auditing reference docs (audited transitively via the SKILL.md they belong to)"
      - "auditing cross-references between skills or docs (use /references-audit)"
  subject:
    what: "Claude Code CLAUDE.md / CLAUDE.local.md files (root, ancestor, child, or local roles), evaluated against the cohesion-principles content-allocation framework."
    subject_type: "corpus"
  criteria:
    - id: "ccp_change_cadence"
      name: "CCP -- content changes for the same reason"
      keywords: ["ccp", "change cadence", "single reason", "content allocation"]
      summary: "Each rule, insight, or convention in a CLAUDE.md belongs to that file only when it changes for the same reason as the file's role (project conventions for project-root CLAUDE.md, directory-local invariants for child CLAUDE.md, etc.)."
      severity: "JUDGMENT"
      detail: "Judgment call per content-allocation.md per_artifact_role.claude_md.audit_rules. The agent reads the body and asks: does this content's change cadence match the file's role?"
    - id: "ccp_cross_file_duplication"
      name: "CCP -- no cross-file rule duplication along the role chain"
      keywords: ["ccp", "duplication", "parent rule", "ancestor inheritance"]
      summary: "A rule stated in a parent CLAUDE.md (ancestor role) must not be restated in a child CLAUDE.md. The agent loads the parent automatically when descending into the child."
      severity: "FAIL"
      detail: "Detected by reading the parent CLAUDE.md (when available) and comparing rule statements. Restated rules signal a misunderstanding of the load model."
    - id: "crp_size_signal"
      name: "CRP -- body size as an evaluation prompt"
      keywords: ["crp", "size threshold", "split signal", "progressive disclosure"]
      summary: "A CLAUDE.md over the size threshold (500 lines / 3000 tokens approx) is a signal to evaluate whether sections serve different reading tasks; the threshold itself is not a verdict."
      severity: "INFO"
      detail: "Mechanical line/token count. Triggers a CRP-evaluation prompt; the agent runs the test (do sections serve different reading tasks?) before proposing a split."
    - id: "crp_role_appropriate"
      name: "CRP -- content sits at the role with the smallest correct scope"
      keywords: ["crp", "role scope", "smallest correct scope", "wrong role"]
      summary: "A rule that applies only to a subdirectory belongs in that subdirectory's CLAUDE.md, not the project root. A rule that applies everywhere belongs in the root, not duplicated per subdirectory."
      severity: "JUDGMENT"
      detail: "Judgment call from content-allocation.md. The agent asks: what is the smallest scope where this rule is correct? Place it there."
    - id: "adp_no_forward_dependency"
      name: "ADP -- no forward dependency on descendant CLAUDE.md content"
      keywords: ["adp", "forward dependency", "dag", "descendant reference"]
      summary: "Parent (root or ancestor) CLAUDE.md must not depend on or reference descendant CLAUDE.md content. The load graph flows root -> ancestor -> child, one direction."
      severity: "FAIL"
      detail: "Detected by scanning the body for descendant-path references or load-time assumptions about subdir CLAUDE.md content."
    - id: "hygiene_thresholds"
      name: "Hygiene -- universal field and length rules"
      keywords: ["hygiene", "line count", "token count", "structural rules"]
      summary: "Body length, broken markdown links, and other universal structural rules. Most are INFO severity unless they cross a hard threshold."
      severity: "INFO"
      detail: "Mechanical universal rules. Distinct from CRP -- hygiene checks structural correctness; CRP checks placement intent."
    - id: "schema_validation"
      name: "claude_md: YAML block validates against schema (when present)"
      keywords: ["claude_md schema", "yaml validation", "optional contract", "claude-md schema"]
      summary: "Files carrying a `claude_md:` YAML contract block in the body must validate against CLAUDE_MD_SCHEMA in schemas.py. Files without the block are not gated on schema validation."
      severity: "FAIL"
      detail: "Mechanical validation via audit.py when the block is present. Conditional: applies only when the file declares the contract."
  taxonomy:
    - id: "A_wrong_role_content"
      name: "Content sits at the wrong role in the CLAUDE.md hierarchy"
      keywords: ["wrong role", "wrong scope", "child rule in root", "root rule in child"]
      detection_signal: "Agent judgment from content-allocation.md role-to-criteria map. Body section's scope is narrower or broader than the file's role allows."
      default_remediation: "Propose moving the section to the correct-scope CLAUDE.md (e.g. narrow root rule -> subdirectory CLAUDE.md; broad subdir rule -> project root CLAUDE.md). User confirms the move."
      bucket: "DISCUSS"
    - id: "B_ccp_cross_file_duplication"
      name: "Rule restated from parent CLAUDE.md"
      keywords: ["duplication", "parent rule", "inheritance violation", "redundant"]
      detection_signal: "Body restates a rule already present in an ancestor CLAUDE.md (read during the audit's role-walk phase)."
      default_remediation: "Delete the restated rule from the child file. The parent rule is loaded automatically when the agent descends into the child."
      bucket: "AUTO"
    - id: "C_crp_split_candidate"
      name: "Body sections serve different reading tasks (CRP split warranted)"
      keywords: ["crp split", "different reading tasks", "progressive disclosure", "decomposition"]
      detection_signal: "Body over size threshold AND agent judgment that sections genuinely serve different reading tasks (e.g. setup-time rules + on-task triggers + reference glossary)."
      default_remediation: "Propose an L1 -> L2 / L3 decomposition: move on-task content to a SKILL.md (L2); move reference content to a reference doc (L3). User confirms before splitting."
      bucket: "DISCUSS"
    - id: "D_adp_forward_dependency"
      name: "Parent CLAUDE.md depends on descendant content"
      keywords: ["adp", "forward dependency", "graph cycle", "wrong load order"]
      detection_signal: "Body references or assumes content from a descendant CLAUDE.md (e.g. 'see subsystem/CLAUDE.md for the rule')."
      default_remediation: "Either inline the descendant content into the parent (if the rule is truly parent-scoped) or remove the forward reference (if the rule is descendant-scoped and the parent has no business assuming it). User confirms."
      bucket: "DISCUSS"
    - id: "E_schema_failure"
      name: "claude_md: YAML block fails schema validation"
      keywords: ["schema fail", "claude_md schema", "yaml validation", "contract block"]
      detection_signal: "audit.py reports schema validation failure for the file's claude_md: YAML block (missing required key, wrong type, forbidden key)."
      default_remediation: "Surface the failing rows. Missing fields with sensible defaults are AUTO sub-cases; authorial fields are DISCUSS."
      bucket: "DISCUSS"
    - id: "F_hygiene_threshold"
      name: "Body over size threshold (CRP-evaluation prompt)"
      keywords: ["hygiene", "size threshold", "line count", "token count"]
      detection_signal: "Mechanical INFO finding: body line count > 500 or token count > 3000."
      default_remediation: "Run the CRP test (do sections serve different reading tasks?). If yes, escalate to C. If no, INFO stays as-is."
      bucket: "DISCUSS"
    - id: "G_descendant_role_mismatch"
      name: "Local file (.local) carries non-local content"
      keywords: [".local", "personal scope", "machine-specific", "wrong file"]
      detection_signal: "CLAUDE.local.md body contains project-conventional content that should be in the checked-in CLAUDE.md instead of a personal override."
      default_remediation: "Propose moving the project-conventional content to the checked-in CLAUDE.md (so all collaborators see it). User confirms before moving."
      bucket: "DISCUSS"
    - id: "K_unclassified"
      name: "Unclassified / special case"
      keywords: ["unclassified", "special case", "escape hatch", "K bucket"]
      detection_signal: "Finding does not match any A-G detection signal after deliberate attempt."
      default_remediation: "Surface to the user with the audit row that fired, attempted matches, and reasons none fit. User proposes strategy."
      bucket: "SPECIAL"
  procedures:
    - id: "audit_claude_md"
      name: "Audit one CLAUDE.md and dispatch remediations"
      keywords: ["audit", "claude.md", "single-file audit", "compliance verdict", "dispatch"]
      goal: "For each target CLAUDE.md, run mechanical and judgment-based checks against the framework's contract, classify findings into the taxonomy, dispatch remediations to AUTO/DISCUSS/SPECIAL buckets, and emit a per-file compliance verdict."
      preconditions:
        - "audit.py is reachable (mechanical schema validator -- only needed if a claude_md: YAML block is present)."
        - "references/audit-criteria.md is loadable (the single self-contained criteria doc; the upstream content-allocation.md is its derivation and is NOT loaded by the audit path)."
        - "The user is in a project directory so role classification works."
      steps:
        - n: 1
          action: "Resolve the audit target set from $ARGUMENTS. Empty -> cwd/CLAUDE.md. 'list' -> emit numbered list via discover.py and stop. Integers -> map to paths from last list. Path -> use directly. Capture (path, role) tuples where role is root / ancestor / child / local."
          tool: "discover.py"
          input: "uv run python ${CLAUDE_PLUGIN_ROOT}/skills/claude-md-audit/scripts/discover.py [--json]"
          expected: "Resolved list of (path, role) tuples."
          on_failure: "If no CLAUDE.md resolves, surface cwd and stop."
        - n: 2
          action: "Load references/audit-criteria.md into context -- the single self-contained criteria doc, which states each testable rule with its CCP/CRP/ADP derivation inline. Do NOT also load content-allocation.md (it is the upstream derivation, redundant for applying criteria). Principle recap so you can apply them without re-derivation: CCP = content that changes for the same reason belongs together (a rule duplicated across scopes is a FAIL); CRP = a fact lives in the smallest scope whose readers all need it; ADP = cross-file references must resolve and run downward in load order (a broken or stale reference is a FAIL)."
          tool: "Read"
          expected: "The role-to-criteria map and all testable CCP / CRP / ADP / Hygiene rules are now loaded from the single criteria doc."
        - n: 3
          action: "For each target file, read it. If role is child, also read the parent CLAUDE.md (for CCP cross-file duplication checks)."
          tool: "Read"
          expected: "File content (plus any required parent) is in context."
        - n: 4
          action: "Apply the criteria from references/audit-criteria.md according to the role-to-criteria map. Produce findings tagged with their group (CCP / CRP / ADP / Hygiene) and severity."
          expected: "Per-file finding list."
        - n: 5
          action: "If the file carries a `claude_md:` YAML contract block, invoke skill-authoring's audit.py for schema validation. Merge findings into the per-file list under Schema."
          tool: "audit.py"
          input: "uv run python ${CLAUDE_PLUGIN_ROOT}/../skill-authoring/scripts/audit.py <path> --json"
          expected: "Schema validation findings appended (if applicable)."
          on_failure: "If audit.py is unavailable, mark Schema group as 'unavailable' and continue."
        - n: 6
          action: "Classify every finding into a taxonomy category (A-G, or K for SPECIAL). Assign bucket per category."
          expected: "Findings sorted into AUTO / DISCUSS / SPECIAL buckets."
        - n: 7
          action: "Dispatch in parallel: AUTO findings to a background agent; DISCUSS + SPECIAL to a foreground Q&A round. Do not block one on the other."
          tool: "Agent"
          input: "Per-finding payloads with file:line, category, default_remediation, agent's recommendation for DISCUSS."
          expected: "Background agent applies AUTO edits; foreground Q&A collects user decisions."
        - n: 8
          action: "Render the per-file report (output_template). When auditing multiple files, render per-file blocks followed by an overall summary."
          expected: "Markdown report in the user's chat with compliance verdicts and finding-bucket summaries."
      output_template: |
        ## <file path> (<role>)

        Lines: <N> / Tokens: <N> / Findings: <count by bucket>

        ### CCP (write-together / change cadence)
        [PASS|FAIL|JUDGMENT] <criterion>: <message>

        ### CRP (read-together / smallest correct scope)
        [PASS|FAIL|JUDGMENT] <criterion>: <message>

        ### ADP (link-forward-only / DAG)
        [PASS|FAIL|JUDGMENT] <criterion>: <message>

        ### Hygiene (universal)
        [PASS|FAIL|INFO] <criterion>: <message>

        ### Schema (when claude_md: YAML block present)
        [PASS|FAIL] <yaml row>: <message>

        ### Compliance verdict

        <P> PASS / <F> FAIL / <I> INFO / <J> JUDGMENT-REQUIRED
        Verdict: COMPLIANT | NON-COMPLIANT
        Remediation routed: AUTO=<N>, DISCUSS=<N>, SPECIAL=<N>
      gotchas:
        - "Role classification depends on cwd. A CLAUDE.md at cwd is `root` from the audit's perspective even if the broader project has a CLAUDE.md higher up. The audit reports the cwd-relative role and notes any ancestor walked."
        - "INFO findings are advisory (size signals, migration opportunities). They do NOT escalate to FAIL on subsequent runs even if unaddressed."
        - "When auditing a child CLAUDE.md, the parent must be read for CCP duplication checks. If the parent cannot be located (e.g. standalone file with no project context), report 'parent unavailable' for parent-relative criteria rather than failing them silently."
        - "For role=local (CLAUDE.local.md), only D-group criteria apply (see role-to-criteria map). Hygiene and ADP rules are skipped because the file is by design personal-scoped."
  remediations:
    auto:
      - category: "B_ccp_cross_file_duplication"
        procedure: "Delete the restated rule from the child file. The parent rule loads automatically when the agent descends into the child directory."
        agent_template: "Background agent receives child CLAUDE.md path + duplicated-rule line range + parent rule reference. Applies the deletion and confirms the parent rule is still present."
    discuss:
      - category: "A_wrong_role_content"
        procedure: "Propose moving the misplaced section to the correct-scope CLAUDE.md. Show the destination and the line range to move. User confirms before applying."
      - category: "C_crp_split_candidate"
        procedure: "Propose an L1 -> L2/L3 decomposition: which sections move to a SKILL.md, which become reference docs, and the triggering criteria per reference. User confirms before splitting."
      - category: "D_adp_forward_dependency"
        procedure: "Surface the forward reference. Ask user: inline the descendant content (rule is parent-scoped) or remove the reference (rule is descendant-scoped)? Apply the user's choice."
      - category: "E_schema_failure"
        procedure: "Show the failing schema rows. AUTO sub-cases (missing optional defaults) can be applied immediately; authorial-choice rows wait for the user."
      - category: "F_hygiene_threshold"
        procedure: "Run the CRP test (do body sections serve different reading tasks?). If yes, escalate to C. If no, INFO stays; the larger CLAUDE.md is correct."
      - category: "G_descendant_role_mismatch"
        procedure: "Propose moving project-conventional content from .local file into the checked-in CLAUDE.md (so all collaborators see it). User confirms before applying."
    special:
      procedure: "Surface the finding with the audit row that fired, attempted categories, and reasons none fit. User proposes strategy. Generalizable strategies become new taxonomy categories in references/audit-criteria.md."
  enforcement:
    gate_kind: "audit-finding"
    gating_rule: "FAIL findings (CCP cross-file duplication, ADP forward dependency, schema validation failures with non-optional missing fields) gate compliance. JUDGMENT findings surface for review without gating; INFO findings are advisory only."
    appeal_process: "JUDGMENT findings are resolved by user confirmation (PASS once the user accepts the exception explicitly). FAIL findings have no bypass; remediation is available within the taxonomy."
  gotchas:
    - "The subject is a corpus of CLAUDE.md files, but the audit procedure visits one file at a time. The role-to-criteria map ensures the right criteria apply to the right file."
    - "Role classification is cwd-relative. A standalone audit of a single file outside a project tree will classify it as root by default; surface that assumption if it affects criteria."
    - "Schema validation is conditional -- only files carrying a `claude_md:` YAML contract block are checked. Files without the block are not failed for its absence; CLAUDE.md is not required to declare a contract."
    - "Idempotency: criteria, taxonomy, and bucket assignments are fixed. Same input produces the same verdict; do not re-rank or re-order findings session-to-session."
  anti_patterns:
    - id: "audit_then_self_remediate"
      name: "Audit and remediate in the same procedure pass"
      keywords: ["self-remediation", "single-pass", "idempotency"]
      why_it_seems_right: "Auditing one file and applying remediations in the same pass seems efficient -- one tool call, fewer round trips."
      why_it_is_wrong: "Mixing detection and remediation in one pass breaks idempotency. The verdict and remediation are separate phases; conflating them prevents re-runs from producing the same findings."
      alternative: "Run the audit procedure to completion. Render the verdict. Dispatch remediations as separate AUTO + DISCUSS work units. Re-run the audit after remediation to verify."
    - id: "duplicate_parent_rule_for_convenience"
      name: "Restate a parent rule in a child file 'for convenience'"
      keywords: ["duplication", "parent rule", "child file", "ccp violation"]
      why_it_seems_right: "Stating the rule in both places means a reader of the child file does not have to consult the parent -- seems more usable."
      why_it_is_wrong: "Duplication violates CCP and creates two sources of truth that drift. The agent always loads the parent CLAUDE.md when descending into the child; the rule is already in context."
      alternative: "Trust the load model. State the rule once at the correct role. If the child file is meant to be read standalone (e.g. distributed without the parent), note that explicitly and consider whether the parent rule belongs at the child's role instead."
```

## Argument grammar

- `(none)` -- audit `<cwd>/CLAUDE.md`.
- `list` -- show numbered list of CLAUDE.md files visible from cwd; do not audit.
- `<path>` -- audit a specific CLAUDE.md or CLAUDE.local.md.
- `<numbers>` -- audit files by index from the most recent `list` output (e.g. `3 7 9`).

Typical workflow: `/claude-md-audit list` to see what's available, then `/claude-md-audit 3 7` to audit specific files.

## Decision rules

- Any FAIL finding -> file is NON-COMPLIANT.
- Only PASS / INFO / JUDGMENT findings -> file is COMPLIANT.
- INFO findings are advisory improvements, not compliance failures, and do not escalate to FAIL on subsequent runs.

## Cross-references

- Canonical placement framework: `content-allocation.md (in skills-kit:skill-authoring)`. The criteria in this skill's `references/audit-criteria.md` derive directly from that doc; when the two diverge, the canonical doc wins.
- Schema validation tooling: `plugins/skills-kit/skills/skill-authoring/scripts/audit.py` (validates `claude_md:` YAML blocks against `CLAUDE_MD_SCHEMA` in schemas.py).
- Sibling audit skills: `/skill-audit` for SKILL.md files; `/references-audit` for broken cross-references across markdown.
