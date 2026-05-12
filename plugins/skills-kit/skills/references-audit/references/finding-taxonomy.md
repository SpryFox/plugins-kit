# Finding Taxonomy and Remediation

Load this when you are interpreting a references-audit report and deciding how to fix each finding. The scanner's job is detection; the classification and remediation here is inference work — that's why it lives in a skill, not in the script.

## The triage pipeline

```
report -> classify each finding -> bucket -> dispatch
                                              |
                            +-----------------+-----------------+
                            v                 v                 v
                          AUTO             DISCUSS           SPECIAL
                  (background agent)   (foreground Q&A)  (foreground Q&A)
```

For each finding produced by the scanner (markdown or JSON output):

1. **Classify** into exactly one category A-J below. If none fit, classify as **K (unclassified)**.
2. **Bucket**:
   - **AUTO** — solution is mechanical and the surrounding context is unambiguous. Categories E, F, G, I, J (always), plus A when the rename map is known. Dispatched to a background agent with a fully-resolved edit payload.
   - **DISCUSS** — the category is clear but a user decision is needed (which sub-case, what mapping). Categories B, C, D, H, A (no mapping), I/J (ambiguous cue).
   - **SPECIAL** — category K, the special-case escape hatch.
3. **Dispatch in parallel**: launch the background agent for the AUTO set, and at the same time open the foreground Q&A for the DISCUSS + SPECIAL set. Do not block one on the other.
4. After both return, merge edits and re-run the audit. Iterate only on newly-surfaced findings.

The AUTO/DISCUSS split is conservative: when in doubt, route to DISCUSS. The user can override an automation choice cheaply; an undetected wrong fix is expensive.

---

## Categories

### A. Renamed skill (1:1 replacement exists)

