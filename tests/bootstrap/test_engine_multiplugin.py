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


def _write_minimal_defaults(fake_root):
    """Write a minimal defaults/config.json with empty self_setup."""
    defaults = fake_root / "defaults"
    defaults.mkdir(exist_ok=True)
    config = {
        "schema_version": 5,
        "no_bootstrap": [],
        "bootstrap_cache": [],
        "log_success_shell": False,
        "log_success_checks": False,
        "self_setup": {},
    }
    (defaults / "config.json").write_text(json.dumps(config))


def make_fake_bootstrap_root(tmp_path, manifest=None, self_setup=None):
    """Create a fake bootstrap plugin root with symlinked lib/engine and custom defaults."""
    fake_root = tmp_path / "bootstrap"
    fake_root.mkdir(parents=True)
    (fake_root / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
    (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
    defaults = fake_root / "defaults"
    defaults.mkdir()
    config = {
        "schema_version": 5,
        "no_bootstrap": [],
        "bootstrap_cache": [],
        "log_success_shell": False,
        "log_success_checks": False,
        "self_setup": self_setup or {},
    }
    (defaults / "config.json").write_text(json.dumps(config))

    if manifest is None:
        manifest = {}
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
        _write_minimal_defaults(fake_root)
        (fake_root / "bootstrap.json").write_text(json.dumps({}))

        # Create a test plugin with a manifest requiring a nonexistent tool
        test_plugin_dir = plugins_dir / "my-test"
        test_plugin_dir.mkdir()
        (test_plugin_dir / "bootstrap.json").write_text(json.dumps({
            "tools": [{"name": "fake_tool_xyz_999", "install": {"macos": "brew install fake"}}],
        }))

        # Create registry
        registry = {"plugins": {"kit:my-test": [{"installPath": "./my-test", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        # Create data dir with config enabling the plugin
        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {"schema_version": 3, "enabled_plugins": ["kit:my-test"], "log_level": "info", "log_success_shell": False, "log_success_checks": False}
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
        _write_minimal_defaults(fake_root)
        (fake_root / "bootstrap.json").write_text(json.dumps({}))

        # Plugin that only checks for 'git' (which should be available)
        test_plugin_dir = plugins_dir / "good-plugin"
        test_plugin_dir.mkdir()
        (test_plugin_dir / "bootstrap.json").write_text(json.dumps({
            "tools": [{"name": "git", "install": {"macos": "brew install git"}}],
        }))

        registry = {"plugins": {"kit:good-plugin": [{"installPath": "./good-plugin", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {"schema_version": 3, "enabled_plugins": ["kit:good-plugin"], "log_level": "info", "log_success_shell": False, "log_success_checks": True}
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(config, f)

        result = run_engine(data_dir, plugin_root=str(fake_root))

        assert result.returncode == 0
        response = json.loads(result.stdout)
        assert response["continue"] is True
        assert "good-plugin" in response["systemMessage"]

    def test_plugin_log_written_to_own_data_dir(self, tmp_path):
        """Plugin log entries are written to plugin's own data dir, not bootstrap's."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        fake_root = plugins_dir / "bootstrap"
        fake_root.mkdir()
        (fake_root / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
        (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
        _write_minimal_defaults(fake_root)
        (fake_root / "bootstrap.json").write_text(json.dumps({}))

        test_plugin_dir = plugins_dir / "logged-plugin"
        test_plugin_dir.mkdir()
        (test_plugin_dir / "bootstrap.json").write_text(json.dumps({
            "tools": [{"name": "git", "install": {"macos": "brew install git"}}],
        }))

        registry = {"plugins": {"kit:logged-plugin": [{"installPath": "./logged-plugin", "version": "2.3.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {"schema_version": 3, "enabled_plugins": ["kit:logged-plugin"], "log_level": "info", "log_success_shell": False, "log_success_checks": True}
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(config, f)

        result = run_engine(data_dir, plugin_root=str(fake_root))
        assert result.returncode == 0

        # Plugin log should be in plugin's own data dir with version in header
        plugin_data_dir = os.path.join(str(tmp_path / "data"), "logged-plugin")
        plugin_log = os.path.join(plugin_data_dir, "bootstrap.log")
        assert os.path.exists(plugin_log)
        with open(plugin_log) as f:
            content = f.read()
        assert "logged-plugin@2.3.0" in content
        assert "git" in content

        # Bootstrap's own log should NOT contain plugin entries
        bootstrap_log = os.path.join(data_dir, "bootstrap.log")
        if os.path.exists(bootstrap_log):
            with open(bootstrap_log) as f:
                bootstrap_content = f.read()
            assert "logged-plugin" not in bootstrap_content

        # But the hook response should still show plugin entries to the user
        response = json.loads(result.stdout)
        assert "logged-plugin" in response["systemMessage"]

    def test_second_run_reruns_checks(self, tmp_path):
        """Second run re-runs all checks — no cache gate."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        fake_root = plugins_dir / "bootstrap"
        fake_root.mkdir()
        (fake_root / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
        (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
        _write_minimal_defaults(fake_root)
        (fake_root / "bootstrap.json").write_text(json.dumps({}))

        test_plugin_dir = plugins_dir / "rerun-plugin"
        test_plugin_dir.mkdir()
        (test_plugin_dir / "bootstrap.json").write_text(json.dumps({
            "tools": [{"name": "git", "install": {"macos": "brew install git"}}],
        }))

        registry = {"plugins": {"kit:rerun-plugin": [{"installPath": "./rerun-plugin", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {"schema_version": 3, "enabled_plugins": ["kit:rerun-plugin"], "log_level": "info", "log_success_shell": False, "log_success_checks": True}
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(config, f)

        # First run
        run_engine(data_dir, plugin_root=str(fake_root))

        # Second run — re-runs checks, produces output
        result = run_engine(data_dir, plugin_root=str(fake_root))
        assert result.returncode == 0
        response = json.loads(result.stdout)
        assert "rerun-plugin" in response["systemMessage"]

    def test_plugin_without_manifest_skipped(self, tmp_path):
        """Plugin with no bootstrap.json is silently skipped."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        fake_root = plugins_dir / "bootstrap"
        fake_root.mkdir()
        (fake_root / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
        (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
        _write_minimal_defaults(fake_root)
        (fake_root / "bootstrap.json").write_text(json.dumps({}))

        # Plugin dir exists but has no bootstrap.json
        no_manifest_dir = plugins_dir / "no-manifest"
        no_manifest_dir.mkdir()

        registry = {"plugins": {"kit:no-manifest": [{"installPath": "./no-manifest", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {"schema_version": 3, "enabled_plugins": ["kit:no-manifest"], "log_level": "info", "log_success_shell": False, "log_success_checks": False}
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
        _write_minimal_defaults(fake_root)
        (fake_root / "bootstrap.json").write_text(json.dumps({}))

        # Plugin that requires a venv (which won't exist)
        venv_plugin_dir = plugins_dir / "venv-plugin"
        venv_plugin_dir.mkdir()
        (venv_plugin_dir / "bootstrap.json").write_text(json.dumps({
            "venv": {"check_imports": ["yaml"]},
        }))

        registry = {"plugins": {"kit:venv-plugin": [{"installPath": "./venv-plugin", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {"schema_version": 3, "enabled_plugins": ["kit:venv-plugin"], "log_level": "info", "log_success_shell": False, "log_success_checks": False}
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
        _write_minimal_defaults(fake_root)
        (fake_root / "bootstrap.json").write_text(json.dumps({}))

        git_plugin_dir = plugins_dir / "git-plugin"
        git_plugin_dir.mkdir()
        (git_plugin_dir / "bootstrap.json").write_text(json.dumps({
            "git_deps": [{"url": "https://invalid.example.invalid/nonexistent/repo", "branch": "main"}],
        }))

        registry = {"plugins": {"kit:git-plugin": [{"installPath": "./git-plugin", "version": "1.0.0"}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {"schema_version": 3, "enabled_plugins": ["kit:git-plugin"], "log_level": "info", "log_success_shell": False, "log_success_checks": False}
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(config, f)

        result = run_engine(data_dir, plugin_root=str(fake_root))

        assert result.returncode == 0
        response = json.loads(result.stdout)
        ctx = response["hookSpecificOutput"]["additionalContext"]
        assert "invalid.example.invalid" in ctx
        assert "[git-plugin]" in ctx

    def test_cache_layout_finds_registry(self, tmp_path):
        """Registry found when bootstrap is nested deep (cache layout)."""
        # Simulate cache layout: plugins/cache/mkt/bootstrap/0.5.0/
        cache_dir = tmp_path / "plugins" / "cache" / "mymkt" / "bootstrap" / "0.5.0"
        cache_dir.mkdir(parents=True)
        (cache_dir / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
        (cache_dir / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
        _write_minimal_defaults(cache_dir)
        (cache_dir / "bootstrap.json").write_text(json.dumps({}))

        # Plugin at cache/mymkt/deep-plugin/1.0.0/
        deep_plugin_dir = tmp_path / "plugins" / "cache" / "mymkt" / "deep-plugin" / "1.0.0"
        deep_plugin_dir.mkdir(parents=True)
        (deep_plugin_dir / "bootstrap.json").write_text(json.dumps({
            "tools": [{"name": "git", "install": {"macos": "brew install git"}}],
        }))

        # Registry at plugins/installed_plugins.json (two levels above cache/mymkt/)
        registry = {"plugins": {"mymkt:deep-plugin": [{"installPath": str(deep_plugin_dir), "version": "1.0.0"}]}}
        (tmp_path / "plugins" / "installed_plugins.json").write_text(json.dumps(registry))

        data_dir = str(tmp_path / "data" / "bootstrap")
        os.makedirs(data_dir)
        config = {"schema_version": 3, "enabled_plugins": ["mymkt:deep-plugin"], "log_level": "info", "log_success_shell": False, "log_success_checks": True}
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(config, f)

        result = run_engine(data_dir, plugin_root=str(cache_dir))
        assert result.returncode == 0
        response = json.loads(result.stdout)
        assert "deep-plugin" in response["systemMessage"]
