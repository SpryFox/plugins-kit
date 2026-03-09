"""Tests for bootstrap lib/config_check.py — config management primitives."""

import os

import pytest

from bootstrap_lib.config_check import config_init, config_validate, load_yaml_config, save_yaml_config


class TestConfigInit:
    def test_copies_defaults_when_missing(self, tmp_path):
        """Config init copies defaults file when target doesn't exist."""
        plugin_root = tmp_path / "plugin"
        plugin_root.mkdir()
        defaults = plugin_root / "defaults"
        defaults.mkdir()
        (defaults / "config.yaml").write_text("P4PORT: \"\"\nP4USER: \"\"\n")

        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir)

        path = config_init(data_dir, str(plugin_root), "defaults/config.yaml", "config.yaml")
        assert os.path.isfile(path)
        assert "P4PORT" in open(path).read()

    def test_skips_copy_when_exists(self, tmp_path):
        """Config init doesn't overwrite existing config."""
        plugin_root = tmp_path / "plugin"
        plugin_root.mkdir()
        defaults = plugin_root / "defaults"
        defaults.mkdir()
        (defaults / "config.yaml").write_text("P4PORT: default\n")

        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir)
        existing = os.path.join(data_dir, "config.yaml")
        with open(existing, "w") as f:
            f.write("P4PORT: custom_value\n")

        config_init(data_dir, str(plugin_root), "defaults/config.yaml", "config.yaml")
        assert "custom_value" in open(existing).read()


class TestConfigValidate:
    def test_all_fields_set_passes(self):
        """No missing fields when all required fields have values."""
        config = {"P4PORT": "ssl:server:1666", "P4USER": "alice"}
        required = {
            "P4PORT": {"user_msg": "P4 port"},
            "P4USER": {"user_msg": "P4 user"},
        }
        updated, missing = config_validate(config, required, "/path/config.yaml")
        assert missing == []
        assert updated["P4PORT"] == "ssl:server:1666"

    def test_missing_fields_collected(self):
        """Empty fields without defaults are collected as missing."""
        config = {"P4PORT": "", "P4USER": ""}
        required = {
            "P4PORT": {"user_msg": "P4 port", "agent_msg": "Set P4PORT in {config_path}"},
            "P4USER": {"user_msg": "P4 user", "agent_msg": "Set P4USER in {config_path}"},
        }
        _, missing = config_validate(config, required, "/data/config.yaml")
        assert len(missing) == 2
        assert missing[0]["field"] == "P4PORT"
        assert "/data/config.yaml" in missing[0]["agent_msg"]

    def test_default_applied(self):
        """Fields with declared defaults get the default value."""
        config = {"AGENT": ""}
        required = {
            "AGENT": {"user_msg": "Agent", "default": "claude-opus"},
        }
        updated, missing = config_validate(config, required, "/path/config.yaml")
        assert missing == []
        assert updated["AGENT"] == "claude-opus"

    def test_default_not_applied_when_value_exists(self):
        """Fields with existing values are not overwritten by defaults."""
        config = {"AGENT": "gpt-4"}
        required = {
            "AGENT": {"user_msg": "Agent", "default": "claude-opus"},
        }
        updated, missing = config_validate(config, required, "/path/config.yaml")
        assert updated["AGENT"] == "gpt-4"

    def test_mixed_fields(self):
        """Some fields set, some defaulted, some missing."""
        config = {"A": "value", "B": "", "C": ""}
        required = {
            "A": {"user_msg": "A"},
            "B": {"user_msg": "B", "default": "b-default"},
            "C": {"user_msg": "C", "agent_msg": "Set C in {config_path}"},
        }
        updated, missing = config_validate(config, required, "/p")
        assert updated["A"] == "value"
        assert updated["B"] == "b-default"
        assert len(missing) == 1
        assert missing[0]["field"] == "C"


class TestYamlRoundTrip:
    def test_save_and_load(self, tmp_path):
        """YAML config round-trips correctly."""
        path = str(tmp_path / "config.yaml")
        original = {"P4PORT": "ssl:server:1666", "P4USER": "alice", "DEFAULT_AGENT": "claude-opus"}
        save_yaml_config(path, original)
        loaded = load_yaml_config(path)
        assert loaded == original

    def test_load_nonexistent_returns_empty(self, tmp_path):
        """Loading a nonexistent file returns empty dict."""
        loaded = load_yaml_config(str(tmp_path / "nope.yaml"))
        assert loaded == {}

    def test_load_empty_file_returns_empty(self, tmp_path):
        """Loading an empty file returns empty dict."""
        path = tmp_path / "empty.yaml"
        path.write_text("")
        loaded = load_yaml_config(str(path))
        assert loaded == {}
