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

Required sections, in order:

1. **Required reads on turn 1** -- explicit list of docs the agent must read before acting. At minimum `plan.md`; add others (e.g. `parent-plan.md`) as needed.

2. **Opening response protocol** -- the `orientation moment` for session resume. What the agent must say after reading the required docs, before picking up tools. Forces a confirmation of orientation. Example template:
   > "I've read plan.md (+ any other required reads). Current goal: <restated in own words>. Starting with: <first concrete action>. Unclear / blocked on: <issue, or 'none'>."

3. **Current goal** -- the work-unit, stated falsifiably so the agent can tell when it's done.

4. **AFK status / autonomy level** -- whether the user is reading every turn or returning cold; how aggressive to be; which actions still need explicit confirmation.

5. **Communication protocol** -- set the default to `/verbose-updates`'s three-part end-of-turn template (see framework). Note any project-specific overrides (audit-log surface/finding/follow-up shape, domain terminology, what NOT to say) here.

6. **Rules to follow** -- project-specific operational rules. Examples: "don't `p4 submit` without approval"; "background long-running work, never inline"; "ASCII-only in source files."

7. **Anti-patterns to avoid** -- explicit don'ts for this work. Make boundaries concrete; "be careful" is vague.

8. **Working context** -- cwd, platform, sub-agent permissions, non-obvious env quirks.

9. **Index of folder docs** -- one line per file, naming and purpose. Indicate which are auto-loaded (the required-reads list) vs on-demand.

Length target: ~50-100 lines. If a section keeps growing, that's a signal the content belongs in a referenced doc and CLAUDE.md should just link to it.

## `plan.md` -- the plan

Read on turn 1 because CLAUDE.md tells the agent to. Two sections only:

1. **Accomplished** -- one line per completed step. No implementation detail.
2. **Forward overview** -- the next 1-3 steps in actionable detail; later steps as one-line summaries only.

**Default target: 2800 characters or below.** Verify every hand-off with `wc -c plan.md`; ASCII-only rule means bytes equal characters. Apply rotation by default to hit this target -- it is not a fallback that activates only when over the limit, it is the standing goal each hand-off should land at. Rotation is the steady-state discipline that keeps the auto-load surface lean; treating it as exceptional ("only when bloated") is how plans drift toward the limit one session at a time.

**Hard limit: 4000 characters.** The enforcement gate. If plan.md is over 4000 at the end of Step 3 of the workflow, the hand-off is NOT complete and rotation rules tighten: every section is in scope (primary AND secondary rotation, see below), no future-step detail is preserved as "nice to have", and the bar for keeping content in plan.md flips from "needed soon" to "needed in the very next agent turn." Keep rotating until at or under 4000. The hard limit catches drift; the 2800 default prevents it.

In short: aim for 2800 every time. Only loosen if the next agent genuinely needs more forward detail visible right now (rare). If you hit 4000 you are too late -- recover by aggressive rotation, not by stopping at 3999.

**Rotation strategy: history first, optional second.** When reducing, walk the file with this priority:

1. **Primary -- move historical content out.** Completed-step detail, retrospective context, accumulated session-by-session log -- these go to `log.md` (or `step-N-completed.md`). The plan is for the remaining work, not the work already done. A completed step keeps a one-line summary plus a link to log.md; no implementation detail.
2. **Secondary -- move not-always-required forward content out.** Identify subsections that the next agent does NOT need on turn 1 of every session: optional branch detail, "alternative approach" subsections, parked-decision lists if they have grown, far-future-step explanations. These go to referenced docs (`alternatives.md`, `parked.md`, `step-N-details.md`) with a one-line pointer in plan.

