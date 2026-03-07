"""Integration tests for bootstrap engine/bootstrap_engine.py."""

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


class TestEngineIntegration:
    @staticmethod
    def _make_minimal_root(tmp_path):
        """Create a fake bootstrap root with minimal ecosystem manifest."""
        fake_root = tmp_path / "bootstrap_minimal"
        fake_root.mkdir()
        (fake_root / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
        (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
        # Custom defaults with self_setup containing tools
        defaults = fake_root / "defaults"
        defaults.mkdir()
        config = {
            "schema_version": 5,
            "no_bootstrap": [],
            "bootstrap_cache": [],
            "log_success_shell": False,
            "log_success_checks": False,
            "self_setup": {
                "tools": [{"name": "git", "install": {"macos": "brew install git"}}],
                "path_entries": ["~/.local/bin"],
            },
        }
        (defaults / "config.json").write_text(json.dumps(config))
        manifest = {}
        (fake_root / "bootstrap.json").write_text(json.dumps(manifest))
        return str(fake_root)

    def test_first_run_silent_on_success(self, data_dir, tmp_path):
        """With log_success disabled, successful runs produce no output."""
        fake_root = self._make_minimal_root(tmp_path)
        result = run_engine(data_dir, plugin_root=fake_root)
        assert result.returncode == 0
        # No stdout when everything succeeds and success logging is off
        assert result.stdout.strip() == ""

    def test_cached_run_silent(self, data_dir, tmp_path):
        """Second run should hit cache — no output with success logging off."""
        fake_root = self._make_minimal_root(tmp_path)
        run_engine(data_dir, plugin_root=fake_root)  # First run populates cache
        result = run_engine(data_dir, plugin_root=fake_root)  # Second run hits cache
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_failure_emits_json(self, data_dir, tmp_path):
        """A self_setup with a fake tool should produce JSON failure output."""
        fake_root = tmp_path / "fake_plugin"
        fake_root.mkdir()
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
            "self_setup": {
                "tools": [{"name": "nonexistent_tool_xyz_abc", "install": {"macos": "brew install fake"}}],
            },
        }
        (defaults / "config.json").write_text(json.dumps(config))
        (fake_root / "bootstrap.json").write_text(json.dumps({}))

        result = run_engine(data_dir, plugin_root=str(fake_root))
        assert result.returncode == 0
        assert result.stdout.strip() != ""

        response = json.loads(result.stdout)
        assert response["continue"] is True
        assert "hookSpecificOutput" in response
        assert "nonexistent_tool_xyz_abc" in response["hookSpecificOutput"]["additionalContext"]

    def test_remediation_attempted_but_still_fails(self, data_dir, tmp_path):
        """When install command runs but tool is still missing, failure JSON is emitted."""
        fake_root = tmp_path / "fake_plugin"
        fake_root.mkdir()
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
            "self_setup": {
                "tools": [{
                    "name": "nonexistent_tool_xyz_abc",
                    "install": {
                        "macos": f"{sys.executable} -c 'pass'",
                        "windows": f"{sys.executable} -c 'pass'",
                        "ubuntu": f"{sys.executable} -c 'pass'",
                    },
                }],
            },
        }
        (defaults / "config.json").write_text(json.dumps(config))
        (fake_root / "bootstrap.json").write_text(json.dumps({}))

        result = run_engine(data_dir, plugin_root=str(fake_root))
        assert result.returncode == 0
        assert result.stdout.strip() != ""

        response = json.loads(result.stdout)
        assert response["continue"] is True
        assert "nonexistent_tool_xyz_abc" in response["hookSpecificOutput"]["additionalContext"]

    def test_config_migration_on_run(self, data_dir):
        """Engine should migrate v0 config to current version on first run."""
        # Pre-create a v0 config
        os.makedirs(data_dir, exist_ok=True)
        v0_config = {"some_setting": True}
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(v0_config, f)

        result = run_engine(data_dir)
        assert result.returncode == 0

        # Config should now be current version
        with open(os.path.join(data_dir, "config.json")) as f:
            config = json.load(f)
        assert config["schema_version"] == 5
        assert config["some_setting"] is True
        assert config["log_success_shell"] is False
        assert config["log_success_checks"] is False
