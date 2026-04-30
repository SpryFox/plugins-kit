# skill-authoring/ insights

Per-directory insight repository for the skill-authoring domain-skill: the canonical contract surface (glossary + framework), the audit-driven evolution that shaped schema v1, and the operating norms a future agent picks up cold. The YAML block below is the load-bearing surface; this file is not narrative.

Insights here capture decision provenance -- the audits that reshaped the framework -- not the canonical content itself. The contract surface lives in `references/glossary.md`, `references/framework.md`, and `scripts/schemas.py` (SSOT); this file records *why those contracts look the way they do* so a future agent can rewind the reasoning.

```yaml
claude_md:
  _schema_version: "1"
  scope:
    directory: plugins/skills-kit/skills/skill-authoring
    covers:
      - canonical contract surface (glossary, framework, schemas) and how it evolved
      - audit-driven framework evolution decisions (Dec-1 / Dec-2 / Dec-3)
      - form-choice in practice on the framework's own content
      - SSOT discipline between glossary, framework, schemas, and the scripts directory
    excludes:
      - validator / audit / classify / tag script internals (covered by scripts/CLAUDE.md)
      - per-plugin-dependency posture (covered by plugins-kit/CLAUDE.md and plugins/skills-kit/CLAUDE.md)
      - per-skill SKILL.md insights for other skills
  insights:
    - id: dec_1_form_choice_bias_structured
      keywords:
        - form choice
        - audience-claude
        - structured by default
        - prose exception
        - bias toward structured
        - yaml default
        - anti-pattern list assertion
        - llm-facing content
      summary: The default for LLM-facing skill content is structured YAML; prose is the documented exception. Earlier framing ("if unclear, prose is the default") was wrong direction for an Audience-Claude framework and was reversed.
      detail: |
        Original glossary phrasing said "if unclear, prose is the default." The audit-prep
        review of the eleven advocated principles surfaced that this was the wrong default
        for LLM-facing content: skills are runtime context for Claude, structure aids
        Claude's comprehension, prose is what Claude generates on demand for the user.
        The form-choice principle was rewritten: default to structured YAML; use prose only
        when (a) the content is naturally narrative -- an identity sentence, an orientation
        paragraph, a single-paragraph explanation that does not decompose into discrete
        records -- or (b) hierarchy carries no meaning. When in doubt, bias toward
        structured data. The bar for prose is "I can articulate why this would be worse as
        YAML"; if that articulation is hard, default to YAML.

        Why this matters operationally: structure carries assertions prose cannot. An
        anti_patterns: list with each entry as a record asserts implicitly that every item
        is genuinely an anti-pattern; a markdown bullet list carries no such assertion.
        Records are routable, keyword-able, and validatable; prose is none of those.

        Codified in: glossary.md (Audience-Claude entry, Form choice subsection);
        framework.md (Content-form choice section).
      origin: |
        Audit-prep work unit 2026-04-29. Surface: review of plugins-kit's advocated
        principles against its own canonical content. Finding: the framework advocated
        bias-toward-structure but its own glossary defaulted to prose. Decision recorded
        as Dec-1 in the project's lessons-learned log; PR #12 (mergeCommit 5d11b93)
        landed the contract change.
      added: "2026-04-29"
    - id: dec_2_ordered_steps_universal
      keywords:
        - technique-skill
        - ordered steps
        - steps required
        - user-only carveout removed
        - output_template optional
        - trigger model metadata
        - schema tightening
      summary: "Every technique-skill requires an ordered steps: list (min 1) regardless of trigger model. The previous user-only carveout was dropped after auditing real user-only skills."
      detail: |
        Phase 4.2 paired finding F-4-2-2 / F-4-2-3 surfaced that the framework exempted
        user-only technique-skills (disable-model-invocation: true) from the ordered-step
        body requirement, and classify.py could not detect ordered steps in the user-only
        branch. Verification against actual user-only technique-skills (cache-report,
        local-code-review, test-greeting) showed every technique reduces to ordered steps,
        even cache-report's "render script stdout verbatim" which maps to a 1-2 step
        procedure. Steps are a sufficient body; output_template: is a separate concept
        (output-shape contract) that stays as an optional companion field, not a
        substitute.

        Implementation: schemas.py TECHNIQUE_SKILL_SCHEMA now requires steps: with min_len
        1 on every technique. trigger_model is metadata. output_template: is optional
        with a note clarifying it's a companion to steps. The trigger-model conditional
        was dropped from framework.md technique-skill row; audit.py and classify.py
        heuristic paths updated; cache-report and test-greeting gained 1-step steps:
        blocks during the audit-prep work unit.
      origin: |
        Audit-prep work unit 2026-04-29. Surface: F-4-2-2 / F-4-2-3 paired finding from
        Phase 4.2 audit of plugins-kit skills. Finding: every audited user-only technique
        decomposed into 1-2 explicit steps, so the carveout protected nothing real.
        Decision recorded as Dec-2 in the project's lessons-learned log; PR #12 landed
        the schema tightening.
      added: "2026-04-29"
    - id: dec_3_schemas_are_floors
      keywords:
        - schemas are floors
        - extras allowed
        - schema strictness
        - load-bearing extras
        - extension keys
        - structure-friendly
        - mixed-type forbidden_keys
      summary: Per-type YAML schemas validate the required minimum; authors may add load-bearing structured keys beyond the schema. Mixed-type drift is detected via explicit forbidden_keys, not via blanket strictness.
      detail: |
        The yaml-refactor design open question Q3 ("extra-key strictness") was resolved:
        always allow extras. Disallowing extras would push authors toward unstructured
        prose when they want to add legitimate load-bearing structure (an exceptions:
        list inside an anti-pattern entry; narration: and subagents: blocks inside
        local-code-review's technique). That contradicts the bias-toward-structured-data
        default codified by Dec-1.

        The schema validates the floor: required keys, required item shapes, required
        list lengths. Authors layer additional structured content on top freely.
        Cross-type drift is still caught -- each schema names a forbidden_keys list
        (e.g. rules: inside reference_skill: is forbidden because rules belong to
        discipline-skills). Unknown keys not in the forbidden list pass silently.

        Codified in: framework.md "Schemas are floors, not ceilings" section;
        schemas.py module docstring; scripts/CLAUDE.md insight extra_keys_allowed
        which is the validator-side detail of the same decision. yaml-refactor-design-spec
        Q3 marked resolved.
      origin: |
        Audit-prep work unit 2026-04-29. Surface: yaml-refactor-design-spec Open
        Questions section 3. Finding: the validator already permitted unknown keys
        (extra_keys_allowed insight in scripts/CLAUDE.md); the framework documents
        needed to make this an explicit principle rather than an implementation
        accident. Decision recorded as Dec-3 in the project's lessons-learned log;
        PR #12 landed the documentation.
      added: "2026-04-29"
    - id: dec_4_anti_patterns_promoted_field
      keywords:
        - anti-patterns
        - structured field
        - structure asserts
        - lookalike-but-wrong
        - technique-skill optional
        - discipline-skill optional
        - schema extension
      summary: "anti_patterns: was promoted from a load-bearing extra (schemas-are-floors territory) to a first-class optional field on technique_skill and discipline_skill. The structured record shape implicitly asserts every entry is a genuine anti-pattern; a markdown bullet list carries no such assertion."
      detail: |
        Schemas-as-floors (Dec-3) said extras are always allowed; it did not say extras
        cannot be promoted to documented optional fields. anti_patterns: is the first
        such promotion. Authors can still add an inline anti-patterns list under any
        skill type as an extra (per Dec-3), but technique_skill and discipline_skill
        now carry a recommended structured shape with the keys id / name / keywords /
        why_it_seems_right / why_it_is_wrong / alternative.

        The promotion exists because anti-patterns are the canonical example of "structure
        asserts." Containment in a list of records with these specific keys implicitly
        asserts every item is a genuine anti-pattern; a markdown bullet list under an
        H3 carries no such assertion. The five-key record shape forces authors to name
        why the lookalike seems right (the rationalization), why it is actually wrong
        (the failure mode), and what to do instead (the alternative pointer). That
        decomposition is what makes the entry useful at audit time -- a list of "don't
        do X" bullets without rationalization counters cannot survive a pressure test.

        Codified in: schemas.py ANTI_PATTERNS_RULE (constant, reused by both schemas);
        framework.md schemas_are_floors.promoted_extensions block listing the new field
        and its rationale.
      origin: |
        Phase 4.6 P4 work (2026-04-30). Surface: the session dialog that named four new
        value propositions on top of the embodiment-closure gap fixes; anti_patterns:
        as a first-class field was one of the four. Finding: anti-patterns lists were
        already a documented schemas-are-floors example (in framework.md and
        scripts/CLAUDE.md), but unstandardized; promoting to a typed shape benefits
        consistency across plugins-kit skills.
      added: "2026-04-30"
    - id: dec_5_hook_killed_keyword_surface_retained
      keywords:
        - y7 hook killed
        - sparse keyword rag
        - retrieval optimization deferred
        - chat-term relevance hints
        - keyword surface as documentation
        - intelligent yaml navigation
        - post-rollout optimization
      origin: |
        Phase 4.6 P7 framing review 2026-04-30. Surface: explanation of the proposed
        hook mechanic to the user against worked examples from real records, followed
        by the user's "is this a simplified RAG?" framing question. Finding: the
        sparse-keyword agentic-RAG framing made the cost/benefit visible -- failure
        modes (suggestion-when-not-relevant, spam, ignored hints) are real, retrieval
        quality is bounded by keyword authoring quality, and hand-curated sparse
        indexes have known precision/recall limits. The higher-value runtime is
        Claude learning to navigate the YAML structure intelligently rather than a
        hook injecting hand-tagged keyword matches. Decision: kill Y7 / P7 before
        implementation; defer retrieval optimization to post-rollout.
      added: "2026-04-30"
      summary: "Y7 hook killed before implementation. The YAML keyword clusters remain on every record as documentation and as a navigation aid for direct reads; the hook that consumes them does not ship. Post-rollout optimization will revisit teaching Claude to search the YAML structure intelligently rather than inject hand-tagged keyword matches."
      detail: |
        The proposed Y7 hook was a sparse-keyword agentic RAG: walk a registered set
        of YAML files, tokenize the user prompt, score keyword overlap per record,
        inject top-N matches as additionalContext on UserPromptSubmit. Three named
        failure modes (suggestion-ignored, suggestion-when-not-relevant, spam) plus
        a 50/50 net-harm risk had been documented in the design spec; a 50-prompt
        validation test plan was drafted before implementation.

        User reasoning for killing it (verbatim summary):
        1. RAG-as-such is not necessary for the current workflow; injecting a
           simplified RAG to optimize a non-bottleneck creates new failure modes
           without solving a real problem.
        2. Keyword-score relevance matching tends to hit the same over-tagged
           records repeatedly -- precision degrades exactly when retrieval would
           need to be smartest.
        3. The higher-value optimization is teaching Claude to navigate the YAML
           structure intelligently (selectively reading by sub-grouping, by
           keyword cluster, by record id), which is best revisited as a
           post-rollout optimization once real usage surfaces what kinds of
           navigation actually matter.

        What stays: the keyword: clusters on every record (glossary, framework,
        CLAUDE.md insights), the chat-term relevance hints principle in the
        glossary, the schema requirement that every load-bearing record carries
        keywords (>=3). These remain valuable as (a) human-readable navigation
        signals when a reader scans a record, (b) inputs to direct-reading agents
        who use the cluster as a navigation aid, (c) the index a future
        intelligent-search runtime would consume.

        What goes: Y7.1-Y7.5 hook implementation steps; the UserPromptSubmit hook
        wiring; the 50-prompt validation corpus (drafted but never run). The test
        plan at tmp/writing-skills-research/y7-validation-test-plan.md is parked
        as a reference artifact, not a live workstream.

        Codified in: yaml-refactor-design-spec.md Y7 section marked superseded;
        project-plan.md P7 row marked killed and Phase 4.6 closed; new "Phase 6
        -- Post-rollout optimizations" section in project-plan.md queues the
        intelligent-YAML-navigation work.
    - id: dec_6_capability_skill_type_and_layering
      keywords:
        - capability-skill
        - wrapper skill
        - external capability provider
        - tool / mcp / api / service / ide / framework
        - L1 L2 L3 layering
        - CLAUDE.md SKILL.md references content allocation
        - frequency of need test
      summary: "Capability-skill added as the 6th skill type. A capability-skill wraps an external capability provider (tool / MCP server / API / service / IDE / framework) with the project's setup and conventions. Conceptually inherits technique-skill (capabilities are techniques+); schema requires capabilities: at root, external_capability declaration, layering manifest (L1/L2/L3 content allocation), and capability-skill-level gotchas. Member skills + Conditional Loading fire conditionally when capabilities grow."
      detail: |
        Surface: Phase 4.3 SC audit Bucket C (reference-shape audit) flagged
        ue-mcp-server, hooks, ue-coding for re-bucket as F-4-3-C-4/5/6 --
        mixed-type drift, "reference-skill that's actually mixed." The
        deeper finding: tool-shape and wrapper-shape skills don't fit
        reference-skill or technique-skill or domain-skill cleanly. Their
        content shape is "structured capabilities wrapping an external
        thing" -- which is its own coherent shape.

        Three options were considered:
        - Use subset (force reference-skill): bad, loses domain structure
          for rich tool skills.
        - Use superset (force domain-skill): bad, fabricates members for
          flat tool skills.
        - New type via inheritance (capability-skill IS-A technique-skill
          + capability-specific structure): best fit; conditional rows
          support the growth curve from flat to rich.

        Naming: "tool-skill" was too narrow (MCP servers, APIs, services
        aren't tools). "Wrapper-skill" too generic. "Capability-skill"
        composes with the existing Capability pattern (a capability-skill
        is a skill of capabilities). The naming layers cleanly: capability
        (unit) -> capability-skill (type that aggregates them).

        L1/L2/L3 content layering principle ships in the same change as a
        new framework section. The principle is general (applies to any
        skill with multi-load-level potential) but most load-bearing for
        capability-skills (which have significant L1 territory because
        the wrapped thing is used widely). The schema's required
        layering manifest enforces it for capability-skills; for other
        types it is authoring guidance.
      origin: |
        Phase 4.3 SC audit (F-4-3-8 mixed-type drift on tool-shape skills)
        + the git/ domain-skill build that demonstrated the layering
        principle in practice (worked example for the principle). User
        framing question pushed past "tool" to the broader "wrapper around
        external capability provider" framing, which generalizes cleanly.
      added: "2026-04-30"
    - id: ssot_canonical_split
      keywords:
        - SSOT
        - glossary canonical
        - framework canonical
        - schemas authoritative
        - markdown table review
        - divergence rule
      summary: Vocabulary lives in glossary.md, contracts in framework.md, machine-readable schemas in scripts/schemas.py. Schemas win on divergence with framework.md tables; framework.md tables stay for human review.
      detail: |
        The three artifacts have different jobs and one canonical owner per fact:
        - glossary.md owns vocabulary (terms, principles, patterns, type names,
          attributes). Other documents reference terms by name without redefining.
        - framework.md owns contracts (per-type required/conditional/prohibited rows,
          description requirements, content-form choice, schemas-as-floors section).
          The markdown contract tables are kept for human review clarity.
        - scripts/schemas.py owns the machine-readable contract. When schemas.py and
          framework.md tables diverge, schemas.py wins. Framework tables get updated
          to match; the schema does not get loosened to match an out-of-date table.

        This split is what makes audits deterministic: audit.py validates against
        schemas.py, not against markdown heuristics. The markdown surface is for the
        human reviewer; the YAML schema is for the agent.
      origin: |
        Phase Y5 schema v1 lock 2026-04-28. Codified in framework.md "Canonical
        contract surface (schema v1, locked 2026-04-28)" section.
      added: "2026-04-28"
    - id: audit_driven_refinement
      keywords:
        - audit-driven evolution
        - lessons-learned
        - friction log
        - re-audit gate
        - strict by default
        - real audits over theoretical iteration
      summary: Framework friction is discovered by running real audits, not by theoretical iteration. Strict-by-default is safer than loose; real audits surface over-strictness, while under-strictness is silent.
      detail: |
        The user methodology is "by actually performing audits we can make it more
        crisp." The framework refines through audit cycles rather than abstract
        polishing. Each audit captures friction in the lessons-learned log
        (project-plan.md in the SC working dir, plus this CLAUDE.md for the
        plugins-kit-resident decisions); each subsequent contract change cites the
        finding that triggered it.

        Operating consequence: when the framework feels under-specified or
        over-specified, do not iterate the framework in isolation. Run an audit on
        a real skill, capture the friction with surface / finding / follow-up
        provenance, and refine the contract from concrete evidence. Default toward
        stricter rules; real audits will surface over-strictness, while
        under-strictness fails silently.
      origin: |
        User methodology captured 2026-04-28 during framework v1 sign-off; reinforced
        through the audit-prep work unit (Dec-1/Dec-2/Dec-3 are themselves
        audit-driven decisions, not theoretical ones).
      added: "2026-04-28"
  conventions:
    - rule: When changing a schema in scripts/schemas.py, update framework.md table rows in the same change so the human-review surface stays in sync.
      keywords:
        - schema change
        - framework sync
        - SSOT discipline
        - paired update
      why: schemas.py is authoritative on divergence, but a stale framework.md table is the most common drift source and confuses reviewers. Pair the updates so the divergence window is zero.
    - rule: Every framework decision lands as a lessons-learned entry with surface / finding / follow-up provenance before the contract change ships.
      keywords:
        - provenance
        - lessons-learned
        - decision log
        - surface finding follow-up
      why: A contract change without provenance cannot be rewound. A future agent must be able to reconstruct what audit surface revealed the friction; outcomes alone (the new schema) do not carry that signal.
    - rule: Re-audit every plugins-kit skill after any schema or framework change. Zero FAILs is the merge gate.
      keywords:
        - re-audit gate
        - merge criterion
        - validator self-test
        - dogfood
      why: "The plugin advocates schema validation as the audit substrate; shipping a contract change that breaks the plugin's own skills would violate the principle. The re-audit also catches second-order effects (e.g. a tightened technique-skill row forcing cache-report to gain a steps block)."
```
