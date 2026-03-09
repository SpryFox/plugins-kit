"""Tests for the project_config engine primitive."""

import os

import pytest

from bootstrap_lib.config_check import load_yaml_config, save_yaml_config
from bootstrap_lib.engine import _process_project_config


def _write_autodetect_script(plugin_root, script_name="custom_bootstrap.py", body=""):
    """Write an autodetect script to plugin_root."""
    path = os.path.join(plugin_root, script_name)
    with open(path, "w") as f:
        f.write(body)
    return path


class TestProcessProjectConfig:
    def test_creates_file_from_autodetect(self, tmp_path, monkeypatch):
        """Autodetect returns values -> project config file created + data-dir updated."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        plugin_root = str(tmp_path / "plugin")
        os.makedirs(plugin_root)
        _write_autodetect_script(plugin_root, body="""\
def autodetect():
    return {"uproject": "/path/to/Game.uproject", "engine_dir": "/path/to/engine"}
""")

        plugin_data_dir = str(tmp_path / "data")
        os.makedirs(plugin_data_dir)

        section = {
            "file": ".claude/unreal-kit.yaml",
            "required_fields": ["uproject", "engine_dir"],
            "autodetect": "custom_bootstrap.py autodetect",
        }

        action_entries = []
        ok_entries = []
        result = _process_project_config(
            section, plugin_data_dir, plugin_root,
            action_entries, ok_entries=ok_entries, plugin_name="test",
        )

        assert result == []
        # Project config file created
        project_config_path = os.path.join(str(project_dir), ".claude", "unreal-kit.yaml")
        assert os.path.isfile(project_config_path)
        project_data = load_yaml_config(project_config_path)
        assert project_data["uproject"] == "/path/to/Game.uproject"
        assert project_data["engine_dir"] == "/path/to/engine"

        # Data-dir config synced
        data_config = load_yaml_config(os.path.join(plugin_data_dir, "config.yaml"))
        assert data_config["uproject"] == "/path/to/Game.uproject"
        assert data_config["engine_dir"] == "/path/to/engine"

        # Action logged
        assert any("created" in e for e in action_entries)

    def test_reads_existing_file(self, tmp_path, monkeypatch):
        """Pre-existing project config is read and synced to data-dir, ok entry logged."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Pre-create project config
        project_config_dir = project_dir / ".claude"
        project_config_dir.mkdir()
        save_yaml_config(
            str(project_config_dir / "unreal-kit.yaml"),
            {"uproject": "/existing/Game.uproject", "engine_dir": "/existing/engine"},
        )

        plugin_root = str(tmp_path / "plugin")
        os.makedirs(plugin_root)
        plugin_data_dir = str(tmp_path / "data")
        os.makedirs(plugin_data_dir)

        section = {
            "file": ".claude/unreal-kit.yaml",
            "required_fields": ["uproject", "engine_dir"],
        }

        action_entries = []
        ok_entries = []
        _process_project_config(
            section, plugin_data_dir, plugin_root,
            action_entries, ok_entries=ok_entries, plugin_name="test",
        )

        # Data-dir config synced
        data_config = load_yaml_config(os.path.join(plugin_data_dir, "config.yaml"))
        assert data_config["uproject"] == "/existing/Game.uproject"
        assert data_config["engine_dir"] == "/existing/engine"

        # Ok entry logged
        assert any("ok" in e for e in ok_entries)
        assert len(action_entries) == 0

    def test_autodetect_returns_none(self, tmp_path, monkeypatch):
        """Autodetect returning None -> no file created, no crash."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        plugin_root = str(tmp_path / "plugin")
        os.makedirs(plugin_root)
        _write_autodetect_script(plugin_root, body="""\
def autodetect():
    return None
""")

        plugin_data_dir = str(tmp_path / "data")
        os.makedirs(plugin_data_dir)

        section = {
            "file": ".claude/unreal-kit.yaml",
            "required_fields": ["uproject", "engine_dir"],
            "autodetect": "custom_bootstrap.py autodetect",
        }

        action_entries = []
        ok_entries = []
        result = _process_project_config(
            section, plugin_data_dir, plugin_root,
            action_entries, ok_entries=ok_entries, plugin_name="test",
        )

        assert result == []
        project_config_path = os.path.join(str(project_dir), ".claude", "unreal-kit.yaml")
        assert not os.path.exists(project_config_path)

    def test_runs_every_session(self, tmp_path, monkeypatch):
        """Existing file -> values re-merged to data-dir (no stale data)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Pre-create project config with updated values
        project_config_dir = project_dir / ".claude"
        project_config_dir.mkdir()
        save_yaml_config(
            str(project_config_dir / "unreal-kit.yaml"),
            {"uproject": "/new/Game.uproject", "engine_dir": "/new/engine"},
        )

        plugin_root = str(tmp_path / "plugin")
        os.makedirs(plugin_root)
        plugin_data_dir = str(tmp_path / "data")
        os.makedirs(plugin_data_dir)

        # Pre-create data-dir config with STALE values
        save_yaml_config(
            os.path.join(plugin_data_dir, "config.yaml"),
            {"uproject": "/old/Game.uproject", "engine_dir": "/old/engine"},
        )

        section = {
            "file": ".claude/unreal-kit.yaml",
            "required_fields": ["uproject", "engine_dir"],
        }

        action_entries = []
        ok_entries = []
        _process_project_config(
            section, plugin_data_dir, plugin_root,
            action_entries, ok_entries=ok_entries, plugin_name="test",
        )

        # Data-dir config updated with new values
        data_config = load_yaml_config(os.path.join(plugin_data_dir, "config.yaml"))
        assert data_config["uproject"] == "/new/Game.uproject"
        assert data_config["engine_dir"] == "/new/engine"

    def test_partial_fields(self, tmp_path, monkeypatch):
        """Autodetect returns only some fields — rest handled by config phase fix-all."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        plugin_root = str(tmp_path / "plugin")
        os.makedirs(plugin_root)
        _write_autodetect_script(plugin_root, body="""\
def autodetect():
    return {"uproject": "/path/to/Game.uproject"}
""")

        plugin_data_dir = str(tmp_path / "data")
        os.makedirs(plugin_data_dir)

        section = {
            "file": ".claude/unreal-kit.yaml",
            "required_fields": ["uproject", "engine_dir"],
            "autodetect": "custom_bootstrap.py autodetect",
        }

        action_entries = []
        ok_entries = []
        _process_project_config(
            section, plugin_data_dir, plugin_root,
            action_entries, ok_entries=ok_entries, plugin_name="test",
        )

        # Project config created with partial data
        project_config_path = os.path.join(str(project_dir), ".claude", "unreal-kit.yaml")
        assert os.path.isfile(project_config_path)
        project_data = load_yaml_config(project_config_path)
        assert project_data["uproject"] == "/path/to/Game.uproject"
        assert "engine_dir" not in project_data

        # Data-dir config has partial data
        data_config = load_yaml_config(os.path.join(plugin_data_dir, "config.yaml"))
        assert data_config["uproject"] == "/path/to/Game.uproject"
