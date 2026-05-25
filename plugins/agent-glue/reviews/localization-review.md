# Review: agent-glue as a basis for the SC localization pipeline

Reviewer: localization-domain-a sub-agent. Reviewed against the SC localization pipeline (`SpiritCrossing/Scripts/automated.py`, `LocalizeExport.bat` / `LocalizeImport.bat` / `LocalizeImportMT.bat`, the XLIFF round-trip, the .po/.locres compile chain, and the QA pipeline including the QA proposal).

## 1. Strong fit

Several agent-glue mechanisms map onto loc pain points so cleanly that they look like they were designed in dialogue:

- **WorkRecord-as-cache is exactly the "out-of-date strings" engine the loc pipeline currently improvises.** Today the system relies on a mix of msgctxt-hash on the source string and Unreal's "stale" flag in `Game.po` to decide what needs retranslation. With WorkRecord keyed by sha256 of the full WorkRequest yaml (input + system prompt + worker config), the question "is this translation still fresh?" becomes a single hash lookup. The `inputs_hash` sibling that excludes worker config the worker doesn't actually consume (e.g. `max_tokens`) is precisely the loc invariant -- a `max_tokens` bump shouldn't invalidate translations. Even better, `CacheControl.invalidate_if` covers the harder case of "source CSV row changed since translation" via mtime / source-content hash.

- **`prompts.yaml` audit sidecars and WorkRecord cohort recordings are the same shape.** The loc skill already describes a materialized-insight pattern: every chunk write a `ChunkRecord` capturing assembled prompts, raw response, `rejected_keys`, `line_overrides`, `auto_overrides`. agent-glue ships that as a first-class concept (WorkRecord with metadata pass-through + structured side_effects). The aggregators (`audit-overrides`, `glossary review-overrides`) become `python_script` workers that consume a directory of WorkRecords. The skill's claim that "aggregators are read-only and source-agnostic" maps directly to agent-glue's "WorkRecords are uniform across live runs and cohort fixtures."

- **`parallel: true` fan-out covers per-chunk translation directly**, and per-chunk cache invalidation ("change one phrase, only re-translate the chunk containing it") is the canonical motivating example in the kit's docs.

- **Iron contract = the loc audit-and-approve workflow, verbatim.** `Disposition = Accepted | AcceptedWithAudit | Rejected` is the exact shape the loc pipeline already enforces: every line emerges with a translation, audit-stamped if the LLM contested or the pipeline auto-overrode. The `AcceptedWithAudit` audit_metadata["source"] convention -- distinguishing LLM-contested vs pipeline-decided -- is already called out in the example pipeline. That's a freebie.

- **The retry-as-sub-graph distinction matches loc's two retry shapes precisely.** Loc has both proposal-rework (regenerate a whole chunk) and batch-rejection-rework (re-prompt with the N rejected items). The kit explicitly carves the line between sub-graph and in-node, and assigns batch-rejection to in-node `execute`. That matches `translate()` today.

- **Cohort substrate replaces all the ad-hoc "test against a saved response" patterns.** No live OpenRouter calls in CI; promote-record from a live cache into a cohort = "freeze this translation as a regression test." That's the long-standing wish-item for the loc test surface.

## 2. Partial fit, doable

- **Per-language XLIFF emission is `outputs:` with Jinja path templating** -- but XLIFF is structured XML with `<unit>`, `<segment>`, `<source>`, `<target>`, `<notes>`, namespace declaration. `format: yaml | json | text` doesn't cover XLIFF natively. The clean workaround is `format: managed` (node writes the file itself), but then you lose the kit's promise of declarative output. **Gap:** add `format: xliff` (or `format: jinja` with a template path) so XLIFF emission is declarative. Until then, every XLIFF-writing node uses `format: managed`.

- **The `_M` / `_M2` -> correct tag fixup on import** is a pure data transform that fits `python_script` worker. But it's currently a side effect of `import_localization()` rather than a discrete pipeline step. Bending loc to agent-glue means decomposing the import path into discrete nodes (parse XLIFF -> fixup tags -> merge PO -> compile locres), which is healthy but is real refactoring work, not a translation.

