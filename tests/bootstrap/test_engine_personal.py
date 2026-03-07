"""Tests for personal config (user-bootstrap.json) in bootstrap engine."""

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
    return subprocess.run(
        [sys.executable, ENGINE_SCRIPT, "--plugin-root", plugin_root, "--data-dir", data_dir],
        capture_output=True,
        text=True,
    )


def make_minimal_root(tmp_path):
    """Create a fake bootstrap root with no requirements."""
    fake_root = tmp_path / "bootstrap_minimal"
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
        "self_setup": {},
    }
    (defaults / "config.json").write_text(json.dumps(config))
    (fake_root / "bootstrap.json").write_text(json.dumps({}))
    return str(fake_root)


class TestPersonalConfig:
    def test_no_user_bootstrap_is_silent(self, data_dir, tmp_path):
        """Without user-bootstrap.json, engine runs normally."""
        fake_root = make_minimal_root(tmp_path)
        result = run_engine(data_dir, plugin_root=fake_root)
        assert result.returncode == 0

    def test_user_bootstrap_processed(self, data_dir, tmp_path):
        """user-bootstrap.json in data_dir is processed by the engine."""
        fake_root = make_minimal_root(tmp_path)

        # Create user-bootstrap.json with a tool check
        user_manifest = {"tools": [{"name": "git", "install": {"macos": "brew install git"}}]}
        user_path = os.path.join(data_dir, "user-bootstrap.json")
        with open(user_path, "w") as f:
            json.dump(user_manifest, f)

        # Enable success logging to see output
        config_path = os.path.join(data_dir, "config.json")
        with open(config_path, "w") as f:
            json.dump({"schema_version": 3, "log_success_checks": True, "enabled_plugins": []}, f)

        result = run_engine(data_dir, plugin_root=fake_root)
        assert result.returncode == 0

    def test_user_bootstrap_cached(self, data_dir, tmp_path):
        """Second run should hit cache for user-bootstrap.json."""
        fake_root = make_minimal_root(tmp_path)

        user_manifest = {"tools": []}
        user_path = os.path.join(data_dir, "user-bootstrap.json")
        with open(user_path, "w") as f:
            json.dump(user_manifest, f)

        run_engine(data_dir, plugin_root=fake_root)  # First run
        result = run_engine(data_dir, plugin_root=fake_root)  # Second run
        assert result.returncode == 0

    def test_user_bootstrap_failure_emits_json(self, data_dir, tmp_path):
        """user-bootstrap.json failures appear in output."""
        fake_root = make_minimal_root(tmp_path)

        user_manifest = {"tools": [{"name": "nonexistent_tool_xyz_personal"}]}
        user_path = os.path.join(data_dir, "user-bootstrap.json")
        with open(user_path, "w") as f:
            json.dump(user_manifest, f)

        result = run_engine(data_dir, plugin_root=fake_root)
        assert result.returncode == 0
        assert result.stdout.strip() != ""
        response = json.loads(result.stdout)
        assert "nonexistent_tool_xyz_personal" in response["hookSpecificOutput"]["additionalContext"]
