# agent-glue: v1 Implementation Plan

## Scope discipline

Build the architecture (yaml-driven ECS model + ECS loader + runtime + work subsystem with show-your-work-as-cache + cohort substrate + CLI), validate with two example pipelines (a character animation pipeline + a localization pipeline). Don't over-build.

Specifically:
- **Render layer is stubbed.** `agent-glue render` emits a placeholder. The design artifact in v1 is `graph.yaml` itself, read as text. The HTML render lands post-v1 once the kit has proven the abstractions hold.
- **The yaml is the source of truth.** Entity type definitions and component schemas live in `entities/` and `components/` directories under the plugin and each subsystem. The loader reads them at startup; runtime systems consume the resulting entity catalog. No hardcoded entity catalogs in Python.
- **Show-your-work is the cache.** One mechanism, owned by the work subsystem. Every successful `submit()` writes a `WorkRecord` that doubles as audit log and cache entry. The graph subsystem has no per-run trace of its own.

## Out of scope for v1 (deferred, not abandoned)

- HTML / Mermaid render (stub only -- see Phase 8).
- `agent-glue validate` does only structural checks (start node exists, edges resolve, contracts import, component schemas validate) -- no graph-shape lint.
- `agent-glue new` scaffolding command -- defer; first two examples are hand-authored as reference templates.
- All previously-deferred items in graph-system DESIGN.md's *Non-goals*.

## Two example pipelines

Each ~5-8 nodes, designed together to exercise every kit feature without contortion. Both are built fresh on agent-glue (not retrofits) -- they're simplified instances of the pipeline *types* the kit is designed to support, and serve as the kit's reference templates.

### Example A: `examples/character_animation/`

**Theme:** assign animations to lines of dialogue. Input: a dialogue file with lines, each tagged by speaker. Output: a per-conversation "brief" YAML containing scene-level direction and per-line animation assignments.

**Pipeline shape** (sidecars noted; all nodes are the same kind):

- `load_conversation` -- read the dialogue file. In-impl (cheap, no caching needed).
- `load_brief` -- read the prior brief if one exists; empty otherwise. In-impl.
- `check_direction_freshness` -- out: `DirectionFresh | DirectionStale`. In-impl.
- `generate_direction` -- *prompt.md sidecar*; delegates to openrouter via `submit()`; proposes scene direction; out: `Disposition[Direction]`. Cacheable.
- `enumerate_stale_lines` -- identifies which lines need (re)assignment based on per-line `inputs_hash`; out: list of stale line ids. In-impl.
- `propose_assignments` -- *prompt.md sidecar*; delegates to openrouter; out: `Disposition[Assignments]`. Cacheable.
- `validate_assignments` -- *rules.yaml sidecar* (speaker -> allowed-animation set lookup); checks each proposed animation; out: `Valid | NeedsRetry(rejected_lines) | Exhausted`. In-impl (deterministic rules-table lookup).
- (Retry edge: `NeedsRetry -> propose_assignments` with bumped attempt count in state.)
- `persist_brief` -- *declares `outputs:` with `format: managed`*; merges new direction + assignments with the prior brief, preserving any hand-edited fields; writes the canonical artifact. In-impl (file write).

**Shape it exercises:**

- Single-graph multi-stage pipeline (direction -> enumeration -> assignment).
- Per-item freshness gate driving stale-subset selection passed to one downstream call (subset-as-input-to-one-call, NOT fan-out).
- Validate-retry sub-graph for proposal-rework.
- Canonical artifact via `format: managed` (the brief preserves hand-edited sections; the persist node owns the write).
- `Disposition[T]` per single proposal.
- Mixed sidecar combinations: nodes with only `prompt.md`, nodes with only `rules.yaml`, nodes with only `outputs:`, nodes with none.
- WorkRecord cache hits on re-runs: identical inputs -> generate_direction and propose_assignments hit cache; the LLM is not invoked.

### Example B: `examples/localization/`

**Theme:** translate a list of phrases from a source language to a target language with a locked-term glossary. Phrases are chunked; chunks translate in parallel; per-line iron contract.

**Pipeline shape** (sidecars noted; all nodes are the same kind):

- `load_phrases` -- read the source-language phrase list and target language code. In-impl.
- `load_glossary` -- *rules.yaml sidecar*; loads the locked-term glossary (term -> required translation per language). In-impl.
- `prepare_chunks` -- partition phrases into chunks of N. In-impl.
- `translate_chunk` -- *prompt.md sidecar*; parallel fan-out per chunk; delegates to openrouter via `submit()`; given chunk + glossary, translates each phrase; out: `list[Disposition[TranslatedPhrase]]`. In-node batch-rejection retry if any phrase rejected by the in-prompt validator (one prompt with N failed items -> one response covering them). Cacheable per chunk.
- `merge_chunks` -- converges fan-out into one list. In-impl.
- `persist_translations` -- *declares `outputs:` with `format: yaml`*; writes the canonical artifact (end-to-end rewrite). In-impl.

