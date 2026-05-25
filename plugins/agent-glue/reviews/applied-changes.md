# Changes applied from review feedback

Tracking what got pulled into the design from the two sub-agent reviews + user follow-up. Reviews live at `first-pass-dialog-review.md` and `localization-review.md`; synthesis at `synthesis.md`.

## Pulled into Phase 2 (was deferred / out-of-scope)

- **`SideEffects` schema on WorkResult** -- first-class structured component (file-written, subprocess-invoked variants), not a deferred "we'll figure it out when claude_agent lands" open question. Cohort-replay uses it to refuse to call workers whose recorded work has unrecorded side effects.
- **`compute_subhashes` helper** -- utility in `agent_glue_lib.work.hashing` for consumers needing sub-element invalidation (e.g. "20-line conversation, only 1 line changed -> compute per-line hashes so unchanged lines stay cached"). Both reviewers asked for this; folded in.
- **`run_subprocess` helper** -- optional convenience in `agent_glue_lib.work.helpers` for python_script functions that shell out. Runs the command and returns the result alongside a pre-populated SideEffects record. Removes boilerplate without forcing a separate worker.

## Refined per follow-up discussion

- **`claude_agent` split into `claude_inference` + `claude_agent`.** Originally one worker. Now:
  - `claude_inference`: Claude Code subagent dispatch with no tools enabled. Pure inference. Determinism defaults to deterministic (same as openrouter); overridable per-request.
  - `claude_agent`: Claude Code subagent with tool / MCP access. Determinism `requires_declaration` (consumer must assert per-request whether their specific work is deterministic_idempotent or non_deterministic; no silent default).
- **Inference workers can be set non-cacheable per-request.** openrouter and claude_inference default to `deterministic` + temp 0 (cacheable). A request that sets `CacheControl.determinism: non_deterministic` is accepted; the worker switches to a non-zero temperature (default 0.7) and skips cache lookups. Temperature stops being a user-facing config field -- it's derived from the declared determinism. `CacheControl.bypass: true` still forces a re-run without changing determinism.
- **Side-effect-capable workers have no default determinism.** claude_agent and python_script require per-request declaration; submit raises if missing. The kit doesn't guess; the consumer knows their work's nature.
- **`subprocess` worker dropped.** Originally added as a 5th worker. Reverted -- python_script can do the same job (the function shells out internally) without a separate worker type. The kit can't introspect function bodies to detect shell-outs, but it doesn't need to: the consumer is responsible for declaring `non_deterministic` (or `deterministic_idempotent` when the wrapped command is genuinely idempotent), and for declaring `consumes_dirs` / `produces_dirs` in the WorkerSelection config when relevant. The kit uses those declarations to auto-derive cache invalidation criteria and to make cohort-replay decisions safely. Documented as a worked example in work-system/DESIGN.md so reviewers can see the pattern carries enough metadata to address the original "we need subprocess" objection without a separate worker.

## Deferred per the synthesis (not pulled in)

These are loc-specific and only matter for a full loc port, which the synthesis explicitly does NOT recommend. None of them block v1.

- `format: xliff` / `format: po` / `format: jinja` for canonical outputs
- Async / continuation worker (translator + QA reviewer round-trips)
- Merge-with-precedence as a first-class artifact writer (MT-under-human)

If a partial loc port (the AI-translation slice) gets prioritized post-v1, none of these are required for it; they're full-port concerns.

## What changed in design vs first review

For reference, the C2 question in the original `open-questions.md` (now deleted) asked whether cached calls should write thin "I'm a cache hit, see original" records. The first-pass-pattern adoption collapsed show-your-work and disk-cached inference into one mechanism: every successful submit writes a WorkRecord; cache hits return the recorded result without writing a new record. The thin-reference idea was discarded; the cached call leaves no trace beyond the original record (which already says everything).
