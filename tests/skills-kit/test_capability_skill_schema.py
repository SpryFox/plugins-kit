"""Schema validation tests for the capability_skill type (Dec-6).

A capability-skill wraps an external capability provider (tool / MCP server /
API / service / IDE / framework) with the project's setup and conventions.
Conceptually IS-A technique-skill: capabilities ARE techniques+, so the schema
extends the technique floor with stronger structural requirements -- an
external_capability declaration, a layering manifest (L1/L2/L3 content
allocation), and capability records carrying user_objective + operation.

Tests follow the minimal-floor + make_invalid mutator pattern established by
test_schemas.py: mutate one field at a time, confirm the schema catches each
class of drift.
"""

# schemas was extracted into skills_kit_lib (on sys.path via pyproject.toml pythonpath).
from skills_kit_lib.schemas.skill_types import CAPABILITY_SKILL_SCHEMA
from skills_kit_lib.schema_registry import (
    SCHEMAS_BY_ROOT,
    detect_mixed_type_yaml,
    resolve_schema,
)
from skills_kit_lib.schema_engine import validate


def _has_fail_at(fails, path_substring: str) -> bool:
    return any(path_substring in path for path, _ in fails)


def _has_fail_with_msg(fails, msg_substring: str) -> bool:
    return any(msg_substring in msg for _, msg in fails)


def _full_anti_pattern() -> dict:
    return {
        "id": "ap1",
        "name": "Reach for shortcut S",
        "keywords": ["shortcut s", "lookalike", "rationalization"],
        "why_it_seems_right": "S looks faster because it skips a check.",
        "why_it_is_wrong": "The check guarantees Z; skipping leads to Z-failure.",
        "alternative": "Use capability c1 instead; the cost difference is small.",
    }


# ---------------------------------------------------------------------------
# Minimum floor
# ---------------------------------------------------------------------------


class TestCapabilitySkillFloor:
    def test_minimal_floor_validates(self, minimal_capability_skill):
        fails, _ = validate(minimal_capability_skill, CAPABILITY_SKILL_SCHEMA)
        assert fails == [], f"unexpected fails: {fails}"

    def test_resolve_schema_picks_capability(self, minimal_capability_skill):
        root, schema = resolve_schema(minimal_capability_skill)
        assert root == "capability_skill"
        assert schema["root"] == "capability_skill"

    def test_capability_skill_registered(self):
        assert "capability_skill" in SCHEMAS_BY_ROOT
        assert SCHEMAS_BY_ROOT["capability_skill"]["root"] == "capability_skill"


# ---------------------------------------------------------------------------
# Required-key mutators
# ---------------------------------------------------------------------------


class TestCapabilitySkillRequiredKeys:
    def test_missing_external_capability_fails(self, minimal_capability_skill, make_invalid):
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].pop("external_capability"),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_at(fails, "external_capability")

    def test_external_capability_missing_kind_fails(self, minimal_capability_skill, make_invalid):
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"]["external_capability"].pop("kind"),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_at(fails, "external_capability.kind")

    def test_missing_layering_fails(self, minimal_capability_skill, make_invalid):
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].pop("layering"),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_at(fails, "layering")

    def test_layering_empty_skill_md_fails_min_len(self, minimal_capability_skill, make_invalid):
        """L2 must carry at least one allocated content item; L1/L3 may be empty."""
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"]["layering"].update({"skill_md": []}),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_with_msg(fails, "list length 0")

    def test_layering_empty_claude_md_permitted(self, minimal_capability_skill, make_invalid):
        """L1 (claude_md) may legitimately be empty -- not every capability-skill
        has ambient setup-for-success content."""
        good = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"]["layering"].update({"claude_md": []}),
        )
        fails, _ = validate(good, CAPABILITY_SKILL_SCHEMA)
        assert fails == [], f"empty claude_md should pass; got {fails}"

    def test_layering_empty_references_permitted(self, minimal_capability_skill, make_invalid):
        """L3 may legitimately be empty -- a flat capability-skill does not yet
        have deep-mechanics content in references/."""
        good = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"]["layering"].update({"references": []}),
        )
        fails, _ = validate(good, CAPABILITY_SKILL_SCHEMA)
        assert fails == [], f"empty references should pass; got {fails}"

    def test_capabilities_empty_fails(self, minimal_capability_skill, make_invalid):
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({"capabilities": []}),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_with_msg(fails, "list length 0")

    def test_capabilities_missing_fails(self, minimal_capability_skill, make_invalid):
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].pop("capabilities"),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_at(fails, "capabilities")

    def test_capability_missing_user_objective_fails(self, minimal_capability_skill, make_invalid):
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"]["capabilities"][0].pop("user_objective"),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_at(fails, "user_objective")

    def test_capability_missing_operation_fails(self, minimal_capability_skill, make_invalid):
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"]["capabilities"][0].pop("operation"),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_at(fails, "operation")

    def test_capability_missing_keywords_fails(self, minimal_capability_skill, make_invalid):
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"]["capabilities"][0].pop("keywords"),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_at(fails, "keywords")

    def test_capability_keywords_below_three_fails(self, minimal_capability_skill, make_invalid):
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"]["capabilities"][0].update(
                {"keywords": ["only", "two"]}
            ),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_at(fails, "keywords")

    def test_missing_top_level_gotchas_fails(self, minimal_capability_skill, make_invalid):
        """capability-skill-level gotchas (provider quirks, project failure modes)
        are required; per-capability gotchas are optional inside each record."""
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].pop("gotchas"),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_at(fails, "capability_skill.gotchas")

    def test_empty_top_level_gotchas_fails_min_len(self, minimal_capability_skill, make_invalid):
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({"gotchas": []}),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_with_msg(fails, "list length 0")


