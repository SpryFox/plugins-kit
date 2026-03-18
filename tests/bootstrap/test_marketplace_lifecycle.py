"""Tests for marketplace_lifecycle.py — CLI-based marketplace and plugin operations."""

import json
import os
import sys
from unittest.mock import patch

import pytest

from bootstrap_lib.marketplace_lifecycle import (
    LifecycleResult,
    ScopeCheckResult,
    _find_claude_cli,
    _run_claude,
    _version_greater,
    check_marketplace_current,
    check_marketplace_exists,
    check_plugin_enabled_at_scope,
    check_plugin_installed,
    check_plugin_scope,
    ensure_registry_scope,
    update_marketplace,
)


class TestFindClaudeCli:
    """Tests for _find_claude_cli — CLAUDE_REAL_BIN env var lookup."""

    def test_returns_path_when_env_set_and_file_exists(self, tmp_path, monkeypatch):
        fake_bin = tmp_path / "claude"
        fake_bin.write_text("#!/bin/sh\n")
        monkeypatch.setenv("CLAUDE_REAL_BIN", str(fake_bin))
        assert _find_claude_cli() == str(fake_bin)

    def test_returns_none_when_env_not_set(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_REAL_BIN", raising=False)
        assert _find_claude_cli() is None

    def test_returns_none_when_env_set_but_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_REAL_BIN", str(tmp_path / "nonexistent"))
        assert _find_claude_cli() is None

    def test_returns_none_when_env_is_empty(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_REAL_BIN", "")
        assert _find_claude_cli() is None


class TestRunClaude:
    """Tests for _run_claude — CLI invocation via _find_claude_cli."""

    def test_returns_failure_when_cli_not_found(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_REAL_BIN", raising=False)
        ok, stdout, stderr = _run_claude(["plugin", "list"])
        assert ok is False
        assert "claude CLI not found" in stderr

    def test_invokes_binary_from_env(self, tmp_path, monkeypatch):
        fake_bin = tmp_path / "claude"
        fake_bin.write_text("#!/bin/sh\n")
        monkeypatch.setenv("CLAUDE_REAL_BIN", str(fake_bin))
        with patch("bootstrap_lib.marketplace_lifecycle.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
            ok, stdout, stderr = _run_claude(["plugin", "list"])
        assert ok is True
        assert mock_run.call_args[0][0][0] == str(fake_bin)


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
        """Add engine to sys.path for direct _process_manifest import."""
        bootstrap_root = os.path.normpath(
            os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "bootstrap")
        )
        engine_dir = os.path.join(bootstrap_root, "engine")
        if engine_dir not in sys.path:
            sys.path.insert(0, engine_dir)

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

        from bootstrap_lib.engine import _process_manifest
        action_entries = []
        ok_entries = []

        with patch("bootstrap_lib.marketplace_lifecycle.check_marketplace_current",
                    return_value=LifecycleResult(passed=False, ref="my-market", message="updates available")), \
             patch("bootstrap_lib.marketplace_lifecycle.update_marketplace",
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

        from bootstrap_lib.engine import _process_manifest
        action_entries = []
        ok_entries = []

        with patch("bootstrap_lib.marketplace_lifecycle.check_marketplace_current",
                    return_value=LifecycleResult(passed=True, ref="my-market", message="up to date")), \
             patch("bootstrap_lib.marketplace_lifecycle.update_marketplace") as mock_update:
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

        from bootstrap_lib.engine import _process_manifest
        action_entries = []
        ok_entries = []

        with patch("bootstrap_lib.marketplace_lifecycle.update_marketplace") as mock_update:
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

        from bootstrap_lib.engine import _process_manifest
        action_entries = []
        ok_entries = []

        with patch("bootstrap_lib.marketplace_lifecycle.check_marketplace_current",
                    return_value=LifecycleResult(passed=False, ref="my-market", message="updates available")), \
             patch("bootstrap_lib.marketplace_lifecycle.update_marketplace",
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


class TestCheckPluginEnabledAtScope:
    """Tests for check_plugin_enabled_at_scope — reading settings files directly."""

    def test_enabled_at_user_scope(self, tmp_path, monkeypatch):
        settings = tmp_path / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({"enabledPlugins": {"bootstrap@plugins-kit": True}}))
        monkeypatch.setenv("HOME", str(tmp_path))
        result = check_plugin_enabled_at_scope("plugins-kit:bootstrap", "user")
        assert result.passed is True
        assert "user scope" in result.message

    def test_not_enabled_at_user_scope(self, tmp_path, monkeypatch):
        settings = tmp_path / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({"enabledPlugins": {}}))
        monkeypatch.setenv("HOME", str(tmp_path))
        result = check_plugin_enabled_at_scope("plugins-kit:bootstrap", "user")
        assert result.passed is False
        assert "not enabled at user scope" in result.message

    def test_enabled_at_project_scope(self, tmp_path, monkeypatch):
        project_dir = tmp_path / "myproject"
        settings = project_dir / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({"enabledPlugins": {"bootstrap@plugins-kit": True}}))
        monkeypatch.setenv("HOME", str(tmp_path))
        result = check_plugin_enabled_at_scope("plugins-kit:bootstrap", "project", str(project_dir))
        assert result.passed is True
        assert "project scope" in result.message

    def test_project_scope_without_project_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        result = check_plugin_enabled_at_scope("plugins-kit:bootstrap", "project")
        assert result.passed is False
        assert "missing project_dir" in result.message

    def test_no_settings_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        result = check_plugin_enabled_at_scope("plugins-kit:bootstrap", "user")
        assert result.passed is False

    def test_enabled_at_user_not_at_project(self, tmp_path, monkeypatch):
        """Plugin enabled at user scope but not project scope."""
        # User settings has the plugin
        user_settings = tmp_path / ".claude" / "settings.json"
        user_settings.parent.mkdir(parents=True)
        user_settings.write_text(json.dumps({"enabledPlugins": {"bootstrap@plugins-kit": True}}))
        # Project settings does NOT have the plugin
        project_dir = tmp_path / "myproject"
        project_settings = project_dir / ".claude" / "settings.json"
        project_settings.parent.mkdir(parents=True)
        project_settings.write_text(json.dumps({"enabledPlugins": {}}))
        monkeypatch.setenv("HOME", str(tmp_path))

        user_result = check_plugin_enabled_at_scope("plugins-kit:bootstrap", "user")
        assert user_result.passed is True
        project_result = check_plugin_enabled_at_scope("plugins-kit:bootstrap", "project", str(project_dir))
        assert project_result.passed is False


class TestScopeRemediation:
    """Tests for scope remediation in the engine — ensure-at-desired-scope pattern."""

    @staticmethod
    def _setup_engine_path():
        bootstrap_root = os.path.normpath(
            os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "bootstrap")
        )
        engine_dir = os.path.join(bootstrap_root, "engine")
        if engine_dir not in sys.path:
            sys.path.insert(0, engine_dir)

    def test_enabled_at_desired_scope_no_action(self, tmp_path, monkeypatch):
        """Plugin already enabled at desired scope → no install action needed."""
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

        from bootstrap_lib.engine import _process_manifest
        action_entries = []
        ok_entries = []

        with patch("bootstrap_lib.marketplace_lifecycle.install_plugin") as mock_inst, \
             patch("bootstrap_lib.marketplace_lifecycle.check_plugin_version") as mock_ver:
            mock_ver.return_value = type("R", (), {"up_to_date": True})()
            _process_manifest(
                manifest, "windows", str(tmp_path / "data"), str(tmp_path / "root"),
                action_entries, ok_entries, plugin_name="test",
            )
            mock_inst.assert_not_called()

        assert not any("installing at" in e for e in action_entries)

    def test_not_enabled_at_desired_scope_triggers_install(self, tmp_path, monkeypatch):
        """Plugin not enabled at desired scope → install at that scope (no uninstall)."""
        self._setup_engine_path()

        # Plugin is in the registry (installed) but NOT in user settings
        ip = tmp_path / ".claude" / "plugins" / "installed_plugins.json"
        ip.parent.mkdir(parents=True)
        ip.write_text(json.dumps({
            "version": 2,
            "plugins": {
                "bootstrap@plugins-kit": [{"scope": "project", "version": "0.5.4", "installPath": "/cache"}]
            }
        }))
        # User settings does NOT have the plugin enabled
        settings = tmp_path / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps({"enabledPlugins": {}}))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        manifest = {
            "plugins": [
                {"ref": "plugins-kit:bootstrap", "enabled": True, "scope": "user"}
            ]
        }

        from bootstrap_lib.engine import _process_manifest
        action_entries = []
        ok_entries = []

        with patch("bootstrap_lib.marketplace_lifecycle.install_plugin",
                    return_value=LifecycleResult(passed=True, ref="plugins-kit:bootstrap", message="installed")) as mock_inst, \
             patch("bootstrap_lib.marketplace_lifecycle.check_plugin_version") as mock_ver:
            mock_ver.return_value = type("R", (), {"up_to_date": True})()
            _process_manifest(
                manifest, "windows", str(tmp_path / "data"), str(tmp_path / "root"),
                action_entries, ok_entries, plugin_name="test",
            )
            # Install at desired scope, no uninstall
            mock_inst.assert_called_once_with("plugins-kit:bootstrap", scope="user")

        assert any("not enabled at user scope" in e for e in action_entries)
        assert any("installed at user scope" in e for e in action_entries)

    def test_stale_registry_scope_no_uninstall(self, tmp_path, monkeypatch):
        """Registry says 'project' but plugin is enabled at user scope → no action.

        This is the exact scenario from the bug report: installed_plugins.json
        has stale scope metadata, but the settings file shows the truth.
        """
        self._setup_engine_path()

        # Registry claims project scope (stale)
        ip = tmp_path / ".claude" / "plugins" / "installed_plugins.json"
        ip.parent.mkdir(parents=True)
        ip.write_text(json.dumps({
            "version": 2,
            "plugins": {
                "bootstrap@plugins-kit": [{"scope": "project", "version": "0.5.4", "installPath": "/cache"}]
            }
        }))
        # But user settings HAS it enabled (truth)
        settings = tmp_path / ".claude" / "settings.json"
        settings.write_text(json.dumps({"enabledPlugins": {"bootstrap@plugins-kit": True}}))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        manifest = {
            "plugins": [
                {"ref": "plugins-kit:bootstrap", "enabled": True, "scope": "user"}
            ]
        }

        from bootstrap_lib.engine import _process_manifest
        action_entries = []
        ok_entries = []

        with patch("bootstrap_lib.marketplace_lifecycle.install_plugin") as mock_inst, \
             patch("bootstrap_lib.marketplace_lifecycle.check_plugin_version") as mock_ver:
            mock_ver.return_value = type("R", (), {"up_to_date": True})()
            _process_manifest(
                manifest, "windows", str(tmp_path / "data"), str(tmp_path / "root"),
                action_entries, ok_entries, plugin_name="test",
            )
            mock_inst.assert_not_called()

        # No scope-related action entries
        assert not any("installing at" in e for e in action_entries)
        assert not any("scope mismatch" in e for e in action_entries)


