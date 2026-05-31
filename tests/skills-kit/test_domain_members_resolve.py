"""Tests for checks.check_domain_members_resolve.

A domain-skill (index.members[]) or capability-skill (members[]) may declare
members whose `ref:`/`name:` no longer points at a skill on disk -- a reorg that
re-wires members can leave a dangling pointer. This check resolves every member
against the on-disk skill-name pool. These tests build tmp skill trees with the
flat `plugins/<plugin>/skills/<skill>/SKILL.md` layout the check globs.
"""

import pytest

from skills_kit_lib import checks


def _write_skill(root, plugin, skill, body_yaml=None, name=None):
    """Create plugins/<plugin>/skills/<skill>/SKILL.md with optional body YAML."""
    d = root / "plugins" / plugin / "skills" / skill
    d.mkdir(parents=True, exist_ok=True)
    fm_name = name if name is not None else skill
    parts = [
        "---",
        f"name: {fm_name}",
        "description: Use when testing. Do NOT use otherwise.",
        "---",
        "",
        "# Test skill",
        "",
    ]
    if body_yaml is not None:
        parts += ["```yaml", body_yaml.rstrip("\n"), "```", ""]
    (d / "SKILL.md").write_text("\n".join(parts), encoding="utf-8")
    return d


def _domain_body(members):
    lines = ["domain_skill:", "  identity: A test domain.",
             "  scope:", "    covers: [x]", "    excludes: [y]",
             "  index:", "    members:"]
    for nm, ref in members:
        lines += [f"      - name: {nm}", "        type: audit-skill",
                  f"        ref: {ref}", "        keywords: [a, b, c]"]
    return "\n".join(lines)


def _capability_body(members):
    lines = ["capability_skill:", "  identity: A test capability."]
    lines += ["  members:"]
    for nm, ref in members:
        lines += [f"    - name: {nm}", "      type: capability-skill",
                  f"      ref: {ref}", "      keywords: [a, b, c]"]
    return "\n".join(lines)


def _result_for(results, domain):
    matches = [r for r in results if r.domain == domain]
    assert matches, f"no result for domain '{domain}'"
    return matches[0]


class TestDomainMemberResolution:
    def test_resolving_member_passes(self, tmp_path):
        _write_skill(tmp_path, "p", "skill-audit")
        _write_skill(tmp_path, "p", "md-audit",
                     body_yaml=_domain_body([("skill-audit", "/skill-audit")]))
        results = checks.check_domain_members_resolve(tmp_path)
        r = _result_for(results, "md-audit")
        assert r.status == "pass", r.message
        assert r.unresolved == []

    def test_dangling_member_unresolved(self, tmp_path):
        _write_skill(tmp_path, "p", "md-audit",
                     body_yaml=_domain_body([("ghost", "/ghost")]))
        results = checks.check_domain_members_resolve(tmp_path)
        r = _result_for(results, "md-audit")
        assert r.status == "unresolved"
        assert any(name == "ghost" for name, _ref in r.unresolved)

    def test_mixed_members_report_only_the_dangling_one(self, tmp_path):
        _write_skill(tmp_path, "p", "skill-audit")
        _write_skill(tmp_path, "p", "md-audit",
                     body_yaml=_domain_body([
                         ("skill-audit", "/skill-audit"),
                         ("ghost", "/ghost"),
                     ]))
        results = checks.check_domain_members_resolve(tmp_path)
        r = _result_for(results, "md-audit")
        assert r.status == "unresolved"
        unresolved_names = {name for name, _ in r.unresolved}
        assert unresolved_names == {"ghost"}

    def test_bare_ref_resolves(self, tmp_path):
        """A member ref without a leading slash still resolves."""
        _write_skill(tmp_path, "ue", "ue-python-api")
        _write_skill(tmp_path, "ue", "unreal-domain",
                     body_yaml=_capability_body([("ue-python-api", "ue-python-api")]))
        results = checks.check_domain_members_resolve(tmp_path)
        r = _result_for(results, "unreal-domain")
        assert r.status == "pass", r.message

    def test_plugin_qualified_ref_resolves(self, tmp_path):
        """A `plugin:skill` qualified ref normalizes to the bare name and resolves."""
        _write_skill(tmp_path, "p", "references-audit")
        _write_skill(tmp_path, "p", "md-audit",
                     body_yaml=_domain_body([("references-audit", "skills-kit:references-audit")]))
        results = checks.check_domain_members_resolve(tmp_path)
        r = _result_for(results, "md-audit")
        assert r.status == "pass", r.message

    def test_frontmatter_name_pool_resolves(self, tmp_path):
        """Resolution uses the frontmatter name, not only the directory name."""
        # Skill lives in dir 'dir-name' but declares name 'real-name'.
        _write_skill(tmp_path, "p", "dir-name", name="real-name")
        _write_skill(tmp_path, "p", "md-audit",
                     body_yaml=_domain_body([("real-name", "/real-name")]))
        results = checks.check_domain_members_resolve(tmp_path)
        r = _result_for(results, "md-audit")
        assert r.status == "pass", r.message

    def test_non_member_skill_is_silent(self, tmp_path):
        """A skill that declares no members produces no result row."""
        _write_skill(tmp_path, "p", "plain-skill")
        results = checks.check_domain_members_resolve(tmp_path)
        assert all(r.domain != "plain-skill" for r in results)

    def test_real_corpus_has_no_unresolved_members(self):
        """Integration: every domain/capability member in the live repo resolves."""
        results = checks.check_domain_members_resolve()
        unresolved = [r for r in results if r.status == "unresolved"]
        assert not unresolved, checks.render_member_results(results)
