# core: Architecture

The architectural patterns every subsystem inherits. Subsystem-specific patterns live in the relevant subsystem's ARCHITECTURE.md.

## MVC + ECS

- **Model** = yaml entities.
- **View** = renderer(s) over the entity catalog. Some Views may also be Controllers (V+C hybrid) -- a renderer that exposes operations to mutate state is permissible. The constraint is that the Model stays the source of truth; mutations flow through it, not around it.
- **Controller** = runtime + CLI.

ECS data model: entities are composed of typed components. No class hierarchy to extend; new entity flavors are new component definitions plus systems that operate on them.

## Pydantic at the yaml boundary

Subsystems load yaml into Pydantic models at the system boundary, then operate on typed in-memory objects. The yaml is the durable model; Pydantic provides validation and type hints in the Python systems. Pydantic models are *derived from* the yaml model, not the source of truth.

For component values whose shape is open or schema-defined rather than class-defined (open maps, `any`-typed fields, anywhere the consumer parses the value into their own domain types), the loader stores the value as a plain dict. Structural validation runs against the loaded `ComponentSchema`, not against a generated Pydantic class.

## Yaml primitive vocabulary

The model uses only these yaml primitives:

- Scalars: strings, ints, floats, bools, nulls.
- Lists: ordered sequences.
- Maps: key/value pairs.
- Named refs: bare strings interpreted as references to entities defined elsewhere (e.g. `in: ValidateIn` is a string interpreted as a contract name; a subsystem-specific loader resolves it).
- Path templates: strings with Jinja2 substitutions; resolved at write time. Used by the graph subsystem only.

No custom yaml tags, no expressions, no eval. A pure-yaml linter can validate the model structure without instantiating anything.

## Failure as a first-class outcome

Both the structural ADTs (Disposition's three variants) and the subsystem-specific failure shapes (the work subsystem's `WorkerNotAvailable`, `CapabilityUnavailable`, `OutputSchemaViolation`, `WorkerError`) express the same philosophy: never silently substitute, never auto-retry without consumer instruction, never return a partial result without raising. A subsystem's job is to surface what happened in a typed shape; what to do about it is the consumer's decision.

## Fail loudly on changed conditions

agent-glue checks ambient conditions (available tools, MCP servers, registered functions, on-disk capability sets) ONCE -- at startup or on first use -- caches the result, and fails loudly if a subsequent operation discovers the condition has changed. The plugin does not adapt to changing conditions to keep things working; adapting silently hides bugs and produces non-deterministic behavior.

When a cached condition is invalidated mid-run, the next operation that depends on it raises a clear error naming the condition and the change observed. The consumer either restarts the session against a stable environment or fixes the upstream cause; the runtime does not paper over the drift.

This drives several subsystem-specific behaviors: the claude_agent worker checks `provided_capabilities` once and fails loudly if missing later; `agent-glue work validate` does NOT pre-check capabilities (the actual failure at execution time is the signal); the work cache invalidates aggressively when any input or worker config changes.

## Pre-commit consistency over schema versioning

Entity-type yamls, component-schema yamls, instance yamls, and the loader must all validate consistently before any commit. There is no per-component `version:` field and no migration shim layer; git history is the canonical record of what existed before (a commit sha identifies a coherent snapshot).

The pre-commit hook runs the loader against the full kit and every example pipeline; any inconsistency (missing component, type mismatch, instance referencing an unknown component, broken enum value) fails the commit. A change touches the entity yamls, the component schemas, the instance yamls, and the loader's expectations in a single CL.

Combined with *no backwards compatibility in development*, this means rename and reshape operations are atomic per-commit and the corpus is always self-consistent.

## No backwards compatibility in development

agent-glue is in active development. Changes don't carry deprecation shims, alias layers, removed-API stubs, or backwards-compatibility facades. Renames are direct; removals are direct; field reshapings don't leave a parallel old shape behind. Git history is the canonical record of what existed before -- if a developer needs to understand a prior shape, `git log` and `git show` are the tools, not surviving artifacts in the codebase.

This applies across yaml (no `_v1` / `_v2` parallel fields), Python (no `@deprecated` aliases kept around), and CLI (no hidden flags preserved for old callers). If a change breaks existing in-flight work, the migration is documented in the commit and applied in one pass.

## Scripts as facades

All CLI scripts (under `bin/`, `scripts/`) are thin facades over `agent_glue_lib/`. Scripts parse arguments, call library functions, format output for terminal display. They contain no business logic, no domain decisions, no orchestration that isn't expressible by library calls. Tests target the library, not the scripts; the script layer is verified by smoke tests that confirm the facade wiring works end-to-end.

This rule makes the library the testable surface, keeps the scripts trivially replaceable, and means any consumer that doesn't want the CLI can use the library directly with no impedance.

## Package cohesion (CRP / CCP / ADP)

Library code organization follows Robert C. Martin's package cohesion principles:

- **Common Reuse Principle (CRP)** -- code that's reused together belongs in the same module. Don't force a consumer to import unrelated code to use the one thing they need. Split modules when their contents serve different reuse patterns.
- **Common Closure Principle (CCP)** -- code that changes for the same reason belongs in the same module. When a system is updated, ideally only one module needs to change.
- **Acyclic Dependencies Principle (ADP)** -- the dependency graph between modules is a DAG. No circular dependencies between modules.

Applied to agent-glue: the four-subsystem split (`core`, `claude-work-queue`, `work-system`, `graph-system`) is a CCP application; the one-way dependency graph (core <- everyone, claude-work-queue <- work-system's claude workers, work-system <- graph-system) is an ADP application; within each subsystem, file organization follows the same principles.

## Test-driven development (80/20)

agent-glue follows TDD selectively. The goal is 80% of the benefit of full TDD for 20% of the effort: confidence the corpus behaves the way we think it does, without ceremony for cases that don't actually catch anything.

In practice:

- **Sensible tests as we go.** Every increment lands with tests that exercise its acceptance criteria. The loader gets round-trip tests, the validator gets a broken-fixture set, the cache gets a hit/miss/bypass matrix. Tests target the library, not the CLI.
- **Bug-first test reflex.** When a bug surfaces, the question is "should a test have caught this?" If yes: write the test first, watch it fail, fix the bug, run the suite, confirm the new test passes and nothing regresses. The test becomes the regression net for that specific failure shape.
- **Tier accordingly.** Fast unit tests (loader, validator, cache hash key, dispatch logic) are the bulk of the suite. Integration tests (a full pipeline run, an end-to-end cache hit + cohort promote) are fewer but still cheap. Anything that requires a live LLM call lives in cohort-driven tests so the suite stays deterministic.
- **What we don't do.** Test-the-test ceremony for trivial getters, mock everything for unit purity at the cost of integration coverage, write tests just because a coverage tool complains. The signal is "would this test have caught something useful?" If no, don't write it.

The pre-commit hook is part of this loop: it runs the structural-consistency validator on every commit so that schema drift never reaches main.