# ---------------------------------------------------------------------------
# Forbidden keys (mixed-type drift signals)
# ---------------------------------------------------------------------------


class TestCapabilitySkillForbiddenKeys:
    def test_forbidden_rules_fails(self, minimal_capability_skill, make_invalid):
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({"rules": []}),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_with_msg(fails, "forbidden key")

    def test_forbidden_techniques_fails(self, minimal_capability_skill, make_invalid):
        """techniques: is forbidden because capabilities: subsumes it."""
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({"techniques": []}),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_with_msg(fails, "forbidden key")

    def test_forbidden_index_fails(self, minimal_capability_skill, make_invalid):
        """index: is forbidden because members: + Conditional Loading is the
        canonical aggregation shape for capability-skills."""
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({"index": {}}),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_with_msg(fails, "forbidden key")

    def test_forbidden_facts_fails(self, minimal_capability_skill, make_invalid):
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({"facts": []}),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_with_msg(fails, "forbidden key")


# ---------------------------------------------------------------------------
# Optional features (must not break the floor when added)
# ---------------------------------------------------------------------------


class TestCapabilitySkillOptionalFeatures:
    def test_anti_patterns_present_validates(self, minimal_capability_skill, make_invalid):
        good = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({"anti_patterns": [_full_anti_pattern()]}),
        )
        fails, _ = validate(good, CAPABILITY_SKILL_SCHEMA)
        assert fails == [], f"anti_patterns should pass; got {fails}"

    def test_companion_present_validates(self, minimal_capability_skill, make_invalid):
        good = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({
                "companion": {
                    "skill": "../wrapper-sibling/SKILL.md",
                    "description": "wrapper sibling that drives this capability set",
                },
            }),
        )
        fails, _ = validate(good, CAPABILITY_SKILL_SCHEMA)
        assert fails == [], f"companion should pass; got {fails}"

    def test_members_present_validates(self, minimal_capability_skill, make_invalid):
        good = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({
                "members": [
                    {
                        "name": "sub-capability-1",
                        "type": "capability_skill",
                        "ref": "../sub-cap-1/SKILL.md",
                        "keywords": ["sub", "capability", "member"],
                    },
                ],
            }),
        )
        fails, _ = validate(good, CAPABILITY_SKILL_SCHEMA)
        assert fails == [], f"members should pass; got {fails}"

    def test_member_missing_keywords_fails(self, minimal_capability_skill, make_invalid):
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({
                "members": [
                    {
                        "name": "sub-capability-1",
                        "type": "capability_skill",
                        "ref": "../sub-cap-1/SKILL.md",
                    },
                ],
            }),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_at(fails, "members")
        assert _has_fail_at(fails, "keywords")

    def test_capability_with_sub_cases_validates(self, minimal_capability_skill, make_invalid):
        good = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"]["capabilities"][0].update({
                "sub_cases": ["case A: foo", "case B: bar"],
                "scope_axes": ["axis 1", "axis 2"],
                "reference_section": "references/x.md#operation-y",
            }),
        )
        fails, _ = validate(good, CAPABILITY_SKILL_SCHEMA)
        assert fails == [], f"optional capability metadata should pass; got {fails}"

    def test_capability_with_inline_steps_validates(self, minimal_capability_skill, make_invalid):
        good = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"]["capabilities"][0].update({
                "steps": [
                    {"n": 1, "action": "Run x do-y --target=foo.", "expected": "Y is done."},
                ],
                "gotchas": ["This capability fails when X is offline."],
            }),
        )
        fails, _ = validate(good, CAPABILITY_SKILL_SCHEMA)
        assert fails == [], f"inline steps + per-capability gotchas should pass; got {fails}"


