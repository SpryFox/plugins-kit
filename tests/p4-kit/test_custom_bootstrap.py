"""Tests for p4-kit custom_bootstrap.py."""

import sys
from unittest.mock import MagicMock, patch

import pytest

import custom_bootstrap as cb
from custom_bootstrap import _strip_annotation, autodetect


class TestStripAnnotation:
    def test_config_with_path(self):
        value = "ssl:perforce.spryfox.com:1666 (config 'D:/dev/p4/main\\.p4config.txt')"
        assert _strip_annotation(value) == "ssl:perforce.spryfox.com:1666"

    def test_set(self):
        assert _strip_annotation("ssl:host:1666 (set)") == "ssl:host:1666"

    def test_enviro(self):
        assert _strip_annotation("alice (enviro)") == "alice"

    def test_no_annotation(self):
        assert _strip_annotation("plain-value") == "plain-value"

    def test_nested_parens_in_value_preserved(self):
        # Only the trailing annotation is stripped — earlier parens stay
        value = "value-with (nested) middle (config)"
        assert _strip_annotation(value) == "value-with (nested) middle"

    def test_empty_string(self):
        assert _strip_annotation("") == ""

    def test_whitespace_trimmed(self):
        assert _strip_annotation("  value  (set)  ") == "value"


class TestAutodetect:
    def _fake_p4_set(self, stdout: str, returncode: int = 0):
        """Build a subprocess.run mock returning the given `p4 set` output."""
        fake = MagicMock()
        fake.stdout = stdout
        fake.returncode = returncode
        return fake

    def test_parses_p4_set_output(self, monkeypatch):
        monkeypatch.delenv("P4PORT", raising=False)
        monkeypatch.delenv("P4USER", raising=False)
        output = (
            "P4PORT=ssl:host:1666 (config 'D:/proj/.p4config')\n"
            "P4USER=alice (config 'D:/proj/.p4config')\n"
            "P4CLIENT=alice_proj (set)\n"
        )
        with patch.object(cb.subprocess, "run", return_value=self._fake_p4_set(output)):
            assert autodetect() == {"P4PORT": "ssl:host:1666", "P4USER": "alice"}

    def test_falls_back_to_env_vars(self, monkeypatch):
        monkeypatch.setenv("P4PORT", "ssl:env-host:1666")
        monkeypatch.setenv("P4USER", "bob")
        with patch.object(cb.subprocess, "run", return_value=self._fake_p4_set("")):
            assert autodetect() == {"P4PORT": "ssl:env-host:1666", "P4USER": "bob"}

    def test_p4_output_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("P4PORT", "ssl:env-host:1666")
        monkeypatch.setenv("P4USER", "bob")
        output = "P4PORT=ssl:p4-host:1666 (set)\nP4USER=alice (set)\n"
        with patch.object(cb.subprocess, "run", return_value=self._fake_p4_set(output)):
            assert autodetect() == {"P4PORT": "ssl:p4-host:1666", "P4USER": "alice"}

    def test_partial_p4_filled_by_env(self, monkeypatch):
        monkeypatch.delenv("P4PORT", raising=False)
        monkeypatch.setenv("P4USER", "bob")
        output = "P4PORT=ssl:host:1666 (set)\n"
        with patch.object(cb.subprocess, "run", return_value=self._fake_p4_set(output)):
            assert autodetect() == {"P4PORT": "ssl:host:1666", "P4USER": "bob"}

    def test_returns_none_when_nothing_found(self, monkeypatch):
        monkeypatch.delenv("P4PORT", raising=False)
        monkeypatch.delenv("P4USER", raising=False)
        with patch.object(cb.subprocess, "run", return_value=self._fake_p4_set("")):
            assert autodetect() is None

    def test_p4_not_installed(self, monkeypatch):
        monkeypatch.delenv("P4PORT", raising=False)
        monkeypatch.delenv("P4USER", raising=False)
        with patch.object(cb.subprocess, "run", side_effect=FileNotFoundError):
            assert autodetect() is None

    def test_p4_not_installed_but_env_set(self, monkeypatch):
        monkeypatch.setenv("P4PORT", "ssl:env:1666")
        monkeypatch.setenv("P4USER", "carol")
        with patch.object(cb.subprocess, "run", side_effect=FileNotFoundError):
            assert autodetect() == {"P4PORT": "ssl:env:1666", "P4USER": "carol"}

    def test_p4_timeout(self, monkeypatch):
        import subprocess as _sp
        monkeypatch.delenv("P4PORT", raising=False)
        monkeypatch.delenv("P4USER", raising=False)
        with patch.object(cb.subprocess, "run", side_effect=_sp.TimeoutExpired(cmd="p4", timeout=5)):
            assert autodetect() is None

    def test_p4_returns_nonzero(self, monkeypatch):
        monkeypatch.delenv("P4PORT", raising=False)
        monkeypatch.delenv("P4USER", raising=False)
        # stdout ignored when returncode != 0
        with patch.object(cb.subprocess, "run", return_value=self._fake_p4_set("P4PORT=should:ignore", returncode=1)):
            assert autodetect() is None

    def test_empty_values_skipped(self, monkeypatch):
        monkeypatch.delenv("P4PORT", raising=False)
        monkeypatch.delenv("P4USER", raising=False)
        # P4PORT has only annotation (value strips to empty) — should be skipped
        output = "P4PORT= (set)\nP4USER=alice (set)\n"
        with patch.object(cb.subprocess, "run", return_value=self._fake_p4_set(output)):
            assert autodetect() == {"P4USER": "alice"}