- **MT-layered-under-human as two cohort directories.** The pattern "MT is fallback, human wins on conflict" doesn't map to a single WorkRecord per translation; logically there are two records per (key, lang) at different priorities. Workable: model each MT request as its own WorkRecord under a separate `worker.config.source: mt` tag, and have a merge node prefer human over MT. The hash machinery is fine; the conceptual gap is that the *artifact* (a single `<target>` element) has two upstream WorkRecords, not one.

- **The `.loc_ignore` exclusion file** is just config; can ride as a `rules.yaml` sidecar on a `filter_units` node. No friction, just convention.

- **zh-Hans policy** (Game_MT_zh-Hans.xlf overrides, the `inherit` semantics relative to zh-Hant) is also config-as-rules. The kit doesn't care, but the loc pipeline's policy logic would need a node that knows "for zh-Hans, fall back to zh-Hant MT unless explicit override exists." Doable in `python_script`, requires careful state.

- **`audit-overrides` and `glossary review-overrides` aggregation across the whole corpus** maps to a graph-of-graphs pattern (one outer driver invokes `runtime.run` per (source, lang)). The kit explicitly supports this via "plain Python function" composition, but doesn't ship a primitive for "walk all artifacts under a directory and aggregate." Loc would supply that as `python_script` workers; fine, but the kit gives no scaffolding.

## 3. Genuine mismatch

- **Unreal commandlet sequencing.** GatherText is a multi-step Unreal commandlet invocation: gather -> export -> compile, with the documented bug that running gather+export in one pass silently fails the export. Each step is a `UnrealEditor-Cmd.exe ... -run=GatherText -config=<ini>` invocation, blocking, with massive side effects (writes to `Content/Localization/`, opens P4 files). agent-glue has no concept of "non-LLM, non-Python, external subprocess as a worker." You could shoehorn it into `python_script` (function that shells out), but: (a) caching becomes incorrect because the on-disk side effects aren't part of the WorkRecord and so a cache hit returns "we ran it" without re-running the commandlet, leaving stale `.po` / `.archive` files on disk; (b) the kit's "WorkRecord = audit + cache" duality assumes the work is a function of its inputs, which commandlets manifestly are not (they depend on the entire `Content/Localization/` directory state).

- **P4 changelist mutation is fundamentally side-effecting and irreversible-in-aggregate.** Today `LocalizeExport.bat` opens a CL, runs `p4 edit`, runs the commandlet sequence, runs `p4 revert -a` to drop unchanged files. None of this fits the WorkRecord-as-cache model: replaying a cohort would not re-open the CL, and a "cache hit" on a P4-mutating WorkRequest is meaningless. The kit's silence on side-effect-bearing operations is a real gap here. The skill's own note "the bat scripts reopen any Content/Localization file into their own CL" highlights that this is genuinely stateful in ways agent-glue can't capture in WorkRecord.

- **XLIFF round-trip with external translators is a multi-day asynchronous handoff.** Upload `Game.xlf` to Google Drive, wait days-to-weeks for human translators, download per-language files. agent-glue is a synchronous-`submit()` design. There is no built-in concept of "this work was started, the worker said 'come back later,' here's a continuation token." You could model "upload" and "download" as separate `python_script` workers and the human work as out-of-band, but then there's no graph-level "this run blocks pending external input." Pipelines that span human time scales don't fit a graph-runtime that runs end-to-end in one process.

- **MT-layered-under-human as one logical translation.** The audit story in agent-glue is "one WorkRecord per submission, identified by request hash." But one shipped translation in loc is *the merge of* an MT proposal and (optionally) a human edit. Asking "what was the audit trail for this `<target>`?" requires walking multiple records and knowing the merge policy. The kit doesn't model "this artifact's lineage = N WorkRecords with a precedence rule." It would need either an explicit merge-node convention plus a domain-specific lineage index, or a new entity type.

- **QA pipeline's spreadsheet round-trip is the same long-async problem as translator round-trip.** The QA proposal flow (export blank workbook -> reviewer fills in `corrected_translation` / `change_category` / `qa_comment` -> ordinal-stamped return -> intake -> merge -> apply -> regen) spans days and humans. The export and intake are scriptable, but the reviewer activity isn't. agent-glue gives nothing for this besides "model each scripted half as its own graph."

- **Source-string format with rich context (msgctxt, InfoMetaData notes, Previous Lines).** The XLIFF `<notes>` carrying Speaker, Emote, Comment, Previous Lines is a domain-specific schema that doesn't fit the kit's generic input/output_schema yaml. Workable but unprincipled -- you end up with a giant input blob the schema can't really validate richly.

