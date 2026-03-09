"""Integration tests for bootstrap engine --background mode."""

import json
import os
import subprocess
import sys

import pytest

BOOTSTRAP_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "bootstrap")
)
ENGINE_SCRIPT = os.path.join(BOOTSTRAP_ROOT, "engine", "bootstrap_engine.py")


def run_engine(data_dir, plugin_root=BOOTSTRAP_ROOT, extra_args=None):
    """Run the bootstrap engine as a subprocess."""
    cmd = [sys.executable, ENGINE_SCRIPT, "--plugin-root", plugin_root, "--data-dir", data_dir]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)


def _make_minimal_root(tmp_path, config_overrides=None):
    """Create a fake bootstrap root with minimal ecosystem manifest."""
    fake_root = tmp_path / "bootstrap_bg"
    fake_root.mkdir(exist_ok=True)
    (fake_root / "bootstrap_lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "bootstrap_lib"))
    (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
    defaults = fake_root / "defaults"
    defaults.mkdir(exist_ok=True)
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
    if config_overrides:
        config.update(config_overrides)
    (defaults / "config.json").write_text(json.dumps(config))
    (fake_root / "bootstrap.json").write_text(json.dumps({}))
    return str(fake_root)


class TestEngineBackground:
    def test_background_writes_display_file(self, data_dir, tmp_path):
        """Engine with --background creates bootstrap_display.pending when there's output."""
        fake_root = _make_minimal_root(tmp_path, {"log_success_checks": True})
        result = run_engine(data_dir, plugin_root=fake_root, extra_args=["--background"])
        assert result.returncode == 0
        display_file = os.path.join(data_dir, "bootstrap_display.pending")
        assert os.path.isfile(display_file)

    def test_background_no_stdout(self, data_dir, tmp_path):
        """In background mode, stdout is empty (output goes to file)."""
        fake_root = _make_minimal_root(tmp_path, {"log_success_checks": True})
        result = run_engine(data_dir, plugin_root=fake_root, extra_args=["--background"])
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_background_success_format(self, data_dir, tmp_path):
        """Display file has Stop-hook-compliant JSON (no hookSpecificOutput)."""
        fake_root = _make_minimal_root(tmp_path, {"log_success_checks": True})
        run_engine(data_dir, plugin_root=fake_root, extra_args=["--background"])
        display_file = os.path.join(data_dir, "bootstrap_display.pending")
        with open(display_file) as f:
            response = json.load(f)
        assert response["continue"] is True
        assert response["suppressOutput"] is False
        assert "systemMessage" in response
        assert "bootstrap complete" in response["systemMessage"]
        # Stop hooks do NOT support hookSpecificOutput
        assert "hookSpecificOutput" not in response

    def test_background_failure_format(self, data_dir, tmp_path):
        """Display file includes remediation in systemMessage (no hookSpecificOutput)."""
        fake_root = tmp_path / "fake_plugin_bg"
        fake_root.mkdir()
        (fake_root / "bootstrap_lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "bootstrap_lib"))
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

        result = run_engine(data_dir, plugin_root=str(fake_root), extra_args=["--background"])
        assert result.returncode == 0
        assert result.stdout.strip() == ""

        display_file = os.path.join(data_dir, "bootstrap_display.pending")
        assert os.path.isfile(display_file)
        with open(display_file) as f:
            response = json.load(f)
        # Stop hooks do NOT support hookSpecificOutput
        assert "hookSpecificOutput" not in response
        # Remediation instructions merged into systemMessage
        assert "nonexistent_tool_xyz_abc" in response["systemMessage"]

    def test_foreground_has_hook_specific_output(self, data_dir, tmp_path):
        """Non-background (SessionStart) output retains hookSpecificOutput."""
        fake_root = _make_minimal_root(tmp_path, {"log_success_checks": True})
        result = run_engine(data_dir, plugin_root=fake_root)
        assert result.returncode == 0
        response = json.loads(result.stdout.strip())
        assert response["hookSpecificOutput"]["hookEventName"] == "SessionStart"

    def test_background_silent_no_file(self, data_dir, tmp_path):
        """When everything is ok and log_success is false, no display file is created."""
        fake_root = _make_minimal_root(tmp_path)
        result = run_engine(data_dir, plugin_root=fake_root, extra_args=["--background"])
        assert result.returncode == 0
        display_file = os.path.join(data_dir, "bootstrap_display.pending")
        assert not os.path.isfile(display_file)

    def test_console_mode_unaffected(self, data_dir, tmp_path):
        """--console still prints to stdout regardless of --background."""
        fake_root = _make_minimal_root(tmp_path)
        result = run_engine(data_dir, plugin_root=fake_root, extra_args=["--console"])
        assert result.returncode == 0
        # Console mode prints plain text to stdout (verbose by default)
        # No display file should be created
        display_file = os.path.join(data_dir, "bootstrap_display.pending")
        assert not os.path.isfile(display_file)
