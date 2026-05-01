# skills-kit plugin orientation

Plugin-level orientation for `plugins-kit:skills-kit`. The plugin ships a single domain-skill (`skill-authoring`) plus a script suite (`audit.py` / `classify.py` / `tag.py` / `schemas.py`) that operationalizes the framework. A fresh agent landing here should read this file before any of the references; this file points at the right surface for the task at hand.

The framework the plugin advocates:

- **Audience-Claude.** Skills are runtime context for Claude, not human documentation.
- **Form-choice bias toward structured data.** Default to YAML for LLM-facing content; prose only when content is naturally narrative.
- **Schemas are floors, not ceilings.** Each per-type schema names the required minimum; authors may add load-bearing structured keys beyond it.
- **Audits drive refinement.** Friction is discovered by running real audits, not theoretical iteration.

The YAML block below is the load-bearing surface for routing into the skill, the scripts, and the canonical references.

```yaml
claude_md:
  _schema_version: "1"
  scope:
    directory: plugins/skills-kit
    covers:
      - what the skills-kit plugin ships and how to use it
      - the four canonical surfaces (glossary, framework, schemas, scripts) and which to load when
      - the merge-gate convention for any change touching schemas or canonical references
      - dependency posture (pyyaml via bootstrap.json + pyproject.toml, never manual pip)
    excludes:
      - audit-driven framework decision provenance (covered by skills/skill-authoring/CLAUDE.md)
      - validator and script internals (covered by skills/skill-authoring/scripts/CLAUDE.md)
      - per-plugin dependency posture for other plugins (covered by plugins-kit/CLAUDE.md)
  insights:
    - id: plugin_surface_overview
      keywords:
        - skills-kit overview
        - what is this plugin
        - skill-authoring domain-skill
        - audit script
        - classify script
        - tag script
        - schema validator
      origin: Phase 4.6 P5 plugin-level orientation surface (2026-04-30).
      added: "2026-04-30"
      summary: skills-kit ships one domain-skill (skill-authoring) plus four scripts (audit / classify / tag / schemas) that operationalize the skill-authoring framework.
      detail: |
        Plugin layout:
        - skills/skill-authoring/SKILL.md -- the domain-skill itself; aggregates the
          framework as content and exposes audit/classify/tag as capabilities.
        - skills/skill-authoring/references/glossary.md -- canonical vocabulary
          (Audience-Claude principle, CRP/CCP/ADP/SSOT, types, patterns, attributes).
          Embedded YAML under root key glossary: with 63 records.
        - skills/skill-authoring/references/framework.md -- type contracts (5 markdown
          tables for human review) plus structured framework records (description
          requirements, content-form choice, audit procedure, schemas-as-floors,
          conditional-requirement grammar) embedded as YAML under root key framework:.
          schemas.py is authoritative on divergence with the markdown tables.
        - skills/skill-authoring/references/scripts.md -- script reference (purpose,
          usage, output verdicts, gotchas).
        - skills/skill-authoring/references/example-audit.md -- worked audit example.
        - skills/skill-authoring/scripts/schemas.py -- canonical machine-readable
          per-type contract. SCHEMAS_BY_ROOT dispatches by YAML root key.
        - skills/skill-authoring/scripts/audit.py -- per-skill or per-CLAUDE.md audit;
          three states (yaml-validated / contract-staged / legacy-fallback).
        - skills/skill-authoring/scripts/classify.py -- type inference; YAML root key
          is deterministic, heuristic scoring is the legacy fallback.
        - skills/skill-authoring/scripts/tag.py -- idempotent skill-type: frontmatter
          writer; refuses to overwrite existing differing values without --force;
          refuses missing-frontmatter cases (never invents).
    - id: which_surface_for_which_task
      keywords:
        - reading order
        - which file
        - vocabulary lookup
        - contract lookup
        - schema lookup
        - audit operation
        - classify operation
        - tag operation
      origin: Phase 4.6 P5 plugin-level orientation surface (2026-04-30).
      added: "2026-04-30"
      summary: Vocabulary -> glossary.md. Contract floor -> schemas.py (or framework.md tables for human review). Audit-driven decisions and provenance -> skill-authoring/CLAUDE.md. Validator internals -> scripts/CLAUDE.md.
      detail: |
        - "What does <term> mean?" -> glossary.md, search the appropriate sub-grouping
          (files / conventions / external_binding / principles / patterns / skill_types
          / attributes / sources). Every record has a keywords cluster for routing.
        - "Does this skill satisfy its type contract?" -> run audit.py against the
          SKILL.md path. Zero FAILs is well-formed.
        - "What are the required keys for type X?" -> schemas.py (canonical) or
          framework.md type contract tables (human-review surface; schemas wins on
          divergence).
        - "Why does the framework forbid Y / require Z?" -> skill-authoring/CLAUDE.md
          insights. Each Dec-N entry cites surface / finding / follow-up.
        - "How does the validator decide between yaml-validated / contract-staged /
          legacy-fallback?" -> scripts/CLAUDE.md three_audit_states insight.
    - id: merge_gate_convention
      keywords:
        - re-audit gate
        - merge criterion
        - schema change discipline
        - framework change discipline
        - zero fails
      origin: P1 convention (skill-authoring/CLAUDE.md) generalized to plugin level during P5 (2026-04-30).
      added: "2026-04-30"
      summary: Any change touching schemas.py, glossary.md, or framework.md must re-audit all six plugins-kit SKILL.md files plus the three CLAUDE.md files (skill-authoring, scripts, plugins-kit root) to zero FAILs before shipping.
      detail: |
        The plugin advocates schema validation as the audit substrate. Shipping a
        contract change that breaks the plugin's own skills would violate the
        principle the plugin teaches.

        Re-audit invocation pattern:

          for f in plugins/*/skills/*/SKILL.md \\
                   plugins/skills-kit/skills/skill-authoring/CLAUDE.md \\
                   plugins/skills-kit/skills/skill-authoring/scripts/CLAUDE.md \\
                   plugins/skills-kit/CLAUDE.md \\
                   CLAUDE.md; do
            python plugins/skills-kit/skills/skill-authoring/scripts/audit.py "$f"
          done

        Catch second-order effects: a tightened technique-skill row may force one or
        more SKILL.md files to gain steps: blocks (this is what happened during the
        audit-prep work unit -- cache-report and test-greeting both gained 1-step
        bodies after Dec-2 was codified).
    - id: dependency_posture
      keywords:
        - pyyaml dependency
        - skills-kit venv path
        - audit graceful degradation
        - HAVE_YAML
      origin: User directive 2026-04-28 codified in plugins-kit/CLAUDE.md; surfaced at plugin level during P5 (2026-04-30).
      added: "2026-04-30"
      summary: skills-kit's only Python dependency is pyyaml; the plugin venv lives at ~/.claude/plugins/data/plugins-kit/skills-kit/.venv. audit.py degrades gracefully when pyyaml is unavailable (contract-staged state). For the cross-plugin dep-management rule, see plugins-kit/CLAUDE.md.
      detail: |
        skills-kit-specific facts (the cross-plugin rule lives in plugins-kit/CLAUDE.md):

        - bootstrap.json declares venv.check_imports = ["yaml"]; pyproject.toml
          declares pyyaml in [project] dependencies.
        - The plugin venv path is ~/.claude/plugins/data/plugins-kit/skills-kit/.venv.
        - audit.py degrades gracefully when pyyaml is unavailable (HAVE_YAML False):
          universal rows still pass, the YAML contract row reports judgment-required
          ("install pyyaml to validate"), and legacy markdown heuristics are skipped
          (the contract is staged but unvalidated).
    - id: invocation_paths
      keywords:
        - invoke skill-authoring
        - run audit
        - run classify
        - run tag
        - bootstrap-installed venv python
      origin: Phase 4.6 P5 plugin-level orientation surface (2026-04-30).
      added: "2026-04-30"
      summary: The skill-authoring domain-skill loads on its trigger (skill design / authoring / audit / classification context). Scripts run via the plugin venv's Python.
      detail: |
        - Domain-skill: trigger fires on skill-design vocabulary (audit, classify,
          contract, schema, framework, type-contract, etc.). Per the
          conditional-loading index in SKILL.md, references load on demand.
        - Scripts: invoke via the plugin venv directly. The bootstrap engine ensures
          the venv exists at ~/.claude/plugins/data/plugins-kit/skills-kit/.venv;
          calling its python.exe runs audit.py / classify.py / tag.py with pyyaml
          available.

          Example (Windows; analogous on Mac/Linux with .venv/bin/python):

          ~/.claude/plugins/data/plugins-kit/skills-kit/.venv/Scripts/python.exe \\
            plugins/skills-kit/skills/skill-authoring/scripts/audit.py \\
            <path-to-SKILL.md-or-CLAUDE.md>

        - Outside the venv (bare system Python): audit.py runs but reports
          judgment-required on the YAML contract row. classify.py and tag.py operate
          on frontmatter and a regex-detected YAML root key; they do not need pyyaml.
  conventions:
    - rule: When changing schemas.py or framework.md or glossary.md, re-audit all 6 plugins-kit SKILL.md + 3 CLAUDE.md files in the same change. Zero FAILs is the merge gate.
      keywords:
        - merge gate
        - re-audit discipline
        - paired update
        - second-order effects
      why: The plugin advocates schema validation as the audit substrate; shipping a contract change that breaks the plugin's own skills would violate the principle. The re-audit also catches second-order effects across SKILL.md files.
    - rule: Surface a framework decision as a lessons-learned entry with surface / finding / follow-up provenance before the contract change ships. Land it in skill-authoring/CLAUDE.md (framework decisions) or scripts/CLAUDE.md (validator-side decisions).
      keywords:
        - provenance
        - decision log
        - lessons-learned
        - surface finding follow-up
      why: A contract change without provenance cannot be rewound. A future agent must be able to reconstruct what audit surface revealed the friction; outcomes alone (the new schema) do not carry that signal.
```
