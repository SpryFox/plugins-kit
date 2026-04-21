"""Tests for p4-kit scripts/run-review.py."""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# run-review.py has a hyphen, so we need importlib to load it
_spec = importlib.util.spec_from_file_location(
    "run_review",
    os.path.join(
        os.path.dirname(__file__),
        os.pardir, os.pardir,
        "plugins", "p4-kit", "scripts", "run-review.py",
    ),
)
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)

read_config = rr.read_config
_resolve_data_dir = rr._resolve_data_dir
_die = rr._die
main = rr.main


# ---------------------------------------------------------------------------
# read_config
# ---------------------------------------------------------------------------


class TestReadConfig:
    def test_valid_quoted_values(self, sample_config):
        path = sample_config('P4PORT: "ssl:host:1666"\nP4USER: "alice"\n')
        result = read_config(path)
        assert result == {"P4PORT": "ssl:host:1666", "P4USER": "alice"}

    def test_comments_and_blanks_skipped(self, sample_config):
        path = sample_config("# Comment\n\nP4USER: alice\n# Another\n")
        result = read_config(path)
        assert result == {"P4USER": "alice"}

    def test_missing_file_returns_empty(self):
        result = read_config("/nonexistent/path/config.yaml")
        assert result == {}

    def test_strips_single_quotes(self, sample_config):
        path = sample_config("P4PORT: 'ssl:host:1666'\n")
        result = read_config(path)
        assert result == {"P4PORT": "ssl:host:1666"}

    def test_line_without_colon_skipped(self, sample_config):
        path = sample_config("no-colon-here\nP4USER: bob\n")
        result = read_config(path)
        assert result == {"P4USER": "bob"}


# ---------------------------------------------------------------------------
# _resolve_data_dir
# ---------------------------------------------------------------------------


class TestResolveDataDir:
    def test_env_var_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PLUGIN_DATA_DIR", str(tmp_path))
        assert _resolve_data_dir() == tmp_path.resolve()

    def test_default_path(self, monkeypatch):
        monkeypatch.delenv("PLUGIN_DATA_DIR", raising=False)
        result = _resolve_data_dir()
        expected = Path("~/.claude/plugins/data/plugins-kit/p4-kit").expanduser().resolve()
        assert result == expected

    def test_expands_tilde(self, monkeypatch):
        monkeypatch.setenv("PLUGIN_DATA_DIR", "~/my-data")
        result = _resolve_data_dir()
        assert "~" not in str(result)
        assert result == Path("~/my-data").expanduser().resolve()


# ---------------------------------------------------------------------------
# _die
# ---------------------------------------------------------------------------


