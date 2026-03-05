"""Integration tests for cross-marketplace plugin refs in the bootstrap engine."""

import json
import os
import subprocess
import sys

import pytest

BOOTSTRAP_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "bootstrap")
)
ENGINE_SCRIPT = os.path.join(BOOTSTRAP_ROOT, "engine", "bootstrap_engine.py")


def run_engine(data_dir, plugin_root=BOOTSTRAP_ROOT):
    """Run the bootstrap engine as a subprocess."""
    return subprocess.run(
        [sys.executable, ENGINE_SCRIPT, "--plugin-root", plugin_root, "--data-dir", data_dir],
        capture_output=True,
        text=True,
    )


def make_fake_bootstrap_root(plugins_dir, manifest=None):
    """Create a fake bootstrap plugin root with symlinked lib/engine/defaults."""
    fake_root = plugins_dir / "bootstrap"
    fake_root.mkdir(parents=True, exist_ok=True)
    (fake_root / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
    (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
    (fake_root / "defaults").symlink_to(os.path.join(BOOTSTRAP_ROOT, "defaults"))

    if manifest is None:
        manifest = {"tools": [], "path_entries": []}
    (fake_root / "bootstrap.json").write_text(json.dumps(manifest))
    return str(fake_root)


class TestCrossMarketplacePluginRefs:
    def test_same_marketplace_uses_local_registry(self, tmp_path):
        """Plugin ref with same marketplace resolves from local registry."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        fake_root = make_fake_bootstrap_root(plugins_dir)

        # Create a plugin in the local marketplace
        plugin_dir = plugins_dir / "my-plugin"
        plugin_dir.mkdir()

        # Local registry has the plugin
        registry = {"plugins": {"kit:my-plugin": [{"installPath": "./my-plugin", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        # Bootstrap manifest references the plugin (same marketplace)
        (plugins_dir / "bootstrap" / "bootstrap.json").write_text(json.dumps({
            "tools": [],
            "plugins": [{"ref": "kit:my-plugin", "enabled": True}],
        }))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {
            "schema_version": 3, "enabled_plugins": [], "log_level": "info",
            "log_success_shell": False, "log_success_checks": True,
        }
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(config, f)

        result = run_engine(data_dir, plugin_root=fake_root)
        assert result.returncode == 0

        # Should find the plugin in local registry and enable it
        if result.stdout.strip():
            response = json.loads(result.stdout)
            msg = response.get("systemMessage", "") + response.get("hookSpecificOutput", {}).get("additionalContext", "")
            # Plugin found — should either log ok or enable it
            assert "my-plugin" in msg

    def test_cross_marketplace_uses_global_registry(self, tmp_path, monkeypatch):
        """Plugin ref with different marketplace resolves from global registry."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        fake_root = make_fake_bootstrap_root(plugins_dir)

        # Local registry identifies this as 'update01' marketplace
        local_registry = {"plugins": {"update01:bootstrap": [{"installPath": "./bootstrap", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(local_registry))

        # Global registry has the cross-marketplace plugin
        global_plugins_dir = tmp_path / "global" / "plugins"
        global_plugins_dir.mkdir(parents=True)
        global_registry = {
            "plugins": {
                "plugins-kit:bootstrap": [{"installPath": str(tmp_path / "cache" / "bootstrap"), "version": "1.0.0"}],
            }
        }
        (global_plugins_dir / "installed_plugins.json").write_text(json.dumps(global_registry))

        # Create the target plugin dir so the registration check works
        target_dir = tmp_path / "cache" / "bootstrap"
        target_dir.mkdir(parents=True)

        # Bootstrap manifest references a plugin from a DIFFERENT marketplace
        (plugins_dir / "bootstrap" / "bootstrap.json").write_text(json.dumps({
            "tools": [],
            "plugins": [{"ref": "plugins-kit:bootstrap", "enabled": True}],
        }))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {
            "schema_version": 3, "enabled_plugins": [], "log_level": "info",
            "log_success_shell": False, "log_success_checks": True,
        }
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(config, f)

        # Monkey-patch home directory so global registry resolves to our test dir
        monkeypatch.setenv("HOME", str(tmp_path / "global"))

        result = run_engine(data_dir, plugin_root=fake_root)
        assert result.returncode == 0

        # The engine should have used the global registry and found the plugin
        if result.stdout.strip():
            response = json.loads(result.stdout)
            msg = response.get("systemMessage", "") + response.get("hookSpecificOutput", {}).get("additionalContext", "")
            # Should reference the cross-marketplace plugin
            assert "plugins-kit:bootstrap" in msg

    def test_cross_marketplace_ref_not_in_global_registry_fails(self, tmp_path, monkeypatch):
        """Cross-marketplace ref not found in global registry produces failure."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        fake_root = make_fake_bootstrap_root(plugins_dir)

        # Local registry identifies this as 'update01' marketplace
        local_registry = {"plugins": {"update01:bootstrap": [{"installPath": "./bootstrap", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(local_registry))

        # Global registry is empty
        global_plugins_dir = tmp_path / "global" / "plugins"
        global_plugins_dir.mkdir(parents=True)
        (global_plugins_dir / "installed_plugins.json").write_text(json.dumps({"plugins": {}}))

        # Bootstrap manifest references a cross-marketplace plugin that doesn't exist
        (plugins_dir / "bootstrap" / "bootstrap.json").write_text(json.dumps({
            "tools": [],
            "plugins": [{"ref": "plugins-kit:bootstrap", "enabled": True}],
        }))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {
            "schema_version": 3, "enabled_plugins": [], "log_level": "info",
            "log_success_shell": False, "log_success_checks": True,
        }
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(config, f)

        monkeypatch.setenv("HOME", str(tmp_path / "global"))

        result = run_engine(data_dir, plugin_root=fake_root)
        assert result.returncode == 0

        # Should emit failure for missing cross-marketplace plugin
        assert result.stdout.strip() != ""
        response = json.loads(result.stdout)
        ctx = response["hookSpecificOutput"]["additionalContext"]
        assert "plugins-kit:bootstrap" in ctx
        assert "not registered" in ctx


class TestDetectMarketplaceName:
    def test_detects_from_registry_keys(self, tmp_path):
        """Marketplace name detected from installed_plugins.json keys."""
        sys.path.insert(0, os.path.join(BOOTSTRAP_ROOT, "engine"))
        from bootstrap_engine import _detect_marketplace_name

        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        registry = {"plugins": {"my-market:some-plugin": [{"installPath": "./some-plugin"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        assert _detect_marketplace_name(str(plugins_dir)) == "my-market"

    def test_falls_back_to_parent_dir(self, tmp_path):
        """Falls back to parent directory name when no registry exists."""
        sys.path.insert(0, os.path.join(BOOTSTRAP_ROOT, "engine"))
        from bootstrap_engine import _detect_marketplace_name

        market_dir = tmp_path / "my-marketplace" / "plugins"
        market_dir.mkdir(parents=True)

        assert _detect_marketplace_name(str(market_dir)) == "my-marketplace"

    def test_empty_registry(self, tmp_path):
        """Falls back when registry has no plugins."""
        sys.path.insert(0, os.path.join(BOOTSTRAP_ROOT, "engine"))
        from bootstrap_engine import _detect_marketplace_name

        market_dir = tmp_path / "fallback-name" / "plugins"
        market_dir.mkdir(parents=True)
        (market_dir / "installed_plugins.json").write_text(json.dumps({"plugins": {}}))

        assert _detect_marketplace_name(str(market_dir)) == "fallback-name"
