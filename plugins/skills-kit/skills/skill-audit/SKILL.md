---
_schema_version: 1
name: skill-audit
author: christina
skill-type: audit-skill
description: Use when the user invokes /skill-audit to audit, inventory, or report on Claude Code skills. Do NOT use for CLAUDE.md (use /claude-md-audit).
disable-model-invocation: true
user-invocable: true
argument-hint: "[ (none) | list | <path> | <numbers> | roster [path|-] | hierarchy [path|-] ]"
---

# Skill Audit

## Plugin version (always echo first)

!`uv run python "${CLAUDE_PLUGIN_ROOT}/scripts/print_version.py"`

The first line of your response MUST be the `Running ...` line printed above. This gives the user immediate confirmation of which plugin version actually executed (the slash registry can lag the on-disk cache; this is the only reliable signal).

`/skill-audit` is the umbrella for **skill analysis tooling** in skills-kit. It hosts three procedures over the same skill corpus (User skills + Project skills + installed Plugin skills, discovered via the shared `_corpus.py` module):

- **Per-skill audit** -- the namesake operation; checks one SKILL.md against the framework's required blocks, cohesion principles, and hygiene rules; classifies findings into a taxonomy and dispatches remediation.
- **Roster** -- corpus-wide markdown inventory grouped by location and type.
- **Hierarchy** -- corpus-wide interactive HTML browser with frontmatter columns and skill-type hover tooltips.