**Shape it exercises:**

- Parallel fan-out (`parallel: true`) over chunks.
- `list[Disposition[TranslatedPhrase]]` per-element batch shape.
- `Accepted` / `AcceptedWithAudit` (LLM contested glossary term) / `Rejected` per-line variants.
- `audit_metadata["source"]` convention to distinguish LLM-decided vs pipeline-decided audit reasons.
- In-node batch-rejection retry.
- A node with both `prompt.md` and access to upstream-loaded `rules.yaml` content (via input contract).
- Canonical artifact via `format: yaml` (rewritten end-to-end).
- Per-chunk WorkRecord cache: changing one phrase only re-translates the chunk that holds it; other chunks hit cache.

Together both examples cover: every sidecar combination (none / `rules.yaml` only / `prompt.md` only / both / `outputs:`), all Disposition variants, both retry shapes (proposal-rework sub-graph + batch-rejection in-node), both canonical-output formats (`managed` + `yaml`), parallel fan-out, subset-as-input-to-one-call, cohort replay via shared work-record mechanism, PipelineState init + accumulated fields, WorkRecord cache hits on re-runs.

## Build phases

Each phase ends with a test gate. Phase N+1 starts when N's gate passes.

| Phase | What | LOC est. | Gate |
|---|---|---|---|
| 1 | Entity-yaml model + ECS loader. Author component schema yamls in `components/`, `graph-system/components/`, `work-system/components/`. Generic loader resolves entity-types from `entities/` + component schemas from `components/`. Names registry. Validator system. Pre-commit hook that runs the loader against the full kit + every example pipeline. | ~250 Python + ~400 yaml | hand-authored entity-instance yamls round-trip cleanly through loader -> typed in-memory entity catalog -> dump-back-to-yaml; pre-commit hook rejects an inconsistent CL |
| 2 | Work subsystem core (includes show-your-work-as-cache). Submit pipeline with request-hash lookup. Worker registry (explicit registration). **Four workers:** `openrouter` (default deterministic + temp 0; non_deterministic override -> non-zero temp + skip cache), `claude_inference` (same determinism rules as openrouter; Claude Code subagent dispatch with tools disabled), `claude_agent` (Claude Code subagent with tool/MCP access; check-once capability detection, fail-loudly on change; Determinism requires_declaration), `python_script` (any dotted-name function, may shell out to external commands; Determinism requires_declaration; optional `consumes_dirs` / `produces_dirs` in config for shell-out functions). Failure-mode classes incl. missing-determinism declaration. WorkRecord write/read against the live cache dir. Per-request `CacheControl` (bypass, invalidate_if, determinism) honored. Structured `SideEffects` component on WorkResult (file-written, subprocess-invoked variants); cohort-replay refuses to call workers whose work has declared `produces_dirs` and isn't being re-invoked. `compute_subhashes` helper in `agent_glue_lib.work.hashing` for consumers needing sub-element invalidation. Optional `run_subprocess` helper in `agent_glue_lib.work.helpers` for python_script functions that shell out. | ~500 | submit a WorkRequest to each of the four workers, get a WorkResult; identical request twice = one worker invocation, second returns cached record; `CacheControl.bypass: true` forces re-run; `CacheControl.determinism: non_deterministic` on inference workers switches to non-zero temperature and skips cache lookups; missing-determinism declaration on a requires_declaration worker raises at submit; capability check fires once + fails loudly on subsequent invalidation; python_script that declares `consumes_dirs` auto-invalidates cache on dir mtime change |
| 3 | Graph runtime. Node/Edge dispatch on discriminated-union variants, PipelineState init + accumulated, StateDelta merge. No serialization (auditability via work subsystem). | ~150 | trivial 3-node in-memory graph runs end-to-end; variant dispatch picks the right edge; nodes that call `submit()` see cache hits on re-run |
| 4 | Canonical outputs. Declared `outputs:` with Jinja2 path templates (`{{ state.x }}` / `{{ input.x }}`). Format dispatch: `yaml` / `json` / `text` / `managed`. | ~120 | declared artifact lands at templated path with correct content; `format: managed` lets the node own the write |
| 5 | Cohort substrate. Cohort + Fixture + ExpectedOutcome entities. `agent-glue replay` (points work cache at cohort recordings dir; asserts terminal state against ExpectedOutcome). `agent-glue promote-fixture` (start state of a live run -> Fixture). `agent-glue work promote-record` (live WorkRecord -> cohort recordings). | ~150 | promote-then-replay round-trip on Example A's structure; `expected/` mismatch fails the replay; cohort-mode replay never makes live worker calls (strict) |
| 6 | CLI + plugin packaging. `cli.py`, `bin/agent-glue` (POSIX + Windows shims), `bootstrap.json` with openrouter-kit dep, `pyproject.toml`. Scripts as facades only. | ~150 | `agent-glue run` / `replay` / `promote-fixture` / `validate` / `work submit` / `work promote-record` callable from a fresh checkout |
| 7 | Stub render. `render.py` emits a placeholder `graph.html` ("design artifact is `graph.yaml`; render TBD"). One View; architecture admits more (incl. V+C hybrids). | ~30 | `agent-glue render` doesn't crash |
| 8 | Example A (character animation pipeline) + cohort with curated Fixtures + recorded WorkRecords for mock LLM responses. | ~300 | `agent-glue replay examples/character_animation --cohort default` passes |
| 9 | Example B (localization pipeline) + cohort. | ~300 | `agent-glue replay examples/localization --cohort default` passes |
| 10 | Skill. `skills/agent-glue/SKILL.md` + references: authoring patterns, contract design, dispatch idioms, show-your-work-as-cache configuration. | ~300 markdown | Skill loads and matches user-invocable schema; points at the two examples as reference templates |