## 4. Missing primitives

In rough priority order:

1. **External-process worker (in work-system).** Beyond `openrouter` / `claude_agent` / `python_script`, loc needs a `subprocess` worker that shells out to `UnrealEditor-Cmd.exe`, `RunUAT.bat`, etc., with explicit declarations of (a) which directories the command consumes (cache-key inputs) and (b) which directories it produces (cache invalidation outputs). Without (b), the cache-as-result-of-pure-function premise breaks for any commandlet step. Belongs in work-system as a peer to the existing three.

2. **Async / continuation worker (in work-system).** For the XLIFF translator round-trip and QA reviewer round-trip: a worker type whose `submit()` doesn't return a result but a "pending claim ticket," and a separate `resume()` API that completes when the human delivers. The kit's synchronous-only assumption rules this out today; the design doc even flags streaming as deferred. Async-with-external-blocking is a bigger leap than streaming.

3. **Merge-with-precedence as a first-class artifact-write primitive (in graph-system).** `format: managed` is the escape hatch, but the MT-under-human pattern is common enough that loc would benefit from a declared "multi-writer artifact" concept where each writer carries a precedence tag and the artifact records its lineage. Otherwise every per-language `Game_<lang>.xlf` ends up written by ad-hoc Python and the audit story shrinks to "read the file."

4. **Side-effecting work declaration (in work-system).** The open question in the kit's own docs about `WorkResult.side_effects` is the right hook. Loc needs a structured shape for "this work wrote these files / opened these P4 CLs" so that cohort replay can refuse to run write-side work (or stub it).

5. **Format dispatch for XLIFF / PO / .locres (in graph-system, `outputs:` extension).** Add `format: xliff` (with namespace + schema-version awareness), `format: po` (gettext semantics), and probably `format: jinja` (arbitrary template-driven). Without these, every loc-format-writing node is `format: managed`, which means the kit gives nothing for the most common operation.

6. **A "wait for external file" trigger primitive.** Doesn't have to be elaborate -- poll-a-directory-for-new-files is enough -- but the QA round-trip and the XLIFF translator round-trip both need it. Could live alongside the async worker.

## 5. Bottom line

A full port of the loc pipeline would be a **wash, leaning slightly negative**, because the parts of loc that need the most help (commandlet sequencing, P4 CL mutation, external-translator handoff, MT-under-human merge) are exactly the parts agent-glue's architecture doesn't yet model. You'd spend more building the missing primitives than you'd save from getting WorkRecord-as-cache and Disposition for free. A wholesale rebuild also breaks the existing-loc-team's mental model of the pipeline for marginal architectural payoff.

A **partial port is a clear win, and the strongest candidate is the AI translation path (`loc.py translate` and its agent-path twin) plus the audit aggregators**. That subsystem is already a graph of LLM calls with chunked fan-out, per-line iron contract, validator-feedback retry, and prompts.yaml audit sidecars. Every one of those features has a native agent-glue analog. The cache substitution alone would replace bespoke "is this chunk fresh?" logic with a hash lookup. The cohort substrate replaces hand-rolled fixtures with promote-record. Disposition replaces the project's own Accepted/AcceptedWithAudit/Rejected reimplementation. Estimate: that sub-piece of loc could plausibly halve in code size, and the audit story would get better at the same time. The QA aggregators (`audit-overrides`, `glossary review-overrides`) are similarly easy wins -- pure-Python data passes over WorkRecord directories.

**Biggest open question before committing to even the partial port:** what does the WorkRecord look like for translations that depend on the *glossary content*? The glossary is large, evolving, and partially-shared across (source, lang) pairs. If the WorkRecord's request_hash includes the full glossary, every glossary edit invalidates every cached translation -- catastrophic for the regen loop the loc audit workflow is built around. If it doesn't, you risk cache hits returning translations that don't reflect the current glossary. The kit's `inputs_hash`-narrower-than-`request_hash` knob is the right shape, but only if a node can compute a per-line glossary-relevant subset rather than hashing the whole file. Answering that question -- "what hash key truly captures whether a cached translation is still authoritative?" -- is the make-or-break design call before any code gets written.
