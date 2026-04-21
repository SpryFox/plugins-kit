"""Tests for engine._load_layered_manifests parse-error surfacing."""

import json
from pathlib import Path

import pytest

from bootstrap_lib.engine import _load_layered_manifests


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Point HOME at a tmp dir so user-level bootstrap.json isolation is clean."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


class TestLoadLayeredManifests:
    def test_no_files_returns_empty(self, isolated_home, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        merged, errors = _load_layered_manifests(str(project))
        assert merged == {}
        assert errors == []

    def test_valid_layers_merged(self, isolated_home, tmp_path):
        # User layer
        user_claude = isolated_home / ".claude"
        user_claude.mkdir()
        (user_claude / "bootstrap.json").write_text(
            json.dumps({"plugins": [{"ref": "a:b", "scope": "user"}]})
        )
        # Project layer
        project = tmp_path / "project"
        project_claude = project / ".claude"
        project_claude.mkdir(parents=True)
        (project_claude / "bootstrap.json").write_text(
            json.dumps({"plugins": [{"ref": "c:d", "scope": "user"}]})
        )

        merged, errors = _load_layered_manifests(str(project))

        assert errors == []
        refs = {p["ref"] for p in merged["plugins"]}
        assert refs == {"a:b", "c:d"}

    def test_malformed_project_layer_surfaces_error(self, isolated_home, tmp_path):
        project = tmp_path / "project"
        project_claude = project / ".claude"
        project_claude.mkdir(parents=True)
        bad = project_claude / "bootstrap.json"
        # Missing comma between objects (real-world failure mode)
        bad.write_text(
            '{"plugins": [\n'
            '  {"ref": "a:b", "scope": "user"}\n'
            '  {"ref": "c:d", "scope": "user"}\n'
            ']}'
        )

        merged, errors = _load_layered_manifests(str(project))

        assert merged == {}
        assert len(errors) == 1
        assert errors[0]["path"] == str(bad)
        assert "JSON parse error" in errors[0]["error"]

    def test_malformed_layer_does_not_block_other_layers(self, isolated_home, tmp_path):
        # Valid user layer
        user_claude = isolated_home / ".claude"
        user_claude.mkdir()
        (user_claude / "bootstrap.json").write_text(
            json.dumps({"plugins": [{"ref": "a:b", "scope": "user"}]})
        )
        # Malformed project layer
        project = tmp_path / "project"
        project_claude = project / ".claude"
        project_claude.mkdir(parents=True)
        (project_claude / "bootstrap.json").write_text("{not json")

        merged, errors = _load_layered_manifests(str(project))

        # User layer still applied
        assert "plugins" in merged
        assert merged["plugins"][0]["ref"] == "a:b"
        # Error still reported
        assert len(errors) == 1
        assert "bootstrap.json" in errors[0]["path"]

    def test_legacy_user_bootstrap_parse_error_reported(self, isolated_home, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        legacy = data_dir / "user-bootstrap.json"
        legacy.write_text("{bad")

        merged, errors = _load_layered_manifests(None, str(data_dir))

        assert merged == {}
        assert len(errors) == 1
        assert errors[0]["path"] == str(legacy)