**Total:** ~1950 LOC of Python + ~400 LOC of yaml schemas + ~300 lines of skill markdown + tests throughout. Realistic estimate: 5 focused sessions for phases 1-7 (the kit itself; Phase 2 grew with the extra inference worker + SideEffects + compute_subhashes + the python_script shell-out pattern), 1-2 sessions per example, 1 session for skill. Call it **2-3 weeks of focused work** end to end.

## Definition of done

v1 ships when:

1. Plugin installs cleanly via `claude plugin install` from `plugins-kit` marketplace.
2. `agent-glue replay examples/character_animation --cohort default` exits 0.
3. `agent-glue replay examples/localization --cohort default` exits 0.
4. `agent-glue work promote-record <request_hash> --to-cohort default` on either example produces a round-trippable cohort entry.
5. WorkRecord cache exercised in both examples: re-running with no input change demonstrably hits cache on every worker call.
6. `agent-glue render` emits a stub HTML page without crashing.
7. Skill is invocable and points at the two examples as reference templates.
8. Pre-commit hook installed and rejects inconsistent CLs (test by intentionally breaking an entity-component reference and confirming the hook fires).

## Test substrate strategy

Two test layers:

- **pytest unit tests** inside `agent_glue_lib/` covering loader edge cases (entity-instance validation, missing components, unknown component types), contract validation failures, variant dispatch, state-delta merge, Jinja path-template substitution, cache key collisions, CacheControl bypass + invalidate_if behavior, Determinism flag honored, cohort replay determinism. Goal: ~85% coverage on the kit lib.
- **End-to-end via the two examples** using their own cohorts. The examples' `expected/` directories are the integration test surface. CI runs `agent-glue replay` on both as the kit's smoke test.

WorkRecords in cohorts are hand-authored YAML files keyed by request hash. No live OpenRouter calls in CI; cohort-mode strict replay fails if a recording is missing (so missing records become test failures rather than network calls).

## Process

- **Build location.** Work in-place at `D:/dev/plugins-kit/plugins/agent-glue/`. The plugin is NOT published to the marketplace until v1 is ready (all 10 phases pass their gates + definition-of-done met).
- **Pre-commit hook.** Phase 1 ships a hook that runs the loader against the full kit + every example pipeline. Inconsistency between entity yamls, component schemas, instance yamls, and the loader fails the commit. There is no per-component schema versioning; consistency is maintained atomically per CL.
- **No publish until ready.** Do not bump the plugin version in `.claude-plugin/plugin.json` or `marketplace.json` during development. Publish only at v1.
- **Phase ordering** is the implementer's call. Default is linear; deviations are taken if a vertical slice de-risks the design earlier.

## Open questions

None outstanding at the plan level. In-architecture open questions live in each subsystem's ARCHITECTURE.md "Open questions" section and can be resolved as the relevant phase progresses (currently: side-effect schema for claude_agent's WorkResult, cache directory location confirmation, renderer-readable component-presence query helper).
