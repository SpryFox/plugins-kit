# agent-glue review synthesis

Two sub-agents (dialog-domain-a, localization-domain-a) reviewed the current agent-glue design against the SC first-pass dialog system and the SC localization pipeline respectively. Full reports: `first-pass-dialog-review.md` and `localization-review.md`.

## Headline verdict

| System | Full port | Partial port |
|---|---|---|
| First-pass dialog | **Net win**: meaningful simplification of the pipeline-internals half (~50% of `firstpass_ops/` goes away). Designer-facing CLI verbs, scope grammar, p4 integration, and reporting stay as Python on top. | N/A -- the natural slice is "the generate/apply graph"; reporting and CLI verbs naturally sit outside. |
| Localization | **Wash, leaning slightly negative.** Parts that need the most help (commandlet sequencing, p4 CL mutation, translator round-trip, MT-under-human merge) are exactly the parts agent-glue doesn't model yet. | **Clear win** for the AI translation path (`loc.py translate` + agent-path twin) plus audit aggregators. That sub-piece could plausibly halve in code size and gain free cohort-replay regression coverage. |

## What both reviewers independently flagged

These two findings converged from independent reviews and are the strongest architectural signal:

### 1. Sub-element hash control is the single biggest design call

Both reviewers identified this as the make-or-break question for their respective systems:

- **First-pass:** "How does the WorkRecord cache invariant survive a brief edit that's not supposed to invalidate?" Designers regularly hand-edit `personality` (shouldn't invalidate) and per-conversation `direction` overrides (should invalidate).
- **Localization:** "What hash key truly captures whether a cached translation is still authoritative?" The glossary is large, evolving, partially-shared across (source, lang) pairs. Hashing the whole glossary -> every edit invalidates everything. Not hashing it -> stale cache hits.

The current design has `InputsHash` as a sibling on `WorkRecord` that can be narrower than `request_hash`, but doesn't ship a primitive for computing per-element subhashes. **Both reviewers suggested the same fix:** a work-system helper like `compute_subhashes(items, key_fn)` that lets consumers construct cache invalidation criteria at sub-request granularity. This is a real Phase-2 question (or maybe a primitive to add now).

### 2. Side-effecting work breaks the WorkRecord-as-cache invariant

Both reviewers independently flagged this. The cache mechanism assumes work is a deterministic function of inputs. When work has external side effects (p4 edit, CSV write, Unreal commandlet, file-system mutation outside the WorkRecord), cache hits return "we did it" without doing it -- leaving the filesystem in a state inconsistent with what the cache claims happened.

- **First-pass:** workable today by keeping side-effecting work in *in-impl* nodes (no caching). The DESIGN acknowledges this with "if it's a cheap data-shape transform, do it in-impl." But the line between "in-impl" and "delegate" has to be drawn carefully.
- **Localization:** much worse. Unreal GatherText commandlets MUST run for their side effects (writing `.po`, `.archive`, `.locres` files); a cache hit that skips the actual commandlet leaves the directory inconsistent. There's no clean in-impl workaround because the work is genuinely a subprocess invocation, not a Python computation.

**Both reviewers requested the same primitive:** a structured `SideEffects` declaration on `WorkResult` that lets cohort replay refuse to run write-side work (or stub it), and an "external-process worker" (subprocess-shell-out) with explicit declarations of consumed and produced directories.

The work-system's existing open question about `SideEffects` schema is the right hook -- but the reviews show this isn't actually a deferrable side-detail; it's central to whether the kit can model real-world pipelines with file-system effects.

## What only first-pass needs

- Speaker-grouped sequential bulk runner (kit explicitly defers; first-pass uses Python driver loop). No regression vs today.
- Validate-against-external-pool documentation pattern (existing `rules.yaml` works, but the example pipeline understates how dynamic the rule subset is).

## What only loc needs

- **Format dispatch beyond yaml/json/text** -- XLIFF, PO, .locres. Reviewer suggests `format: xliff`, `format: po`, `format: jinja`.
- **Async / continuation worker** -- for the XLIFF translator round-trip and QA reviewer round-trip (multi-day human handoffs). The kit's synchronous-`submit()` design assumes the work completes in one process.
- **Merge-with-precedence as a first-class artifact writer** -- the MT-under-human pattern where one shipped translation is the merge of multiple upstream WorkRecords with a precedence rule. Reviewer suggests a new graph-system primitive for "multi-writer artifact with lineage."

## What both reviewers said looks great

The example pipelines (character_animation, localization) were clearly written with these exact systems in mind -- both reviewers commented that the example is a faithful sketch. Specific strong-fit items both flagged:

- **Disposition iron contract** is the exact shape both pipelines already enforce ad-hoc.
- **WorkRecord-as-cache** is the right architecture for "skip work when inputs haven't changed." First-pass's `inputs_hash` and loc's "out-of-date strings" engine are both bespoke implementations of the same idea.
- **Validate-retry as sub-graph** matches how both systems already want to express retry loops.
- **Cohort substrate** solves the long-standing wish-item of "regression tests for LLM-driven pipelines."

## Recommended next moves

If the goal is to ship agent-glue and *then* use it to simplify SC systems:

1. **Add `SideEffects` schema and an external-process worker to Phase 2.** Don't defer. Both reviewers identified this as central, not optional. The work-system needs a third primitive worker (`subprocess`) and a structured-side-effects component.
2. **Author the `inputs_hash`-narrower-than-`request_hash` story with a worked example before Phase 1.** Show a Node whose `WorkRequest` includes a hand-computed `inputs_hash` derived from a subset of the input. Both reviewers identified this as the single biggest open question for their domain.
3. **Defer `format: xliff` / `format: po` / async worker / merge-with-precedence to post-v1.** None of these are needed for the v1 examples. They're loc-only and only matter once a full loc port is contemplated.

If the goal is to use the existing v1 design to simplify *first-pass specifically*:

- The current architecture is a good fit. The two issues to settle are (a) the brief-fields-in-hash discipline and (b) keeping p4-mutating work in in-impl nodes.
- A first-pass port is realistic as a post-v1 third example pipeline (after character_animation and localization).

If the goal is to use the existing v1 design to simplify *the loc AI-translation slice*:

- Also a good fit, with the caveat that the glossary-hash question must be settled cleanly.
- The slice is small enough to fit a post-v1 third example.

## What this synthesis does NOT recommend

- Attempting a full loc port. Both the kit AND loc would have to grow significantly; the architectural payoff is marginal for the existing well-functioning system.
- Adding loc-specific primitives (XLIFF format, async worker, merge-with-precedence) to v1. They're real needs but only for a hypothetical full loc port that the synthesis explicitly does not recommend.
