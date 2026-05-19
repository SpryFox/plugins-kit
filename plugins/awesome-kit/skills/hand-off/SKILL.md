---
_schema_version: 1
name: hand-off
author: christina
skill-type: technique-skill
description: Use when /hand-off is invoked to package session work for a fresh agent via a folder that manages next-session context. Do NOT use for ad-hoc summaries.
disable-model-invocation: true
user-invocable: true
argument-hint: "[optional notes about the hand-off]"
---

# Hand-Off

The user wants to hand the current session's work off to a fresh agent. Your job in this turn is to produce (or update) a project folder whose contents orient the next agent on turn 1 and manage their context budget thereafter.

Optional notes from the user: $ARGUMENTS

This skill operationalizes the cross-session side of the communication framework. The shared glossary -- `work-unit`, `auto-loaded vs on-demand context`, `three-part end-of-turn template`, `State A / State B`, `orientation moment`, `self-contained briefs`, `hand-off baton`, `provenance triad`, `argument-based invocation modes` -- is canonical at `references/communication-framework.md`. Definitions live there; this file describes only how the protocol applies them.

A worked example of the produced CLAUDE.md is bundled at `references/example-claude-md.md`. Read it if the template below feels abstract -- it makes the shape concrete.

## The core idea: two gates

A hand-off folder is a context-management strategy, not a filing system. The two gates -- `auto-loaded` vs `on-demand` -- are defined in the framework. Applied here:

- **Auto-loaded** -- `CLAUDE.md` (Claude Code auto-loads when cwd is the folder), plus anything `CLAUDE.md` directs the next agent to read on turn 1 (notably `plan.md`).
- **On-demand** -- everything else (log.md, parent-plan.md, design notes, archived step details).

The discipline of the hand-off is keeping the auto-loaded set tight. Anything that does not need to be in the agent's head on turn 1 of the next session belongs in an on-demand doc.

## Folder layout

```
./tmp/<short-slug>/
    CLAUDE.md         <- continuation prompt + guide; auto-loaded
    plan.md           <- the plan; read on turn 1 because CLAUDE.md says so
    log.md            <- history; on-demand
    [other docs]      <- on-demand reference material (parent plan, step details, design notes)
```

`<short-slug>` should be the natural scope of the work-unit (phase or project), not session-scoped. Example: `atoms-17-phase2` (phase) or `loc-pipeline` (project) -- not `atoms-22` (one session within the phase).

## `CLAUDE.md` -- continuation prompt + guide

Auto-loaded every session. This is the agent's first 60 seconds of orientation. Everything they need in those 60 seconds goes here; everything else gets indexed and lives elsewhere.

### Required template (eight `##` sections under a single `# Project Overview`)

The eight `##` sections below are template-required. Project-specific `###` subsections (or `####` deeper) are additional -- include them where the work needs them. The produced CLAUDE.md does NOT need to annotate template-vs-additional; the consistent eight `##` shape is the contract.

```
# Project Overview
## Where we are today
### Environment
## Where we want to get to
## Immediate Priorities
## Project vocabulary
## Protocols
### Always-invoke skills (BEFORE any doc reads)
### Required reads on turn 1
### Opening response protocol
### Communication protocol
## Behaviors
### Autonomy status
### Authorizations
### Rules to follow
### Sub-agent orchestration -- main-context preservation
### Anti-patterns to avoid
## Relevant files
### Project folder
### External files
```

### Section semantics

