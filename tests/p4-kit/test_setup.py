"""Tests for p4-kit scripts/setup.py."""

import json
import os
import subprocess
import sys

import pytest

import setup as setup_mod
from setup import (
    REQUIRED_FIELDS,
    _has_real_key,
    _is_set,
    do_apply,
    do_check,
    do_init_defaults,
    main,
    read_config,
    write_config,
)


# ---------------------------------------------------------------------------
# read_config
# ---------------------------------------------------------------------------


class TestReadConfig:
    def test_valid_quoted_values(self, sample_config):
        path = sample_config('P4PORT: "ssl:host:1666"\nP4USER: "alice"\n')
        result = read_config(path)
        assert result == {"P4PORT": "ssl:host:1666", "P4USER": "alice"}

    def test_valid_unquoted_values(self, sample_config):
        path = sample_config("P4PORT: ssl:host:1666\nP4USER: alice\n")
        result = read_config(path)
        assert result == {"P4PORT": "ssl:host:1666", "P4USER": "alice"}

    def test_single_quoted_values(self, sample_config):
        path = sample_config("P4PORT: 'ssl:host:1666'\n")
        result = read_config(path)
        assert result == {"P4PORT": "ssl:host:1666"}

    def test_missing_file_returns_empty(self):
        result = read_config("/nonexistent/path/config.yaml")
        assert result == {}

    def test_comments_and_blank_lines_ignored(self, sample_config):
        path = sample_config("# Comment\n\nP4USER: alice\n# Another comment\n")
        result = read_config(path)
        assert result == {"P4USER": "alice"}

    def test_empty_value(self, sample_config):
        path = sample_config('OPENAI_API_KEY: ""\n')
        result = read_config(path)
        assert result == {"OPENAI_API_KEY": ""}

    def test_line_without_colon_skipped(self, sample_config):
        path = sample_config("no-colon-here\nP4USER: bob\n")
        result = read_config(path)
        assert result == {"P4USER": "bob"}


# ---------------------------------------------------------------------------
# write_config
# ---------------------------------------------------------------------------


class TestWriteConfig:
    def test_writes_quoted_yaml(self, tmp_path):
        path = str(tmp_path / "out.yaml")
        write_config(path, {"P4USER": "alice", "P4PORT": "host:1666"})
        content = open(path).read()
        assert 'P4USER: "alice"' in content
        assert 'P4PORT: "host:1666"' in content

    def test_creates_parent_directories(self, tmp_path):
        path = str(tmp_path / "deep" / "nested" / "config.yaml")
        write_config(path, {"KEY": "val"})
        assert os.path.isfile(path)

    def test_roundtrip(self, tmp_path):
        path = str(tmp_path / "rt.yaml")
        original = {"P4USER": "alice", "P4PORT": "host:1666", "DEFAULT_AGENT": "claude-opus"}
        write_config(path, original)
        result = read_config(path)
        assert result == original


# ---------------------------------------------------------------------------
# _is_set / _has_real_key
# ---------------------------------------------------------------------------


class TestIsSet:
    def test_empty_string_false(self):
        assert _is_set("") is False

    def test_none_value_true(self):
        assert _is_set("none") is True

    def test_real_value_true(self):
        assert _is_set("sk-abc123") is True


class TestHasRealKey:
    def test_empty_string_false(self):
        assert _has_real_key("") is False

    def test_none_lowercase_false(self):
        assert _has_real_key("none") is False

    def test_none_uppercase_false(self):
        assert _has_real_key("NONE") is False

    def test_none_mixed_case_false(self):
        assert _has_real_key("None") is False

    def test_real_value_true(self):
        assert _has_real_key("sk-abc123") is True


# ---------------------------------------------------------------------------
# do_check
# ---------------------------------------------------------------------------


class TestDoCheck:
    def test_all_fields_set_returns_0(self, data_dir, full_config_data):
        write_config(os.path.join(data_dir, "config.yaml"), full_config_data)
        assert do_check(data_dir) == 0

    def test_missing_fields_returns_1(self, data_dir, capsys):
        partial = {"P4USER": "alice", "DEFAULT_AGENT": "claude-opus"}
        write_config(os.path.join(data_dir, "config.yaml"), partial)
        assert do_check(data_dir) == 1

        output = json.loads(capsys.readouterr().out)
        assert output["status"] == "needs_setup"
        assert "OPENAI_API_KEY" in output["missing_fields"]
        assert "P4USER" not in output["missing_fields"]

    def test_no_config_file_returns_1(self, data_dir, capsys):
        assert do_check(data_dir) == 1
        output = json.loads(capsys.readouterr().out)
        assert output["status"] == "needs_setup"
        assert len(output["missing_fields"]) == len(REQUIRED_FIELDS)

    def test_none_values_count_as_set(self, data_dir):
        config = {
            "OPENAI_API_KEY": "none",
            "OPENROUTER_API_KEY": "none",
            "P4PORT": "ssl:host:1666",
            "P4USER": "alice",
            "DEFAULT_AGENT": "claude-opus",
        }
        write_config(os.path.join(data_dir, "config.yaml"), config)
        assert do_check(data_dir) == 0