Always exhaust primary before secondary. Removing future work from plan is more expensive (the next agent has to follow a link to know what's coming) than removing past work (the next agent does not care). If primary alone gets you to 2800, stop -- you preserved maximum visibility into upcoming work.

The plan is a moving window, not a record (the framework's "rotate forward" principle, applied to the auto-load surface).

## `log.md` -- history

On-demand only. Holds:

- Approaches tried and didn't work, with reasons.
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
- **Implicit communication protocol.** "Behave well" -- vague. Section 5 of CLAUDE.md must name `/verbose-updates` (or another explicit protocol) as the end-of-turn default and call out any project-specific overrides.
- **Rules without anti-patterns.** "Be careful with X" -- agent fills in their own definition. Anti-patterns make the boundary concrete.
- **Index-without-purpose.** "Files: a.md, b.md, c.md" -- agent has to read each to know what they're for. One-line purpose per doc.
- **Separate must-read decisions doc.** False economy. If must-read, it belongs in the plan. If not must-read, it belongs in the log.
- **Plan as record.** Plan accumulates every step's full detail forever. Auto-load surface bloats. Rotate.
- **Session-scoped slug.** `atoms-22` outlived by `atoms-17-phase2`. Pick the scope that outlives the session -- the work-unit, not the conversation.

## Workflow

Run in a single response. Don't pause for confirmation between steps unless something is ambiguous.

### Step 1 -- Locate or create the folder

If a folder already exists for this work, update in place. Two passes:

- **Rotation pass.** Move completed-step details from plan.md to log.md; move far-future-step details to referenced docs; trim CLAUDE.md sections that have grown stale.
- **Stale-state pass.** Anything now untrue under current scope (e.g. "ready to ship" when scope just expanded) gets fixed in place. Untrue text is worse than missing text.

If no folder exists, create one at `./tmp/<short-slug>/`. Pick the slug at phase or project scope (the work-unit, not the session); confirm it in your end-of-turn summary so the user can correct.

### Step 2 -- Write or update `CLAUDE.md`

Use the nine required sections above, in order. If a previous CLAUDE.md exists, keep what's still true; update the current goal, AFK status, and operational changes; refresh the index. Section 5 (Communication protocol) sets `/verbose-updates` as the default unless the project explicitly overrides.

### Step 3 -- Write or update `plan.md`

Two sections: accomplished + forward overview. After writing, run `wc -c plan.md`. The target is **at or below 2800 characters** -- this is the default goal applied every hand-off, not a fallback. If over 2800, rotate detailed content out (primary first -- completed-step detail to log.md; secondary if needed -- far-future-step detail to a referenced `step-N-details.md`) and re-verify. If over 4000 you have hit the hard limit -- all primary AND secondary rotation rules become mandatory; keep rotating until at or under 4000, ideally back at or below 2800. Do not move on until the count is at or below 2800; if you stop above 2800 (e.g. 3000-3999) you must justify in your end-of-turn report which forward-step detail genuinely needed the extra room.

### Step 4 -- Update or create `log.md`

Capture anything worth retaining but not worth auto-loading: dead ends with reasons, decisions and rejected alternatives (use provenance triad shape where useful), surprises, details rotated out of plan.

### Step 5 -- Self-verify

Read CLAUDE.md and plan.md as if you were the next agent. Verify:

- Can you identify the current goal without reading anything else?
- Do you know what to do next, concretely?
- Do you know what to say back after reading the docs (the opening-response protocol)?
- Are the working directory and any non-obvious operational rules stated?

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
- **Fit the work to the framework.** The required elements above cover most hand-offs. Resist adding more required sections to suit a specific work shape; let judgment fill the artifacts with what the work needs.

## Contract

```yaml
technique_skill:
  _schema_version: "1"
  trigger_model: user-only
  identity: "Package the current session's work for a fresh agent by creating or updating a project folder whose contents manage the next agent's auto-loaded context budget."
  references:
    - "references/communication-framework.md (canonical glossary for shared vocabulary)"
  scope:
    covers:
      - "Producing or updating ./tmp/<slug>/ with CLAUDE.md + plan.md + log.md + optional referenced docs."
      - "Rotating completed-step detail and stale state out of the auto-load surface and into on-demand docs."
      - "Verifying plan.md stays at or under the 4000-character hard limit."
    excludes:
      - "Ad-hoc end-of-session summaries that produce no on-disk artifacts."
      - "Single-file hand-offs with no accumulating state."
  techniques:
    - id: prepare_hand_off
      name: Prepare hand-off folder
      keywords: [hand off, hand-off, continuation, fresh agent, context budget, project folder, plan rotation]
      goal: "Produce or update a project folder whose CLAUDE.md orients the next agent on turn 1 and whose plan.md is at or below the 2800-character default target (4000 hard-limit fallback)."
      preconditions:
        - "Current session has work-in-flight that a fresh agent will continue."
        - "wc -c is available to verify the plan.md size."
      steps:
        - n: 1
          action: "Locate or create the project folder at ./tmp/<short-slug>/. Slug is phase or project scope (the work-unit), not session scope. If folder exists, do the rotation pass (move completed-step detail out, trim stale CLAUDE.md sections) and stale-state pass (fix anything now untrue)."
        - n: 2
          action: "Write or update CLAUDE.md with the nine required sections in order: required reads on turn 1; opening response protocol (orientation moment); current goal (work-unit); AFK / autonomy; communication protocol (default to /verbose-updates); rules; anti-patterns; working context; index of folder docs."
        - n: 3
          action: "Write or update plan.md with two sections: accomplished (one line per completed step) and forward overview (next 1-3 steps actionable; later steps one-line summaries). Run `wc -c plan.md`. Default target is at or below 2800 characters -- apply rotation by default to land there. If between 2800 and 4000, rotate further unless you can justify in your end-of-turn report why the extra forward-step detail is genuinely needed. If at or above 4000 the hard limit is breached: primary AND secondary rotation become mandatory; keep rotating until at or under 4000 and ideally back at or below 2800. Do not move on until the count is at or below 2800 (or, exceptionally, justified above)."
        - n: 4
          action: "Update or append log.md with dead ends, decision rationale (provenance triad shape where useful), surprises, and any content rotated out of plan.md."
        - n: 5
          action: "Self-verify: read CLAUDE.md and plan.md as the next agent. Confirm the current goal (work-unit) is identifiable, the next concrete action is clear, the opening-response template is present, and the working context is stated. Fix any gap before reporting back."
        - n: 6
          action: "Report folder path, filenames, and one-line purpose for each. End the response with the explicit hand-off baton: a two-line block whose first line is literally `Paste into a new session to continue:` and whose second line is the paste-able instruction pointing the next agent at CLAUDE.md."
      gotchas:
        - "plan.md has a 2800-character default target verified with `wc -c plan.md`. Apply rotation to hit it every hand-off, not just when bloated -- treating rotation as exceptional is how plans drift toward the 4000 hard limit one session at a time. If you stop above 2800 you must justify which forward-step detail needed the extra room; if you hit 4000 the hard limit is breached and stricter rotation kicks in."
        - "CLAUDE.md is auto-loaded every session; treat its length as a context budget paid repeatedly. ~50-100 lines is the soft target; sections that keep growing are signals that content belongs in a referenced doc."
        - "The opening-response protocol in CLAUDE.md is what catches the silent-go-to-work anti-pattern. Skipping it leaves the next agent to invent their own orientation check, or skip it entirely."
        - "Pick the slug at the work-unit's natural scope (phase or project), not the session name. Sessions come and go; the folder outlives them."
        - "Never name a separate must-read decisions.md doc. If a decision is must-read, it belongs in plan.md; if not, it belongs in log.md. A third must-read doc is false economy."
        - "The hand-off baton at the end of the response is the explicit transfer signal; without it the user has nothing to paste into the new session and has to compose the instruction themselves."
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
      why_it_is_wrong: "plan.md is auto-load surface paid every session. Past-step detail in plan bloats the budget for content the next agent will not act on. The 4000-char hard limit forces the rotation discipline; treating plan as a record violates the contract."
      alternative: "Rotate completed-step detail to log.md (or step-N-completed.md) as steps close. plan.md keeps a one-line summary plus a link."
    - id: session_scoped_slug
      name: Session-scoped folder slug
      keywords: [session slug, atoms-22, ephemeral name]
      why_it_seems_right: "The session has a name; using it as the folder slug ties artifacts to the conversation that produced them."
      why_it_is_wrong: "Sessions are smaller than the work-unit. A multi-session project would need a new folder per session and lose the cross-session continuity that the project folder is meant to provide."
      alternative: "Pick the slug at the work-unit's natural scope (phase or project). Sessions reference the folder; they do not own it."
```
