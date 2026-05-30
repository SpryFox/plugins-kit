"""Tests for claude-md-audit/scripts/discover.py role classification.

Focus: the cwd CLAUDE.md is `root` only when no CLAUDE.md ancestor exists above
it. An ancestor CLAUDE.md demotes the launch-dir file to `child` so the
project-root-only hygiene checks (H1/H2/H3) do not fire on a subordinate file
and the parent-child duplication check runs against the ancestor. A personal
CLAUDE.local.md ancestor is not a project-root marker and does NOT demote it.
"""

from pathlib import Path

import discover


def _write(path: Path, text: str = "# CLAUDE.md\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _role_of(results, path: Path) -> str:
    for p, role in results:
        if p == path:
            return role
    raise AssertionError(f"{path} not found in discover() results: {results}")


class TestCwdRootClassification:
    def test_cwd_claude_md_is_root_when_no_ancestor(self, tmp_path):
        proj = tmp_path / "proj"
        cwd_md = proj / "CLAUDE.md"
        _write(cwd_md)
        results = discover.discover(proj)
        assert _role_of(results, cwd_md) == "root"

    def test_cwd_claude_md_is_child_when_ancestor_exists(self, tmp_path):
        _write(tmp_path / "CLAUDE.md")  # the real project root
        sub = tmp_path / "services" / "payments"
        cwd_md = sub / "CLAUDE.md"
        _write(cwd_md)
        results = discover.discover(sub)
        assert _role_of(results, cwd_md) == "child"

    def test_ancestor_claude_md_is_classified_ancestor(self, tmp_path):
        anc_md = tmp_path / "CLAUDE.md"
        _write(anc_md)
        sub = tmp_path / "services"
        _write(sub / "CLAUDE.md")
        results = discover.discover(sub)
        assert _role_of(results, anc_md) == "ancestor"

    def test_local_md_ancestor_does_not_demote_cwd(self, tmp_path):
        # A personal CLAUDE.local.md above cwd is not a project-root marker.
        _write(tmp_path / "CLAUDE.local.md")
        sub = tmp_path / "work"
        cwd_md = sub / "CLAUDE.md"
        _write(cwd_md)
        results = discover.discover(sub)
        assert _role_of(results, cwd_md) == "root"


class TestCollectAtCwd:
    def test_default_flag_is_root(self, tmp_path):
        # Backward-compatible default: no flag -> root.
        _write(tmp_path / "CLAUDE.md")
        out = discover.collect_at_cwd(tmp_path)
        assert "root" in [role for _, role in out]

    def test_flag_true_yields_child_not_root(self, tmp_path):
        _write(tmp_path / "CLAUDE.md")
        out = discover.collect_at_cwd(tmp_path, has_ancestor_root=True)
        roles = [role for _, role in out]
        assert "child" in roles and "root" not in roles

    def test_local_at_cwd_unaffected_by_flag(self, tmp_path):
        # CLAUDE.local.md at cwd stays `local` regardless of the ancestor flag.
        _write(tmp_path / "CLAUDE.local.md")
        out = discover.collect_at_cwd(tmp_path, has_ancestor_root=True)
        assert "local" in [role for _, role in out]
