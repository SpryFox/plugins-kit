"""Tests for p4-kit cleanup_legacy_config.py."""

from pathlib import Path

import pytest

from cleanup_legacy_config import cleanup


class FakeCtx:
    def __init__(self, project_dir):
        self.project_dir = str(project_dir) if project_dir is not None else None
        self.logs = []

    def log(self, msg):
        self.logs.append(msg)


def _write(path: Path, content: str = "P4PORT: ssl:host:1666\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_removes_new_path_and_prunes_empty_parent(tmp_path):
    cfg = tmp_path / ".local-data" / "p4-kit" / "config.yaml"
    _write(cfg)

    ctx = FakeCtx(tmp_path)
    cleanup(ctx)

    assert not cfg.exists()
    assert not (tmp_path / ".local-data" / "p4-kit").exists()
    assert not (tmp_path / ".local-data").exists()
    assert any("removed" in m for m in ctx.logs)


def test_removes_legacy_path(tmp_path):
    legacy = tmp_path / ".claude" / "p4-kit.yaml"
    _write(legacy)

    ctx = FakeCtx(tmp_path)
    cleanup(ctx)

    assert not legacy.exists()
    assert any("removed" in m for m in ctx.logs)


def test_removes_both_when_both_present(tmp_path):
    cfg = tmp_path / ".local-data" / "p4-kit" / "config.yaml"
    legacy = tmp_path / ".claude" / "p4-kit.yaml"
    _write(cfg)
    _write(legacy)

    ctx = FakeCtx(tmp_path)
    cleanup(ctx)

    assert not cfg.exists()
    assert not legacy.exists()


def test_preserves_nonempty_parent_dirs(tmp_path):
    cfg = tmp_path / ".local-data" / "p4-kit" / "config.yaml"
    _write(cfg)
    # Sibling file in `.local-data/` that must survive
    sibling = tmp_path / ".local-data" / "other-tool" / "data.yaml"
    _write(sibling, "x: 1\n")

    ctx = FakeCtx(tmp_path)
    cleanup(ctx)

    assert not cfg.exists()
    # p4-kit dir was pruned
    assert not (tmp_path / ".local-data" / "p4-kit").exists()
    # .local-data survives because it still has other-tool/
    assert (tmp_path / ".local-data").is_dir()
    assert sibling.exists()


def test_preserves_dotclaude_with_other_contents(tmp_path):
    legacy = tmp_path / ".claude" / "p4-kit.yaml"
    other = tmp_path / ".claude" / "settings.json"
    _write(legacy)
    _write(other, "{}\n")

    ctx = FakeCtx(tmp_path)
    cleanup(ctx)

    assert not legacy.exists()
    # .claude/ stays because settings.json is still there
    assert (tmp_path / ".claude").is_dir()
    assert other.exists()


def test_noop_when_nothing_to_remove(tmp_path):
    ctx = FakeCtx(tmp_path)
    cleanup(ctx)

    assert ctx.logs == []


def test_noop_when_project_dir_is_none(tmp_path):
    ctx = FakeCtx(None)
    cleanup(ctx)

    assert ctx.logs == []
