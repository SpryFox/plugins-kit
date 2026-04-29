"""Schema definitions for the YAML skill-contract refactor.

Each canonical skill type carries a schema. Schemas are Python dicts using
a small rule vocabulary (no external schema language). The validator walks
the schema and emits per-row pass/fail verdicts.

Schemas are floors, not ceilings. The schema validates the required
minimum is present and well-formed; authors may add load-bearing
structured keys beyond what the schema enumerates (e.g. an `exceptions:`
list inside an anti-pattern entry, a `narration:` sub-block inside a
technique). Mixed-type drift is detected via the explicit
`forbidden_keys` list on each schema -- forbidden keys are deliberate
cross-type signals; unknown keys not in the forbidden list are
permitted. This biases authors toward adding structure rather than
falling back to unstructured prose.

Rule vocabulary:

- {"required": True}                       -- key must be present
- {"required": False}                      -- key is optional
- {"type": "string"}                       -- value must be a string
- {"type": "list"}                         -- value must be a list
- {"type": "dict"}                         -- value must be a dict
- {"min_len": N}                           -- a list field must have N or more items
- {"max_len": N}                           -- a list field must have N or fewer items
- {"forbid_regex": "<pat>", "msg": "..."}  -- string field must not match the regex
- {"items": <subschema>}                   -- each item in a list must match the subschema
- {"keys": {<key>: <rule_dict>, ...}}      -- dict field has these sub-keys

Each rule may also carry "note" with explanatory text shown in audit output.

The validator imports yaml (PyYAML) for parsing. If pyyaml is not available
the audit falls back to the legacy markdown-heuristic path.
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

IDENTITY_RULE = {"type": "string", "required": True, "note": "one-sentence identity for the skill"}


REFERENCE_SKILL_SCHEMA = {
    "root": "reference_skill",
    "keys": {
        "_schema_version": {"type": "string", "required": False},
        "identity": IDENTITY_RULE,
        "scope": SCOPE_RULE,
        "facts": {
            "type": "list",
            "required": True,
            "min_len": 1,
            "items": {
                "keys": {
                    "id": {"type": "string", "required": True},
                    "summary": {"type": "string", "required": True},
                    "keywords": KEYWORDS_RULE,
                    "detail": {"required": True},
                    "gotchas": {"type": "list", "required": False, "min_len": 1},
                    "example": {"type": "dict", "required": False, "keys": {
                        "input": {"type": "string", "required": True},
                        "output": {"type": "string", "required": True},
                    }},
                },
            },
        },
        "groupings": {"type": "list", "required": False, "items": {"keys": {
            "name": {"type": "string", "required": True},
            "keywords": KEYWORDS_RULE,
            "fact_ids": {"type": "list", "required": True, "min_len": 1},
        }}},
        "references": {"type": "list", "required": False, "items": {"keys": {
            "id": {"type": "string", "required": True},
            "path": {"type": "string", "required": True},
            "keywords": KEYWORDS_RULE,
            "summary": {"type": "string", "required": True},
        }}},
    },
    "facts_must_include_gotcha": True,
    "facts_must_include_example": True,
    "forbidden_keys": ["procedures", "steps", "rules", "counters", "patterns",
                       "apply_when", "do_not_apply_when", "members", "index"],
}


PATTERN_SKILL_SCHEMA = {
    "root": "pattern_skill",
    "keys": {
        "_schema_version": {"type": "string", "required": False},
        "identity": IDENTITY_RULE,
        "scope": SCOPE_RULE,
        "patterns": {
            "type": "list",
            "required": True,
            "min_len": 1,
            "items": {
                "keys": {
                    "id": {"type": "string", "required": True},
                    "name": {"type": "string", "required": True},
                    "keywords": KEYWORDS_RULE,
                    "problem": {"type": "string", "required": True},
                    "mechanic": {"type": "string", "required": True},
                    "why": {"type": "string", "required": True},
                    "apply_when": {"type": "list", "required": True, "min_len": 1, "items": {"keys": {
                        "signal": {"type": "string", "required": True},
                        "example": {"type": "string", "required": True},
                    }}},
                    "do_not_apply_when": {"type": "list", "required": True, "min_len": 1, "items": {"keys": {
                        "signal": {"type": "string", "required": True},
                        "counter_example": {"type": "string", "required": True},
                    }}},
                    "examples": {"type": "list", "required": True, "min_len": 1, "items": {"keys": {
                        "title": {"type": "string", "required": True},
                        "before": {"type": "string", "required": True},
                        "after": {"type": "string", "required": True},
                    }}},
                },
            },
        },
    },
    "forbidden_keys": ["procedures", "steps", "rules", "counters", "facts",
                       "tools", "scripts", "members", "index"],
}


_TECHNIQUE_STEP = {"keys": {
    "n": {"type": "int", "required": True},
    "action": {"type": "string", "required": True},
    "tool": {"type": "string", "required": False},
    "input": {"type": "string", "required": False},
    "expected": {"type": "string", "required": False},
    "on_failure": {"type": "string", "required": False},
}}

# Unified technique_skill schema. Every technique requires ordered steps
# (min_len 1). output_template is an optional companion field carrying the
# output-shape contract for the agent's reply -- not an alternative to
# steps. Trigger model (auto vs user-only) is metadata; it does not change
# what the body must contain. Even user-only slash-command skills reduce
# to a 1-step procedure ("invoke command; render output") and write that
# step explicitly.
TECHNIQUE_SKILL_SCHEMA = {
    "root": "technique_skill",
    "keys": {
        "_schema_version": {"type": "string", "required": False},
        "identity": IDENTITY_RULE,
        "scope": SCOPE_RULE,
        "trigger_model": {"type": "string", "required": False,
                          "note": "'auto' (default) or 'user-only'"},
        "techniques": {
            "type": "list",
            "required": True,
            "min_len": 1,
            "items": {
                "keys": {
                    "id": {"type": "string", "required": True},
                    "name": {"type": "string", "required": True},
                    "keywords": KEYWORDS_RULE,
                    "goal": {"type": "string", "required": True},
                    "preconditions": {"type": "list", "required": False},
                    "steps": {"type": "list", "required": True, "min_len": 1, "items": _TECHNIQUE_STEP,
                              "note": "ordered-step procedure body; required for every technique regardless of trigger_model"},
                    "output_template": {"type": "string", "required": False,
                                        "note": "optional output-shape contract for the agent's reply; companion to steps, not a substitute"},
                    "arguments": {"type": "list", "required": False, "items": {"keys": {
                        "name": {"type": "string", "required": True},
                        "required": {"type": "bool", "required": True},
                        "description": {"type": "string", "required": True},
                    }}},
                    "gotchas": {"type": "list", "required": True, "min_len": 1},
                    "validator": {"type": "dict", "required": False, "keys": {
                        "type": {"type": "string", "required": True},
                        "ref": {"type": "string", "required": False},
                    }},
                    "checklist": {"type": "list", "required": False},
                },
            },
        },
    },
    "forbidden_keys": ["rules", "counters", "facts", "patterns",
                       "apply_when", "do_not_apply_when", "members", "index"],
}

# Backwards-compat aliases (the old variant names still resolve)
TECHNIQUE_SKILL_SCHEMA_AUTO = TECHNIQUE_SKILL_SCHEMA
TECHNIQUE_SKILL_SCHEMA_USER_ONLY = TECHNIQUE_SKILL_SCHEMA


DISCIPLINE_SKILL_SCHEMA = {
    "root": "discipline_skill",
    "keys": {
        "_schema_version": {"type": "string", "required": False},
        "identity": IDENTITY_RULE,
        "scope": SCOPE_RULE,
        "target": {"type": "dict", "required": True, "keys": {
            "type": {"type": "string", "required": True},
            "ref": {"type": "string", "required": True},
        }},
        "rules": {
            "type": "list",
            "required": True,
            "min_len": 1,
            "items": {
                "keys": {
                    "id": {"type": "string", "required": True},
                    "keywords": KEYWORDS_RULE,
                    "statement": {"type": "string", "required": True,
                                  "forbid_regex": r"\b(should|might|try to|consider|usually|prefer)\b",
                                  "msg": "discipline rule statements must not hedge"},
                    "why": {"type": "string", "required": True,
                            "note": "explain-the-why on every rule"},
                    "counters": {"type": "list", "required": True, "min_len": 1, "items": {"keys": {
                        "excuse": {"type": "string", "required": True},
                        "reality": {"type": "string", "required": True},
                        "observed_in": {"type": "string", "required": True,
                                        "note": "every counter cites a baseline run; no hypotheticals"},
                    }}},
                    "red_flags": {"type": "list", "required": True, "min_len": 1},
                    "exceptions": {"type": "list", "required": False, "items": {"keys": {
                        "case": {"type": "string", "required": True},
                        "rationale": {"type": "string", "required": True,
                                      "note": "bounded exceptions require explicit rationale"},
                    }}},
                },
            },
        },
        "pressure_test": {"type": "dict", "required": True, "keys": {
            "baseline": {"type": "string", "required": True},
            "green": {"type": "string", "required": True},
            "refactor": {"type": "list", "required": True, "min_len": 1, "items": {"keys": {
                "loophole": {"type": "string", "required": True},
                "closed_by": {"type": "string", "required": True},
            }}},
        }},
    },
    "forbidden_keys": ["facts", "patterns", "apply_when", "do_not_apply_when",
                       "members", "index", "tools", "scripts"],
}


DOMAIN_SKILL_SCHEMA = {
    "root": "domain_skill",
    "keys": {
        "_schema_version": {"type": "string", "required": False},
        "identity": IDENTITY_RULE,
        "companions": {"type": "dict", "required": True, "keys": {
            "siblings": {"type": "list", "required": True},
            "note": {"type": "string", "required": False},
        }},
        "scope": SCOPE_RULE,
        "orientation": {"type": "dict", "required": True, "keys": {
            "summary": {"type": "string", "required": True},
            "vocabulary": {"type": "list", "required": False, "items": {"keys": {
                "term": {"type": "string", "required": True},
                "definition": {"type": "string", "required": True},
            }}},
            "behavioral_guardrails": {"type": "list", "required": False},
        }},
        "index": {"type": "dict", "required": True, "keys": {
            "references": {"type": "list", "required": True, "min_len": 1, "items": {"keys": {
                "id": {"type": "string", "required": True},
                "path": {"type": "string", "required": True},
                "keywords": KEYWORDS_RULE,
                "summary": {"type": "string", "required": True},
            }}},
            "members": {"type": "list", "required": False, "items": {"keys": {
                "name": {"type": "string", "required": True},
                "type": {"type": "string", "required": True},
                "ref": {"type": "string", "required": True},
                "keywords": KEYWORDS_RULE,
            }}},
        }},
        "capabilities": {"type": "list", "required": False, "items": {"keys": {
            "id": {"type": "string", "required": True},
            "keywords": KEYWORDS_RULE,
            "description": {"type": "string", "required": True},
            "operation": {"type": "string", "required": True},
            "tool": {"type": "string", "required": False},
            "scope_axes": {"type": "list", "required": False},
            "reference_section": {"type": "string", "required": False},
        }}},
        "tools": {"type": "list", "required": False, "items": {"keys": {
            "name": {"type": "string", "required": True},
            "command": {"type": "string", "required": True},
            "description": {"type": "string", "required": True},
        }}},
        "agent_binding": {"type": "dict", "required": False, "keys": {
            "agent_name": {"type": "string", "required": True},
            "auto_load": {"type": "bool", "required": True},
        }},
    },
    "forbidden_keys": ["rules", "counters", "facts", "patterns",
                       "apply_when", "do_not_apply_when", "steps_at_root"],
    "max_orientation_summary_words": 300,
}


CLAUDE_MD_SCHEMA = {
    "root": "claude_md",
    "keys": {
        "_schema_version": {"type": "string", "required": False},
        "scope": {"type": "dict", "required": True, "keys": {
            "directory": {"type": "string", "required": True},
            "covers": {"type": "list", "required": True, "min_len": 1},
            "excludes": {"type": "list", "required": False},
        }},
        "insights": {"type": "list", "required": True, "min_len": 1, "items": {"keys": {
            "id": {"type": "string", "required": True},
            "keywords": KEYWORDS_RULE,
            "summary": {"type": "string", "required": True},
            "detail": {"required": True},
            "origin": {"type": "string", "required": True},
            "added": {"type": "string", "required": True},
            "stale_when": {"type": "string", "required": False},
        }}},
        "conventions": {"type": "list", "required": False, "items": {"keys": {
            "rule": {"type": "string", "required": True},
            "keywords": KEYWORDS_RULE,
            "why": {"type": "string", "required": True},
        }}},
        "glossary": {"type": "list", "required": False, "items": {"keys": {
            "term": {"type": "string", "required": True},
            "definition": {"type": "string", "required": True},
        }}},
    },
}


SCHEMAS_BY_ROOT = {
    "reference_skill": REFERENCE_SKILL_SCHEMA,
    "pattern_skill": PATTERN_SKILL_SCHEMA,
    "discipline_skill": DISCIPLINE_SKILL_SCHEMA,
    "domain_skill": DOMAIN_SKILL_SCHEMA,
    "claude_md": CLAUDE_MD_SCHEMA,
    # technique_skill is dispatched by trigger_model; see resolve_technique_schema.
}


def resolve_technique_schema(yaml_data: dict) -> dict:
    """technique_skill has two variants by trigger_model."""
    block = yaml_data.get("technique_skill", {})
    if isinstance(block, dict) and block.get("trigger_model") == "user-only":
        return TECHNIQUE_SKILL_SCHEMA_USER_ONLY
    return TECHNIQUE_SKILL_SCHEMA_AUTO


def resolve_schema(yaml_data: dict) -> tuple[str, dict] | tuple[None, None]:
    """Return (root_key, schema) for the YAML data, or (None, None) if no recognized root."""
    if not isinstance(yaml_data, dict):
        return None, None
    if "technique_skill" in yaml_data:
        return "technique_skill", resolve_technique_schema(yaml_data)
    for root, schema in SCHEMAS_BY_ROOT.items():
        if root in yaml_data:
            return root, schema
    return None, None


def detect_mixed_type_yaml(yaml_data: dict) -> list[str]:
    """Return a list of canonical-type root keys present in the YAML data.

    More than one means mixed-type (deterministic detection).
    """
    if not isinstance(yaml_data, dict):
        return []
    canonical_roots = ["reference_skill", "pattern_skill", "technique_skill",
                       "discipline_skill", "domain_skill"]
    return [root for root in canonical_roots if root in yaml_data]


# ---------------------------------------------------------------------------
# Schema walker
# ---------------------------------------------------------------------------

import re as _re


def _typecheck(value, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "list":
        return isinstance(value, list)
    if expected_type == "dict":
        return isinstance(value, dict)
    if expected_type == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "bool":
        return isinstance(value, bool)
    return True


def _validate_value(value, rule: dict, path: str, fails: list, ok_paths: list):
    """Walk a single value against a rule. Append failure descriptors to fails;
    record successfully-checked paths in ok_paths.
    """
    expected_type = rule.get("type")
    if expected_type and not _typecheck(value, expected_type):
        fails.append((path, f"expected {expected_type}, got {type(value).__name__}"))
        return

    min_len = rule.get("min_len")
    if min_len is not None and isinstance(value, list) and len(value) < min_len:
        fails.append((path, f"list length {len(value)} < required {min_len}"))

    max_len = rule.get("max_len")
    if max_len is not None and isinstance(value, list) and len(value) > max_len:
        fails.append((path, f"list length {len(value)} > permitted {max_len}"))

    forbid = rule.get("forbid_regex")
    if forbid and isinstance(value, str):
        m = _re.search(forbid, value, _re.IGNORECASE)
        if m:
            msg = rule.get("msg", "matched forbidden pattern")
            fails.append((path, f"{msg} (matched '{m.group(0)}')"))

    items_rule = rule.get("items")
    if items_rule and isinstance(value, list):
        for i, item in enumerate(value):
            sub_path = f"{path}[{i}]"
            keys_rule = items_rule.get("keys", {})
            if not isinstance(item, dict):
                fails.append((sub_path, f"expected dict in list item, got {type(item).__name__}"))
                continue
            for sub_key, sub_rule in keys_rule.items():
                sub_sub_path = f"{sub_path}.{sub_key}"
                present = sub_key in item
                if sub_rule.get("required") and not present:
                    fails.append((sub_sub_path, "required key missing"))
                elif present:
                    _validate_value(item[sub_key], sub_rule, sub_sub_path, fails, ok_paths)

    keys_rule = rule.get("keys")
    if keys_rule and isinstance(value, dict):
        for sub_key, sub_rule in keys_rule.items():
            sub_path = f"{path}.{sub_key}"
            present = sub_key in value
            if sub_rule.get("required") and not present:
                fails.append((sub_path, "required key missing"))
            elif present:
                _validate_value(value[sub_key], sub_rule, sub_path, fails, ok_paths)

    ok_paths.append(path)


def validate(yaml_data: dict, schema: dict) -> tuple[list, list]:
    """Validate yaml_data against a per-type schema.

    Returns (fails, checked) where:
    - fails: list of (path, message) tuples for each failure
    - checked: list of paths that were checked without failure (informational)
    """
    fails: list = []
    checked: list = []

    root = schema["root"]
    block = yaml_data.get(root)
    if block is None:
        fails.append((root, "root key missing"))
        return fails, checked
    if not isinstance(block, dict):
        fails.append((root, f"root must be a dict, got {type(block).__name__}"))
        return fails, checked

    schema_keys = schema.get("keys", {})
    for key, rule in schema_keys.items():
        path = f"{root}.{key}"
        present = key in block
        if rule.get("required") and not present:
            fails.append((path, "required key missing"))
        elif present:
            _validate_value(block[key], rule, path, fails, checked)

    forbidden = schema.get("forbidden_keys", [])
    for f_key in forbidden:
        if f_key in block:
            fails.append((f"{root}.{f_key}", "forbidden key (mixed-type drift signal)"))

    if schema.get("facts_must_include_gotcha"):
        facts = block.get("facts", [])
        if isinstance(facts, list) and not any(
            isinstance(f, dict) and f.get("gotchas") for f in facts
        ):
            fails.append((f"{root}.facts[*].gotchas", "at least one fact must carry gotchas"))

    if schema.get("facts_must_include_example"):
        facts = block.get("facts", [])
        if isinstance(facts, list) and not any(
            isinstance(f, dict) and f.get("example") for f in facts
        ):
            fails.append((f"{root}.facts[*].example", "at least one fact must carry example"))

    return fails, checked