class TestUpdateMarketplaceFallback:
    """Tests for update_marketplace CLI fallback when directory already exists."""

    def _write_known_marketplaces(self, tmp_path, monkeypatch, install_location):
        km = tmp_path / ".claude" / "plugins" / "known_marketplaces.json"
        km.parent.mkdir(parents=True, exist_ok=True)
        km.write_text(json.dumps({
            "my-market": {
                "source": {"source": "git", "url": "https://example.com"},
                "installLocation": str(install_location),
            }
        }))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

    def test_should_fallback_to_git_pull_when_cli_fails_with_already_exists(self, tmp_path, monkeypatch):
        """When CLI update fails with 'already exists', git pull the install location directly."""
        install_dir = tmp_path / "marketplaces" / "my-market"
        install_dir.mkdir(parents=True)
        self._write_known_marketplaces(tmp_path, monkeypatch, install_dir)

        already_exists_error = (
            "✘ Failed to update marketplace(s): Failed to refresh marketplace 'my-market': "
            "Failed to clone marketplace repository: fatal: destination path "
            f"'{install_dir}' already exists and is not an empty directory."
        )

        with patch("bootstrap_lib.marketplace_lifecycle._run_claude",
                   return_value=(False, "", already_exists_error)), \
             patch("bootstrap_lib.marketplace_lifecycle.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            result = update_marketplace("my-market")

        assert result.passed is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["git", "pull"]
        assert str(install_dir) in str(call_args[1].get("cwd", ""))

    def test_should_return_failure_when_cli_fails_without_already_exists(self, tmp_path, monkeypatch):
        """Non-'already exists' CLI failures propagate as failures (no git fallback)."""
        install_dir = tmp_path / "marketplaces" / "my-market"
        install_dir.mkdir(parents=True)
        self._write_known_marketplaces(tmp_path, monkeypatch, install_dir)

        with patch("bootstrap_lib.marketplace_lifecycle._run_claude",
                   return_value=(False, "", "network timeout")), \
             patch("bootstrap_lib.marketplace_lifecycle.subprocess.run") as mock_run:
            result = update_marketplace("my-market")

        assert result.passed is False
        mock_run.assert_not_called()

    def test_should_return_failure_when_git_pull_fails_in_fallback(self, tmp_path, monkeypatch):
        """If git pull also fails during fallback, return failure."""
        install_dir = tmp_path / "marketplaces" / "my-market"
        install_dir.mkdir(parents=True)
        self._write_known_marketplaces(tmp_path, monkeypatch, install_dir)

        already_exists_error = "already exists and is not an empty directory"

        with patch("bootstrap_lib.marketplace_lifecycle._run_claude",
                   return_value=(False, "", already_exists_error)), \
             patch("bootstrap_lib.marketplace_lifecycle.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 1, "stdout": "", "stderr": "merge conflict"})()
            result = update_marketplace("my-market")

        assert result.passed is False
        assert "merge conflict" in result.message or "git pull" in result.message

    def test_should_return_failure_when_install_location_not_found(self, tmp_path, monkeypatch):
        """If CLI fails with 'already exists' but installLocation unknown, return failure."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        # No known_marketplaces.json written

        already_exists_error = "already exists and is not an empty directory"

        with patch("bootstrap_lib.marketplace_lifecycle._run_claude",
                   return_value=(False, "", already_exists_error)), \
             patch("bootstrap_lib.marketplace_lifecycle.subprocess.run") as mock_run:
            result = update_marketplace("my-market")

        assert result.passed is False
        mock_run.assert_not_called()


class TestEnsureRegistryScope:
    """Tests for ensure_registry_scope — fixing stale scope in installed_plugins.json."""

    def _write_registry(self, tmp_path, monkeypatch, plugins_data):
        ip = tmp_path / ".claude" / "plugins" / "installed_plugins.json"
        ip.parent.mkdir(parents=True, exist_ok=True)
        ip.write_text(json.dumps({"version": 2, "plugins": plugins_data}))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        return ip

    def test_fixes_stale_scope(self, tmp_path, monkeypatch):
        """Registry says 'project', desired is 'user' → updates to 'user'."""
        ip = self._write_registry(tmp_path, monkeypatch, {
            "bootstrap@plugins-kit": [{"scope": "project", "version": "0.8.4"}]
        })
        result = ensure_registry_scope("plugins-kit:bootstrap", "user")
        assert result is True
        data = json.loads(ip.read_text())
        assert data["plugins"]["bootstrap@plugins-kit"][0]["scope"] == "user"

    def test_already_correct_scope(self, tmp_path, monkeypatch):
        """Registry already has correct scope → no change needed."""
        ip = self._write_registry(tmp_path, monkeypatch, {
            "bootstrap@plugins-kit": [{"scope": "user", "version": "0.8.4"}]
        })
        result = ensure_registry_scope("plugins-kit:bootstrap", "user")
        assert result is True
        data = json.loads(ip.read_text())
        assert data["plugins"]["bootstrap@plugins-kit"][0]["scope"] == "user"

    def test_plugin_not_in_registry(self, tmp_path, monkeypatch):
        """Plugin not in registry → returns True (nothing to fix)."""
        self._write_registry(tmp_path, monkeypatch, {})
        result = ensure_registry_scope("plugins-kit:bootstrap", "user")
        assert result is True

    def test_no_registry_file(self, tmp_path, monkeypatch):
        """No registry file → returns False."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        result = ensure_registry_scope("plugins-kit:bootstrap", "user")
        assert result is False