- **Detection signal.** WARNING `/example:old-name` (or ERROR `skill: "example:old-name"`); a current skill `/example:new-name` clearly covers the same responsibility (confirmable from upstream CHANGELOG, the new skill's description, or an explicit "renamed from" line).
- **Bucket.** AUTO when the mapping is known. DISCUSS otherwise (ask once for the whole audit: "I see refs to `/example:old-name`. Best guess `/example:new-name`. Apply?").
- **Default remediation.** Mechanical find/replace of the old name with the new name within the file. If the surrounding sentence describes old behavior, also update the prose so it matches the new skill.
- **Example (CL 147036).**
  ```
  - references using this prefix are not flagged as `/skill-deps`
  + references using this prefix are not flagged as `/references-audit`
  ```

### B. Retired/deleted skill (no replacement)

- **Detection signal.** WARNING `/example:old-name`; no current skill covers the responsibility. The reference is often the subject of a whole section or paragraph.
- **Bucket.** DISCUSS — the delete-vs-rephrase sub-case is judgment.
- **Default remediation.** Four sub-cases, picked by structural context:
  1. Reference is the **subject of a whole section/paragraph** -> delete the section.
  2. Reference is an **incidental clause** (e.g. "similar to the old skill") -> delete the clause, keep the surrounding sentence.
  3. Reference is **historical context inside a doc that mixes live and stale names** (e.g. "previously known as ...") -> demote to backticked literal (`` `old-name` ``).
  4. **The whole document is a historical artifact** (rollout summary, design plan recording past intent, postmortem) where consistent backtick-demotion would either be noise or destroy the historical record -> add the legacy names to the file's `references-audit-allow-stale` YAML frontmatter and write an editor's note at the top explaining current state. Leave the slash refs in place. This preserves typography parity with the doc's other still-live references and keeps the audit honest: a *new* broken ref in the same doc still fires.
- **Example (CL 147036).** dialog-domain referenced the deleted `dialog-experiments` skill; the whole "External Analysis Tools" section was removed. **Example (allow-stale).** A rollout summary describing 2026-Q1 work lists `/plan`, `/preflight`, `/swarm submit` in a single bullet. `/plan` was later merged into `/designer-plan-domain`; the others still resolve. Demoting just `/plan` would produce inconsistent typography; adding `plan, designer-plan` to the file's `references-audit-allow-stale` plus a one-line editor's note silences the audit without rewriting the historical record.

### C. Merged skill (subskill folded into parent)

- **Detection signal.** WARNING `/example:parent-sub`; a current skill `/example:parent` exists; release notes or SKILL.md document the merge.
- **Bucket.** AUTO for prose rewrites. DISCUSS when the reference appears inside a dispatch-alias table (a literal-string matcher) -- those need to stay as a backticked literal, not converted to the new dispatch form.
- **Default remediation.**
  - In prose: rewrite the slash form (e.g. `/example:parent-sub`) to the new dispatch form (`/example:parent sub`).
  - In dispatch alias tables / synonyms lists: keep the literal name in backticks (e.g. `` `parent-sub` ``), not as a slash reference. The skill code may still accept the legacy literal as a synonym; the reference shouldn't look like a callable skill.
- **Example (CL 147036).**
  ```
  - Via `/playtest preflight` (or the legacy `/playtest-preflight`) for standalone validation
  + Via `/playtest preflight` (or the legacy `playtest-preflight` argument) for standalone validation
  ```

### D. Scope-violating cross-reference (project <-> personal)

- **Detection signal.** WARNING `/example:ref-name`; the referenced skill **exists** but in the opposite scope (project skill referencing a personal skill, or a shipped plugin skill referencing a project-only skill). The scanner reports it as missing because the resolver respects scope boundaries.
- **Bucket.** DISCUSS if the entire skill is structured around the comparison; AUTO if it's an incidental "vs ..." comparison.
- **Default remediation.**
  - **Project / plugin -> personal:** delete the cross-reference. A shipped skill cannot assume the reader has the personal skill installed.
  - **Personal -> project:** usually fine; only flag if the personal skill is meant to be portable.
- **Example (CL 147036).** project-scoped `claude-feedback` SKILL.md had a "Key Differences vs /retro" section; `/retro` is a personal skill, so the section was deleted entirely.

### E. Compound-adjective false positive

- **Detection signal.** WARNING `/example:word-foo`; the literal text contains `X-/Y-thing` (compound adjective with embedded slash) or other prose where a slash appears as punctuation, not as a skill reference.
- **Bucket.** AUTO.
- **Default remediation.** Reword the prose to eliminate the slash. Preserve technical meaning -- the rewrite is "express the same idea differently", not "escape the scanner".
- **Example (CL 147036).**
  ```
  - 'Slack file downloads are bot-/user-token-gated.'
  + 'Slack file downloads are gated by bot or user token scopes.'
  ```

### F. Non-skill CLI flag false positive

- **Detection signal.** WARNING `/example:flag-name`; surrounding text is a shell or CLI invocation (binary name + flags). Common with MSBuild, `devenv`, `cl.exe`, the linker, and other Windows-native tools.
- **Bucket.** AUTO.
- **Default remediation.** Wrap the whole command in a fenced code block (```` ``` ````). The scanner masks fenced regions, so refs inside them produce no findings.
- **Example.**
  ```
  - Run: devenv /debugexe "...exe" /minidump "...dmp"
  + Run:
  +
  + ```
  + devenv /debugexe "...exe" /minidump "...dmp"
  + ```
  ```

### G. XML / template placeholder false positive

- **Detection signal.** WARNING `/example:tag-name`; surrounding text contains XML or HTML closing tags (such as `</example:foo>`) or template placeholders inside angle brackets.
- **Bucket.** AUTO.
- **Default remediation.** Same as F — wrap the XML or template example in a fenced code block. Same scanner masking applies.

### H. Harness transcript false positive

- **Detection signal.** Many WARNINGs in the same file or directory; references match Claude-harness vocabulary (`/example:command-args`, `/example:system-reminder`, `/example:task-id`, `/example:tool-use-id`, `/example:command-name`, `/example:command-message`, etc.).
- **Bucket.** DISCUSS — pick the exclusion mechanism once, then apply.
- **Default remediation.** Add the directory to the scanner's `--ignore-dir` flag in the project's invocation wrapper. If the transcripts are project-specific, also commit the wrapper invocation (or document the recommended flags in the host project's CLAUDE.md).
- **Example.** Adding `--ignore-dir 'ClaudeFeedback'` removes ~30 spurious warnings from a session-log archive in one config entry, with no per-file edits.

### I. Illustrative example in a design doc

- **Detection signal.** WARNING `/example:foo` **or** ERROR `skill: "example:foo"`; the surrounding sentence is describing skill-reference syntax in the abstract -- the doc is *about* references, not *making* one.
- **Bucket.** AUTO when the surrounding sentence is clearly meta-descriptive ("a `/example:skill-name` reference looks like..."). DISCUSS when the reference sits inside a procedure or playbook (it could be a real instruction).
- **Default remediation.** Add the `example:` prefix to the slash-form, and likewise to any `skill: "..."` hard-dep literal. Both are documented escape prefixes that the scanner ignores.
- **Example.**
  ```
  - soft references (`/name` in documentation text that mislead)
  + soft references (`/example:name` in documentation text that mislead)
  ```

### J. Forward-looking / proposed skill

- **Detection signal.** WARNING `/example:foo`; no current skill named `foo`; surrounding prose frames it as "planned", "future", "we should build", "today: <legacy approach>".
- **Bucket.** AUTO when the prose explicitly cues "planned" / "future" / "proposed". DISCUSS if it's ambiguous (could be a real ref to a deleted skill rather than an aspirational plan).
- **Default remediation.** Add the `proposed:` prefix to the slash-form (a documented escape prefix). Optionally append a one-line "(planned, not built)" note if the context isn't already explicit.

### K. Unclassified / special case

- **Detection signal.** None of A-J fit cleanly after a deliberate attempt.
- **Bucket.** SPECIAL.
- **Default remediation.** Surface the finding to the user with: the report line, what you tried to match, why none of A-J fit. The user decides the strategy. If the strategy generalizes, propose it as a new category and add it to this doc in a follow-up.

---

## Background-agent brief template

When the AUTO bucket is non-empty, launch a single background agent. The brief is fully self-contained -- the agent does not reclassify, it applies. Use this template:

> **Task: apply references-audit AUTO fixes.**
>
> Audit-references identified N broken cross-references in this project. The classification and remediation has been done already; your job is to apply the listed edits exactly as specified. Do not reclassify; do not invent new fixes; do not touch files outside the list.
>
> **Per-finding payload** (one block per fix):
>
> - File: `<absolute or project-relative path>`
> - Line: `<1-indexed line number from the scanner>`
> - Category: `<A | C | E | F | G | I | J>`
> - Before (exact text to match): `<single-line or short snippet>`
> - After (exact replacement): `<single-line or short snippet>`
>
> **Authority and constraints**:
>
> - You may modify any file in the per-finding list. Honor the host project's version-control gate (e.g. `p4 edit` on Perforce projects, `git add` on git) before editing.
> - You may NOT submit, push, or otherwise publish the changes.
> - You may NOT touch files outside the per-finding list.
> - If a finding's "Before" text does not match the file (file changed since classification), skip that finding and surface it back. Do not guess a replacement.
>
> **Return contract**:
>
> 1. The list of findings successfully applied (file + line + category).
> 2. The list of findings skipped, each with the reason.
> 3. Any newly-noticed issues that fall outside the brief (do not act on them).
>
> Return this as a short structured report. The main agent will re-run references-audit after you return and reconcile any remaining findings.

The main agent constructs the per-finding payload by:

- Reading the JSON output from `references_audit.py --json`.
- For each finding routed to AUTO, computing the **exact before-text** by reading the cited file at the cited line.
- Computing the **after-text** per the category's default remediation above.
- Bundling all payloads into the single Agent call.

This keeps inference (classification, remediation strategy) on the main agent and execution (apply edits) on the background agent. The background agent is cheap to parallelize against the foreground DISCUSS/SPECIAL conversation.

---

## Foreground Q&A pattern (DISCUSS + SPECIAL)

Batch every DISCUSS and SPECIAL finding into one user-question round. Render as a numbered list, each item showing:

- The scanner's report line (file + line + ref).
- The category letter and rationale.
- The inferred options (e.g. "delete section / rewrite clause / demote to backtick" for category B).
- Your recommendation.

The user answers in one pass. Anti-pattern: per-finding round-trips. Anti-pattern: asking the user to gate the AUTO bucket on the DISCUSS decisions -- the two are independent.

---

## When this taxonomy needs to grow

If a finding lands in category K (unclassified) and the user's chosen strategy generalizes, propose a new category. Criteria for adding:

- The detection signal is recognizable from the scanner's output without the agent having to re-read the file.
- The remediation can be expressed as a default that applies to the majority of instances in the new category.
- The category is **mutually exclusive** with A-J. If a finding can fit two existing categories, refine the detection signal of one of them rather than adding a new one.

The taxonomy is closed-world only for the scanner's current detection capabilities. As the scanner gains the ability to detect new kinds of staleness (e.g. broken file paths, dead URLs, orphaned references in `Skill: { name: ... }` blocks the regex currently misses), new categories will be added here.
