"""Tests for marketplace_lifecycle.py — CLI-based marketplace and plugin operations."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "bootstrap", "lib"))

from marketplace_lifecycle import (
    check_marketplace_exists,
    check_plugin_installed,
)


class TestCheckMarketplaceExists:
    def test_exists(self, tmp_path, monkeypatch):
        km = tmp_path / ".claude" / "plugins" / "known_marketplaces.json"
        km.parent.mkdir(parents=True)
        km.write_text(json.dumps({
            "my-market": {"source": {"source": "git", "url": "https://example.com"}, "autoUpdate": True}
        }))
        monkeypatch.setenv("HOME", str(tmp_path))

        result = check_marketplace_exists("my-market")
        assert result.passed is True

    def test_not_exists(self, tmp_path, monkeypatch):
        km = tmp_path / ".claude" / "plugins" / "known_marketplaces.json"
        km.parent.mkdir(parents=True)
        km.write_text(json.dumps({}))
        monkeypatch.setenv("HOME", str(tmp_path))

        result = check_marketplace_exists("missing-market")
        assert result.passed is False

    def test_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        result = check_marketplace_exists("anything")
        assert result.passed is False


class TestCheckPluginInstalled:
    def test_installed_colon_format(self, tmp_path, monkeypatch):
        ip = tmp_path / ".claude" / "plugins" / "installed_plugins.json"
        ip.parent.mkdir(parents=True)
        ip.write_text(json.dumps({
            "version": 2,
            "plugins": {"plugins-kit:bootstrap": [{"installPath": "/some/path", "version": "1.0"}]}
        }))
        monkeypatch.setenv("HOME", str(tmp_path))

        result = check_plugin_installed("plugins-kit:bootstrap")
        assert result.passed is True

    def test_installed_at_format(self, tmp_path, monkeypatch):
        """Finds plugin even when registry uses plugin@marketplace format."""
        ip = tmp_path / ".claude" / "plugins" / "installed_plugins.json"
        ip.parent.mkdir(parents=True)
        ip.write_text(json.dumps({
            "version": 2,
            "plugins": {"bootstrap@plugins-kit": [{"installPath": "/some/path", "version": "1.0"}]}
        }))
        monkeypatch.setenv("HOME", str(tmp_path))

        result = check_plugin_installed("plugins-kit:bootstrap")
        assert result.passed is True

    def test_not_installed(self, tmp_path, monkeypatch):
        ip = tmp_path / ".claude" / "plugins" / "installed_plugins.json"
        ip.parent.mkdir(parents=True)
        ip.write_text(json.dumps({"version": 2, "plugins": {}}))
        monkeypatch.setenv("HOME", str(tmp_path))

        result = check_plugin_installed("plugins-kit:bootstrap")
        assert result.passed is False

    def test_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        result = check_plugin_installed("plugins-kit:bootstrap")
        assert result.passed is False
