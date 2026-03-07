"""Tests for marketplace_lifecycle.py — CLI-based marketplace and plugin operations."""

import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "bootstrap", "lib"))

from marketplace_lifecycle import (
    LifecycleResult,
    ScopeCheckResult,
    _version_greater,
    check_marketplace_current,
    check_marketplace_exists,
    check_plugin_installed,
    check_plugin_scope,
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

    def test_always_update_calls_update_when_behind(self, tmp_path, monkeypatch):
        """When alwaysUpdate is true and marketplace is behind, update_marketplace is called."""
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

        with patch("marketplace_lifecycle.check_marketplace_current",
                    return_value=LifecycleResult(passed=False, ref="my-market", message="updates available")), \
             patch("marketplace_lifecycle.update_marketplace",
                    return_value=LifecycleResult(passed=True, ref="my-market", message="updated")) as mock_update:
            _process_manifest(
                manifest, "windows", str(tmp_path / "data"), str(tmp_path / "root"),
                action_entries, ok_entries, plugin_name="test",
            )
            mock_update.assert_called_once_with("my-market")

        assert any("updating (alwaysUpdate)" in e for e in action_entries)
        assert any("updated" in e for e in action_entries)

    def test_always_update_silent_when_current(self, tmp_path, monkeypatch):
        """When alwaysUpdate is true but marketplace is current, result is silent (ok_entries)."""
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

        with patch("marketplace_lifecycle.check_marketplace_current",
                    return_value=LifecycleResult(passed=True, ref="my-market", message="up to date")), \
             patch("marketplace_lifecycle.update_marketplace") as mock_update:
            _process_manifest(
                manifest, "windows", str(tmp_path / "data"), str(tmp_path / "root"),
                action_entries, ok_entries, plugin_name="test",
            )
            mock_update.assert_not_called()

        assert any("up to date" in e for e in ok_entries)
        assert not any("updating" in e for e in action_entries)

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

        with patch("marketplace_lifecycle.check_marketplace_current",
                    return_value=LifecycleResult(passed=False, ref="my-market", message="updates available")), \
             patch("marketplace_lifecycle.update_marketplace",
                    return_value=LifecycleResult(passed=False, ref="my-market", message="network error")):
            failures = _process_manifest(
                manifest, "windows", str(tmp_path / "data"), str(tmp_path / "root"),
                action_entries, ok_entries, plugin_name="test",
            )

        assert any("update failed" in e for e in action_entries)
        assert any(f["type"] == "marketplace" for f in failures)


class TestVersionGreater:
    """Tests for _version_greater semver comparison."""

    def test_greater(self):
        assert _version_greater("0.5.2", "0.5.1") is True

    def test_equal(self):
        assert _version_greater("0.5.2", "0.5.2") is False

    def test_less(self):
        assert _version_greater("0.5.1", "0.5.2") is False

    def test_major_greater(self):
        assert _version_greater("1.0.0", "0.9.9") is True

    def test_installed_newer_than_marketplace(self):
        """The exact case that caused the bug: installed 0.5.2 vs marketplace 0.5.1."""
        assert _version_greater("0.5.1", "0.5.2") is False



class TestCheckPluginScope:
    """Tests for check_plugin_scope — detecting scope mismatches."""

    def _write_installed(self, tmp_path, monkeypatch, plugins_data):
        ip = tmp_path / ".claude" / "plugins" / "installed_plugins.json"
        ip.parent.mkdir(parents=True, exist_ok=True)
        ip.write_text(json.dumps({"version": 2, "plugins": plugins_data}))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

    def test_scope_matches(self, tmp_path, monkeypatch):
        self._write_installed(tmp_path, monkeypatch, {
            "bootstrap@plugins-kit": [{"scope": "user", "version": "0.5.4"}]
        })
        result = check_plugin_scope("plugins-kit:bootstrap", "user")
        assert result.matches is True
        assert result.installed_scope == "user"

    def test_scope_mismatch_project_vs_user(self, tmp_path, monkeypatch):
        self._write_installed(tmp_path, monkeypatch, {
            "bootstrap@plugins-kit": [{"scope": "project", "version": "0.5.4"}]
        })
        result = check_plugin_scope("plugins-kit:bootstrap", "user")
        assert result.matches is False
        assert result.installed_scope == "project"
        assert "want user" in result.message

    def test_scope_mismatch_user_vs_project(self, tmp_path, monkeypatch):
        self._write_installed(tmp_path, monkeypatch, {
            "bootstrap@plugins-kit": [{"scope": "user", "version": "0.5.4"}]
        })
        result = check_plugin_scope("plugins-kit:bootstrap", "project")
        assert result.matches is False
        assert result.installed_scope == "user"
        assert "want project" in result.message

    def test_not_installed_returns_matches(self, tmp_path, monkeypatch):
        """Not installed → matches=True (nothing to fix)."""
        self._write_installed(tmp_path, monkeypatch, {})
        result = check_plugin_scope("plugins-kit:bootstrap", "user")
        assert result.matches is True
        assert result.installed_scope == ""

    def test_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        result = check_plugin_scope("plugins-kit:bootstrap", "user")
        assert result.matches is True


class TestScopeRemediation:
    """Tests for scope mismatch remediation in the engine."""

    @staticmethod
    def _setup_engine_path():
        bootstrap_root = os.path.normpath(
            os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "bootstrap")
        )
        engine_dir = os.path.join(bootstrap_root, "engine")
        lib_dir = os.path.join(bootstrap_root, "lib")
        for d in (engine_dir, lib_dir):
            if d not in sys.path:
                sys.path.insert(0, d)

    def test_scope_mismatch_triggers_reinstall(self, tmp_path, monkeypatch):
        """Plugin at wrong scope gets uninstalled and reinstalled at correct scope."""
        self._setup_engine_path()

        # installed_plugins.json with project scope
        ip = tmp_path / ".claude" / "plugins" / "installed_plugins.json"
        ip.parent.mkdir(parents=True)
        ip.write_text(json.dumps({
            "version": 2,
            "plugins": {
                "bootstrap@plugins-kit": [{"scope": "project", "version": "0.5.4", "installPath": "/cache"}]
            }
        }))
        # settings.json with plugin enabled
        settings = tmp_path / ".claude" / "settings.json"
        settings.write_text(json.dumps({"enabledPlugins": {"bootstrap@plugins-kit": True}}))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        manifest = {
            "plugins": [
                {"ref": "plugins-kit:bootstrap", "enabled": True, "scope": "user"}
            ]
        }

        from bootstrap_engine import _process_manifest
        action_entries = []
        ok_entries = []

        with patch("marketplace_lifecycle.uninstall_plugin",
                    return_value=LifecycleResult(passed=True, ref="plugins-kit:bootstrap", message="uninstalled")) as mock_uninst, \
             patch("marketplace_lifecycle.install_plugin",
                    return_value=LifecycleResult(passed=True, ref="plugins-kit:bootstrap", message="installed")) as mock_inst, \
             patch("marketplace_lifecycle.check_plugin_version") as mock_ver:
            mock_ver.return_value = type("R", (), {"up_to_date": True})()
            _process_manifest(
                manifest, "windows", str(tmp_path / "data"), str(tmp_path / "root"),
                action_entries, ok_entries, plugin_name="test",
            )
            mock_uninst.assert_called_once_with("plugins-kit:bootstrap", scope="project")
            mock_inst.assert_called_once_with("plugins-kit:bootstrap", scope="user")

        assert any("scope mismatch" in e for e in action_entries)
        assert any("reinstalled at user scope" in e for e in action_entries)

    def test_correct_scope_no_reinstall(self, tmp_path, monkeypatch):
        """Plugin at correct scope does not trigger reinstall."""
        self._setup_engine_path()

        ip = tmp_path / ".claude" / "plugins" / "installed_plugins.json"
        ip.parent.mkdir(parents=True)
        ip.write_text(json.dumps({
            "version": 2,
            "plugins": {
                "bootstrap@plugins-kit": [{"scope": "user", "version": "0.5.4", "installPath": "/cache"}]
            }
        }))
        settings = tmp_path / ".claude" / "settings.json"
        settings.write_text(json.dumps({"enabledPlugins": {"bootstrap@plugins-kit": True}}))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        manifest = {
            "plugins": [
                {"ref": "plugins-kit:bootstrap", "enabled": True, "scope": "user"}
            ]
        }

        from bootstrap_engine import _process_manifest
        action_entries = []
        ok_entries = []

        with patch("marketplace_lifecycle.uninstall_plugin") as mock_uninst, \
             patch("marketplace_lifecycle.check_plugin_version") as mock_ver:
            mock_ver.return_value = type("R", (), {"up_to_date": True})()
            _process_manifest(
                manifest, "windows", str(tmp_path / "data"), str(tmp_path / "root"),
                action_entries, ok_entries, plugin_name="test",
            )
            mock_uninst.assert_not_called()

        assert not any("scope mismatch" in e for e in action_entries)