# ---------------------------------------------------------------------------
# do_apply
# ---------------------------------------------------------------------------


class TestDoApply:
    def test_valid_key_value_writes_config(self, data_dir, capsys):
        result = do_apply(data_dir, ["P4USER=alice"])
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        assert output["status"] == "ok"
        assert "P4USER" in output["fields_written"]

        config = read_config(os.path.join(data_dir, "config.yaml"))
        assert config["P4USER"] == "alice"

    def test_invalid_format_returns_2(self, data_dir, capsys):
        result = do_apply(data_dir, ["NO_EQUALS_SIGN"])
        assert result == 2
        assert "Invalid" in capsys.readouterr().err

    def test_unknown_field_returns_2(self, data_dir, capsys):
        result = do_apply(data_dir, ["UNKNOWN_FIELD=value"])
        assert result == 2
        assert "Unknown field" in capsys.readouterr().err

    def test_merges_with_existing(self, data_dir):
        write_config(os.path.join(data_dir, "config.yaml"), {"P4USER": "alice"})
        do_apply(data_dir, ["P4PORT=host:1666"])

        config = read_config(os.path.join(data_dir, "config.yaml"))
        assert config["P4USER"] == "alice"
        assert config["P4PORT"] == "host:1666"

    def test_no_set_args_returns_2(self, data_dir, capsys):
        result = do_apply(data_dir, [])
        assert result == 2
        assert "No --set" in capsys.readouterr().err

    def test_multiple_set_args(self, data_dir):
        result = do_apply(data_dir, ["P4USER=alice", "P4PORT=host:1666"])
        assert result == 0

        config = read_config(os.path.join(data_dir, "config.yaml"))
        assert config["P4USER"] == "alice"
        assert config["P4PORT"] == "host:1666"


# ---------------------------------------------------------------------------
# do_init_defaults
# ---------------------------------------------------------------------------


class TestDoInitDefaults:
    def test_copies_template(self, data_dir, defaults_dir, capsys):
        result = do_init_defaults(data_dir, defaults_dir)
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        assert output["status"] == "ok"

        config = read_config(os.path.join(data_dir, "config.yaml"))
        assert "DEFAULT_AGENT" in config
        assert config["DEFAULT_AGENT"] == "claude-opus"

    def test_missing_source_returns_2(self, data_dir, tmp_path, capsys):
        result = do_init_defaults(data_dir, str(tmp_path / "nonexistent"))
        assert result == 2
        assert "not found" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# main (CLI dispatch)
# ---------------------------------------------------------------------------


class TestMain:
    def test_check_mode(self, data_dir, full_config_data, monkeypatch):
        write_config(os.path.join(data_dir, "config.yaml"), full_config_data)
        monkeypatch.setattr(sys, "argv", ["setup.py", "--check", "--data-dir", data_dir])
        assert main() == 0

    def test_apply_mode(self, data_dir, monkeypatch, capsys):
        monkeypatch.setattr(
            sys, "argv",
            ["setup.py", "--apply", "--data-dir", data_dir, "--set", "P4USER=alice"],
        )
        assert main() == 0
        config = read_config(os.path.join(data_dir, "config.yaml"))
        assert config["P4USER"] == "alice"

    def test_no_mode_returns_2(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["setup.py", "--data-dir", "/tmp"])
        assert main() == 2
        assert "No mode" in capsys.readouterr().err

    def test_no_data_dir_returns_2(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["setup.py", "--check"])
        assert main() == 2
        assert "--data-dir" in capsys.readouterr().err

    def test_init_defaults_requires_source(self, data_dir, monkeypatch, capsys):
        monkeypatch.setattr(
            sys, "argv",
            ["setup.py", "--init-defaults", "--data-dir", data_dir],
        )
        assert main() == 2
        assert "--source" in capsys.readouterr().err

    def test_unknown_arg_returns_2(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["setup.py", "--bogus"])
        assert main() == 2
        assert "Unknown argument" in capsys.readouterr().err
