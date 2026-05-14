---
_schema_version: 1
required_skills: ['md-read', 'skill-write']
name: knowledge-encoding
description: Encode conversation insights into persistent project locations
---

## Skill Purpose

Translate discovered knowledge into appropriate implementations within the project system. This is the inverse of search-and-discovery: where search finds information that exists, encoding makes the environment have information you discovered.

**Encoding is not an algorithm.** It requires design thinking to translate knowledge into the right form—a skill update, an anti-pattern, a reference doc section, a rule. The design framework (DISCLOSURE-ARCHITECTURE, DESIGN-LANGUAGE) provides the vocabulary and structure that makes this translation thoughtful rather than mechanical.

This skill addresses Axiom 5 (Intelligence Scales With Capability): conversations are ephemeral, but the workspace persists.

## When to Use

- Scenario: You discovered an insight or pattern that future agents should know
- Scenario: You're asking "where should this information live?"
- Scenario: A conversation revealed a gap in documentation or anti-patterns
- Scenario: You want to prevent future agents from repeating the same discovery process
- Scenario: User feedback corrected a misunderstanding that others might have

---

```yaml
activation_contexts:
  - "where should this live"
  - "encode this insight"
  - "persist this learning"
  - "future agents should know"
  - "document this pattern"
  - "add this to"
  - "prevent repeating this conversation"
  - "knowledge encoding"

core_expertise:
  relationship_to_search:
    search_and_discovery: "Find information that exists in the project"
    knowledge_encoding: "Make the environment have information you discovered"
    symmetry: |
      These are inverses. Search navigates existing structure to find knowledge.
      Encoding translates new knowledge into that same structure.

      Both require understanding the project's design framework—search to know
      where to look, encoding to know where things belong.

  three_modes_of_engagement:
    work_with_design: |
      DEFAULT MODE: Use the system as designed.
      All operational skills support this mode.

    improve_design: |
      META MODE: Evolve the system by encoding insights.
      This skill (knowledge-encoding) is the entry point.
      Determines WHAT to encode and WHERE it belongs.

    implement_design: |
      BUILD MODE: Create capabilities within the system.
      Domain-specific *-development skills support this mode:
      - hooks-write
      - rules-development
      - skill-write
      - command-write
      - script-write
      - agent-write
      - mcp-server-write

    workflow: |
      improve-design (this skill) often leads to implement-design:

      1. Insight discovered → invoke knowledge-encoding
      2. Determine encoding target (skill? rule? hook? doc section?)
      3. If new capability needed → invoke appropriate *-development skill
      4. Development skill provides patterns for that capability type

      Example: "Agents keep making this mistake"
      → knowledge-encoding: "This should be a blocking hook"
      → hooks-write: "Here's how to create one"

  fundamental_principle: |
    **Conversations are ephemeral. The workspace persists.**

    Every session ends. What lives on are:
    - Documentation (docs/, skills/, CLAUDE.md)
    - Code and configuration (hooks/, scripts/, commands/)
    - Data structures (KNOWN-PROBLEMS.yaml, issues/)

    The goal is not to complete tasks in a session—it's to leave artifacts
    that make future sessions smarter.

  encoding_as_proposition: |
    Encoding always starts with a proposition: "We could encode this."

    Not every insight belongs in the project. The goal isn't guaranteeing
    encoding—it's asking the question: "How should this be encoded?" and
    then making the judgment call on whether the system is better with
    that encoding or not.

    Sometimes the answer is "it shouldn't be." Sometimes translation reveals
    that the insight points to other improvements needed. The process of
    asking the question has value even when the answer is no.

  encoding_as_product_improvement: |
    Don't just "jam it in somewhere." Treat encoding as an opportunity to
    improve the product.

    The process:
    1. Break the knowledge down into discrete insights
    2. For each insight, determine how it would be disclosed within the project
    3. Evaluate whether that encoding improves the system

    Each encoded insight is a product increment that embodies a design principle.
    The encoding should make the system better, not just more documented.

    Usually the user is involved in this judgment. Over time, you may develop
    enough understanding of the project's design framework to perform this
    independently—but that judgment is earned through demonstrated alignment,
    not assumed.

  design_process_as_quality_gate: |
    The design process applies rigor that improves encoding quality.

    Working within the design framework (DISCLOSURE-ARCHITECTURE, DESIGN-LANGUAGE,
    existing patterns) creates natural review points. You're forced to consider:
    - Does this fit the existing structure, or fight it?
    - Is this solution elegant, or just complex?
    - Does the encoding serve discovery, or create noise?

    This rigor surfaces problems before they're encoded. A proposed encoding
    that doesn't fit cleanly often indicates the insight needs refinement,
    or points to structural improvements needed elsewhere.

    Design-first encoding means the framework reviews your work as you do it.

  encoding_as_translation: |
    When encoding is warranted, it's translation, not transcription.
    The same insight might become:
    - An anti-pattern in a criteria document
    - A new section in a skill's core expertise
    - A rule in system-prompt-rules.yaml
    - A checkpoint in a workflow
    - An advisory hook that fires on detection

    The design framework provides the target vocabulary. Your job is to
    recognize which form best serves discovery and application—or to
    recognize that no encoding improves the system.

  encoding_process:
    step_1_identify_insight:
      description: "What did we learn that should persist?"
      questions:
        - "What insight emerged from this conversation?"
        - "What mistake was corrected?"
        - "What pattern was discovered?"
        - "What would have saved time if known earlier?"
      examples:
        - "High co-invocation between layered skills is expected, not redundancy"
        - "Data informs but doesn't prescribe—metrics need context verification"
        - "Check for X before doing Y"

    step_2_identify_trigger:
      description: "What work context would trigger needing this?"
      questions:
        - "When would an agent need this insight?"
        - "What task or question would they be working on?"
        - "What keywords would they search for?"
      examples:
        - "Agent considering skill consolidation"
        - "Agent interpreting metrics data"
        - "Agent completing a task and deciding what to deliver"

    step_3_find_discovery_path:
      description: "What document would they naturally read in that context?"
      questions:
        - "If doing that work, what would they search for?"
        - "What document is in the natural path of that work?"
        - "What skill would they invoke?"
      method: |
        Search for documents related to the trigger context:
        - Grep for keywords in docs/, skills/
        - Check if there's an existing skill for that domain
        - Look at CLAUDE.md Quick Reference for entry points

    step_4_encode_appropriately:
      description: "Add the insight to that document"
      placement_by_type:
        anti_pattern: "Add to existing anti-patterns section or create one"
        best_practice: "Add to best practices or guidelines section"
        decision_criteria: "Add to decision framework or criteria section"
        definition: "Add to terminology or concepts section"
        process: "Add to workflow or process section"
      format: |
        Match the document's existing format. If adding an anti-pattern:
        - Use the same structure as existing anti-patterns
        - Include: what NOT to do, why, what to do instead
        - Add detection criteria if applicable

  entry_points:
    description: "Where information becomes available without prior navigation"
    types:
      claude_md:
        when: "Universal guidance every agent needs at session start"
        depth: 0
        examples: ["Operational rules", "Key frameworks", "Quick reference"]

      skills:
        when: "Domain-specific expertise invoked contextually"
        depth: 0 (from skill's perspective)
        examples: ["design-domain", "architectural-decision-making"]

      reference_docs:
        when: "Detailed guidance for specific work contexts"
        depth: 1-2 from CLAUDE.md
        examples: ["SKILL-CONSOLIDATION-CRITERIA.md", "DISCLOSURE-ARCHITECTURE.md"]

      searchable_orphans:
        when: "Specialist content discoverable by keyword search"
        depth: N/A (search-driven)
        examples: ["Historical analysis", "Implementation details"]

  placement_decision_tree: |
    Is this insight needed by EVERY agent at session start?
    ├─ YES → Consider CLAUDE.md (but keep it lean)
    └─ NO → Continue...

    Is there an existing skill for this domain?
    ├─ YES → Add to that skill or its references
    └─ NO → Continue...

    Is there a reference doc for this specific work context?
    ├─ YES → Add to that document
    └─ NO → Continue...

    Would an agent find this by searching keywords?
    ├─ YES → Create searchable orphan with clear keywords
    └─ NO → Consider creating new skill or reference doc

  worked_example:
    title: "Encoding the Skill Layering Anti-Pattern"
    insight: |
      "High co-invocation (94.7%) between git-vllm-read and pr-workflow
      doesn't indicate redundancy—they're intentionally layered (general
      framework + specific extension)."

    step_1_identify: |
      Insight: Layered skills co-invoke by design, not by accident.
      This is a false positive for the >80% consolidation rule.

    step_2_trigger: |
      When would an agent need this?
      → When analyzing skill co-invocation data
      → When considering consolidating skills
      → When interpreting the "80% rule" from CONTEXT-EFFICIENCY-THEORY

    step_3_discovery_path: |
      What would they read?
      → Search: "skill consolidation" "merge skills" "co-invocation"
      → Found: SKILL-CONSOLIDATION-CRITERIA.md
      → This document already has anti-patterns section

    step_4_encode: |
      Added Anti-Pattern 6: "Intentional Skill Layering"
      - What NOT to do: Merge skills with >80% co-invocation without checking
      - Why: One may intentionally extend the other
      - Detection: One skill explicitly references the other
      - Updated False Positive Indicators table

  common_mistakes:
    asking_instead_of_searching: |
      ❌ "Where should this insight live?"
      ✅ Search for documents related to the work context, then propose placement

    creating_new_when_exists: |
      ❌ Creating new document when insight fits existing structure
      ✅ Add to existing anti-patterns/best-practices/criteria sections

    encoding_too_broadly: |
      ❌ Adding to CLAUDE.md when only specialists need it
      ✅ Add to domain-specific skill or reference doc

    encoding_too_narrowly: |
      ❌ Creating searchable orphan when insight is essential
      ✅ Ensure insight is in the natural discovery path

best_practices:
  - "Search before creating—existing documents usually have the right home"
  - "Match the format of surrounding content"
  - "Include detection criteria when encoding anti-patterns"
  - "Add worked examples when encoding processes"
  - "Update cross-references if adding to multiple places"

cross_skill_references:
  design_domain: "For design vs implementation alignment decisions"
  architectural_decision_making: "For where capabilities should live"
  document_optimization: "For documentation structure decisions"

documentation_references:
  disclosure_architecture: "~/.claude/docs/reference/DISCLOSURE-ARCHITECTURE.md"
  orphaned_document_policy: "~/.claude/docs/reference/ORPHANED-DOCUMENT-POLICY.md"
  skill_consolidation_criteria: "~/.claude/docs/reference/SKILL-CONSOLIDATION-CRITERIA.md"

conditional_loading:
  - condition:
      name: disclosure_architecture_detail
      if_request_contains: [entry point, depth level, disclosure chain, progressive disclosure]
    then:
      load_references:
        - "~/.claude/docs/reference/DISCLOSURE-ARCHITECTURE.md"

  - condition:
      name: orphan_policy_detail
      if_request_contains: [orphan, searchable, archive, not referenced]
    then:
      load_references:
        - "~/.claude/docs/reference/ORPHANED-DOCUMENT-POLICY.md"
```

## Quick Reference: Encoding Checklist

**Before encoding:**
- [ ] Clearly articulate the insight in one sentence
- [ ] Identify what work context triggers needing it
- [ ] Search for existing documents in that context
- [ ] Verify no existing coverage of this insight

**During encoding:**
- [ ] Match the document's existing format
- [ ] Include "why" not just "what"
- [ ] Add detection criteria for anti-patterns
- [ ] Include worked example if process-oriented

**After encoding:**
- [ ] Verify the insight is discoverable via likely search terms
- [ ] Update cross-references if needed
- [ ] Consider if other documents need pointers

## The Meta-Insight

This skill itself is an example of knowledge encoding:

1. **Insight**: We repeatedly have conversations about "where should X live?" without a framework
2. **Trigger**: Agent discovers something that should persist, asks where to put it
3. **Discovery path**: Agent would search "encode" "persist" "where should" "future agents"
4. **Encoding**: Created this skill with the process documented

The conversation that created this skill won't repeat—the knowledge now persists.
