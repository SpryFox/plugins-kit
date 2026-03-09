"""Tests for config autodetect lifecycle."""

import os

import pytest

from bootstrap_lib.config_check import run_autodetect, save_yaml_config, load_yaml_config


def _write_autodetect_script(plugin_root, script_name="custom_bootstrap.py", body=""):
    """Write an autodetect script to plugin_root."""
    path = os.path.join(plugin_root, script_name)
    with open(path, "w") as f:
        f.write(body)
    return path


class TestRunAutodetect:
    def test_calls_function_when_fields_empty(self, tmp_path):
        """Autodetect function is called and can modify config."""
        plugin_root = str(tmp_path / "plugin")
        os.makedirs(plugin_root)

        _write_autodetect_script(plugin_root, body="""\
def autodetect(config, config_path):
    config["P4PORT"] = "detected:1666"
    return True
""")
        config = {"P4PORT": "", "P4USER": ""}
        changed = run_autodetect(plugin_root, "custom_bootstrap.py autodetect", config, "/path/c.yaml")
        assert changed is True
        assert config["P4PORT"] == "detected:1666"

    def test_not_called_when_spec_invalid(self, tmp_path):
        """Invalid autodetect spec (no function name) returns False."""
        plugin_root = str(tmp_path / "plugin")
        os.makedirs(plugin_root)
        config = {"P4PORT": ""}
        changed = run_autodetect(plugin_root, "just-a-script.py", config, "/path/c.yaml")
        assert changed is False

    def test_not_called_when_script_missing(self, tmp_path):
        """Missing script file returns False."""
        plugin_root = str(tmp_path / "plugin")
        os.makedirs(plugin_root)
        config = {"P4PORT": ""}
        changed = run_autodetect(plugin_root, "nonexistent.py autodetect", config, "/path/c.yaml")
        assert changed is False

    def test_errors_caught_gracefully(self, tmp_path):
        """Script that raises exception returns False."""
        plugin_root = str(tmp_path / "plugin")
        os.makedirs(plugin_root)

        _write_autodetect_script(plugin_root, body="""\
def autodetect(config, config_path):
    raise RuntimeError("boom")
""")
        config = {"P4PORT": ""}
        changed = run_autodetect(plugin_root, "custom_bootstrap.py autodetect", config, "/path/c.yaml")
        assert changed is False

    def test_returns_false_no_changes(self, tmp_path):
        """Script that returns False means no changes."""
        plugin_root = str(tmp_path / "plugin")
        os.makedirs(plugin_root)

        _write_autodetect_script(plugin_root, body="""\
def autodetect(config, config_path):
    return False
""")
        config = {"P4PORT": ""}
        changed = run_autodetect(plugin_root, "custom_bootstrap.py autodetect", config, "/path/c.yaml")
        assert changed is False

    def test_config_written_back_after_changes(self, tmp_path):
        """When autodetect changes config, caller should save it (tested via save_yaml_config)."""
        plugin_root = str(tmp_path / "plugin")
        os.makedirs(plugin_root)

        _write_autodetect_script(plugin_root, body="""\
def autodetect(config, config_path):
    config["DETECTED"] = "yes"
    return True
""")
        config_path = str(tmp_path / "config.yaml")
        save_yaml_config(config_path, {"DETECTED": ""})

        config = load_yaml_config(config_path)
        changed = run_autodetect(plugin_root, "custom_bootstrap.py autodetect", config, config_path)
        assert changed is True

        save_yaml_config(config_path, config)
        reloaded = load_yaml_config(config_path)
        assert reloaded["DETECTED"] == "yes"
