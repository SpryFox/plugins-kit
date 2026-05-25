# agent-glue: User Feedback

Anonymized findings from users of related systems who reviewed the agent-glue design with adoption in mind. Per the user-anonymity convention in `CLAUDE.md`, users are named by their role only; no employer / project / file-path details are recorded here.

## Users represented

- **Loc system user** -- maintainer of a localization pipeline (translation, glossary, QA workbook, audit substrate; ~32k LOC).
- **Dialog system user** -- maintainer of a first-pass dialog generation pipeline (brief generation, per-line direction, animation assignment with validate-retry loops, canonical brief artifacts; ~12k LOC).

Both reviewed the four-subsystem post-restructure design with the question "if you adopted this when v1 ships, what would change?"

## Overall posture

Both users reached the same shape: agent-glue replaces the LLM-call / cache / audit substrate cleanly; consumer-side domain logic stays as-is. Roughly a quarter of each system's code is plausibly retired by adoption -- concentrated in the most-fragile area (the LLM-dispatch + cache + audit + agent-validate-loop plumbing). The remaining ~65-75% is domain shape that doesn't belong in a general framework: corpus-wide invariant scans, format-specific I/O (XLSX, CSV with row-interleave, comment-preserving YAML), p4 side effects, hand-authored content preservation, outer-driver loops over heterogeneous source families.

Net: adopt for the substrate, keep the rest as consumer business logic that sits on top. Neither user expects a wholesale port.

## Convergent recommendations

### claude-work-queue design (now locked)

Both users independently arrived at the same answers for claude-work-queue's three open design questions. The matching reasoning is captured here for completeness; the locked decisions live in `claude-work-queue/DESIGN.md`.

- **Queue storage: file-based on disk.** Both users need cross-process accessibility (subprocess-spawned Claude invocations dropping results back into the queue; bulk runners drafting hundreds of items from a shell script with no Python dependency; sessions handing off work to other sessions across restarts). SQLite would force every external writer through a Python API and break the "yaml all the way down" substrate the rest of the kit commits to. In-memory was a non-starter for both because the bulk runs outlive any single session.
- **Signaling: Stop-hook with re-prompt.** Both users have long-running orchestrators that push items mid-session and need them picked up promptly. Session-start-only signaling misses mid-session adds; external-trigger-per-item is too expensive (launches a fresh session per item). Stop-hook + same script at session-start gets both cases with one mechanism.
- **Writer scope: open to any writer.** The wire format being human-authorable lets external producers (CI jobs, shell scripts, scheduled runs, hand-rolled tools) drop items in without spinning up a Claude SDK dependency. This was the explicit driver for the dialog system user (designer bulk runs) and the loc system user (subprocess-spawned per-chunk Claude calls).

## Gaps surfaced (post-v1 candidates)

None of the items below are v1 blockers. They are framed by the reviewers as "things that would shift the adoption calculus from break-even to clearly worth it" -- worth tracking for post-v1 prioritization.

### From the loc system user

1. **Domain-shaped output validation as a first-class hook.** JSON-Schema validation at the worker boundary is necessary but not sufficient. Loc's validator has five typed rejection kinds, hard/soft fail semantics, per-line glossary-mismatch substring checks against required terms, and feedback-retry input construction from the rejection list -- and the *same validator function* must run on both the OpenRouter chunk path and the MCP-tool agent path. agent-glue currently has no first-class hook for this; loc would either re-validate above the kit (losing agent-path symmetry) or push validation entirely into the worker (losing the kit's typed-violation semantics). Suggested resolution: a per-WorkRequest `domain_validator` hook (dotted-path function) that runs after JSON-Schema validation, returns a `Disposition[T]` or `list[Disposition[T]]`, and the runtime treats `Rejected` dispositions inside a batched output as fan-out variants.

2. **Parameterized graphs (graph templates) with bind-time inputs.** Loc has one logical pipeline shape multiplied across many (source-family, language) tuples that all share a topology. Today the design has one `graph.yaml` per concrete pipeline; loc would either accept many near-identical graph directories or pack the variation into PipelineState init and dispatch by-hand inside nodes (anti-pattern relative to variant-dispatch). Suggested resolution: graph-level `parameters:` block; bind at run time (`agent-glue run translate --param source_family=... --param lang=...`); per-parameter sidecars resolve via parameter substitution; renderer shows the parameter axes explicitly.

3. **WorkRecord aggregator API across many records.** Loc has corpus-wide audit aggregators that walk every recorded LLM call and rank by token / rejection kind. With agent-glue those records would live in `.agent-glue-cache/` -- and the kit has no documented surface for "iterate all WorkRecords matching a metadata filter and stream them to an aggregator." Loc would walk the cache dir by hand, defeating the abstraction. Suggested resolution: `work.records.iter(filter=...)` library function streaming records matching a filter expressed against the Attribution component.

### From the dialog system user

1. **Hand-edit-preserving YAML round-trip for canonical artifacts.** The first-pass system's per-conversation briefs have multiple concurrent writers (designer-typed prose fields, LLM-written assignment fields, refresh-written derived state) and the file must round-trip without trashing the hand-edited prose. agent-glue's canonical-outputs design has a `format: managed` escape hatch (node owns the write) -- but that puts the consumer back to bespoke writer code, and gives up the kit's "declare an artifact, get it written" property at exactly the place it matters most. Suggested resolution: a `format: yaml_round_trip` mode backed by ruamel.yaml round-trip semantics plus a declared `preserve_paths:` allow-list for hand-edited fields.

2. **Multi-source freshness keys (composed sub-hash across N inputs from M sources).** The first-pass system's per-line freshness combines six heterogeneous sources (line text from CSV, per-line direction from brief, animation pool snapshot from speaker yaml + tags, prompt version from prompts file, disables version from disables yaml, predecessor identity from graph walk). `compute_subhashes` handles one list with one key function; this is N source files where any one drifting invalidates a different shape of subset. Suggested resolution: an `InputsFingerprint` component that names multiple source-tracked inputs by path + version; the kit computes the composed hash and surfaces per-source invalidation reasons in the WorkRecord (so cache-miss debugging is grounded in "input X changed at time Y" rather than "hash mismatch").

3. **GroupedSequentialFanOut for prompt-cache discipline.** The first-pass bulk runner groups by primary speaker in a two-phase sweep specifically to keep the per-speaker animation pool warm in the LLM's prompt cache. graph-system's design explicitly defers this ("Pipelines that need ordered iteration for cache discipline ... stay as Python driver loops that call `runtime.run` per item"). For the dialog system user that means the most-important production execution path bypasses the graph runtime entirely and loses cohort replay coverage. Suggested resolution: a `GroupedSequentialFanOut` edge variant taking a `group_by` key -- runs same-group items sequentially in the same process, parallel across groups. The cache-discipline use case is recurring whenever an LLM call has a stable system-prompt prefix and a per-item suffix.

## Where the consumer reviews land in the v1 plan

- **claude-work-queue/DESIGN.md** -- the three locked design decisions are recorded; rationale references this document.
- **Post-v1 candidates list** in top-level `IMPLEMENTATION-PLAN.md` -- the six gaps above are out of v1 scope and tracked there as candidate post-v1 increments.
- **Raw reviews** -- the full consumer reviews (which name specific code paths and consumer-project artifacts) are session-private working notes outside the plugin tree, per the user-anonymity convention.
