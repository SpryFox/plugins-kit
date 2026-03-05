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
    def test_first_run_bare_exit(self, data_dir):
        """All tools in the real manifest (uv, git) should be present on dev machines."""
        result = run_engine(data_dir)
        assert result.returncode == 0
        assert result.stdout == ""  # Bare exit = no stdout
        # Cache and log should be written
        assert os.path.exists(os.path.join(data_dir, "bootstrap_cache.sha256"))
        assert os.path.exists(os.path.join(data_dir, "bootstrap.log"))

    def test_cached_run_bare_exit(self, data_dir):
        """Second run should hit cache — still bare exit."""
        run_engine(data_dir)  # First run populates cache
        result = run_engine(data_dir)  # Second run hits cache
        assert result.returncode == 0
        assert result.stdout == ""
        # Log should contain "cached" entry
        log_path = os.path.join(data_dir, "bootstrap.log")
        with open(log_path) as f:
            content = f.read()
        assert "cached" in content

    def test_failure_emits_json(self, data_dir, tmp_path):
        """A manifest with a fake tool should produce JSON failure output."""
        # Create a fake plugin root with a manifest referencing a nonexistent tool
        fake_root = tmp_path / "fake_plugin"
        fake_root.mkdir()
        (fake_root / "lib").symlink_to(os.path.join(BOOTSTRAP_ROOT, "lib"))
        (fake_root / "engine").symlink_to(os.path.join(BOOTSTRAP_ROOT, "engine"))
        (fake_root / "defaults").symlink_to(os.path.join(BOOTSTRAP_ROOT, "defaults"))

        manifest = {
            "tools": [{"name": "nonexistent_tool_xyz_abc", "install": {"macos": "brew install fake"}}],
            "path_entries": [],
        }
        (fake_root / "bootstrap.json").write_text(json.dumps(manifest))

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
        (fake_root / "defaults").symlink_to(os.path.join(BOOTSTRAP_ROOT, "defaults"))

        # Install command succeeds (python -c pass) but tool still won't exist after
        manifest = {
            "tools": [{
                "name": "nonexistent_tool_xyz_abc",
                "install": {
                    "macos": f"{sys.executable} -c 'pass'",
                    "windows": f"{sys.executable} -c 'pass'",
                    "ubuntu": f"{sys.executable} -c 'pass'",
                },
            }],
        }
        (fake_root / "bootstrap.json").write_text(json.dumps(manifest))

        result = run_engine(data_dir, plugin_root=str(fake_root))
        assert result.returncode == 0
        assert result.stdout.strip() != ""

        response = json.loads(result.stdout)
        assert response["continue"] is True
        assert "nonexistent_tool_xyz_abc" in response["hookSpecificOutput"]["additionalContext"]

    def test_config_migration_on_run(self, data_dir):
        """Engine should migrate v0 config to v1 on first run."""
        # Pre-create a v0 config
        os.makedirs(data_dir, exist_ok=True)
        v0_config = {"some_setting": True}
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump(v0_config, f)

        result = run_engine(data_dir)
        assert result.returncode == 0

        # Config should now be v1
        with open(os.path.join(data_dir, "config.json")) as f:
            config = json.load(f)
        assert config["schema_version"] == 1
        assert config["some_setting"] is True
