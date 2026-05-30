"""Shared schema-rule fragments.

Composable building blocks for the schemas/ modules. A fragment is a rule
dict that schemas reuse to avoid re-stating common shapes (a keywords list,
a covers/excludes scope, a fact item, an anti-pattern record).
"""


KEYWORDS_RULE = {
    "type": "list",
    "min_len": 3,
    "required": True,
    "note": "every load-bearing record carries a keywords cluster (>=3) for chat-term routing",
}


SCOPE_RULE = {
    "type": "dict",
    "required": True,
    "keys": {
        "covers": {"type": "list", "min_len": 1, "required": True},
        "excludes": {"type": "list", "min_len": 1, "required": True,
                     "note": "exclusion clause materialized in YAML"},
    },
}


IDENTITY_RULE = {
    "type": "string",
    "required": True,
    "note": "one-sentence identity for the skill",
}


# Shared fact-item shape -- referenced by REFERENCE_SKILL_SCHEMA.facts.items
# (when facts live nested inside the skill-type contract) and by FACTS_SCHEMA.items
# (when facts live as their own top-level portable unit). Cross-cutting rules
# ("at least one fact carries gotchas", "at least one fact carries example") are
# enforced at audit-time across the union of all fact sources in a document.
FACT_ITEM_RULE = {"keys": {
    "id": {"type": "string", "required": True},
    "category": {"type": "string", "required": False,
                 "note": "optional cluster label grouping related facts; flat list of facts ordered by category aids human reading without requiring a separate groupings: block"},
    "summary": {"type": "string", "required": True},
    "keywords": KEYWORDS_RULE,
    "detail": {"required": True},
    "gotchas": {"type": "list", "required": False, "min_len": 1},
    "example": {"type": "dict", "required": False, "keys": {
        "input": {"type": "string", "required": True},
        "output": {"type": "string", "required": True},
    }},
}}


# anti_patterns is an optional first-class field on technique-skill and
# discipline-skill -- skills that prescribe a procedure or enforce a rule
# benefit from naming the lookalike-but-wrong moves a future agent might
# reach for. The structured shape implicitly asserts every item is a
# genuine anti-pattern (a markdown bullet list carries no such assertion).
ANTI_PATTERNS_RULE = {
    "type": "list",
    "required": False,
    "items": {"keys": {
        "id": {"type": "string", "required": True},
        "name": {"type": "string", "required": True},
        "keywords": KEYWORDS_RULE,
        "why_it_seems_right": {"type": "string", "required": True,
                               "note": "the lookalike rationalization an agent would reach for"},
        "why_it_is_wrong": {"type": "string", "required": True,
                            "note": "the failure mode this anti-pattern produces"},
        "alternative": {"type": "string", "required": True,
                        "note": "what to do instead -- typically a pointer to a technique or rule in the same skill"},
    }},
    "note": "named anti-patterns the skill discourages; the structured record shape asserts every entry is a real anti-pattern",
}


# Shared technique-step shape -- referenced by technique-skill / capability-skill /
# audit-skill schemas wherever an ordered-step procedure body appears.
TECHNIQUE_STEP_RULE = {"keys": {
    "n": {"type": "int", "required": True},
    "action": {"type": "string", "required": True},
    "tool": {"type": "string", "required": False},
    "input": {"type": "string", "required": False},
    "expected": {"type": "string", "required": False},
    "on_failure": {"type": "string", "required": False},
}}