class TestDie:
    def test_prints_to_stderr_and_exits(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            _die("something broke")
        assert exc_info.value.code == 1
        assert "something broke" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# main — error paths
# ---------------------------------------------------------------------------


class TestMainErrors:
    def _write_config(self, tmp_path, content="DEFAULT_AGENT: \"claude-haiku\"\n"):
        """Helper: write a config.yaml and set PLUGIN_DATA_DIR."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(content)
        return str(tmp_path)

    def test_missing_config_exits(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PLUGIN_DATA_DIR", str(tmp_path))
        monkeypatch.setattr(sys, "argv", ["run-review.py", "12345"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_no_agent_specified_exits(self, monkeypatch, tmp_path):
        data_dir = self._write_config(tmp_path, "P4PORT: \"host:1666\"\n")
        monkeypatch.setenv("PLUGIN_DATA_DIR", data_dir)
        monkeypatch.setattr(sys, "argv", ["run-review.py", "12345"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_missing_code_review_root_exits(self, monkeypatch, tmp_path):
        data_dir = self._write_config(tmp_path)
        monkeypatch.setenv("PLUGIN_DATA_DIR", data_dir)
        monkeypatch.setattr(sys, "argv", ["run-review.py", "12345"])
        # github/code-review-research doesn't exist under tmp_path
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_missing_diff_file_exits(self, monkeypatch, tmp_path):
        data_dir = self._write_config(tmp_path)
        monkeypatch.setenv("PLUGIN_DATA_DIR", data_dir)
        # Create the expected code-review-research directory
        cr_root = tmp_path / "github" / "code-review-research"
        cr_root.mkdir(parents=True)
        monkeypatch.setattr(
            sys, "argv",
            ["run-review.py", "12345", "--diff-file", "/nonexistent/file.diff"],
        )
        # Mock the code_review imports that happen after directory checks
        mock_lac = MagicMock()
        mock_bp = MagicMock()
        mock_rr = MagicMock()
        with patch.dict("sys.modules", {
            "code_review": MagicMock(),
            "code_review.config": MagicMock(load_agent_config=mock_lac),
            "code_review.review_engine": MagicMock(build_prompts=mock_bp, run_review=mock_rr),
        }):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# main — dry-run
# ---------------------------------------------------------------------------


class TestMainDryRun:
    def test_dry_run_prints_prompts_to_stderr(self, monkeypatch, tmp_path, capsys):
        # Set up data dir with config
        config_path = tmp_path / "config.yaml"
        config_path.write_text('DEFAULT_AGENT: "test-agent"\n')
        monkeypatch.setenv("PLUGIN_DATA_DIR", str(tmp_path))

        # Create code-review-research directory
        cr_root = tmp_path / "github" / "code-review-research"
        cr_root.mkdir(parents=True)

        # Create a diff file
        diff_file = tmp_path / "test.diff"
        diff_file.write_text("--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new\n")

        monkeypatch.setattr(
            sys, "argv",
            ["run-review.py", "12345", "--diff-file", str(diff_file), "--dry-run"],
        )

        # Mock code_review modules
        mock_agent_config = MagicMock()
        mock_prompts = MagicMock()
        mock_prompts.system_prompt = "System prompt content"
        mock_prompts.user_prompt = "User prompt content"
        mock_prompts.overflow_files = []

        mock_load = MagicMock(return_value=mock_agent_config)
        mock_build = MagicMock(return_value=mock_prompts)

        with patch.dict("sys.modules", {
            "code_review": MagicMock(),
            "code_review.config": MagicMock(load_agent_config=mock_load),
            "code_review.review_engine": MagicMock(build_prompts=mock_build, run_review=MagicMock()),
        }):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0
        stderr = capsys.readouterr().err
        assert "SYSTEM PROMPT" in stderr
        assert "System prompt content" in stderr
        assert "USER PROMPT" in stderr


# ---------------------------------------------------------------------------
# main — JSON output
# ---------------------------------------------------------------------------


class TestMainJsonOutput:
    def test_json_output_serializes_result(self, monkeypatch, tmp_path, capsys):
        # Set up data dir with config
        config_path = tmp_path / "config.yaml"
        config_path.write_text('DEFAULT_AGENT: "test-agent"\n')
        monkeypatch.setenv("PLUGIN_DATA_DIR", str(tmp_path))

        # Create code-review-research directory
        cr_root = tmp_path / "github" / "code-review-research"
        cr_root.mkdir(parents=True)

        # Create a diff file
        diff_file = tmp_path / "test.diff"
        diff_file.write_text("--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new\n")

        monkeypatch.setattr(
            sys, "argv",
            ["run-review.py", "12345", "--json", "--diff-file", str(diff_file)],
        )

        # Mock code_review modules
        mock_agent_config = MagicMock()
        fake_result = MagicMock()
        fake_result.model_dump.return_value = {
            "changelist": "12345",
            "agent": "test-agent",
            "findings": [{"message": "test finding", "severity": "medium"}],
        }

        mock_load = MagicMock(return_value=mock_agent_config)
        mock_run = MagicMock(return_value=fake_result)

        with patch.dict("sys.modules", {
            "code_review": MagicMock(),
            "code_review.config": MagicMock(load_agent_config=mock_load),
            "code_review.review_engine": MagicMock(build_prompts=MagicMock(), run_review=mock_run),
        }):
            main()

        stdout = capsys.readouterr().out
        data = json.loads(stdout)
        assert data["changelist"] == "12345"
        assert data["agent"] == "test-agent"
        assert len(data["findings"]) == 1
