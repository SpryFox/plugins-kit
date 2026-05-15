---
_schema_version: 1
name: references-audit
author: christina
skill-type: audit-skill
description: Use when the user invokes /references-audit to scan markdown for broken skill cross-references. Do NOT use for single-skill validation (use /skill-audit).
disable-model-invocation: true
user-invocable: true
argument-hint: "[--scope skills|references|md|all] [--path FILE] [--ignore-dir GLOB] [--ignore-file GLOB] [--verbose] [--json]"
---

# References Audit

## Plugin version (always echo first)

!`uv run python "${CLAUDE_PLUGIN_ROOT}/scripts/print_version.py"`

The first line of your response MUST be the `Running ...` line printed above. This gives the user immediate confirmation of which plugin version actually executed (the slash registry can lag the on-disk cache; this is the only reliable signal).

## Framework

This skill operationalizes the **references-audit** audit-kind under the shared audit framework. The shared glossary -- `subject`, `primitive`, `composition`, `discovery`, `audit-kind`, `rule`, `finding`, `severity`, `taxonomy`, `bucket`, `corpus`, `scaffolding` -- is canonical at `plugins/skills-kit/skills/skill-audit/references/audit-framework.md`, with the data side (primitives + compositions + audit-kind registry) at `audit-framework.yaml` alongside. Definitions live there; this file describes only how the audit applies the framework.

In framework terms, `/references-audit` is:

