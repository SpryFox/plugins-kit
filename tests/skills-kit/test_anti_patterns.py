"""Tests for the P4 anti_patterns: optional first-class field.

anti_patterns: is OPTIONAL on technique_skill and discipline_skill (and absent
from the other schemas). When present, every entry must carry the five-key
record shape (id / name / keywords / why_it_seems_right / why_it_is_wrong /
alternative). The structured shape is what makes the field useful at audit
time -- a list of bullets without rationalization counters cannot survive
pressure testing.
"""

# schemas was extracted into skills_kit_lib (on sys.path via pyproject.toml pythonpath).
from skills_kit_lib.schemas.skill_types import (
    TECHNIQUE_SKILL_SCHEMA,
    DISCIPLINE_SKILL_SCHEMA,
    REFERENCE_SKILL_SCHEMA,
)
from skills_kit_lib.schema_engine import validate


def _full_anti_pattern() -> dict:
    return {
        "id": "ap1",
        "name": "Reach for shortcut S",
        "keywords": ["shortcut s", "lookalike", "rationalization"],
        "why_it_seems_right": "S looks faster because it skips step 2.",
        "why_it_is_wrong": "Step 2 is what guarantees Z; skipping leads to Z-failure downstream.",
        "alternative": "Use technique T (see techniques[0]); the cost difference is small.",
    }


def _has_fail_at(fails, path_substring: str) -> bool:
    return any(path_substring in path for path, _ in fails)


class TestAntiPatternsOnTechnique:
    def test_present_well_formed_validates(self, minimal_technique_skill, make_invalid):
        good = make_invalid(
            minimal_technique_skill,
            lambda d: d["technique_skill"].update({"anti_patterns": [_full_anti_pattern()]}),
        )
        fails, _ = validate(good, TECHNIQUE_SKILL_SCHEMA)
        assert fails == [], f"valid anti_patterns rejected: {fails}"

    def test_absent_validates(self, minimal_technique_skill):
        """anti_patterns: is OPTIONAL -- absence is the default and must validate."""
        fails, _ = validate(minimal_technique_skill, TECHNIQUE_SKILL_SCHEMA)
        assert fails == []

    def test_missing_why_it_seems_right_fails(self, minimal_technique_skill, make_invalid):
        ap = _full_anti_pattern()
        ap.pop("why_it_seems_right")
        bad = make_invalid(
            minimal_technique_skill,
            lambda d: d["technique_skill"].update({"anti_patterns": [ap]}),
        )
        fails, _ = validate(bad, TECHNIQUE_SKILL_SCHEMA)
        assert _has_fail_at(fails, "why_it_seems_right")

    def test_missing_why_it_is_wrong_fails(self, minimal_technique_skill, make_invalid):
        ap = _full_anti_pattern()
        ap.pop("why_it_is_wrong")
        bad = make_invalid(
            minimal_technique_skill,
            lambda d: d["technique_skill"].update({"anti_patterns": [ap]}),
        )
        fails, _ = validate(bad, TECHNIQUE_SKILL_SCHEMA)
        assert _has_fail_at(fails, "why_it_is_wrong")

    def test_missing_alternative_fails(self, minimal_technique_skill, make_invalid):
        ap = _full_anti_pattern()
        ap.pop("alternative")
        bad = make_invalid(
            minimal_technique_skill,
            lambda d: d["technique_skill"].update({"anti_patterns": [ap]}),
        )
        fails, _ = validate(bad, TECHNIQUE_SKILL_SCHEMA)
        assert _has_fail_at(fails, "alternative")

    def test_missing_id_fails(self, minimal_technique_skill, make_invalid):
        ap = _full_anti_pattern()
        ap.pop("id")
        bad = make_invalid(
            minimal_technique_skill,
            lambda d: d["technique_skill"].update({"anti_patterns": [ap]}),
        )
        fails, _ = validate(bad, TECHNIQUE_SKILL_SCHEMA)
        assert _has_fail_at(fails, "id")

    def test_keywords_below_three_fails(self, minimal_technique_skill, make_invalid):
        ap = _full_anti_pattern()
        ap["keywords"] = ["only", "two"]
        bad = make_invalid(
            minimal_technique_skill,
            lambda d: d["technique_skill"].update({"anti_patterns": [ap]}),
        )
        fails, _ = validate(bad, TECHNIQUE_SKILL_SCHEMA)
        assert _has_fail_at(fails, "keywords")


class TestAntiPatternsOnDiscipline:
    def test_present_well_formed_validates(self, minimal_discipline_skill, make_invalid):
        good = make_invalid(
            minimal_discipline_skill,
            lambda d: d["discipline_skill"].update({"anti_patterns": [_full_anti_pattern()]}),
        )
        fails, _ = validate(good, DISCIPLINE_SKILL_SCHEMA)
        assert fails == [], f"valid anti_patterns rejected: {fails}"

    def test_absent_validates(self, minimal_discipline_skill):
        fails, _ = validate(minimal_discipline_skill, DISCIPLINE_SKILL_SCHEMA)
        assert fails == []

    def test_malformed_entry_fails(self, minimal_discipline_skill, make_invalid):
        bad = make_invalid(
            minimal_discipline_skill,
            lambda d: d["discipline_skill"].update(
                {"anti_patterns": [{"id": "ap1", "name": "P"}]}
            ),
        )
        fails, _ = validate(bad, DISCIPLINE_SKILL_SCHEMA)
        # Several required keys missing on the entry; the schema should report
        # at least one specific path.
        assert any("anti_patterns" in path for path, _ in fails)


class TestAntiPatternsExtrasOnOtherTypes:
    """Per Dec-3 (schemas-as-floors), anti_patterns: as an unknown key on
    schemas that don't declare it must NOT fail -- it's a load-bearing extra,
    not a forbidden key. Authors who want anti-pattern entries on a
    reference_skill or pattern_skill or domain_skill simply add them; the
    typed shape is enforced only on the schemas that declare anti_patterns:
    in their keys block.
    """

    def test_reference_skill_extras_allowed(self, minimal_reference_skill, make_invalid):
        bad = make_invalid(
            minimal_reference_skill,
            lambda d: d["reference_skill"].update(
                {"anti_patterns": [{"name": "freeform"}]}
            ),
        )
        fails, _ = validate(bad, REFERENCE_SKILL_SCHEMA)
        assert fails == [], f"extras on non-declaring schema should pass; got: {fails}"
