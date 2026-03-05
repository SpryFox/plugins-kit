"""Integration tests for multi-plugin bootstrap engine flow."""

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


def make_fake_bootstrap_root(tmp_path, manifest=None):
    """Create a fake bootstrap plugin root with symlinked lib/engine/defaults."""
    fake_root = tmp_path / "bootstrap"
    fake_root.mkdir(parents=True)
    (fake_root / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
    (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
    (fake_root / "defaults").symlink_to(os.path.join(BOOTSTRAP_ROOT, "defaults"))

    if manifest is None:
        manifest = {"tools": [], "path_entries": []}
    (fake_root / "bootstrap.json").write_text(json.dumps(manifest))
    return str(fake_root)


class TestMultiPluginEngine:
    def test_no_enabled_plugins_emits_log(self, tmp_path):
        """Engine with no enabled plugins should emit log after self-bootstrap."""
        fake_root = make_fake_bootstrap_root(tmp_path)
        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir)

        result = run_engine(data_dir, plugin_root=fake_root)

        assert result.returncode == 0
        # Empty manifest = no checks = no log entries = silent exit
        assert result.stdout == ""

    def test_enabled_plugin_with_tool_check(self, tmp_path):
        """Engine processes an enabled plugin's tool checks."""
        # Set up fake bootstrap root (in plugins/ subdir so registry resolution works)
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        fake_root = plugins_dir / "bootstrap"
        fake_root.mkdir()
        (fake_root / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
        (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
        (fake_root / "defaults").symlink_to(os.path.join(BOOTSTRAP_ROOT, "defaults"))
        (fake_root / "bootstrap.json").write_text(json.dumps({"tools": [], "path_entries": []}))

        # Create a test plugin with a manifest requiring a nonexistent tool
        test_plugin_dir = plugins_dir / "my-test"
        test_plugin_dir.mkdir()
        (test_plugin_dir / "bootstrap.json").write_text(json.dumps({
            "tools": [{"name": "fake_tool_xyz_999", "install": {"macos": "brew install fake"}}],
        }))

        # Create registry
        registry = {"plugins": {"my-test@kit": [{"installPath": "./my-test", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        # Create data dir with config enabling the plugin
        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {"schema_version": 3, "enabled_plugins": ["my-test@kit"], "log_level": "info", "log_success_shell": False, "log_success_checks": False}
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(config, f)

        result = run_engine(data_dir, plugin_root=str(fake_root))

        assert result.returncode == 0
        # Should emit failure JSON for the missing tool
        assert result.stdout.strip() != ""
        response = json.loads(result.stdout)
        assert response["continue"] is True
        assert "fake_tool_xyz_999" in response["hookSpecificOutput"]["additionalContext"]
        assert "[my-test]" in response["hookSpecificOutput"]["additionalContext"]

    def test_enabled_plugin_all_pass_emits_log(self, tmp_path):
        """Plugin with passing checks emits log."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        fake_root = plugins_dir / "bootstrap"
        fake_root.mkdir()
        (fake_root / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
        (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
        (fake_root / "defaults").symlink_to(os.path.join(BOOTSTRAP_ROOT, "defaults"))
        (fake_root / "bootstrap.json").write_text(json.dumps({"tools": [], "path_entries": []}))

        # Plugin that only checks for 'git' (which should be available)
        test_plugin_dir = plugins_dir / "good-plugin"
        test_plugin_dir.mkdir()
        (test_plugin_dir / "bootstrap.json").write_text(json.dumps({
            "tools": [{"name": "git", "install": {"macos": "brew install git"}}],
        }))

        registry = {"plugins": {"good-plugin@kit": [{"installPath": "./good-plugin", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {"schema_version": 3, "enabled_plugins": ["good-plugin@kit"], "log_level": "info", "log_success_shell": False, "log_success_checks": True}
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(config, f)

        result = run_engine(data_dir, plugin_root=str(fake_root))

        assert result.returncode == 0
        response = json.loads(result.stdout)
        assert response["continue"] is True
        assert "good-plugin" in response["systemMessage"]

        # Plugin cache should be written in its own data dir
        plugin_data_dir = os.path.join(str(tmp_path / "data"), "good-plugin")
        assert os.path.exists(os.path.join(plugin_data_dir, "bootstrap_cache.sha256"))

    def test_per_plugin_caching(self, tmp_path):
        """Second run hits per-plugin cache."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        fake_root = plugins_dir / "bootstrap"
        fake_root.mkdir()
        (fake_root / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
        (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
        (fake_root / "defaults").symlink_to(os.path.join(BOOTSTRAP_ROOT, "defaults"))
        (fake_root / "bootstrap.json").write_text(json.dumps({"tools": [], "path_entries": []}))

        test_plugin_dir = plugins_dir / "cached-plugin"
        test_plugin_dir.mkdir()
        (test_plugin_dir / "bootstrap.json").write_text(json.dumps({
            "tools": [{"name": "git", "install": {"macos": "brew install git"}}],
        }))

        registry = {"plugins": {"cached-plugin@kit": [{"installPath": "./cached-plugin", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {"schema_version": 3, "enabled_plugins": ["cached-plugin@kit"], "log_level": "info", "log_success_shell": False, "log_success_checks": True}
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(config, f)

        # First run
        run_engine(data_dir, plugin_root=str(fake_root))

        # Second run — hits cache, but entries already displayed → silent
        result = run_engine(data_dir, plugin_root=str(fake_root))
        assert result.returncode == 0
        # All entries were already displayed on first run
        assert result.stdout == ""

        # Verify cache entries are in the log file
        log_path = os.path.join(data_dir, "bootstrap.log")
        with open(log_path) as f:
            log_content = f.read()
        assert "cached-plugin: cached" in log_content

    def test_plugin_without_manifest_skipped(self, tmp_path):
        """Plugin with no bootstrap.json is silently skipped."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        fake_root = plugins_dir / "bootstrap"
        fake_root.mkdir()
        (fake_root / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
        (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
        (fake_root / "defaults").symlink_to(os.path.join(BOOTSTRAP_ROOT, "defaults"))
        (fake_root / "bootstrap.json").write_text(json.dumps({"tools": [], "path_entries": []}))

        # Plugin dir exists but has no bootstrap.json
        no_manifest_dir = plugins_dir / "no-manifest"
        no_manifest_dir.mkdir()

        registry = {"plugins": {"no-manifest@kit": [{"installPath": "./no-manifest", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {"schema_version": 3, "enabled_plugins": ["no-manifest@kit"], "log_level": "info", "log_success_shell": False, "log_success_checks": False}
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(config, f)

        result = run_engine(data_dir, plugin_root=str(fake_root))

        assert result.returncode == 0
        # Plugin with no manifest is skipped — nothing to log → silent exit
        assert result.stdout == ""

    def test_venv_failure_in_plugin(self, tmp_path):
        """Plugin with venv check that fails emits JSON with remediation."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        fake_root = plugins_dir / "bootstrap"
        fake_root.mkdir()
        (fake_root / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
        (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
        (fake_root / "defaults").symlink_to(os.path.join(BOOTSTRAP_ROOT, "defaults"))
        (fake_root / "bootstrap.json").write_text(json.dumps({"tools": [], "path_entries": []}))

        # Plugin that requires a venv (which won't exist)
        venv_plugin_dir = plugins_dir / "venv-plugin"
        venv_plugin_dir.mkdir()
        (venv_plugin_dir / "bootstrap.json").write_text(json.dumps({
            "venv": {"check_imports": ["yaml"]},
        }))

        registry = {"plugins": {"venv-plugin@kit": [{"installPath": "./venv-plugin", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {"schema_version": 3, "enabled_plugins": ["venv-plugin@kit"], "log_level": "info", "log_success_shell": False, "log_success_checks": False}
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(config, f)

        result = run_engine(data_dir, plugin_root=str(fake_root))

        assert result.returncode == 0
        response = json.loads(result.stdout)
        assert "venv" in response["hookSpecificOutput"]["additionalContext"].lower()
        assert "[venv-plugin]" in response["hookSpecificOutput"]["additionalContext"]

    def test_git_dep_failure_in_plugin(self, tmp_path):
        """Plugin with missing git dep emits JSON with remediation."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        fake_root = plugins_dir / "bootstrap"
        fake_root.mkdir()
        (fake_root / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
        (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
        (fake_root / "defaults").symlink_to(os.path.join(BOOTSTRAP_ROOT, "defaults"))
        (fake_root / "bootstrap.json").write_text(json.dumps({"tools": [], "path_entries": []}))

        git_plugin_dir = plugins_dir / "git-plugin"
        git_plugin_dir.mkdir()
        (git_plugin_dir / "bootstrap.json").write_text(json.dumps({
            "git_deps": [{"url": "https://github.com/octocat/Hello-World", "branch": "master"}],
        }))

        registry = {"plugins": {"git-plugin@kit": [{"installPath": "./git-plugin", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {"schema_version": 3, "enabled_plugins": ["git-plugin@kit"], "log_level": "info", "log_success_shell": False, "log_success_checks": False}
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(config, f)

        result = run_engine(data_dir, plugin_root=str(fake_root))

        assert result.returncode == 0
        response = json.loads(result.stdout)
        ctx = response["hookSpecificOutput"]["additionalContext"]
        assert "Hello-World" in ctx
        assert "[git-plugin]" in ctx
