"""Tests for plugins/bootstrap/lib/plugin_lifecycle.py."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "bootstrap", "lib"))

from plugin_lifecycle import (
    check_plugin_registered,
    register_plugin,
    unregister_plugin,
    check_plugin_enabled,
    enable_plugin,
    disable_plugin,
)


class TestCheckPluginRegistered:
    def test_registered(self, tmp_path):
        reg = tmp_path / "installed_plugins.json"
        reg.write_text(json.dumps({
            "plugins": {"my-plugin@market": [{"installPath": "./my-plugin", "version": "1.0"}]}
        }))
        result = check_plugin_registered(str(reg), "my-plugin@market")
        assert result.passed is True

    def test_not_registered(self, tmp_path):
        reg = tmp_path / "installed_plugins.json"
        reg.write_text(json.dumps({"plugins": {}}))
        result = check_plugin_registered(str(reg), "my-plugin@market")
        assert result.passed is False

    def test_registry_missing(self, tmp_path):
        result = check_plugin_registered(str(tmp_path / "missing.json"), "my-plugin@market")
        assert result.passed is False


class TestRegisterPlugin:
    def test_register_new(self, tmp_path):
        reg = tmp_path / "installed_plugins.json"
        reg.write_text(json.dumps({"plugins": {}}))

        result = register_plugin(str(reg), "new@market", "./new", "1.0")
        assert result.passed is True

        data = json.loads(reg.read_text())
        assert "new@market" in data["plugins"]
        assert data["plugins"]["new@market"][0]["installPath"] == "./new"

    def test_register_creates_file(self, tmp_path):
        reg = tmp_path / "sub" / "installed_plugins.json"
        result = register_plugin(str(reg), "new@market", "./new")
        assert result.passed is True
        assert reg.is_file()


class TestUnregisterPlugin:
    def test_unregister(self, tmp_path):
        reg = tmp_path / "installed_plugins.json"
        reg.write_text(json.dumps({
            "plugins": {"old@market": [{"installPath": "./old", "version": "1.0"}]}
        }))

        result = unregister_plugin(str(reg), "old@market")
        assert result.passed is True

        data = json.loads(reg.read_text())
        assert "old@market" not in data["plugins"]

    def test_unregister_already_gone(self, tmp_path):
        reg = tmp_path / "installed_plugins.json"
        reg.write_text(json.dumps({"plugins": {}}))
        result = unregister_plugin(str(reg), "old@market")
        assert result.passed is True


class TestCheckPluginEnabled:
    def test_enabled(self, tmp_path):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"enabled_plugins": ["my-plugin@market"]}))
        result = check_plugin_enabled(str(config), "my-plugin@market")
        assert result.passed is True

    def test_not_enabled(self, tmp_path):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"enabled_plugins": []}))
        result = check_plugin_enabled(str(config), "my-plugin@market")
        assert result.passed is False


class TestEnablePlugin:
    def test_enable(self, tmp_path):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"enabled_plugins": []}))
        result = enable_plugin(str(config), "my-plugin@market")
        assert result.passed is True

        data = json.loads(config.read_text())
        assert "my-plugin@market" in data["enabled_plugins"]

    def test_enable_idempotent(self, tmp_path):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"enabled_plugins": ["my-plugin@market"]}))
        enable_plugin(str(config), "my-plugin@market")

        data = json.loads(config.read_text())
        assert data["enabled_plugins"].count("my-plugin@market") == 1


class TestDisablePlugin:
    def test_disable(self, tmp_path):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"enabled_plugins": ["my-plugin@market"]}))
        result = disable_plugin(str(config), "my-plugin@market")
        assert result.passed is True

        data = json.loads(config.read_text())
        assert "my-plugin@market" not in data["enabled_plugins"]
