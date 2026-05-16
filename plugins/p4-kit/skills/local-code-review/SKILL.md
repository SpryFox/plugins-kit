---
_schema_version: 1
name: local-code-review
author: christina
skill-type: technique-skill
description: Use when reviewing a pending Perforce changelist, or before asking the user to submit a CL just opened. Do NOT use for git diffs or non-Perforce reviews.
---

# Local Code Review

Run a multi-agent code review of a Perforce changelist directly in conversation. Reviewer subagents (set by the selected review profile) examine the diff in parallel; each flagged issue is then validated by an independent subagent to suppress false positives. Path-scoped pre-submit reminders (submit gates) authored in ancestor CLAUDE.md files are surfaced alongside the review for author confirmation. Results are rendered as markdown -- no persistence to disk.

```yaml
technique_skill:
  _schema_version: "1"
  trigger_model: auto
  identity: Run a multi-agent code review of a Perforce changelist using parallel Claude subagents.
  scope:
    covers:
      - reviewing pending Perforce changelists by CL number
      - CLAUDE.md compliance audits in a P4 workspace
      - bug audits scoped to introduced code
      - surfacing path-scoped pre-submit reminders (submit gates) from CLAUDE.md
    excludes:
      - git diffs and non-Perforce review workflows
      - persisting review output to disk or Swarm
      - reviewing previously-submitted changelists
      - enforcing submit gates (advisory only; enforcement belongs in a pre-shelve/pre-submit hook)
  techniques:
    - id: full_review
      name: Full multi-agent review
      keywords: [code review, perforce review, CL review, multi-agent review, claude.md compliance, parallel reviewers, p4 review]
      goal: Produce a markdown summary of confirmed issues for one pending Perforce CL.
      preconditions:
        - User has at least one pending CL OR has passed a CL number argument.
      steps:
        - n: 1
          action: Resolve the CL number (from argument, else list pending CLs and prompt the user).
          tool: p4
          input: "p4 -ztag changes -s pending -u $(p4 set -q P4USER | cut -d= -f2) -m 20"
          expected: A single integer CL number confirmed by the user.
        - n: 2
          action: Run prepare_review.py to fetch the diff (with shelved fallback), map ancestor CLAUDE.md files for each changed file, detect unreconciled files in the directories the CL touches, detect unresolved merges in the CL, and scan ancestor CLAUDE.md files for submit-gate reminders that apply to this CL.
          tool: ${CLAUDE_PLUGIN_ROOT}/scripts/prepare_review.py
          input: "<CL>"
          expected: JSON with cl, description, diff, changed_files, unique_claude_mds, unreconciled, unresolved, submit_gates.
          on_failure: Surface the stderr message to the user and stop. No retry.
        - n: 3
          action: |
            If bundle.unreconciled is non-empty, list the files (grouped by action: add / edit / delete) and ask the user whether any should be folded into the CL before review.
            - If the user picks one or more: run `p4 reconcile -c <CL> <local-paths>` to open them directly into the CL, then re-run prepare_review.py and use the new bundle.
            - If the user declines all: continue with the current bundle.
            On the post-reconcile re-run, do NOT prompt again about unreconciled files even if some remain -- the user already decided.
            Skip this step entirely if bundle.unreconciled is empty.
          tool: AskUserQuestion + p4 reconcile + prepare_review.py
        - n: 4
          action: Read every CLAUDE.md path in unique_claude_mds. Subagents do not need to re-read.
          tool: Read
        - n: 5
          action: |
            If bundle.submit_gates is non-empty, surface each gate as a checklist item the
            author must confirm BEFORE the review renders. Issue ONE AskUserQuestion call
            with `multiSelect: true`, one option per gate, labeled with the gate's summary
            and (in the description) the source CLAUDE.md path and the triggering files.
            Phrase the question as: "Confirm each pre-submit obligation you've already
            completed for CL <CL>."
            - Selected options become CONFIRMED gates.
            - Unselected options become UNCONFIRMED gates -- still rendered, just marked.
            Do NOT skip a gate, do NOT collapse multiple gates into one option, do NOT
            re-prompt. The author's answer (or lack thereof) is final.
            Skip this step entirely if bundle.submit_gates is empty.
          tool: AskUserQuestion
        - n: 6
          action: |
            Select one profile from `review_profiles` using its `selection.guidance` -- this is
            an inference call, not regex. Read each profile's guidance, weigh the actual contents
            of `bundle.changed_files`, and pick the most appropriate profile. Default to `code`
            when uncertain. Then launch every reviewer in that profile's `reviewers` list in
            parallel via a single message with N Agent calls, using the model named in each
            reviewer entry. Reviewers not listed in the selected profile are NOT launched.
          tool: Agent
          expected: JSON arrays of candidate issues from each launched reviewer.
        - n: 7
          action: |
            Launch one validator subagent per candidate issue, all in parallel via a single message.
            Use the selected profile's `validator_models[reason]` to pick the model per issue.
          tool: Agent
          expected: CONFIRMED or REJECTED per issue.
        - n: 8
          action: Drop rejected issues silently (do not report rejected issues to the user).
        - n: 9
          action: |
            Render the markdown review.
            - When `bundle.submit_gates` is non-empty, prepend a `## Submit checklist`
              section (confirmed and unconfirmed gates both rendered).
            - When `bundle.unresolved` is non-empty, prepend a `## Unresolved merges`
              section listing each unresolved file with its resolve type. This is
              informational, not a finding -- the CL is not submittable until the
              user runs `p4 resolve` on each entry, but the review still renders.
            Group the review body by file.
      checklist:
        - CL number resolved
        - Context bundled via prepare_review.py
        - Unreconciled files surfaced (and either folded in via `p4 reconcile -c <CL>` with a re-run, or explicitly declined)
        - All CLAUDE.md files read
        - Submit gates surfaced (if any) and author confirmation collected via a single AskUserQuestion
        - Review profile selected from review_profiles (first match)
        - Reviewers launched in parallel (single message, one Agent call per reviewer in the selected profile)
        - Validators launched in parallel (single message, N Agent calls), models picked from the profile's validator_models
        - Filtered to confirmed-only
        - Markdown rendered to chat (Submit checklist section prepended when gates applied; Unresolved merges section prepended when bundle.unresolved is non-empty)
      gotchas:
        - Always quote the exact CLAUDE.md rule text when flagging a claude_md issue. If you cannot quote it verbatim, do not flag it.
        - Sequential reviewer or validator calls waste time. Reviewers run in one message with one concurrent Agent call per reviewer in the selected profile (2 for data_only, 3 for code). Validators run in one message with N concurrent Agent calls.
        - Render only -- this skill outputs in chat. There is no Swarm comment, PR comment, or disk write step.
        - If prepare_review.py fails, report the error and stop. No retry.
        - Validators are independent of reviewers. The validator does not see who flagged the issue.
        - The unreconciled check must happen BEFORE reviewers spawn. Folding in forgotten files after agents have already reviewed the diff wastes their work and produces a stale review.
        - On the post-reconcile re-run, do NOT prompt again about unreconciled files. The user already chose. Re-prompting on the same list is annoying; re-prompting on a smaller list (because they only added some) implies the rest were forgotten when they were declined.
        - Submit gates are reminders, not findings -- they do NOT go through reviewer or validator subagents. They are parsed deterministically by prepare_review.py and rendered verbatim in a separate output section. Do not try to validate, score, or filter them.
        - The submit-gates AskUserQuestion fires once, regardless of gate count. multiSelect bundles all gates into one prompt. Re-prompting per gate is rude and adds no value -- the author's response is final either way.
        - Unconfirmed submit gates are NOT errors. Render them with ✗ so they're visible, but do not block the review or refuse to render the rest.
        - Unresolved merges are NOT findings -- they do NOT go through reviewer or validator subagents. They are detected deterministically by prepare_review.py (`p4 resolve -n -c <CL>`) and rendered verbatim in a separate output section. The reviewers see the raw diff (including any conflict markers) and may legitimately flag bugs in it; the unresolved section is a separate informational warning to the user.
  narration:
    note: Reviews involve long silent stretches (batched file reads, parallel subagents that take 30s+). Post one short status line per step using these templates verbatim, filling in the bracketed counts. Do not paraphrase, omit, or add extras.
    templates:
      - when: "Before step 1 (only if no CL arg was passed)"
        template: "Listing your pending changelists."
      - when: "Before step 2"
        template: "Gathering context for CL <CL>: fetching diff, mapping CLAUDE.md scopes, scanning for unreconciled files."
      - when: "Before step 3 (U >= 1)"
        template: "Found <U> unreconciled file(s) in the directories this CL touches. Asking before reviewing."
      - when: "After step 3 if user folded files in (U_added >= 1)"
        template: "Folded <U_added> file(s) into CL <CL> via `p4 reconcile`. Re-running prepare to refresh the diff."
      - when: "After step 3 if user declined (U_added = 0 and U >= 1)"
        template: "Continuing with CL <CL> as-is."
      - when: "After step 3, before step 4 (M >= 1)"
        template: "Got <N> changed file(s) and <M> unique CLAUDE.md scope(s). Reading them now."
      - when: "After step 3, before step 4 (M = 0)"
        template: "Got <N> changed file(s); no CLAUDE.md scopes apply."
      - when: "After step 2 (V >= 1)"
        template: "Found <V> file(s) with unresolved merges in CL <CL>. Will surface in the review output -- CL is not submittable until resolved."
      - when: "Before step 5 (G >= 1)"
        template: "Found <G> submit-gate reminder(s) applying to this CL. Asking the author to confirm."
      - when: "Before step 6"
        template: "Selected review profile: <P>. Launching <R> reviewer(s) in parallel: <reviewer_summary>."
      - when: "After step 6, before step 7 (X >= 1)"
        template: "Reviewers returned <X> candidate issue(s) (<B> bug, <C> CLAUDE.md). Launching <X> validator(s) in parallel."
      - when: "After step 6 (X = 0)"
        template: "Reviewers found no issues. Skipping validation."
      - when: "After step 7, before step 9"
        template: "Validators confirmed <Y> of <X>. Rendering review."
    variables:
      "<CL>": "the changelist number"
      "<N>": "len(bundle.changed_files)"
      "<M>": "len(bundle.unique_claude_mds)"
      "<U>": "len(bundle.unreconciled)"
      "<U_added>": "count of files the user chose to fold into the CL"
      "<X>": "total candidate issues from all launched reviewers combined"
      "<B>": "count where reason == 'bug'"
      "<C>": "count where reason == 'claude_md'"
      "<Y>": "count of validators returning CONFIRMED"
      "<P>": "selected review profile id (e.g. code, data_only)"
      "<R>": "count of reviewers in the selected profile"
      "<reviewer_summary>": "comma-separated '<model> <reviewer short name>' for each launched reviewer (e.g. 'sonnet CLAUDE.md compliance, opus diff-only bugs, opus introduced-code')"
      "<G>": "len(bundle.submit_gates)"
      "<V>": "len(bundle.unresolved)"
  review_profiles:
    description: |
      Routing table for selecting reviewers and models based on CL content. Exactly one
      profile is selected per review. Selection is an inference call -- read each profile's
      `selection.guidance` and pick the most appropriate one based on the actual contents
      of `bundle.changed_files`. Default to `code` when uncertain.
    profiles:
      - id: data_only
        selection:
          data_only_extensions: [".csv", ".yaml", ".yml", ".json", ".tsv", ".md"]
          guidance: |
            Select this profile when every changed file is either:
              (a) in `data_only_extensions` (flat data / docs), OR
              (b) an inert binary asset -- images, audio, video, fonts, compiled binaries,
                  3D/animation assets -- whose presence wouldn't change what a code-grade
                  review would find. These files aren't reviewable for logic anyway, so
                  including them in a CL shouldn't force the heavier `code` profile.
            Use judgment: the question is "is there any file in this CL that needs Opus-level
            semantic reasoning to review?" -- not "is every extension on a fixed list?"

            Pick `code` instead the moment any changed file contains executable logic
            (source code, scripts, build configuration that runs code, templated configs
            that are interpreted as code, etc.).
        rationale: |
          Flat data and doc files don't exhibit the failure modes Opus is uniquely good at
          (concurrency, lifetime, deep semantic reasoning). Bugs in these files are
          surface-level: malformed syntax, duplicate keys, column-count mismatches, broken
          cross-file references, schema violations -- pattern-matching tasks where Sonnet is
          at near-parity with Opus. `reviewer_c_introduced_code`'s scope is essentially empty
          for data/doc files; running it just burns tokens and generates hallucinations the
          validator must reject.
        reviewers:
          - { name: reviewer_a_claude_md_compliance, model: sonnet }
          - { name: reviewer_b_diff_only_bugs,       model: sonnet }
        validator_models:
          bug: sonnet
          claude_md: sonnet
      - id: code
        selection:
          guidance: |
            Default profile. Use whenever any changed file contains executable logic
            (source code, scripts, build configuration that runs code) -- i.e. anytime
            `data_only` doesn't clearly apply.
        rationale: "Full reviewer set with Opus where deep semantic reasoning pays off."
        reviewers:
          - { name: reviewer_a_claude_md_compliance, model: sonnet }
          - { name: reviewer_b_diff_only_bugs,       model: opus }
          - { name: reviewer_c_introduced_code,      model: opus }
        validator_models:
          bug: opus
          claude_md: sonnet
  # subagents: reviewer/validator definitions (scope, input, restrictions).
  # Models are NOT set here -- they are bound by the selected `review_profiles` entry.
  subagents:
    - name: reviewer_a_claude_md_compliance
      subagent_type: general-purpose
      scope: CLAUDE.md compliance only
      input: "full diff + per-file CLAUDE.md mapping with full text of each CLAUDE.md (read in step 3)"
      restrictions:
        - "Only consider CLAUDE.md files that share a path with the file being reviewed (use the per-file mapping; do not cross-apply)."
    - name: reviewer_b_diff_only_bugs
      subagent_type: general-purpose
      scope: obvious bugs visible in the diff alone
      input: "diff and CL description only"
      restrictions:
        - "MUST NOT use Read or any other tool to look beyond the diff."
        - "Only flag won't-compile, syntax/type errors, missing imports, unresolved references, definitely-wrong logic regardless of inputs."
        - "For data/doc files (data_only profile): focus on malformed syntax, duplicate keys, schema or column-count violations, and broken cross-file references."
    - name: reviewer_c_introduced_code
      subagent_type: general-purpose
      scope: bugs/security/logic problems in the introduced code that need broader context
      input: "diff, CL description, list of local file paths"
      restrictions:
        - "MAY use Read to look at surrounding context in the changed files when needed."
        - "Examples: concurrency issues, lifetime bugs, security holes."
    - name: validator
      subagent_type: general-purpose
      scope: confirm or reject one candidate issue with high confidence
      input: "the issue (JSON), the full diff, [if claude_md: relevant CLAUDE.md contents]"
      output_format: "exactly one line: 'CONFIRMED: <one-sentence reason>' or 'REJECTED: <one-sentence reason>'"
      restrictions:
        - "Validator does not see who flagged the issue. Independence is the value."
  false_positive_guardrails:
    only_flag:
      - "code that will fail to compile or parse (syntax errors, type errors, missing imports, unresolved references)"
      - "code that will definitely produce wrong results regardless of inputs (clear logic errors)"
      - "a CLAUDE.md rule clearly and unambiguously violated, with the exact rule quotable"
    do_not_flag:
      - "code style or quality concerns"
      - "potential issues that depend on specific inputs or state"
      - "subjective suggestions or improvements"
      - "pre-existing issues (only review the diff)"
      - "anything a linter would catch (do not run a linter)"
      - "issues that appear in CLAUDE.md but are explicitly silenced in the code (e.g. lint-ignore comments)"
    rule: "If you are not certain an issue is real, do not flag it. False positives erode trust."
  agent_assumptions:
    - "All tools are functional. Do not test tools or make exploratory calls."
    - "Only call a tool if it is required to complete the task."
  issue_format:
    description: "JSON shape returned by reviewer subagents and accepted by validators."
    schema: |
      [{
        "file": "<depot or local path>",
        "lines": "<line range, e.g. 42 or 42-48>",
        "reason": "bug" | "claude_md",
        "description": "<one-sentence explanation>",
        "citation": "<exact rule quote, only for claude_md issues>"
      }]
  submit_gates:
    description: |
      Path-scoped pre-submit reminders authored in CLAUDE.md files. Surfaced verbatim at
      review time when at least one file in the CL falls within the gate's scope. Reminders
      are not findings -- they don't go through reviewer or validator subagents. Detection
      is deterministic, performed by prepare_review.py.
    authoring_format: |
      Add this block to any CLAUDE.md (root, subdirectory, or both):

        **Submit gate:** <imperative -- what the author must do>.
        Applies to:
        - <path prefix or glob>
        - <path prefix or glob>

        <optional rationale paragraph, rendered verbatim with the gate>

      Scope path semantics:
        - No glob characters (`*`, `?`, `[`): prefix match. `Foo/Bar/` matches every file
          under Foo/Bar/. `Foo/Bar` (no trailing slash) is equivalent and does NOT
          accidentally match `Foo/BarBaz/`.
        - Contains glob characters: fnmatch-style glob, anchored to the workspace root.
          `*` matches anything including `/`; `?` matches one character.
        - Case-insensitive on Windows, case-sensitive elsewhere.

      Multiple gates per CLAUDE.md allowed; blocks must be separated by a blank line.
      Malformed blocks (missing `Applies to:`, empty scope list) are skipped with a
      one-line stderr warning -- never silently dropped.
    rendering: |
      When bundle.submit_gates is non-empty, the rendered review prepends a
      `## Submit checklist` section ABOVE the per-file review body. Each gate renders as:

        - **[✓|✗] <summary>** -- per `<source>`, triggered by `<file>` (+N more if many).
          > <rationale, indented as blockquote, omitted if empty>

      ✓ = author confirmed in the step-5 AskUserQuestion.
      ✗ = author did not confirm. NOT an error; the review still renders.

      Always show the section when gates applied -- including in the "no issues" path.
  output_format:
    description: "Final markdown rendered to chat. Unresolved merges (when applicable) and Submit checklist (when applicable) above the per-file review body."
    template: |
      ## Unresolved merges
      CL is not submittable until each file below is run through `p4 resolve`.
      - `path/to/file.cpp` -- content resolve pending (from `//depot/branch/file.cpp`)
      - `path/to/other.csv` -- branch resolve pending

      ## Submit checklist
      - **[✓] ./build.sh configbinaries must pass before submit** -- per `<path>/CLAUDE.md`, triggered by `GameConfigs/Real/x.csv`.
      - **[✗] Regenerate the asset index** -- per `<path>/CLAUDE.md`, triggered by `Content/Assets/y.uasset`.
        > <rationale if any, as a blockquote>

      ## Review: CL <CL> -- <description>

      Found N issues (M filtered as false positives).

      ### path/to/file.cpp
      - **[bug]** L42: Buffer overflow risk -- `items[i]` accessed without bounds check.
      - **[claude_md]** L78: Violates `src/CLAUDE.md` rule "Use absl::Status not bool returns".
    empty_template: |
      ## Submit checklist
      - **[✓] ./build.sh configbinaries must pass before submit** -- per `<path>/CLAUDE.md`, triggered by `GameConfigs/Real/x.csv`.

      ## Review: CL <CL> -- <description>

      No issues found. Reviewed for bugs and CLAUDE.md compliance.
    notes:
      - "Omit the Unresolved merges section entirely when bundle.unresolved is empty."
      - "Omit the Submit checklist section entirely when bundle.submit_gates is empty."
      - "When matched_files has >3 entries, render the first 3 then '(+N more)'."
      - "Rationale renders as a markdown blockquote (`> `) indented one level below the bullet, only if non-empty."
      - "Unresolved-merge entries render local path first (workspace-relative if possible); append `(from <fromFile>)` only when from_file is non-empty (integrations); omit for plain edit/sync resolves."
```