- **Subject:** a `directory` composition (the default), or one of `skill | plugin | project` when discovery hits that marker, or a single primitive `md` file when `--path` names one.
- **Primitive consumed:** `md` (today's only scanner input; `script` and `code` are listed as future stubs in `audit-framework.yaml`).
- **Discovery:** walks the scan tree; activates plugin rules when it hits `.claude-plugin/plugin.json`, skill rules when it hits `SKILL.md`, directory rules otherwise. Rules stack rather than override.
- **Scaffolding:** `scripts/references_audit.py` -- the one repeatable invocation that replaces what would otherwise be agent inference over every file.
- **Rules per composition:** the bindings table in `audit-framework.yaml::audit_kinds.references_audit.rules_per_composition`. Canonical rule definitions (id, severity, summary, detail) live in this skill's own `criteria:` block below -- the framework registry only catalogs which rule ids bind to which compositions. Today's implemented set: `hard_dep_missing`, `soft_ref_missing`, `name_mismatch`, `shadowing`. Tracked in `audit-framework.yaml::future_rules`: `references_reachable_from_skill_md`, `manifest_declarations_resolve`, `no_cross_scope_personal_refs`.
- **Taxonomy + buckets:** the A-K categories below classify findings; AUTO / DISCUSS / SPECIAL dispatch them in parallel (background agent for AUTO, foreground Q&A for the rest).

```yaml
audit_skill:
  _schema_version: "1"
  identity: "Scan markdown files for broken Claude Code skill cross-references, classify each finding into a taxonomy category, and dispatch the remediation to the appropriate bucket (AUTO mechanical fix, DISCUSS user judgment, SPECIAL escape hatch)."
  scope:
    covers:
      - "scanning SKILL.md, reference docs (references/*.md, in-skill CLAUDE.md), and arbitrary markdown for broken `/example:skill-name` references and `skill: \"...\"` hard-dep invocations"
      - "classifying findings into categories A-K (renamed / retired / merged / scope-violating / false positives / illustrative / proposed / unclassified)"
      - "bucketing findings into AUTO (mechanical fix via background agent), DISCUSS (foreground Q&A on options), or SPECIAL (escape hatch for unanticipated cases)"
      - "re-running the audit after remediation to verify no new findings surfaced from the fixes"
    excludes:
      - "single-skill contract validation (use /skill-audit)"
      - "CLAUDE.md cohesion auditing (use /claude-md-audit)"
      - "non-markdown files (settings.json, *.py, etc.) -- not scanned at any scope"
      - "runtime resolution of references during skill execution (this is static-analysis only)"
  subject:
    what: "markdown files (SKILL.md, references/*.md, in-skill CLAUDE.md, standalone docs) checked for broken cross-references to Claude Code skills"
    subject_type: "corpus"
  criteria:
    - id: "hard_dep_missing"
      name: "Hard dependency targets a non-existent skill"
      keywords: ["hard dep", "skill invocation", "runtime failure", "ERROR finding", "skill tool"]
      summary: "A Skill-tool invocation (`skill: \"...\"`) in scanned source targets a skill that does not exist in the resolved skill pool."
      severity: "FAIL"
      detail: "Will fail at runtime when the code path fires. Surfaced by the scanner as ERROR. This is the only severity that gates exit code 1."
    - id: "soft_ref_missing"
      name: "Prose reference to a non-existent skill"
      keywords: ["soft ref", "prose reference", "slash reference", "WARNING finding"]
      summary: "A `/example:skill-name` reference in scanned prose does not resolve against the skill pool."
      severity: "INFO"
      detail: "Misleading to readers but not a runtime failure. Surfaced by the scanner as WARNING. The taxonomy below categorizes the *why* and remediates accordingly."
    - id: "name_mismatch"
      name: "Frontmatter name diverges from directory name"
      keywords: ["name mismatch", "frontmatter name", "directory name", "inconsistency"]
      summary: "A SKILL.md's frontmatter `name:` field does not match the directory the file lives in."
      severity: "INFO"
      detail: "May cause confusion when looking up the skill. Surfaced by the scanner as WARNING. Usually a rename leftover."
    - id: "shadowing"
      name: "User skill shadows a project skill"
      keywords: ["shadowing", "user skill", "project skill", "override", "precedence"]
      summary: "A user-level skill (`~/.claude/skills/<name>`) has the same name as a project-level skill and overrides it at runtime."
      severity: "INFO"
      detail: "Intentional in some workflows (personal overrides), accidental in others. Surfaced by the scanner as INFO; the agent surfaces but does not remediate without user direction."
  taxonomy:
    - id: "A_renamed"
      name: "Renamed skill (1:1 replacement exists)"
      keywords: ["renamed", "rename map", "mechanical replacement", "find-and-replace"]
      detection_signal: "WARNING `/example:old-name` (or ERROR `skill: \"example:old-name\"`); a current skill `/example:new-name` clearly covers the same responsibility (confirmable from upstream CHANGELOG, the new skill's description, or an explicit 'renamed from' line)."
      default_remediation: "Mechanical find/replace of the old name with the new name within the file. If the surrounding sentence describes old behavior, also update the prose so it matches the new skill."
      bucket: "AUTO"
      examples:
        - before: "references using this prefix are not flagged as `/skill-deps`"
          after: "references using this prefix are not flagged as `/references-audit`"
    - id: "B_retired"
      name: "Retired or deleted skill (no replacement)"
      keywords: ["retired", "deleted", "no replacement", "demote to backtick", "allow-stale"]
      detection_signal: "WARNING `/example:old-name`; no current skill covers the responsibility. The reference is often the subject of a whole section or paragraph."
      default_remediation: "Four sub-cases by structural context -- (1) reference is the subject of a section: delete the section; (2) incidental clause: delete the clause, keep the surrounding sentence; (3) historical context inside a mixed-live-and-stale doc: demote to backticked literal; (4) whole doc is a historical artifact: add to `references-audit-allow-stale` frontmatter list with an editor's note."
      bucket: "DISCUSS"
    - id: "C_merged"
      name: "Merged skill (subskill folded into parent)"
      keywords: ["merged", "folded", "parent skill", "sub-skill", "dispatch alias"]
      detection_signal: "WARNING `/example:parent-sub`; current skill `/example:parent` exists; release notes or SKILL.md document the merge."
      default_remediation: "In prose: rewrite the slash form (`/example:parent-sub`) to the new dispatch form (`/example:parent sub`). In dispatch alias tables / synonyms lists: keep the literal name in backticks (not a callable slash reference)."
      bucket: "AUTO"
      examples:
        - before: "Via `/playtest preflight` (or the legacy `/playtest-preflight`) for standalone validation"
          after: "Via `/playtest preflight` (or the legacy `playtest-preflight` argument) for standalone validation"
    - id: "D_scope_violating"
      name: "Scope-violating cross-reference (project / personal boundary)"
      keywords: ["scope violation", "personal skill", "project skill", "shipped plugin", "cross-scope"]
      detection_signal: "WARNING `/example:ref-name`; the referenced skill exists but in the opposite scope (project skill referencing a personal skill, or a shipped plugin skill referencing a project-only skill)."
      default_remediation: "Project / plugin -> personal: delete the cross-reference (a shipped skill cannot assume the personal skill is installed). Personal -> project: usually fine; only flag if the personal skill is meant to be portable."
      bucket: "DISCUSS"
    - id: "E_compound_adjective"
      name: "Compound-adjective false positive (slash as punctuation)"
      keywords: ["false positive", "compound adjective", "punctuation slash", "prose rewrite"]
      detection_signal: "WARNING `/example:word-foo`; the literal text contains `X-/Y-thing` (compound adjective with embedded slash) or other prose where a slash appears as punctuation, not as a skill reference."
      default_remediation: "Reword the prose to eliminate the slash; preserve the technical meaning (the rewrite is 'express the same idea differently', not 'escape the scanner')."
      bucket: "AUTO"
      examples:
        - before: "Slack file downloads are bot-/user-token-gated."
          after: "Slack file downloads are gated by bot or user token scopes."
    - id: "F_cli_flag"
      name: "Non-skill CLI flag false positive"
      keywords: ["false positive", "cli flag", "devenv", "msbuild", "shell command", "code fence"]
      detection_signal: "WARNING `/example:flag-name`; surrounding text is a shell or CLI invocation (binary name + flags). Common with MSBuild, `devenv`, `cl.exe`, the linker, and other Windows-native tools."
      default_remediation: "Wrap the whole command in a fenced code block. The scanner masks fenced regions, so refs inside them produce no findings."
      bucket: "AUTO"
    - id: "G_xml_template"
      name: "XML or template placeholder false positive"
      keywords: ["false positive", "xml tag", "html tag", "template placeholder", "angle brackets"]
      detection_signal: "WARNING `/example:tag-name`; surrounding text contains XML or HTML closing tags (such as `</example:foo>`) or template placeholders inside angle brackets."
      default_remediation: "Wrap the XML or template example in a fenced code block. Same scanner masking as category F."
      bucket: "AUTO"
    - id: "H_harness_transcript"
      name: "Harness transcript false positive"
      keywords: ["false positive", "harness transcript", "session log", "ignore-dir", "claude feedback"]
      detection_signal: "Many WARNINGs in the same file or directory; references match Claude-harness vocabulary (`/example:command-args`, `/example:system-reminder`, `/example:task-id`, `/example:tool-use-id`, `/example:command-name`, `/example:command-message`, etc.)."
      default_remediation: "Add the directory to the scanner's `--ignore-dir` flag in the project's invocation wrapper (one config entry, no per-file edits)."
      bucket: "DISCUSS"
    - id: "I_illustrative"
      name: "Illustrative example in a design doc"
      keywords: ["illustrative", "meta-descriptive", "design doc", "syntax example", "example prefix"]
      detection_signal: "WARNING `/example:foo` or ERROR `skill: \"example:foo\"`; the surrounding sentence is describing skill-reference syntax in the abstract -- the doc is about references, not making one."
      default_remediation: "Add the `example:` prefix to the slash-form, and likewise to any `skill: \"...\"` hard-dep literal. Both are documented escape prefixes that the scanner ignores."
      bucket: "AUTO"
      examples:
        - before: "soft references (`/name` in documentation text that mislead)"
          after: "soft references (`/example:name` in documentation text that mislead)"
    - id: "J_forward_looking"
      name: "Forward-looking or proposed skill"
      keywords: ["forward-looking", "proposed", "future", "planned", "aspirational", "proposed prefix"]
      detection_signal: "WARNING `/example:foo`; no current skill named `foo`; surrounding prose frames it as 'planned', 'future', 'we should build', 'today: <legacy approach>'."
      default_remediation: "Add the `proposed:` prefix to the slash-form (a documented escape prefix). Optionally append a one-line '(planned, not built)' note if the context isn't already explicit."
      bucket: "AUTO"
    - id: "K_unclassified"
      name: "Unclassified / special case"
      keywords: ["unclassified", "special case", "escape hatch", "K bucket", "surface to user"]
      detection_signal: "None of A-J fit cleanly after a deliberate attempt."
      default_remediation: "Surface the finding to the user with the report line, what you tried to match, and why none of A-J fit. The user decides the strategy."
      bucket: "SPECIAL"
  procedures:
    - id: "scan_and_report"
      name: "Scan markdown corpus for broken cross-references"
      keywords: ["scan", "audit", "discover", "run scanner", "report"]
      goal: "Run the references_audit.py script over the chosen scope and emit a markdown or JSON report of findings (ERRORs, WARNINGs, INFOs) against the resolved skill pool."
      preconditions:
        - "Python is available on PATH (stdlib only; no external dependencies)."
        - "Installed-plugins manifest exists at `~/.claude/plugins/installed_plugins.json` if plugin skills should be in the pool."
      steps:
        - n: 1
          action: "Parse the user's scope intent from $ARGUMENTS into one or more of `--scope skills|references|md|all` (combine with commas; default `skills`). If the user named a specific file, capture `--path PATH` (repeatable)."
          expected: "A flag set ready to pass to the scanner."
        - n: 2
          action: "Run the scanner via the plugin venv. Pass through any additional flags from $ARGUMENTS (`--verbose`, `--ignore-dir`, `--ignore-file`, `--json`)."
          tool: "references_audit.py"
          input: |
            uv run python "${CLAUDE_PLUGIN_ROOT}/skills/references-audit/scripts/references_audit.py" \
              --project-dir .claude/skills \
              --user-dir $HOME/.claude/skills \
              $ARGUMENTS
          expected: "Markdown (default) or JSON (when --json given) report containing: scope summary, skill-pool counts, issues by severity, hard-dependency graph, summary counts."
        - n: 3
          action: "If remediation will follow (the user asked to fix findings, not just see them), re-run with `--json` so the classify procedure can consume structured findings."
          expected: "JSON findings ready for taxonomy classification."
      gotchas:
        - "Prose-form hard deps (e.g. 'invoke `/example:foo` using the Skill tool') are caught as WARNING soft refs, not as ERROR hard deps. The runtime risk is still real; do not dismiss the WARNING."
        - "Frontmatter parsing is regex-based; the skill pool is built from frontmatter `name:` only. A skill that fails to parse frontmatter (e.g. truncated `---` fence) is silently absent from the pool."
        - "The NON_SKILL_WORDS exclusion list can filter a legitimate skill name colliding with a common path segment (e.g. a skill literally named `build`). Inspect the exclusion list in references_audit.py if a real ref is mis-reported as missing."
    - id: "classify_and_dispatch"
      name: "Categorize findings per taxonomy and dispatch by bucket"
      keywords: ["classify", "categorize", "taxonomy", "bucket", "dispatch", "AUTO DISCUSS SPECIAL"]
      goal: "For each finding from the scan, assign exactly one category from A-K, route to its bucket (AUTO / DISCUSS / SPECIAL), and dispatch remediation appropriately. Background-agent execution for AUTO; foreground Q&A for DISCUSS + SPECIAL."
      preconditions:
        - "The scan procedure has completed; findings are available as JSON."
      steps:
        - n: 1
          action: "For each finding, identify its detection signal and match to a taxonomy category (A-J). If none fits after deliberate attempt, classify as K (SPECIAL)."
          expected: "Every finding has exactly one category assignment."
        - n: 2
          action: "Assign bucket per category (per the bucket field): AUTO when the category's default remediation is mechanical and unambiguous; DISCUSS when the category requires user input on a sub-case or mapping; SPECIAL for K."
          expected: "Findings sorted into AUTO / DISCUSS / SPECIAL buckets."
        - n: 3
          action: "For the AUTO bucket, compute the exact before-text (read the cited file at the cited line) and the after-text (per the category's default_remediation). Bundle one payload per finding."
          expected: "Per-finding edit payloads ready for the background agent."
        - n: 4
          action: "Dispatch in parallel -- launch a single background agent for the AUTO bucket (Skill tool with the brief template); open foreground Q&A for DISCUSS + SPECIAL findings. Do not block one on the other."
          tool: "Agent"
          input: "Background-agent brief template (see references/finding-taxonomy.md, 'Background-agent brief template' section)."
          expected: "Background agent applies AUTO edits; foreground Q&A collects user decisions for DISCUSS/SPECIAL."
        - n: 5
          action: "After both return, merge edits and re-run the scan procedure. Iterate only on newly-surfaced findings (do not re-classify already-resolved ones)."
          expected: "Audit confirms no new findings introduced; remaining findings (if any) are surfaced for next-pass remediation."
      output_template: |
        ## Audit summary

        Scope: <scopes scanned>
        Files: <N scanned>
        Skills pool: <project N> / <user N> / <plugin N>

        ## Findings by bucket

        AUTO (N): [list with file:line + category + before/after]
        DISCUSS (N): [list with file:line + category + options + recommendation]
        SPECIAL (N): [list with file:line + rationale]

        ## Remediation results

        Applied: <N>
        Skipped (file changed): <N>
        Outstanding (newly surfaced or unclassifiable): <N>
      gotchas:
        - "Do not reclassify findings the taxonomy has already settled. The agent's job is classification + judgment on OPTIONS within a category, not second-guessing the taxonomy."
        - "The background agent (AUTO) does not classify -- it applies edits from the brief. Build the brief with exact before/after text; the agent skips findings whose before-text no longer matches."
        - "Re-running the audit after remediation is required; newly-surfaced findings often appear (e.g. a backticked literal reveals another broken ref nearby that was previously masked)."
        - "When the AUTO bucket and the DISCUSS bucket are dispatched in parallel, the user's foreground answers do NOT gate the background-agent run. Both run independently; their results merge at the end."
  remediations:
    auto:
      - category: "A_renamed"
        procedure: "Mechanical find/replace old-name -> new-name in the file. Update surrounding prose if it describes old behavior."
        agent_template: "See references/finding-taxonomy.md 'Background-agent brief template'."
      - category: "C_merged"
        procedure: "Rewrite `/example:parent-sub` prose to `/example:parent sub`. In dispatch alias tables, demote to backticked literal instead."
        agent_template: "See references/finding-taxonomy.md 'Background-agent brief template'."
      - category: "E_compound_adjective"
        procedure: "Reword prose to eliminate the slash; preserve technical meaning."
        agent_template: "See references/finding-taxonomy.md 'Background-agent brief template'."
      - category: "F_cli_flag"
        procedure: "Wrap the entire command in a fenced code block."
        agent_template: "See references/finding-taxonomy.md 'Background-agent brief template'."
      - category: "G_xml_template"
        procedure: "Wrap the XML or template example in a fenced code block."
        agent_template: "See references/finding-taxonomy.md 'Background-agent brief template'."
      - category: "I_illustrative"
        procedure: "Add `example:` prefix to slash-form refs and `skill: \"example:...\"` literals."
        agent_template: "See references/finding-taxonomy.md 'Background-agent brief template'."
      - category: "J_forward_looking"
        procedure: "Add `proposed:` prefix to the slash-form. Optionally append a '(planned, not built)' note."
        agent_template: "See references/finding-taxonomy.md 'Background-agent brief template'."
    discuss:
      - category: "A_renamed"
        procedure: "(Sub-case: mapping unknown.) Ask once for the whole audit: 'I see refs to `/example:old-name`. Best guess `/example:new-name`. Apply?' Batch response covers all old-name refs."
      - category: "B_retired"
        procedure: "Ask per finding which sub-case applies: delete section / delete clause / demote to backtick / add to allow-stale. Surrounding structural context determines the best choice."
      - category: "C_merged"
        procedure: "(Sub-case: dispatch alias table.) Ask: keep as backticked literal for dispatch, or update to the new form? Table context matters."
      - category: "D_scope_violating"
        procedure: "Ask whether the cross-reference should be deleted entirely (shipped skill referencing personal) or kept (personal skill comparing to project). The skill's structural intent determines the answer."
      - category: "H_harness_transcript"
        procedure: "Pick exclusion mechanism once: --ignore-dir flag in the project's wrapper, or document the recommended flags in the host project's CLAUDE.md. Apply to all matching files."
    special:
      procedure: "Surface the finding to the user with: the scanner's report line, the categories you attempted to match, the reasons none fit. The user proposes a strategy. If the strategy generalizes (mutually exclusive with A-J, recognizable detection signal, default remediation applies broadly), propose adding it as a new category in references/finding-taxonomy.md."
  enforcement:
    gate_kind: "merge-gate"
    gating_rule: "No ERRORs (broken hard dependencies) in any changelist submitted for merge. WARNINGs and INFOs are permissible and can be addressed in follow-up changes but should be minimized."
    appeal_process: "ERRORs in category E/F/G/H (false positives) are resolved by applying the category's default remediation (rewording, code-fencing, ignore-dir flag). ERRORs in category J (forward-looking) are resolved by adding the `proposed:` prefix. Genuine retired-skill ERRORs (category B) require either deletion or the historical-artifact `references-audit-allow-stale` allowlist with an editor's note. No appeals process bypasses the gate; remediation is always available within the taxonomy."
  gotchas:
    - "The skill pool is built from `installed_plugins.json` and the project/user `.claude/skills/` directories. A skill on disk that is not registered in installed_plugins.json will not resolve, even if a SKILL.md exists at its install path. This is correct -- the resolver mirrors what the harness does at runtime."
    - "The `references-audit-allow-stale:` frontmatter field (legacy: `audit-references-allow-stale`) silences findings *inside that file only*, for the listed names only. A new broken ref in the same file still fires. Use this for genuine historical artifacts; do not use it as a bypass for live docs."
    - "Compound-adjective false positives (category E) and harness-transcript false positives (category H) account for the majority of WARNINGs in many projects. If your warning count is in the hundreds, before investigating individual findings, check whether one of these categories applies to the whole batch."
    - "Hard-dependency edges across scanned source files are reported as a separate graph in the markdown output. Use this to spot orphaned skills (no inbound edges) or circular invocations during corpus-wide reviews."
  anti_patterns:
    - id: "per_finding_user_round_trip"
      name: "Per-finding user round-trip"
      keywords: ["round-trip", "per-finding question", "conversation friction", "batching"]
      why_it_seems_right: "Each DISCUSS finding has a genuine user decision; surely the agent should ask about each one individually so the user can give the right answer."
      why_it_is_wrong: "Per-finding round-trips multiply conversation friction and slow remediation to a crawl. The user has to context-switch into each finding individually. Cost of being wrong is one revert; cost of friction is the user abandoning the audit."
      alternative: "Batch every DISCUSS + SPECIAL finding into one foreground question round. Render as a numbered list with category, options, and a recommendation. The user answers in one pass."
    - id: "bucket_gates_other_bucket"
      name: "Gating AUTO on DISCUSS answers (or vice versa)"
      keywords: ["gating", "sequencing", "parallel dispatch", "blocking"]
      why_it_seems_right: "It seems prudent to wait for the user's DISCUSS answers before letting the background agent loose on AUTO findings -- maybe the answers reveal that the AUTO classifications were wrong."
      why_it_is_wrong: "AUTO and DISCUSS classifications are independent by construction (different detection signals, different categories). Gating AUTO on DISCUSS serializes work that should run in parallel and doubles the time-to-fix."
      alternative: "Dispatch AUTO and DISCUSS in parallel. Merge edits at the end. If a DISCUSS answer reveals a genuine AUTO misclassification, the re-run after merge surfaces it; iterate on the re-run, not by serializing the original dispatch."
```

## What this skill does

Scan one or more sets of markdown files for broken Claude Code skill references and report them. The default scope (`skills`) is the original `skill-deps` behavior — scan every `SKILL.md` and check that each `/example:skill-name` or `skill:"example:skill-name"` reference points to a real skill. Other scopes extend the scan to additional file types so reference files and standalone docs (e.g. `references/*.md`, `CLAUDE.md`) can be audited too.

Plugin skills are discovered from `~/.claude/plugins/installed_plugins.json` and resolved by both their bare name (e.g. `/example:skill-name`) and their plugin-qualified name (e.g. `/example:plugin-skill-name`).

## Invocation

This skill can be invoked three ways:

- **Slash command (project-scoped):** `/references-audit [args]`
- **Slash command (plugin-qualified):** `/skills-kit:references-audit [args]`
- **Skill tool (from another skill):** `Skill: "references-audit"` with `args` containing the desired flags. Pass scope decisions through `args` rather than hardcoding them at the call site so the caller stays generic.

All three resolve to the same SKILL.md and run the same `references_audit.py` script.

## Documentation Convention

When showing example skill-reference syntax in prose, use `/example:` or `/proposed:` prefixes (e.g. `/example:skill-name`, `/proposed:run-bot`). The scanner ignores any reference with one of these prefixes and never reports it as broken.

For **historical artifacts** (rollout summaries, design plans whose proposed names were later renamed or never built, postmortem docs that record past state), a per-file allowlist in YAML frontmatter declares which legacy names are expected to no longer resolve:

```yaml
---
references-audit-allow-stale: plan, designer-plan, rollback-to-preflight
---
```

The legacy field name `audit-references-allow-stale` is still recognized for backward compatibility with files written before the 0.8.0 rename; prefer the new name on any file you touch.

Listed bare names are silenced inside that file only, for both soft refs and hard deps. Any *new* broken reference in the same file still fires — the allowlist is an explicit exception list, not a file-level bypass. Prefer this over rewriting historical refs to backticks or `/proposed:` prefixes when the doc's value is the historical record itself. The allowlist is documented in the editor's note inside the doc, so a reader sees both the declared exceptions and the reason for them.

## Step 1: Pick the Scope

The scope tells the script which files to audit. The agent picks based on what the user asked for; if the user did not specify, use the default `skills`.

| User said... | Pass | Effect |
|---|---|---|
| (nothing specific, or "audit my skills") | `--scope skills` (default) | Scan every `SKILL.md` (project + user + plugin). |
| "audit my reference docs" / "check references/ files" | `--scope references` | Scan every `*.md` file that sits inside a skill directory but is NOT `SKILL.md` (i.e. `references/*.md`, `CLAUDE.md` inside a skill dir, etc.). The skill pool itself is still loaded from SKILL.md files so refs can resolve. |
| "audit every markdown file" / "check all .md" | `--scope md` | Scan every `*.md` file under the scan roots, including SKILL.md, references, and standalone docs. |
| "audit everything" | `--scope all` | Alias for `--scope md`. |
| "audit this one file: PATH" | `--path PATH` (combine with `--scope` if the skill-pool scope matters) | Scan only the file at PATH; refs still resolve against the full skill pool. May be repeated. |

Scopes can also be combined with commas: `--scope skills,references` audits SKILL.md and reference files but skips standalone docs.

## Step 2: Run the Analysis

```
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/references-audit/scripts/references_audit.py" \
  --project-dir .claude/skills \
  --user-dir $HOME/.claude/skills \
  $ARGUMENTS
```

If `uv` isn't available in the host environment, fall back to whatever Python entry point fits (e.g. `python`, `python3`, `py`, or a project-bundled `python.bat`). The script depends only on the Python standard library.

Pass through any of these flags from `$ARGUMENTS`:

- `--verbose` / `-v` — full soft-reference graph and per-source-file table.
- `--ignore-dir GLOB` (repeatable) — skip files whose path contains a matching ancestor directory. Use for harness transcript dirs (e.g. `--ignore-dir 'ClaudeFeedback'`) and vendored third-party doc trees.
- `--ignore-file GLOB` (repeatable) — skip files matching the glob.
- `--json` — emit a structured JSON report instead of markdown. Use when downstream tooling (or the remediation step below) needs to consume findings programmatically.

## Step 3: Display Results

Show the script's markdown output directly to the user when remediation will be conversational. When remediation is in scope (Step 5 below), prefer `--json` and synthesize a short human summary for the user — the JSON feeds the classification step.

The output (markdown form) includes:

- **Scope summary**: which scopes ran and how many source files were scanned for each.
- **Skills discovered**: counts of project, user, and plugin skills (the resolvable name pool).
- **Issues**: each finding includes the file path, line number, and the missing ref. ERRORs (broken hard deps), WARNINGs (broken soft refs, name mismatches), INFOs (shadowed skills).
- **Hard Dependencies**: the Skill-tool invocation graph (edges across scanned source files), with line numbers.
- **Summary**: counts of each issue type.

If `--verbose` was used, also shows the full soft-reference graph (with line numbers) and a table of every scanned source file.

## Step 4: Interpret

This level only classifies the *scanner's* output type. For the **semantic categories** of broken references (the A–K taxonomy declared in the contract above), load `references/finding-taxonomy.md` in Step 5 for full detection signals, default remediations, and the background-agent brief template.

| Issue type | Meaning |
|------------|---------|
| ERROR | A Skill-tool call (e.g. `skill: "X"`) in a scanned source targets a skill that does not exist. This **will fail at runtime** when that path fires. |
| WARNING (broken ref) | A `/example:skill-name` reference in scanned prose targets a skill that does not exist. Misleading but not a runtime failure on its own. |
| WARNING (name mismatch) | The YAML frontmatter `name:` on a SKILL.md does not match what the directory structure suggests. May cause confusion. |
| INFO (shadowed) | A user-level skill has the same name as a project skill and overrides it at runtime. |

Exit code 0 = no ERRORs (warnings and infos are OK). Exit code 1 = broken hard dependencies exist.

## Step 5: Categorize and Remediate

Only run this step when the user asks to fix the findings (or it is otherwise in scope). Don't volunteer remediation if the user only wanted to see the report.

The flow is encoded in the `classify_and_dispatch` procedure of the audit-skill contract above. Operational summary:

1. Re-run the script with `--json` if you didn't already.
2. For each finding, classify into one of the categories in the contract's `taxonomy:` block (A–J, plus K for special cases). Full detection signals and remediation details live in `references/finding-taxonomy.md`.
3. Bucket findings into **AUTO** / **DISCUSS** / **SPECIAL** per the taxonomy.
4. **In parallel**: launch a single background agent for the AUTO bucket with the brief template from `references/finding-taxonomy.md`, and open a foreground Q&A round for DISCUSS + SPECIAL.
5. After both return, merge changes, re-run the audit, iterate only on newly-surfaced findings.

The taxonomy doc is the authoritative reference for the **background-agent brief template** and the **foreground Q&A batching pattern**. The contract above declares the taxonomy structure; the reference doc supplies the operational templates.

## Scope Definitions in Detail

- **skills**: every `SKILL.md` under the scan roots (project, user, installed plugins). Backward-compatible with the original `skill-deps` behavior.
- **references**: every `*.md` file that lives inside a skill directory but is not the `SKILL.md` itself. Typically `references/*.md`, but also picks up any other markdown shipped alongside a skill (a per-skill `CLAUDE.md`, design notes, etc.). The skill pool is still populated from SKILL.md frontmatter; reference files contribute references, not skill identities.
- **md**: every `*.md` file under the scan roots, including SKILL.md, references, and any standalone docs.
- **all**: alias for **md**.

## Known Limitations

- **Prose-form hard deps** like "invoke `/example:review-read-comments` using the Skill tool" are classified as soft refs, not hard deps. The slash reference is still caught, just at WARNING level instead of ERROR.
- **Frontmatter parsing is regex-based** — handles the simple `key: value` shape used by SKILL.md files but does not parse the YAML contract block inside the body. The skill pool is built from frontmatter `name:` values only.
- **NON_SKILL_WORDS exclusion list** may occasionally filter a real skill name that collides with a common path segment (e.g. if someone creates a skill named "build"). Check the exclusion list in `references_audit.py` if a reference seems missing.
- **`settings.json`, `*.py`, and other non-markdown files** are not scanned at any scope.
- **Compound-adjective prose** like `X-/Y-foo` will match the trailing token (here, `Y-foo`) as a slash reference and produce a false positive. Category E in the taxonomy doc covers the remediation: reword the prose.
