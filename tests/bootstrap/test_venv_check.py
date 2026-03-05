"""Tests for venv_check.py — Python venv validation."""

import os
import stat
import subprocess
import sys
from unittest.mock import patch

import pytest

from venv_check import VenvCheckResult, check_venv


class TestCheckVenv:
    def test_missing_venv_dir(self, tmp_path):
        """Returns failure when venv directory doesn't exist."""
        result = check_venv(str(tmp_path / "data"), str(tmp_path / "plugin"), ["yaml"])

        assert not result.passed
        assert "not found" in result.message
        assert result.remediation_cmd is not None
        assert "uv sync" in result.remediation_cmd

    def test_no_python_binary(self, tmp_path):
        """Returns failure when venv exists but has no python binary."""
        venv_dir = tmp_path / "data" / ".venv"
        venv_dir.mkdir(parents=True)

        result = check_venv(str(tmp_path / "data"), str(tmp_path / "plugin"), ["yaml"])

        assert not result.passed
        assert "no python binary" in result.message

    def test_working_venv_with_imports(self, tmp_path):
        """Passes when venv has working python and all imports succeed."""
        # Create a real venv using the current Python
        venv_dir = tmp_path / "data" / ".venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True, capture_output=True,
        )

        # sys and os are always available
        result = check_venv(str(tmp_path / "data"), str(tmp_path / "plugin"), ["sys", "os"])

        assert result.passed
        assert "2 imports verified" in result.message
        assert result.remediation_cmd is None

    def test_import_failure(self, tmp_path):
        """Returns failure when an import doesn't work in the venv."""
        venv_dir = tmp_path / "data" / ".venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True, capture_output=True,
        )

        result = check_venv(
            str(tmp_path / "data"), str(tmp_path / "plugin"),
            ["nonexistent_module_xyz_abc_123"],
        )

        assert not result.passed
        assert "import nonexistent_module_xyz_abc_123 failed" in result.message
        assert result.remediation_cmd is not None

    def test_empty_imports_list(self, tmp_path):
        """Passes when no imports to check."""
        venv_dir = tmp_path / "data" / ".venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True, capture_output=True,
        )

        result = check_venv(str(tmp_path / "data"), str(tmp_path / "plugin"), [])

        assert result.passed
        assert "0 imports verified" in result.message

    def test_remediation_includes_plugin_root(self, tmp_path):
        """Remediation command references the plugin root for uv sync."""
        plugin_root = str(tmp_path / "my-plugin")
        result = check_venv(str(tmp_path / "data"), plugin_root, ["yaml"])

        assert not result.passed
        assert plugin_root in result.remediation_cmd