- **`## Where we are today`** -- live state. Static descriptive snapshot: environment values, in-flight processes, what's wired up right now. Things that are simply *true* of the project as of this hand-off. Includes a `### Environment` subsection with cwd, platform, key tool versions, env quirks.
- **`## Where we want to get to`** -- the goal the work is converging on. Folds in the old "Current goal" -- state it falsifiably so the next agent can tell when it's done.
- **`## Immediate Priorities`** -- decisions and actions queued *against* the snapshot in "Where we are today." Near-term blockers, pending decisions the user needs to make, the concrete next 1-2 actions. **Seam test**: if it would still be true after the agent acts (a fact of the project), it belongs in *Where we are today*; if acting on it changes it (a decision or next step), it belongs in *Immediate Priorities*.
- **`## Project vocabulary`** -- terms, stage names, trial names, domain conventions used in the rest of the file. Includes naming evolutions that left on-disk paths with old names (e.g. "renamed `cycle` to `pass` in prose; on-disk paths retain `cycle`"). The next agent reads the rest of the file fluently because vocabulary is established here.
- **`## Protocols`** -- time-boxed procedures with a defined trigger and a defined output shape. **Test**: if you can name the trigger ("turn 1", "end of every turn", "before any tool use") AND the output shape (a checklist, a sentence template, a sequence of skill invocations), it is a Protocol. Otherwise it is a Behavior. Subsections:
  - **`### Always-invoke skills (BEFORE any doc reads)`** -- one tool call per listed skill, before reading `plan.md` or any other doc. Skills load vocabulary that the rest of CLAUDE.md assumes; reading docs first means reading them without the right vocabulary in context.
  - **`### Required reads on turn 1`** -- explicit list of docs to read before acting. At minimum `plan.md`. Add `log.md` only if the next agent needs prior rationale to act on turn 1; otherwise leave it on-demand.
  - **`### Opening response protocol`** -- the `orientation moment` for session resume. What the agent says after reading the required docs, before tool use. Example template (project-specific text varies):
    > "Read plan.md (+ any other required reads). Current goal: <restated in own words>. Starting with: <first concrete action>. Unclear / blocked on: <issue, or 'none'>."
  - **`### Communication protocol`** -- default to `/verbose-updates`'s three-part end-of-turn template (see framework). Note project-specific overrides here (audit-log shape, domain terminology, what NOT to say).
