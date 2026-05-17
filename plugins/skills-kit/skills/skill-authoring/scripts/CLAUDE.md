# skill-authoring/scripts/ insights

Per-directory insight repository for the audit / classify / tag / schemas script set. Insights captured during the YAML contract refactor (this project's Phase Y1-Y4). The YAML block below is the load-bearing surface; this file is not narrative.

**Phase / finding identifier legend.** `Phase Y1`-`Y4` = phases of the YAML contract refactor (Y1 = stdlib walker design; Y4 = local-code-review conversion). `Phase 4.2` = corpus audit pass. `F-4-2-N` = numbered findings from Phase 4.2 (e.g. F-4-2-2 / F-4-2-3 = paired user-only technique-skill findings). For the full legend, see ../CLAUDE.md.

```yaml
claude_md:
  _schema_version: "1"
  scope:
    directory: plugins/skills-kit/skills/skill-authoring/scripts
    covers:
      - audit.py / classify.py / tag.py / schemas.py / _shared.py design
      - the heuristic vocabulary used by the legacy markdown fallback
      - the YAML schema walker rule grammar
      - dependency posture (stdlib + optional pyyaml)
    excludes:
      - skill content authoring (covered by ../references/glossary.md and ../references/framework.md)
      - bootstrap-engine internals (covered by plugins/bootstrap/skills/bootstrap/SKILL.md)
  insights:
    - id: strip_code_fences_before_heuristics
      keywords: [code fence, fenced block, narrative body, mixed-type false positive, audience-claude, yaml block, stripped body, heuristic over-fire]
      summary: Apply narrative heuristics to body text with fenced code blocks removed; structured data inside fences must not raise type-signal scores.
      detail: |
        _shared.strip_code_fences() removes ```...``` blocks before applying type signal heuristics
        (count_ordered_steps, has_recognition_marker, etc.). The principle: structured data inside
        fenced YAML/JSON/python is reference content for machine comprehension, not narrative or
        procedure. Counting ordered list items inside a fenced ```python code block raised technique
        scores on reference-skills (bootstrap mixed-type false positive). _shared.has_yaml_block()
        is the inverse signal: presence of a fenced YAML block is a positive reference-content marker.
      origin: Phase 4.2 audit lessons-learned (F-4-2 series); Audience-Claude principle.
      added: "2026-04-28"
    - id: user_only_via_disable_model_invocation
      keywords: [user-only, disable-model-invocation, slash-command, technique-skill carve-out, ordered-step exemption]
      summary: User-only technique-skills (disable-model-invocation true in frontmatter) skip the ordered-step body requirement; the technique IS the slash-command.
      detail: |
        _shared.is_user_only(fm) returns true when frontmatter sets disable-model-invocation: true.
        type_signals(body, fm) adds +3 to technique-skill score for user-only skills so classify
        recognizes them as technique-skill even when the body has zero ordered-step entries.
        audit.check_technique_skill threads frontmatter so the ordered-step row reports n/a for
        user-only skills with note "user-only ... the technique IS the slash-command". The unified
        TECHNIQUE_SKILL_SCHEMA in schemas.py enforces "techniques must have steps OR output_template"
        instead of the previous variant-separated schemas.
      origin: Phase 4.2 audit lessons-learned F-4-2-2 / F-4-2-3.
      added: "2026-04-28"
    - id: schema_walker_rule_vocabulary
      keywords: [schema, walker, validator, rule grammar, required, type, min_len, forbid_regex, items, keys]
      summary: schemas.py uses a small Python-dict rule vocabulary; no external schema language.
      detail: |
        Each schema row is a dict with keys from a fixed vocabulary: required (bool), type (string|list|dict|int|bool), min_len/max_len (int), forbid_regex (regex with msg), items (subschema for list members), keys (subschema for dict children). schemas._validate_value walks recursively. Custom rules (e.g. facts_must_include_gotcha, techniques_must_have_body) live as schema-level flags and are evaluated after the walker. Adding new rules: extend _validate_value, add the schema-flag check at the bottom of validate(). No jsonschema or pydantic dependency.
      origin: Phase Y1 design choice for the YAML contract refactor.
      added: "2026-04-28"
    - id: three_audit_states
      keywords: [audit states, yaml-validated, contract-staged, legacy fallback, pyyaml, transition]
      summary: audit.py has three runtime states; the staged middle state lets converted skills audit cleanly before pyyaml lands.
      detail: |
        State 1 (yaml-validated): pyyaml present + a recognized YAML contract block. Schema walker runs, deterministic per-row pass/fail, mixed-type signal deterministic. Legacy heuristics skipped.
        State 2 (contract-staged): pyyaml absent BUT a YAML contract block is detected by regex (root key match). Universal rows pass; YAML contract row reports judgment-required ("install pyyaml to validate"); legacy heuristics skipped (because a contract is staged, just unvalidated). Mixed-type signal deferred.
        State 3 (legacy markdown fallback): no YAML contract block at all. All legacy heuristics run as before; mixed-type via narrative scoring.
        The middle state was added so the converted skills don't report bogus markdown-heuristic failures during the transition.
      origin: Phase Y1.3 implementation; permission denial on global pip install of pyyaml in this dev env.
      added: "2026-04-28"
    - id: pyyaml_dependency_posture
      keywords: [pyyaml, dependency, stdlib, plugin venv, bootstrap, optional]
      summary: pyyaml is a runtime dependency declared in plugins/skills-kit/pyproject.toml; the audit runs without it via the contract-staged state.
      detail: |
        plugins/skills-kit/pyproject.toml declares pyyaml under dependencies. The bootstrap engine sets up a plugin venv at ~/.claude/plugins/data/plugins-kit/skills-kit/.venv/ where the audit script can be invoked with pyyaml available. Outside that venv (e.g. running with bare system Python), audit.py degrades gracefully: HAVE_YAML False, contract-staged state, JUDGMENT row noting parser unavailable. Do not add stdlib-only YAML parsing -- the multi-step YAML sequence pattern uses real YAML (lists, nested mappings) that a hand-rolled subset parser cannot cover.
      origin: Phase Y1.1 dependency decision; proposal section E.6.
      added: "2026-04-28"
    - id: extra_keys_allowed
      keywords: [extra keys, schema strictness, open record, narration, subagents, skill-specific structure]
      summary: The validator does not reject unknown keys; skill-specific structure (e.g. p4-code-review's narration, subagents) is preserved.
      detail: |
        validate() walks declared schema keys but does not error on additional keys present in the YAML data. This permits skill-specific structured fields the generic schema doesn't cover (e.g. p4-code-review carries narration:, subagents:, false_positive_guardrails: alongside the technique_skill: required keys). Forbidden cross-type keys (rules:, counters:, facts:, etc. inside a wrong root) DO fail. The trade: unknown keys pass silently rather than flagging for review. Y5 schema lock may revisit this if real audits surface load-bearing content hiding in extra keys.
      origin: Phase Y4 conversion of local-code-review; proposal recommendation in section E.3.
      added: "2026-04-28"
  conventions:
    - rule: When extending heuristics, modify _shared.py first; audit.py and classify.py both import from there.
      keywords: [SSOT, _shared.py, helper extraction, drift]
      why: Duplicating heuristics between audit.py and classify.py was an early-version mistake; the refactor pulled them into _shared.py so a single update reaches both consumers.
    - rule: Custom schema rules go in schemas.validate(), checked after the walker. Do not embed custom logic inside the walker itself.
      keywords: [walker, custom rule, schema flag, validation order]
      why: Walker stays general; custom rules are per-schema and benefit from explicit schema-level flags (facts_must_include_gotcha, techniques_must_have_body). Walker should remain reusable across schema types.
    - rule: Audit output rows describe what was checked, not what was good or bad in isolation. Verdict is one of pass/fail/judgment-required/n/a.
      keywords: [verdict vocabulary, four-state output, audit row]
      why: Three-state (pass/fail) loses the conditional-not-fired case (n/a) and the agent-must-judge case (judgment-required). Both are real and deserve their own slot.
```
