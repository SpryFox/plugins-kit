"""Tests for marketplace_lifecycle.py — CLI-based marketplace and plugin operations."""

import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "bootstrap", "lib"))

from marketplace_lifecycle import (
    LifecycleResult,
    check_marketplace_exists,
    check_plugin_installed,
    update_marketplace,
)


class TestCheckMarketplaceExists:
    def test_exists(self, tmp_path, monkeypatch):
        km = tmp_path / ".claude" / "plugins" / "known_marketplaces.json"
        km.parent.mkdir(parents=True)
        km.write_text(json.dumps({
            "my-market": {"source": {"source": "git", "url": "https://example.com"}, "autoUpdate": True, "installLocation": str(tmp_path / "marketplaces" / "my-market")}
        }))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        result = check_marketplace_exists("my-market")
        assert result.passed is True

    def test_not_exists(self, tmp_path, monkeypatch):
        km = tmp_path / ".claude" / "plugins" / "known_marketplaces.json"
        km.parent.mkdir(parents=True)
        km.write_text(json.dumps({}))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        result = check_marketplace_exists("missing-market")
        assert result.passed is False

    def test_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
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
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

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
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        result = check_plugin_installed("plugins-kit:bootstrap")
        assert result.passed is True

    def test_not_installed(self, tmp_path, monkeypatch):
        ip = tmp_path / ".claude" / "plugins" / "installed_plugins.json"
        ip.parent.mkdir(parents=True)
        ip.write_text(json.dumps({"version": 2, "plugins": {}}))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        result = check_plugin_installed("plugins-kit:bootstrap")
        assert result.passed is False

    def test_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        result = check_plugin_installed("plugins-kit:bootstrap")
        assert result.passed is False


class TestMarketplaceAlwaysUpdate:
    """Tests for alwaysUpdate marketplace behavior in the engine's _process_manifest."""

    @staticmethod
    def _setup_engine_path():
        """Add engine and lib to sys.path for direct _process_manifest import."""
        bootstrap_root = os.path.normpath(
            os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "bootstrap")
        )
        engine_dir = os.path.join(bootstrap_root, "engine")
        lib_dir = os.path.join(bootstrap_root, "lib")
        for d in (engine_dir, lib_dir):
            if d not in sys.path:
                sys.path.insert(0, d)

    def test_always_update_calls_update(self, tmp_path, monkeypatch):
        """When alwaysUpdate is true and marketplace exists, update_marketplace is called."""
        self._setup_engine_path()

        # Setup known_marketplaces.json so check_marketplace_exists passes
        km = tmp_path / ".claude" / "plugins" / "known_marketplaces.json"
        km.parent.mkdir(parents=True)
        km.write_text(json.dumps({
            "my-market": {
                "source": {"source": "git", "url": "https://example.com"},
                "installLocation": str(tmp_path / "marketplaces" / "my-market"),
            }
        }))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        manifest = {
            "marketplaces": [
                {"name": "my-market", "source": "https://example.com", "alwaysUpdate": True}
            ]
        }

        from bootstrap_engine import _process_manifest
        action_entries = []
        ok_entries = []

        with patch("marketplace_lifecycle.update_marketplace",
                    return_value=LifecycleResult(passed=True, ref="my-market", message="updated")) as mock_update:
            _process_manifest(
                manifest, "windows", str(tmp_path / "data"), str(tmp_path / "root"),
                action_entries, ok_entries, plugin_name="test",
            )
            mock_update.assert_called_once_with("my-market")

        assert any("updating (alwaysUpdate)" in e for e in action_entries)
        assert any("updated" in e for e in action_entries)

    def test_no_always_update_skips_update(self, tmp_path, monkeypatch):
        """When alwaysUpdate is not set, marketplace just logs ok."""
        self._setup_engine_path()

        km = tmp_path / ".claude" / "plugins" / "known_marketplaces.json"
        km.parent.mkdir(parents=True)
        km.write_text(json.dumps({
            "my-market": {
                "source": {"source": "git", "url": "https://example.com"},
                "installLocation": str(tmp_path / "marketplaces" / "my-market"),
            }
        }))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        manifest = {
            "marketplaces": [
                {"name": "my-market", "source": "https://example.com"}
            ]
        }

        from bootstrap_engine import _process_manifest
        action_entries = []
        ok_entries = []

        with patch("marketplace_lifecycle.update_marketplace") as mock_update:
            _process_manifest(
                manifest, "windows", str(tmp_path / "data"), str(tmp_path / "root"),
                action_entries, ok_entries, plugin_name="test",
            )
            mock_update.assert_not_called()

        assert any("ok" in e for e in ok_entries)

    def test_always_update_failure_logged(self, tmp_path, monkeypatch):
        """When alwaysUpdate update fails, failure is recorded."""
        self._setup_engine_path()

        km = tmp_path / ".claude" / "plugins" / "known_marketplaces.json"
        km.parent.mkdir(parents=True)
        km.write_text(json.dumps({
            "my-market": {
                "source": {"source": "git", "url": "https://example.com"},
                "installLocation": str(tmp_path / "marketplaces" / "my-market"),
            }
        }))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        manifest = {
            "marketplaces": [
                {"name": "my-market", "source": "https://example.com", "alwaysUpdate": True}
            ]
        }

        from bootstrap_engine import _process_manifest
        action_entries = []
        ok_entries = []

        with patch("marketplace_lifecycle.update_marketplace",
                    return_value=LifecycleResult(passed=False, ref="my-market", message="network error")):
            failures = _process_manifest(
                manifest, "windows", str(tmp_path / "data"), str(tmp_path / "root"),
                action_entries, ok_entries, plugin_name="test",
            )

        assert any("update failed" in e for e in action_entries)
        assert any(f["type"] == "marketplace" for f in failures)