- **`## Behaviors`** -- standing principles and gates that apply continuously regardless of which protocol is firing. **Test**: if it has no trigger -- it constrains *how* you act between/within protocol firings -- it is a Behavior. Subsections:
  - **`### Autonomy status`** -- whether the user is reading every turn or returning cold; how aggressive to be; what the standing posture is. (Promoted from the old "AFK status / autonomy level"; framed as the situational state of the user's attention, not a binary AFK toggle.)
  - **`### Authorizations`** -- explicit, named pre-authorized actions. `p4 edit` of tracked files: proceed. `p4 submit` of CLs touching X: permitted after local review. Background-agent dispatch on independent work: pre-authorized. LLM-spending under $N: pre-authorized. The point is to enumerate the standing yes-list so the next agent does not round-trip for already-authorized work.
  - **`### Rules to follow`** -- project-specific operational rules. "Don't `p4 submit` without approval"; "background long-running work, never inline"; "ASCII-only in source files"; concurrency settings; tool wrappers.
  - **`### Sub-agent orchestration -- main-context preservation`** -- when work should be pushed to sub-agents, when main launches things itself (long-running processes), the single-tier sub-agent constraint (sub-agents can't spawn sub-agents). Main's job is orchestration; heavy reading goes to sub-agents.
  - **`### Anti-patterns to avoid`** -- explicit don'ts for this work. "Be careful with X" is vague; anti-patterns make boundaries concrete.
- **`## Relevant files`** -- file index. Split into:
  - **`### Project folder`** -- contents of `./tmp/<short-slug>/` (this hand-off's own working tree). One-line purpose per file. Indicate which are auto-loaded (the required-reads list) vs on-demand.
  - **`### External files`** -- files, scripts, directories outside the project folder that this work depends on. One-line purpose per file. Group under `####` subsections where natural (`#### Prompt YAMLs`, `#### Audit-directory shapes`, etc.). Link out to summary documents when the underlying data is large -- the body here is the project-local quick index, not a full re-enumeration.

**One-line purpose per file.** Every doc listed under `## Relevant files` carries a one-line description of what it is and why the agent would read it. "Files: a.md, b.md, c.md" is the anti-pattern -- the next agent should not have to open a file to discover whether to open it.

### Length

**Soft target: up to 400 lines.** The shape is "every section has what it needs, nothing has accumulated unnecessarily." A section that keeps growing is a signal its content belongs in a referenced doc and CLAUDE.md should just link to it. CLAUDE.md is auto-loaded every session, so length is a context budget; 400 lines is the comfortable ceiling, not a goal. Land lower when the work allows.

## `plan.md` -- the plan

Read on turn 1 because CLAUDE.md tells the agent to. Two sections only:

1. **Accomplished** -- one line per completed step. No implementation detail.
2. **Forward overview** -- the next 1-3 steps in actionable detail; later steps as one-line summaries only.

**Soft target: up to 400 lines** (verify with `wc -l plan.md`). plan.md is read on turn 1 of every session, so length is a context budget; 400 lines is the comfortable ceiling, not a goal. Land lower when the work allows.

Apply rotation by default to stay under this target -- it is not a fallback that activates only when over the limit, it is the standing discipline. Rotation is the steady-state habit that keeps the auto-load surface lean; treating it as exceptional ("only when bloated") is how plans drift over 400 one session at a time.

**Rotation strategy: history first, optional second.** When reducing, walk the file with this priority:

1. **Primary -- move historical content out.** Completed-step detail, retrospective context, accumulated session-by-session log -- these go to `log.md` (or `step-N-completed.md`). The plan is for the remaining work, not the work already done. A completed step keeps a one-line summary plus a link to log.md; no implementation detail.
2. **Secondary -- move not-always-required forward content out.** Identify subsections that the next agent does NOT need on turn 1 of every session: optional branch detail, "alternative approach" subsections, parked-decision lists if they have grown, far-future-step explanations. These go to referenced docs (`alternatives.md`, `parked.md`, `step-N-details.md`) with a one-line pointer in plan.

When over 400 lines, rotate primary content (completed-step detail to log.md) first; secondary (far-future-step detail to referenced docs) only if primary alone doesn't get under 400. Removing future work from plan is more expensive (the next agent has to follow a link to know what's coming) than removing past work (the next agent does not care).

The plan is a moving window, not a record (the framework's "rotate forward" principle, applied to the auto-load surface).

## `log.md` -- history

On-demand only. Holds:

- Approaches tried and didn't work, with reasons -- **but only if the reason would re-bite a fresh agent.** A superseded approach whose reasoning is now obvious goes nowhere; the log is not a session diary.
- Decision rationale (only if not currently actionable; current-decision rationale belongs in the plan). Use the `provenance triad` shape from the framework -- surface / finding / follow-up -- where it fits.
- Surprises about the codebase that informed direction.
- Completed-step details rotated out of the plan.
- Notes that would help someone six months from now reconstruct reasoning.

Multiple log files (`log-decisions.md`, `log-dead-ends.md`) are fine when volume justifies the split.

## Optional referenced docs

Named per the work; CLAUDE.md indexes them with one-line purposes. Common patterns:

- `parent-plan.md` -- architecture / multi-phase context when this work is a slice.
- `step-N-details.md` -- detailed implementation for one step.
- `step-N-completed.md` -- post-completion archive of details rotated out of plan.
- Design docs, glossaries, snapshots -- whatever the work needs.

No prescribed names. The rule: every doc in the folder is named in CLAUDE.md's index with a one-line purpose.

## Rotation discipline

The plan should always answer "where are we now and what's coming." History and far-future detail get rotated out.

- **Step completed** -- move its detailed instructions from plan.md to log.md (or a `step-N-completed.md`). Plan keeps one line: "Step N: done [link]."
- **Future step too far away** -- move its implementation detail to a referenced doc. Plan keeps one line: "Step N: <goal> [link]."
- **Decision made** -- if currently-actionable, one line in plan; if not, into the log.

Rule: if it's not actionable for the next session's work, it does not belong in the auto-load surface.

## Anti-patterns

- **Silent-go-to-work.** Next agent reads docs, picks up tools, makes changes. No orientation check, no question if confused. Misorientation discovered turns later. The opening-response protocol in CLAUDE.md is the antidote -- it is the framework's `orientation moment` made explicit.
- **Implicit communication protocol.** "Behave well" -- vague. The Communication protocol subsection of CLAUDE.md must name `/verbose-updates` (or another explicit protocol) as the end-of-turn default and call out any project-specific overrides.
- **Rules without anti-patterns.** "Be careful with X" -- agent fills in their own definition. Anti-patterns make the boundary concrete.
- **Index-without-purpose.** "Files: a.md, b.md, c.md" -- agent has to read each to know what they're for. One-line purpose per doc.
- **Separate must-read decisions doc.** False economy. If must-read, it belongs in the plan. If not must-read, it belongs in the log.
- **Plan as record.** Plan accumulates every step's full detail forever. Auto-load surface bloats. Rotate.
- **Session-scoped slug.** `atoms-22` outlived by `atoms-17-phase2`. Pick the scope that outlives the session -- the work-unit, not the conversation.
- **Vocabulary loss across the hand-off.** Mid-session, terms evolve (`T4` -> `G4`, `cycle` -> `pass`, `op#2` -> `glossary-correct stage`). Without a `## Project vocabulary` section, the next agent reads the file in a different dialect from the one that wrote it and either re-derives the vocabulary or asks the user to. Capture the final names AND the decoder for paths that retain old names.
- **Session diary in log.md.** Every superseded approach dumped in regardless of whether the reasoning still matters. The filter is "would this rationale re-bite a fresh agent if not recorded?" -- if no, discard.
- **Conversation-context references in CLAUDE.md or plan.md.** "As we discussed", "the user just clarified that...", "see the prior turn's analysis." A cold reader cannot resolve these. The fact in question goes in the artifact; the conversation pointer goes nowhere.

## Workflow

Run in a single response. Don't pause for confirmation between steps unless something is ambiguous.

### Step 1 -- Locate or create the folder

If a folder already exists for this work, update in place. Three passes:

- **Rotation pass.** Move completed-step details from plan.md to log.md; move far-future-step details to referenced docs; trim CLAUDE.md sections that have grown stale.
- **Stale-state pass.** Anything now untrue under current scope (e.g. "ready to ship" when scope just expanded) gets fixed in place. Untrue text is worse than missing text.
- **Vocabulary pass.** Compare the vocabulary the session evolved (names that drifted, stage names, trial names, paths that retain old names) against what is currently in `## Project vocabulary`. Update so the next agent reads CLAUDE.md in the same dialect the session ended in.

If no folder exists, create one at `./tmp/<short-slug>/`. Pick the slug at phase or project scope (the work-unit, not the session); confirm it in your end-of-turn summary so the user can correct.

### Step 2 -- Write or update `CLAUDE.md`

Use the eight required `##` sections in order (see "Required template" above). Project-specific `###` subsections under any of those go in where the work needs them.

If a previous CLAUDE.md exists, keep what's still true; update *Where we are today*, *Immediate Priorities*, *Autonomy status*, operational changes, and the file index.

**Vocabulary capture.** Before writing the rest of CLAUDE.md, populate `## Project vocabulary`. Include: stage / phase names, trial names, terms whose meaning evolved this session, paths whose on-disk literal disagrees with current prose (the decoder). If you can't name three vocabulary items the session leaned on, you are under-capturing -- think again about what a fresh agent would have to ask the user to translate.

**Session-vs-project filter.** Include only what a fresh agent needs to act. Abandoned approaches whose reason would re-bite go to `log.md`; abandoned approaches whose reason is now obvious go nowhere. Interrupted thoughts go nowhere.

**Checklist sweep.** Before declaring CLAUDE.md done, consider each of the eight `##` sections explicitly. For each, ask: "is there session content that belongs here that I have not transcribed?" Common omissions: project-specific Authorizations (the standing yes-list the session built up), Project vocabulary, External files outside the project folder. Silent omissions are the failure mode this checklist exists to catch.

### Step 3 -- Write or update `plan.md`

Two sections: accomplished + forward overview.

**In-flight triage.** Before writing forward overview, classify every in-flight item into one of four buckets:

- **Blocked on user decision** -- needs the user to choose between named options. Surface under `## Immediate Priorities` in CLAUDE.md; do not list as a forward step in plan.md until decided.
- **Blocked on prior step** -- waiting on a previous step to land. List in plan.md as the prior step's continuation, not as a standalone item.
- **Done but uncommitted** -- work is on disk but not yet committed / submitted / merged. Note in plan.md so the next agent does not re-do.
- **Queued** -- ready to start. The next-1-3-steps actionable detail covers these.

After writing, run `wc -l plan.md`. The target is **at or below 400 lines** -- the comfortable ceiling, not a goal; land lower when the work allows. If over 400, rotate detailed content out (primary first -- completed-step detail to log.md; secondary if needed -- far-future-step detail to a referenced `step-N-details.md`) and re-verify. Do not move on until the count is at or below 400.

### Step 4 -- Update or create `log.md`

Capture anything worth retaining but not worth auto-loading: dead ends with reasons (only if the reason would re-bite), decisions and rejected alternatives (use provenance triad shape where useful), surprises, details rotated out of plan.

### Step 5 -- Self-verify

Read CLAUDE.md and plan.md as if you were the next agent. Verify:

- Can you identify the current goal without reading anything else?
- Do you know what to do next, concretely?
- Do you know what to say back after reading the docs (the opening-response protocol)?
- Are the working directory and any non-obvious operational rules stated?
- **Cold-reader self-containment.** Does anything in CLAUDE.md or plan.md reference conversation context a cold reader cannot resolve ("as we discussed", "the user just said", "see the prior turn")? If yes, restate the fact in the artifact and drop the conversation pointer.
- **Vocabulary coverage.** If a fresh agent read CLAUDE.md and then opened a path in `## Relevant files`, would the path's literal name match the prose name? If not, `## Project vocabulary` is missing the decoder.

If any answer is unclear, fix before reporting back.

### Step 6 -- Report back

End the turn with: folder path, filenames, one line each on contents. Then the `hand-off baton` (defined in the framework). Your response must end with exactly this two-line block, as the last thing in the response:

```
Paste into a new session to continue:
<prompt text>
```

The first line is literal. The second line (`<prompt text>`) is a short, actionable instruction that points the next agent at the entry point -- typically `Read <project-folder>/CLAUDE.md and proceed per its protocol.`. The user copies the second line, opens a new session, and pastes it as the first user message. Do not omit it.

## Principles specific to hand-offs

The framework's general principles (context is a budget, rotate forward, conversations are ephemeral) apply -- see `references/communication-framework.md`. Hand-off-specific additions:

- **One must-read doc per concern.** Plan for the work; CLAUDE.md for the operation. No third must-read.
- **Don't duplicate.** Each fact lives in exactly one doc.
- **Prefer editing over creating.** Update existing artifacts unless there is a genuinely new concern.
- **Sibling hand-offs.** If parallel-stream folders exist for related work, CLAUDE.md mentions them so the next agent doesn't re-claim.
- **ASCII only** in all files (no smart quotes, em dashes, or other Unicode look-alikes).
- **No absolute paths** in the artifacts -- use project-root-relative paths so they work across machines.
- **Fit the work to the framework.** The eight `##` sections above cover most hand-offs. Resist adding more required sections to suit a specific work shape; let `###` subsections fill them with what the work needs.

## Contract

```yaml
technique_skill:
  _schema_version: "1"
  trigger_model: user-only
  identity: "Package the current session's work for a fresh agent by creating or updating a project folder whose contents manage the next agent's auto-loaded context budget."
  references:
    - "references/communication-framework.md (canonical glossary for shared vocabulary)"
    - "references/example-claude-md.md (bundled worked example of the produced CLAUDE.md template)"
  scope:
    covers:
      - "Producing or updating ./tmp/<slug>/ with CLAUDE.md + plan.md + log.md + optional referenced docs."
      - "Rotating completed-step detail and stale state out of the auto-load surface and into on-demand docs."
      - "Capturing project vocabulary, in-flight triage, and the cold-reader self-containment check."
      - "Verifying plan.md stays at or below the 400-line soft target."
    excludes:
      - "Ad-hoc end-of-session summaries that produce no on-disk artifacts."
      - "Single-file hand-offs with no accumulating state."
  techniques:
    - id: prepare_hand_off
      name: Prepare hand-off folder
      keywords: [hand off, hand-off, continuation, fresh agent, context budget, project folder, plan rotation, vocabulary capture, in-flight triage]
      goal: "Produce or update a project folder whose CLAUDE.md (eight ## sections under # Project Overview) orients the next agent on turn 1 and whose plan.md is at or below the 400-line soft target."
      preconditions:
        - "Current session has work-in-flight that a fresh agent will continue."
        - "wc -l is available to verify the plan.md size."
      steps:
        - n: 1
          action: "Locate or create the project folder at ./tmp/<short-slug>/. Slug is phase or project scope (the work-unit), not session scope. If folder exists, do three passes: rotation (move completed-step detail out, trim stale CLAUDE.md sections), stale-state (fix anything now untrue), vocabulary (update ## Project vocabulary against terms the session evolved)."
        - n: 2
          action: "Write or update CLAUDE.md using the eight required ## sections under a single # Project Overview: Where we are today (with ### Environment); Where we want to get to; Immediate Priorities; Project vocabulary; Protocols (### Always-invoke skills BEFORE any doc reads; ### Required reads on turn 1; ### Opening response protocol; ### Communication protocol -- default /verbose-updates); Behaviors (### Autonomy status; ### Authorizations; ### Rules to follow; ### Sub-agent orchestration -- main-context preservation; ### Anti-patterns to avoid); Relevant files (### Project folder; ### External files). Apply the session-vs-project filter; run the checklist sweep before declaring done."
        - n: 3
          action: "Write or update plan.md with two sections: accomplished (one line per completed step) and forward overview (next 1-3 steps actionable; later steps one-line summaries). Before writing forward overview, classify in-flight items into blocked-on-user / blocked-on-prior-step / done-uncommitted / queued; surface blocked-on-user items under ## Immediate Priorities in CLAUDE.md. Run `wc -l plan.md`. Soft target is at or below 400 lines -- the comfortable ceiling, not a goal; land lower when the work allows. If over 400, rotate detailed content out (primary first -- completed-step detail to log.md; secondary if needed -- far-future-step detail to a referenced step-N-details.md) and re-verify. Do not move on until the count is at or below 400."
        - n: 4
          action: "Update or append log.md with dead ends whose reason would re-bite (filter out reasoning now obvious), decision rationale (provenance triad shape where useful), surprises, and any content rotated out of plan.md."
        - n: 5
          action: "Self-verify: read CLAUDE.md and plan.md as the next agent. Confirm the current goal (work-unit) is identifiable, the next concrete action is clear, the opening-response template is present, the working context is stated, NOTHING references conversation context a cold reader cannot resolve, and ## Project vocabulary decodes any path whose literal name disagrees with the prose name. Fix any gap before reporting back."
        - n: 6
          action: "Report folder path, filenames, and one-line purpose for each. End the response with the explicit hand-off baton: a two-line block whose first line is literally `Paste into a new session to continue:` and whose second line is the paste-able instruction pointing the next agent at CLAUDE.md."
      gotchas:
        - "The eight ## sections are template-required and ordered. Project-specific ### subsections (or deeper) are additional but go inside the appropriate ##. Skipping or reordering a top-level ## is a template violation; under-populating is not."
        - "## Project vocabulary is the biggest workflow loss when omitted. If you can't name three vocabulary items the session leaned on, you are under-capturing. Include the decoder for paths that retain old literal names."
        - "## Where we are today and ## Immediate Priorities have a subtle seam: state = static descriptive snapshot (what is true), priorities = decisions / actions queued against that snapshot (what changes next). When in doubt, ask: would this still be true after the agent acts? If yes, it's state."
        - "## Protocols vs ## Behaviors seam: Protocols have a trigger and an output shape (turn 1 -> say the opening-response sentence; end of every turn -> emit the three-part template). Behaviors are standing principles with no trigger -- they constrain how you act regardless of which protocol is firing."
        - "plan.md has a 400-line soft target verified with `wc -l plan.md`. Apply rotation to stay under it every hand-off, not just when bloated -- treating rotation as exceptional is how plans drift over 400 one session at a time. 400 is the comfortable ceiling, not a goal; land lower when the work allows."
        - "CLAUDE.md is auto-loaded every session; treat its length as a context budget paid repeatedly. Soft target is up to 400 lines; sections that keep growing are signals that content belongs in a referenced doc."
        - "The opening-response protocol in CLAUDE.md is what catches the silent-go-to-work anti-pattern. Skipping it leaves the next agent to invent their own orientation check, or skip it entirely."
        - "Pick the slug at the work-unit's natural scope (phase or project), not the session name. Sessions come and go; the folder outlives them."
        - "Never name a separate must-read decisions.md doc. If a decision is must-read, it belongs in plan.md; if not, it belongs in log.md. A third must-read doc is false economy."
        - "The hand-off baton at the end of the response is the explicit transfer signal; without it the user has nothing to paste into the new session and has to compose the instruction themselves."
        - "One-line purpose per file in ## Relevant files. 'Files: a.md, b.md, c.md' is the index-without-purpose anti-pattern -- the next agent should not have to open a file to discover whether to open it."
  anti_patterns:
    - id: silent_go_to_work
      name: Silent go-to-work
      keywords: [silent, no confirmation, no orientation check]
      why_it_seems_right: "The agent has read the docs and knows what to do; jumping straight into tool use saves the user a round trip."
      why_it_is_wrong: "Without a stated orientation check (the framework's orientation moment), misorientation is discovered turns later when the agent has already mutated state. The user pays for that recovery; the round trip the silence avoided is cheap by comparison."
      alternative: "The opening-response protocol in CLAUDE.md mandates the next agent restate the current goal, name the first concrete action, and flag any blocker before picking up tools."
    - id: plan_as_record
      name: Plan as historical record
      keywords: [history in plan, plan accumulates, never rotates]
      why_it_seems_right: "Keeping every step's full detail in plan.md preserves history in one place; readers can scroll for context."
      why_it_is_wrong: "plan.md is auto-load surface paid every session. Past-step detail in plan bloats the budget for content the next agent will not act on. The 400-line soft target enforces the rotation discipline; treating plan as a record violates the contract."
      alternative: "Rotate completed-step detail to log.md (or step-N-completed.md) as steps close. plan.md keeps a one-line summary plus a link."
    - id: session_scoped_slug
      name: Session-scoped folder slug
      keywords: [session slug, atoms-22, ephemeral name]
      why_it_seems_right: "The session has a name; using it as the folder slug ties artifacts to the conversation that produced them."
      why_it_is_wrong: "Sessions are smaller than the work-unit. A multi-session project would need a new folder per session and lose the cross-session continuity that the project folder is meant to provide."
      alternative: "Pick the slug at the work-unit's natural scope (phase or project). Sessions reference the folder; they do not own it."
    - id: vocabulary_loss
      name: Vocabulary loss across the hand-off
      keywords: [vocabulary, naming evolution, terms drift, decoder, on-disk vs prose]
      why_it_seems_right: "The terms feel obvious by end-of-session; everyone in this conversation knows what they mean. The next agent will figure it out."
      why_it_is_wrong: "The next agent is a stranger to this conversation. Without ## Project vocabulary, drifted names (T4 -> G4, cycle -> pass, op#2 -> glossary-correct stage) and decoders for old-named paths get re-derived on the fly or surfaced to the user as questions. The session-end vocabulary IS state -- it does not auto-transfer."
      alternative: "Populate ## Project vocabulary explicitly. Include stage / phase / trial names AND the decoder for paths whose on-disk literal disagrees with the current prose name. If you cannot name three vocabulary items the session leaned on, you are under-capturing."
    - id: session_diary_log
      name: Session diary masquerading as log.md
      keywords: [log dumping, every dead end, no filter, superseded approaches]
      why_it_seems_right: "Dumping every tried-and-discarded approach into log.md preserves history thoroughly; the next agent can search if they need."
      why_it_is_wrong: "log.md is an on-demand reference, not a transcript. Including dead ends whose reasoning is now obvious dilutes the signal -- the next agent loads log.md to find rationale they would otherwise re-derive, and a diary buries the rationale that actually matters."
      alternative: "Filter: would this dead end re-bite a fresh agent if not recorded? If yes, log it. If no (the reason is obvious in retrospect, or the approach was a momentary detour), discard."
    - id: conversation_context_in_artifact
      name: Conversation-context references in CLAUDE.md or plan.md
      keywords: [as we discussed, the user just said, prior turn, cold reader]
      why_it_seems_right: "The conversation just resolved this; pointing at it saves restating."
      why_it_is_wrong: "A cold reader -- the fresh agent the hand-off exists for -- cannot resolve 'as we discussed'. The pointer is opaque the moment the conversation ends."
      alternative: "Restate the fact in the artifact. Drop the conversation pointer. The artifact is the substrate; the conversation is not."
```
