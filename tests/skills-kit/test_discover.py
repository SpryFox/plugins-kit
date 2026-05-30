"""Tests for claude-md-audit/scripts/discover.py role classification.

Two behaviours under test:

1. Root anchoring: the cwd CLAUDE.md is `root` only when no CLAUDE.md ancestor
   exists above it (within the project). An ancestor demotes it to `child` so
   the project-root-only hygiene checks (H1/H2/H3) do not false-positive on a
   subordinate file. A personal CLAUDE.local.md ancestor is not a project-root
   marker and does NOT demote it.

2. Project boundary: the upward walk stops at the project root (nearest .git
   ancestor) and never looks outside it. A CLAUDE.md above the project root is
   ignored, so it cannot demote the project root or be reported as an ancestor.

Each multi-level test plants a .git marker at the intended project root so the
boundary is deterministic regardless of the real filesystem above tmp_path.
"""

from pathlib import Path

import discover


def _write(path: Path, text: str = "# CLAUDE.md\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _mkgit(directory: Path) -> None:
    (directory / ".git").mkdir(parents=True, exist_ok=True)


def _role_of(results, path: Path) -> str:
    for p, role in results:
        if p == path:
            return role
    raise AssertionError(f"{path} not found in discover() results: {results}")


def _paths(results) -> set:
    return {p for p, _ in results}


class TestCwdRootClassification:
    def test_cwd_claude_md_is_root_when_no_ancestor(self, tmp_path):
        proj = tmp_path / "proj"
        _mkgit(proj)
        cwd_md = proj / "CLAUDE.md"
        _write(cwd_md)
        results = discover.discover(proj)
        assert _role_of(results, cwd_md) == "root"

    def test_cwd_claude_md_is_child_when_ancestor_exists(self, tmp_path):
        _mkgit(tmp_path)  # project root
        _write(tmp_path / "CLAUDE.md")
        sub = tmp_path / "services" / "payments"
        cwd_md = sub / "CLAUDE.md"
        _write(cwd_md)
        results = discover.discover(sub)
        assert _role_of(results, cwd_md) == "child"

    def test_ancestor_claude_md_is_classified_ancestor(self, tmp_path):
        _mkgit(tmp_path)  # project root
        anc_md = tmp_path / "CLAUDE.md"
        _write(anc_md)
        sub = tmp_path / "services"
        _write(sub / "CLAUDE.md")
        results = discover.discover(sub)
        assert _role_of(results, anc_md) == "ancestor"

    def test_local_md_ancestor_does_not_demote_cwd(self, tmp_path):
        # A personal CLAUDE.local.md above cwd is not a project-root marker.
        _mkgit(tmp_path)  # project root
        _write(tmp_path / "CLAUDE.local.md")
        sub = tmp_path / "work"
        cwd_md = sub / "CLAUDE.md"
        _write(cwd_md)
        results = discover.discover(sub)
        assert _role_of(results, cwd_md) == "root"


class TestProjectBoundary:
    def test_find_project_root_returns_nearest_git_dir(self, tmp_path):
        _mkgit(tmp_path / "proj")
        deep = tmp_path / "proj" / "a" / "b"
        deep.mkdir(parents=True, exist_ok=True)
        assert discover.find_project_root(deep) == tmp_path / "proj"

    def test_ancestor_above_project_root_is_excluded(self, tmp_path):
        # CLAUDE.md above the project root must not be scanned.
        outside_md = tmp_path / "CLAUDE.md"
        _write(outside_md)
        proj = tmp_path / "proj"
        _mkgit(proj)
        _write(proj / "CLAUDE.md")
        sub = proj / "sub"
        cwd_md = sub / "CLAUDE.md"
        _write(cwd_md)
        results = discover.discover(sub)
        assert outside_md not in _paths(results)
        assert _role_of(results, proj / "CLAUDE.md") == "ancestor"
        assert _role_of(results, cwd_md) == "child"

    def test_project_root_not_demoted_by_outside_ancestor(self, tmp_path):
        # Launching AT the project root: a CLAUDE.md above it must not demote it.
        _write(tmp_path / "CLAUDE.md")  # outside the project
        proj = tmp_path / "proj"
        _mkgit(proj)
        root_md = proj / "CLAUDE.md"
        _write(root_md)
        results = discover.discover(proj)
        assert _role_of(results, root_md) == "root"
        assert tmp_path / "CLAUDE.md" not in _paths(results)

    def test_no_ancestors_when_cwd_is_project_root(self, tmp_path):
        proj = tmp_path / "proj"
        _mkgit(proj)
        _write(proj / "CLAUDE.md")
        assert discover.collect_ancestors(proj) == []


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
