"""Tests for skills_kit_lib/corpus.py SKILL.md parsing -- focused on the graceful
pyyaml-absent degradation (the "contract-staged" behavior).

corpus.parse_skill_md must never crash when pyyaml is unavailable: it degrades
to empty frontmatter and a None body contract instead of raising
ModuleNotFoundError. This is the behavior the bootstrap-dependency work hardened
(corpus.py previously did an unguarded `import yaml`).
"""

import pytest

from skills_kit_lib import corpus


def _write_skill(tmp_path, *, frontmatter=True, fence=True):
    parts = []
    if frontmatter:
        parts.append("---\nname: x\nskill-type: technique-skill\n---\n")
    parts.append("# Title\n\nbody text\n")
    if fence:
        parts.append('```yaml\ntechnique_skill:\n  _schema_version: "1"\n```\n')
    d = tmp_path / "x"
    d.mkdir()
    p = d / "SKILL.md"
    p.write_text("".join(parts), encoding="utf-8")
    return p


class TestParseSkillMd:
    def test_parses_frontmatter_and_contract_with_yaml(self, tmp_path):
        if not corpus.HAVE_YAML:
            pytest.skip("pyyaml not installed in this env")
        rec = corpus.parse_skill_md(_write_skill(tmp_path))
        assert rec is not None
        assert rec.frontmatter.get("name") == "x"
        assert rec.body_contract is not None
        assert "technique_skill" in rec.body_contract

    def test_degrades_without_yaml(self, tmp_path, monkeypatch):
        # The new guard: with pyyaml unavailable, parsing must not raise.
        monkeypatch.setattr(corpus, "HAVE_YAML", False)
        rec = corpus.parse_skill_md(_write_skill(tmp_path))
        assert rec is not None
        assert rec.skill_name == "x"
        assert rec.frontmatter == {}      # degraded: no frontmatter parse
        assert rec.body_contract is None  # degraded: no contract parse

    def test_no_module_level_yaml_use_when_absent(self, tmp_path, monkeypatch):
        # Even a malformed-yaml frontmatter must not crash when degraded.
        monkeypatch.setattr(corpus, "HAVE_YAML", False)
        d = tmp_path / "y"
        d.mkdir()
        p = d / "SKILL.md"
        p.write_text("---\n: : not valid : yaml :\n---\n# T\n", encoding="utf-8")
        rec = corpus.parse_skill_md(p)  # must not raise
        assert rec is not None and rec.frontmatter == {}

    def test_read_failure_returns_none(self, tmp_path):
        rec = corpus.parse_skill_md(tmp_path / "missing" / "SKILL.md")
        assert rec is None