# ---------------------------------------------------------------------------
# Mixed-type detection for the new root
# ---------------------------------------------------------------------------


class TestCapabilitySkillMixedType:
    def test_capability_alone_no_mixed_signal(self, minimal_capability_skill):
        roots = detect_mixed_type_yaml(minimal_capability_skill)
        assert roots == ["capability_skill"]

    def test_capability_plus_technique_signals_mixed(
        self, minimal_capability_skill, minimal_technique_skill
    ):
        merged = {**minimal_capability_skill, **minimal_technique_skill}
        roots = detect_mixed_type_yaml(merged)
        assert set(roots) == {"capability_skill", "technique_skill"}
        assert len(roots) > 1


# ---------------------------------------------------------------------------
# Sub-domain config (Dec-12, optional list field on capability-skill)
# ---------------------------------------------------------------------------


class TestCapabilitySkillSubdomainConfig:
    def test_subdomain_config_omitted_validates(self, minimal_capability_skill):
        """Field is optional; omitting it does not fail."""
        fails, _ = validate(minimal_capability_skill, CAPABILITY_SKILL_SCHEMA)
        assert fails == [], f"unexpected fails: {fails}"

    def test_subdomain_config_minimal_entry_validates(self, minimal_capability_skill, make_invalid):
        """A subdomain_config entry with only the required `name` field validates."""
        good = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({
                "subdomain_config": [{"name": "subdomain-A"}],
            }),
        )
        fails, _ = validate(good, CAPABILITY_SKILL_SCHEMA)
        assert fails == [], f"minimal subdomain_config entry should pass; got {fails}"

    def test_subdomain_config_full_entry_validates(self, minimal_capability_skill, make_invalid):
        """A subdomain_config entry with every optional field populated validates."""
        good = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({
                "subdomain_config": [{
                    "name": "subdomain-A",
                    "state_terms": ["enabled", "disabled", "pending"],
                    "operations": ["toggle", "validate", "reset"],
                    "scope_axes": [
                        {"name": "target", "values": ["single", "batch", "all"]},
                    ],
                    "canonical_phrasing": "I'll <operation> <target>. Confirm?",
                    "llm_dependent_content": ["validation_explanation"],
                    "dependency_order": ["validate before toggle"],
                }],
            }),
        )
        fails, _ = validate(good, CAPABILITY_SKILL_SCHEMA)
        assert fails == [], f"full subdomain_config entry should pass; got {fails}"

    def test_subdomain_config_multiple_subareas_validates(self, minimal_capability_skill, make_invalid):
        """A subdomain_config list with multiple sub-areas validates."""
        good = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({
                "subdomain_config": [
                    {"name": "subdomain-A", "state_terms": ["a", "b"]},
                    {"name": "subdomain-B", "operations": ["x", "y"]},
                    {"name": "subdomain-C"},
                ],
            }),
        )
        fails, _ = validate(good, CAPABILITY_SKILL_SCHEMA)
        assert fails == [], f"multi-sub-area config should pass; got {fails}"

    def test_subdomain_config_missing_name_fails(self, minimal_capability_skill, make_invalid):
        """A subdomain_config entry without `name` fails validation."""
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({
                "subdomain_config": [{"state_terms": ["enabled"]}],
            }),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_at(fails, "subdomain_config[0].name")
        assert _has_fail_with_msg(fails, "required key missing")

    def test_subdomain_config_state_terms_wrong_type_fails(self, minimal_capability_skill, make_invalid):
        """state_terms as a string (instead of list) fails validation."""
        bad = make_invalid(
            minimal_capability_skill,
            lambda d: d["capability_skill"].update({
                "subdomain_config": [{
                    "name": "subdomain-A",
                    "state_terms": "enabled disabled pending",
                }],
            }),
        )
        fails, _ = validate(bad, CAPABILITY_SKILL_SCHEMA)
        assert _has_fail_at(fails, "subdomain_config")