```yaml
audit_skill:
  _schema_version: "1"
  identity: "Audit Claude Code SKILL.md files against the skill-authoring framework -- required blocks, cohesion placement, hygiene -- and dispatch remediations by finding category. Includes corpus-wide roster and hierarchy reports over the same subject."
  scope:
    covers:
      - "auditing a single SKILL.md against its declared type contract (schema validation via audit.py)"
      - "auditing a SKILL.md against CCP / CRP / ADP placement rules (judgment-based from content-allocation.md)"
      - "auditing description hygiene (length, directive form, exclusion clause) and decision-provenance leakage"
      - "categorizing per-file findings into remediation buckets (AUTO / DISCUSS / SPECIAL)"
      - "listing all SKILL.md files visible from cwd (the cwd-relative discover.py helper for index-based selection)"
      - "generating a corpus-wide markdown roster grouped by location and skill-type (the roster procedure)"
      - "generating an interactive HTML hierarchy of the corpus with frontmatter columns and skill-type tooltips (the hierarchy procedure)"
    excludes:
      - "auditing CLAUDE.md files (use /claude-md-audit)"
      - "auditing reference docs in isolation (audited transitively via the SKILL.md they belong to)"
      - "auditing cross-references between skills (use /references-audit)"
  subject:
    what: "Claude Code SKILL.md files from the User / Project / installed-Plugin corpus, evaluated against the skill-authoring framework's required-blocks / cohesion / hygiene contract."
    subject_type: "corpus"
  criteria:
    - id: "required_frontmatter"
      name: "Required frontmatter fields present and well-formed"
      keywords: ["frontmatter", "name field", "description field", "skill-type field", "required keys"]
      summary: "SKILL.md frontmatter must declare name, description, and a valid skill-type. Name conforms to the lowercase-hyphen pattern; description fits within 160 characters and uses the directive form."
      severity: "FAIL"
      detail: "Mechanical check via audit.py universal-rules section. Missing or malformed frontmatter blocks all downstream analysis."
    - id: "description_quality"
      name: "Description directive form and exclusion clause"
      keywords: ["description", "directive form", "exclusion clause", "do not use", "use when"]
      summary: "Description must start with 'Use when...' or 'Invoke when...' (directive form) and carry a 'Do NOT use for...' exclusion clause that contrasts the skill with neighbors."
      severity: "FAIL"
      detail: "Captured by audit.py mechanically. Vague or under-specified descriptions fail to route correctly when the model picks among skills."
    - id: "yaml_contract_block"
      name: "Body YAML contract block parses against declared skill-type schema"
      keywords: ["yaml contract", "schema validation", "audit.py", "contract block"]
      summary: "The SKILL.md body must contain a fenced yaml block with the declared skill-type's root key, and the block must validate against the type's schema in schemas.py."
      severity: "FAIL"
      detail: "Mechanical schema validator. Captures missing required keys, wrong types, forbidden cross-type keys (mixed-type drift), and contract floor violations."
    - id: "mixed_type_signal"
      name: "No mixed-type drift (single contract root)"
      keywords: ["mixed-type", "contract root", "drift signal", "single type"]
      summary: "Exactly one canonical contract root key appears in the body YAML. Multiple roots signal the skill grew across type boundaries and should split."
      severity: "FAIL"
      detail: "Mechanical check by detect_mixed_type_yaml. A judgment finding when the orientation-summary exception applies (a domain-skill's orientation may include a single technique-flavored summary section without triggering the signal)."
    - id: "ccp_placement"
      name: "CCP -- content changes for the same reason"
      keywords: ["ccp", "common closure principle", "content allocation", "change cadence"]
      summary: "SKILL.md content belongs there only when it changes with the skill's contract. Project-convention content (changes with project conventions) belongs in the co-located CLAUDE.md, not SKILL.md."
      severity: "JUDGMENT"
      detail: "Judgment call per content-allocation.md per_artifact_role.skill_md.audit_rules. The agent reads the body and asks: does this content change with the skill's contract or with project conventions?"
    - id: "crp_placement"
      name: "CRP -- read-together rule for SKILL.md vs references/"
      keywords: ["crp", "common reuse principle", "progressive disclosure", "reference split"]
      summary: "Content in SKILL.md is read together; content in references/ is loaded on-demand for distinct sub-tasks. Splitting must serve different reading tasks, not arbitrary size reduction."
      severity: "JUDGMENT"
      detail: "Judgment call. Body length is a signal that the split deserves evaluation (line/token thresholds), not a verdict. A stub-with-always-co-loaded-reference is a tool-call doubling, not a context-efficiency win."
    - id: "adp_back_reference"
      name: "ADP -- reference graph is a DAG with no SKILL.md back-references"
      keywords: ["adp", "acyclic dependencies", "back-reference", "reference graph"]
      summary: "Reference docs in references/ must be one hop deep from SKILL.md and must not cite SKILL.md sections. A back-reference creates a cycle and a context-loading hazard."
      severity: "FAIL"
      detail: "Partially mechanical via audit.py one-hop-deep check; judgment for back-reference detection inside reference body text."
    - id: "decision_provenance"
      name: "Decision provenance does not bleed into SKILL.md"
      keywords: ["decision provenance", "Dec-N entries", "audit-finding logs", "ccp violation"]
      summary: "Dec-N entries, audit-finding logs, and decision history change with audits, not with the skill's contract. Their home is the co-located CLAUDE.md, not SKILL.md."
      severity: "FAIL"
      detail: "Detected by scanning the SKILL.md body for Dec-N patterns or 'audit-finding' / 'decision log' markers. Always a CCP failure -- the content changes for a different reason than the skill's contract."
    - id: "hygiene_thresholds"
      name: "Hygiene -- body line and token thresholds"
      keywords: ["hygiene", "line count", "token count", "progressive disclosure threshold"]
      summary: "Body length above 500 lines or 3000 tokens is a signal to evaluate splitting; the threshold is informational, not a verdict."
      severity: "INFO"
      detail: "Mechanical line/token count from audit.py. Surfaces a CRP-evaluation prompt but never gates compliance on its own."
  taxonomy:
    - id: "A_missing_required_frontmatter"
      name: "Missing or malformed required frontmatter field"
      keywords: ["missing frontmatter", "required field", "frontmatter fail", "mechanical fix"]
      detection_signal: "audit.py FAIL on a universal-rules row (frontmatter.name, frontmatter.description, skill-type value, name charset, etc.)."
      default_remediation: "Add the missing field with a sensible default (e.g. derive name from directory). If the value requires authorial judgment (description), surface to the user."
      bucket: "AUTO"
    - id: "B_description_quality"
      name: "Description fails directive-form / exclusion-clause / length checks"
      keywords: ["description", "directive form", "use when", "exclusion clause", "160 char limit"]
      detection_signal: "audit.py FAIL on description length (>160 chars), missing 'Use when' / 'Invoke when' prefix, or missing 'Do NOT use for' exclusion clause."
      default_remediation: "Rewrite the description via a background agent to fit the directive form, name the trigger condition, and exclude a contrasting neighbor. User reviews the proposed text."
      bucket: "DISCUSS"
    - id: "C_wrong_skill_type"
      name: "Declared skill-type does not match content shape"
      keywords: ["wrong type", "skill-type mismatch", "classify.py", "single-type suggestion"]
      detection_signal: "Run classify.py; suggested type differs from declared skill-type with single-type confidence >= 2."
      default_remediation: "Propose the classify.py suggestion to the user with rationale; user confirms the type change. If user agrees, re-run audit against the new type's contract."
      bucket: "DISCUSS"
    - id: "D_mixed_type_signal"
      name: "Multiple contract root keys or cross-type content drift"
      keywords: ["mixed-type", "drift", "boundary split", "multiple roots"]
      detection_signal: "detect_mixed_type_yaml returns >1 canonical root, OR mixed-type heuristic score >= 2 from audit.py."
      default_remediation: "Surface the cross-type signals to the user. Propose a split along the type boundary (e.g. extract the technique-flavored section into a sibling technique-skill). User decides whether to split or to apply the orientation-summary exception."
      bucket: "DISCUSS"
    - id: "E_schema_validation_failure"
      name: "Body YAML block fails schema validation"
      keywords: ["schema fail", "yaml validation", "required key missing", "forbidden key"]
      detection_signal: "audit.py reports YAML contract validation failure: missing required key, wrong type, list below min_len, forbidden key present."
      default_remediation: "Surface the specific failing rows to the user; remediation depends on which row failed. Missing fields can be added (AUTO sub-case); forbidden keys indicate mixed-type drift (treat as D)."
      bucket: "DISCUSS"
    - id: "F_ccp_misallocation"
      name: "CCP violation -- project-convention content in SKILL.md"
      keywords: ["ccp", "project convention", "wrong home", "claude.md", "content allocation"]
      detection_signal: "Agent judgment from content-allocation.md per_artifact_role.skill_md.audit_rules. Body section changes with project conventions (e.g. local code-review rules, project-specific tool preferences) rather than the skill's contract."
      default_remediation: "Propose moving the misallocated section into the co-located CLAUDE.md (or the project root CLAUDE.md if the convention is project-wide). User confirms the move."
      bucket: "DISCUSS"
    - id: "G_crp_violation"
      name: "CRP violation -- SKILL.md should split into references/"
      keywords: ["crp", "reference split", "progressive disclosure", "different reading tasks"]
      detection_signal: "Agent judgment. Body sections serve genuinely different reading tasks (e.g. usage docs + worked examples + deep-mechanic reference); body length is over thresholds; a CRP-passing split exists."
      default_remediation: "Propose an L2 -> L3 decomposition with concrete reference-doc paths and a triggering criterion per ref. User confirms before splitting."
      bucket: "DISCUSS"
    - id: "H_adp_back_reference"
      name: "Reference doc cites its own SKILL.md sections"
      keywords: ["adp", "back-reference", "cycle", "one-hop"]
      detection_signal: "Audit detects a `..in skills-kit:<this-skill>` reference inside a doc under this skill's references/ directory."
      default_remediation: "Rewrite the reference doc to not cite the SKILL.md (the load-graph flows one way: SKILL.md -> references). Inline the relevant context if the reference truly needs it."
      bucket: "AUTO"
    - id: "I_decision_provenance"
      name: "Dec-N entries or audit-finding logs in SKILL.md body"
      keywords: ["decision provenance", "Dec-N", "audit history", "ccp violation", "wrong home"]
      detection_signal: "Body contains Dec-N patterns (`Dec-1:`, `Dec-2:` etc.), 'audit-finding-N' tags, or decision-log entries dated by audit pass."
      default_remediation: "Move the Dec-N entries to the co-located CLAUDE.md (or create one if missing). The SKILL.md retains only the resulting rule, not the audit history that produced it."
      bucket: "AUTO"
    - id: "J_hygiene_threshold"
      name: "Body over line / token threshold (CRP evaluation prompt)"
      keywords: ["hygiene", "line count", "token count", "size threshold"]
      detection_signal: "audit.py reports line count > 500 or token count > 3000. This is INFO severity -- a prompt to evaluate CRP, not a verdict."
      default_remediation: "Run the CRP test: do the body sections serve different reading tasks? If yes, route to G. If no, the larger SKILL.md is the correct answer."
      bucket: "DISCUSS"
    - id: "K_unclassified"
      name: "Unclassified / special case"
      keywords: ["unclassified", "special case", "escape hatch", "K bucket"]
      detection_signal: "Finding does not match any A-J detection signal after deliberate attempt."
      default_remediation: "Surface to the user with the audit row that fired, attempted category matches, and reasons none fit. User proposes strategy."
      bucket: "SPECIAL"
  procedures:
    - id: "audit_skill_md"
      name: "Audit one SKILL.md against the framework and dispatch remediations"
      keywords: ["audit", "single-file audit", "namesake operation", "dispatch", "compliance verdict"]
      goal: "For each target SKILL.md, run mechanical and judgment-based checks against the framework's contract, classify findings into the taxonomy, dispatch remediations to AUTO/DISCUSS/SPECIAL buckets, and emit a per-file compliance verdict (COMPLIANT or NON-COMPLIANT)."
      preconditions:
        - "audit.py is reachable (mechanical schema validator)."
        - "content-allocation.md is loadable (cohesion-principle reference)."
      steps:
        - n: 1
          action: "Resolve the audit target set from $ARGUMENTS. Empty -> cwd/SKILL.md if present, else stop. 'list' -> emit numbered list via discover.py and stop. Integers -> map to paths from last list output. Path -> use it directly."
          tool: "discover.py"
          input: "uv run python ${CLAUDE_PLUGIN_ROOT}/skills/skill-audit/scripts/discover.py [--json]"
          expected: "A resolved list of SKILL.md file paths to audit."
          on_failure: "If no target resolves, surface cwd and stop. Do not improvise a target."
        - n: 2
          action: "Load content-allocation.md into context (the cohesion-principles audit rules)."
          tool: "Read"
          input: "skills-kit:skill-authoring -- content-allocation.md"
          expected: "CCP / CRP / ADP placement rules and per-artifact audit criteria are now loaded."
        - n: 3
          action: "For each target, run audit.py to get mechanical schema validation findings."
          tool: "audit.py"
          input: "uv run python ${CLAUDE_PLUGIN_ROOT}/../skill-authoring/scripts/audit.py <path> --json"
          expected: "Per-row PASS / FAIL / JUDGMENT-REQUIRED verdicts for universal rules, YAML schema, type-specific checks, and mixed-type signal."
          on_failure: "If pyyaml is unavailable, mark Schema group as 'unavailable' and proceed with cohesion-principle judgment only."
        - n: 4
          action: "For each target, read the SKILL.md and apply cohesion-principle judgment from content-allocation.md per_artifact_role.skill_md.audit_rules. Output findings under CCP / CRP / ADP / Hygiene groups."
          expected: "Judgment-based finding list per file."
        - n: 5
          action: "Classify every finding into a taxonomy category (A-J, or K for SPECIAL). For each category, assign the bucket per the taxonomy's bucket field."
          expected: "Findings sorted into AUTO / DISCUSS / SPECIAL buckets."
        - n: 6
          action: "Dispatch in parallel: AUTO findings to a background agent with per-finding payloads; DISCUSS + SPECIAL findings to a foreground Q&A round. Do not block one on the other."
          tool: "Agent"
          input: "Per-finding payloads with file:line, category, default_remediation. For DISCUSS, include the agent's recommendation."
          expected: "Background agent applies AUTO edits; foreground Q&A collects user decisions."
        - n: 7
          action: "Render the per-file report (output_template). When auditing multiple files, render the per-file blocks followed by an overall summary."
          expected: "Markdown report in the user's chat with compliance verdicts and finding-bucket summaries."
      output_template: |
        ## <skill name> (<skill-type>) -- <file path>

        Lines: <N> / Tokens: <N> / Findings: <count by bucket>

        ### Schema (audit.py)
        [PASS|FAIL|JUDGMENT] <row>: <message>

        ### CCP (content allocation -- change cadence)
        [PASS|FAIL|JUDGMENT] <criterion>: <message>

        ### CRP (read-together -- progressive disclosure)
        [PASS|FAIL|JUDGMENT] <criterion>: <message>

        ### ADP (one-hop-deep, no back-references)
        [PASS|FAIL|JUDGMENT] <criterion>: <message>

        ### Hygiene (universal rules)
        [PASS|FAIL|INFO] <criterion>: <message>

        ### Compliance verdict

        <P> PASS / <F> FAIL / <I> INFO / <J> JUDGMENT-REQUIRED
        Verdict: COMPLIANT | NON-COMPLIANT
        Remediation routed: AUTO=<N>, DISCUSS=<N>, SPECIAL=<N>
      gotchas:
        - "audit.py is the canonical mechanical validator. Do not re-implement its checks here; consume its JSON output and present it under the Schema group. The cohesion-principle judgment (CCP/CRP/ADP) is what this skill adds on top."
        - "CCP for SKILL.md asks: does this content change with the skill's contract, or with project conventions? Project-convention content bleeding into SKILL.md is a CCP-fail; the content belongs in the co-located CLAUDE.md."
        - "Hygiene thresholds (line / token count) are CRP-evaluation signals, not verdicts. A SKILL.md over the threshold is not automatically NON-COMPLIANT; apply the CRP test (do sections serve different reading tasks?) before proposing a split."
        - "Idempotency: criteria, taxonomy, and bucket assignments are fixed. Same input produces the same verdict; do not re-rank or re-order findings session-to-session."
    - id: "generate_roster"
      name: "Generate corpus-wide markdown roster"
      keywords: ["roster", "markdown inventory", "corpus listing", "location by type", "report.py"]
      goal: "Produce a markdown roster of every SKILL.md in the corpus (User + Project + installed Plugins), grouped by location then by skill-type, with per-type implied frontmatter declared once."
      preconditions:
        - "report.py is reachable; PyYAML is available."
      steps:
        - n: 1
          action: "Parse $ARGUMENTS for an optional output path or '-' for stdout."
          expected: "Output destination resolved."
        - n: 2
          action: "Run report.py with the roster subcommand."
          tool: "report.py"
          input: "uv run python ${CLAUDE_PLUGIN_ROOT}/skills/skill-audit/scripts/report.py roster [out]"
          expected: "Markdown roster written to the resolved path (or stdout), with skill-bearing plugins only."
        - n: 3
          action: "Relay the resolved output path to the user."
          expected: "User can open the file."
      gotchas:
        - "Implied frontmatter is per (skill-type, variant). User-only technique-skills imply both disable-model-invocation true and user-invocable true; per-skill rows show only flags that DIFFER from the implied set."
        - "Project skills resolve relative to cwd. If invoked from outside a project tree the Project section will be empty; this is expected, not a bug."
    - id: "generate_hierarchy"
      name: "Generate corpus-wide interactive HTML hierarchy"
      keywords: ["hierarchy", "html", "interactive", "frontmatter columns", "skill-type tooltips"]
      goal: "Produce a self-contained HTML hierarchy of the corpus: collapsible <details> sections, one column per frontmatter key, skill-type hover tooltips."
      preconditions:
        - "report.py is reachable; PyYAML is available."
      steps:
        - n: 1
          action: "Parse $ARGUMENTS for an optional output path or '-' for stdout."
          expected: "Output destination resolved."
        - n: 2
          action: "Run report.py with the hierarchy subcommand."
          tool: "report.py"
          input: "uv run python ${CLAUDE_PLUGIN_ROOT}/skills/skill-audit/scripts/report.py hierarchy [out]"
          expected: "Single-file HTML hierarchy written to the resolved path (or stdout). Plugins with no skills are dropped."
        - n: 3
          action: "Relay the resolved output path to the user."
          expected: "User can open the HTML in a browser."
      gotchas:
        - "Column union is per-section, not corpus-wide. A frontmatter key used by only one project skill (e.g. `allowed-tools`) appears in the Project-skills table only."
        - "Built-in slash commands without on-disk SKILL.md (e.g. /loop, /init, /review) do not appear in the hierarchy. This is correct -- they are not authored skills under any discovery root."
        - "The hierarchy does NOT apply the per-type implied-frontmatter convention from the roster -- every frontmatter key is shown as its own column."
  remediations:
    auto:
      - category: "A_missing_required_frontmatter"
        procedure: "Add the missing field with a sensible default. For 'name', derive from the directory; for 'skill-type', use classify.py's suggestion if single-type. Description and other authorial fields are NOT AUTO -- route to B / DISCUSS."
        agent_template: "Background agent receives file path + missing field name + default value; applies the edit; reports back."
      - category: "H_adp_back_reference"
        procedure: "Open the cited reference doc; rewrite the back-citing sentence to inline the necessary context instead of referencing back to SKILL.md. Confirm the load-graph flows one way after the edit."
        agent_template: "Background agent receives reference doc path + back-citing line; rewrites to remove the back-reference; reports back."
      - category: "I_decision_provenance"
        procedure: "Identify Dec-N entries / audit-finding tags in SKILL.md. Move them to the co-located CLAUDE.md (create the CLAUDE.md if absent). Retain only the resulting rule in SKILL.md, not the audit history."
        agent_template: "Background agent receives SKILL.md path + Dec-N line ranges; cuts from SKILL.md, appends to CLAUDE.md; reports back."
    discuss:
      - category: "B_description_quality"
        procedure: "Background agent proposes a rewritten description. User reviews and either accepts or directs a different angle. Apply only after user confirmation."
      - category: "C_wrong_skill_type"
        procedure: "Surface classify.py's suggestion with rationale. Ask user to confirm the type change; if confirmed, re-run audit against the new type's contract before finalizing."
      - category: "D_mixed_type_signal"
        procedure: "Surface the cross-type signals (which root keys, which structural markers). Propose a split along the type boundary OR confirm the orientation-summary exception applies (a domain-skill's orientation may include one technique-flavored summary). User decides."
      - category: "E_schema_validation_failure"
        procedure: "Show the specific failing schema rows. Some are AUTO (missing optional default), some are DISCUSS (genuine authorial choice). Route per row."
      - category: "F_ccp_misallocation"
        procedure: "Propose the destination (co-located CLAUDE.md or project root CLAUDE.md). User confirms the move; agent applies."
      - category: "G_crp_violation"
        procedure: "Propose an L2 -> L3 decomposition with explicit reference-doc paths and triggering criteria per ref. User confirms before splitting; agent applies."
      - category: "J_hygiene_threshold"
        procedure: "Run the CRP test (do the body sections serve different reading tasks?). If yes, escalate to G. If no, INFO stays as-is; the larger SKILL.md is the correct answer."
    special:
      procedure: "Surface the finding to the user with: the audit row that fired, the categories you attempted to match, the reasons none fit. The user proposes a strategy. If the strategy generalizes (mutually exclusive with A-J, recognizable detection signal, default remediation applies broadly), propose adding it as a new category in this taxonomy."
  enforcement:
    gate_kind: "audit-finding"
    gating_rule: "FAIL findings (categories A, C-class wrong-type with confirmed mismatch, D-mixed-type with confirmed drift, E-schema, H-back-reference, I-decision-provenance) gate compliance. The verdict is NON-COMPLIANT until all FAIL findings are resolved via the dispatched remediations. JUDGMENT findings do not gate compliance but are surfaced for review; INFO findings are advisory only."
    appeal_process: "JUDGMENT findings are resolved by user confirmation (treat as PASS once the user explicitly accepts the orientation-summary exception or the threshold-violation acceptance). FAIL findings have no bypass; remediation is always available within the taxonomy."
  gotchas:
    - "The corpus discovery (used by the roster and hierarchy procedures) and the cwd-relative discover.py (used by the audit procedure's index-based selection) are different tools. The corpus discovery walks User + Project + installed-Plugin roots; discover.py walks downward from cwd to enumerate nearby SKILL.md for the audit selector."
    - "The audit procedure operates on individual SKILL.md files even though the audit_skill's subject_type is corpus. The corpus is the addressable namespace (User + Project + Plugins); the audit procedure visits one file at a time within it. Roster and hierarchy use the same corpus subject."
    - "Decision rules for the audit verdict (FAIL -> NON-COMPLIANT; only PASS/INFO/JUDGMENT -> COMPLIANT) are unchanged across the type migration. The semantics are preserved; the YAML structure formalizes them."
    - "Roster and hierarchy procedures coexist with the audit procedure inside this audit-skill because they share the same corpus subject. They do NOT exercise the taxonomy + remediation dispatch (their output is inventory, not findings). The audit-skill contract permits supporting procedures that share the subject; only one procedure must exercise the dispatch machinery."
  anti_patterns:
    - id: "audit_then_self_remediate"
      name: "Audit and remediate in the same procedure pass"
      keywords: ["self-remediation", "single-pass", "verdict-and-fix"]
      why_it_seems_right: "It seems efficient to audit one file and apply remediations in the same pass -- one tool call, fewer round trips."
      why_it_is_wrong: "Mixing detection and remediation in one pass invalidates the idempotency contract. The verdict and the remediation are separate phases; conflating them prevents re-runs from producing the same findings and lets the agent silently mutate the subject without surfacing the change to the user."
      alternative: "Run the audit procedure to completion. Render the verdict. Dispatch remediations as separate AUTO (background agent) and DISCUSS (foreground Q&A) work units. Re-run the audit after remediation to verify."
    - id: "hygiene_as_verdict"
      name: "Treat hygiene thresholds as FAIL verdicts"
      keywords: ["hygiene threshold", "line count fail", "auto-split", "premature split"]
      why_it_seems_right: "The SKILL.md is over 500 lines / 3000 tokens; the threshold says so; surely that's a compliance failure?"
      why_it_is_wrong: "The threshold is a CRP-evaluation signal, not a verdict. Splitting a SKILL.md whose sections all serve the same reading task is a tool-call doubling, not a context-efficiency win. Auto-splitting on threshold alone destroys CRP."
      alternative: "Treat hygiene findings as INFO. Run the CRP test before proposing a split: do the body sections serve different reading tasks? Split only if yes."
```

## Argument grammar

Per-skill audit (the namesake procedure):

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

## Decision rules (per-skill audit verdict)

- Any FAIL finding -> file is NON-COMPLIANT.
- Only PASS, INFO, JUDGMENT findings -> file is COMPLIANT (with judgment-required calls noted).
- INFO findings are advisory improvements, not compliance failures.
- INFO findings do not escalate to FAIL on subsequent runs.

## Cross-references

- Canonical placement framework: `content-allocation.md (in skills-kit:skill-authoring)`.
- Canonical type contracts: `framework.md (in skills-kit:skill-authoring)` and `plugins/skills-kit/skills/skill-authoring/scripts/schemas.py`.
- Mechanical validator: `plugins/skills-kit/skills/skill-authoring/scripts/audit.py`.
- Type classifier (for category C remediation): `plugins/skills-kit/skills/skill-authoring/scripts/classify.py`.
- Shared corpus discovery: `plugins/skills-kit/scripts/_corpus.py` (used by the roster and hierarchy procedures).
- Sibling audit skill: `/claude-md-audit` for CLAUDE.md files.
- Sibling reference scanner: `/references-audit` for broken skill cross-references across markdown.
