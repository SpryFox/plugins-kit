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
