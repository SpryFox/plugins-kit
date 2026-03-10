"""Tests for bootstrap lib/tool_check.py."""

import os
import stat
import sys

from bootstrap_lib.tool_check import check_tool, run_install


class TestCheckTool:
    def test_installed_tool_passes(self):
        result = check_tool("python3")
        assert result.passed is True
        assert result.name == "python3"
        assert "found at" in result.message

    def test_missing_tool_fails(self):
        result = check_tool("nonexistent_xyz_tool_abc")
        assert result.passed is False
        assert result.name == "nonexistent_xyz_tool_abc"
        assert result.install_cmd is None

    def test_missing_tool_includes_install_cmd(self):
        install_cmds = {"macos": "brew install fake", "ubuntu": "apt install fake"}
        result = check_tool("nonexistent_xyz", install_cmds=install_cmds, current_os="macos")
        assert result.passed is False
        assert result.install_cmd == "brew install fake"

    def test_missing_tool_no_install_for_unknown_os(self):
        install_cmds = {"macos": "brew install fake"}
        result = check_tool("nonexistent_xyz", install_cmds=install_cmds, current_os="freebsd")
        assert result.passed is False
        assert result.install_cmd is None


class TestInstallPath:
    """Tests for the install_path parameter of check_tool."""

    def test_found_in_install_path(self, tmp_path):
        """Tool binary found in install_path passes."""
        tool_name = "mytool"
        tool_file = tmp_path / tool_name
        tool_file.write_text("#!/bin/sh\necho hi")
        tool_file.chmod(tool_file.stat().st_mode | stat.S_IEXEC)

        result = check_tool(tool_name, install_path=str(tmp_path))
        assert result.passed is True
        assert str(tmp_path) in result.message

    def test_found_exe_in_install_path(self, tmp_path):
        """On Windows/MSYSTEM, tool.exe found in install_path passes."""
        tool_name = "mytool"
        exe_file = tmp_path / (tool_name + ".exe")
        exe_file.write_text("fake exe")

        # This test relies on the platform check in check_tool;
        # on non-Windows the .exe candidate is skipped, so place the bare name too
        bare_file = tmp_path / tool_name
        bare_file.write_text("fake binary")

        result = check_tool(tool_name, install_path=str(tmp_path))
        assert result.passed is True

    def test_install_path_missing_dir(self, tmp_path):
        """install_path pointing to nonexistent dir falls through to which."""
        result = check_tool("nonexistent_xyz_tool", install_path=str(tmp_path / "nope"))
        assert result.passed is False

    def test_install_path_empty_dir(self, tmp_path):
        """install_path exists but tool binary not in it falls through."""
        result = check_tool("nonexistent_xyz_tool", install_path=str(tmp_path))
        assert result.passed is False

    def test_install_path_with_tilde(self, tmp_path, monkeypatch):
        """Tilde in install_path is expanded."""
        tool_name = "tildetool"
        tool_file = tmp_path / tool_name
        tool_file.write_text("#!/bin/sh\necho hi")
        tool_file.chmod(tool_file.stat().st_mode | stat.S_IEXEC)

        monkeypatch.setenv("HOME", str(tmp_path))
        # Also set USERPROFILE for Windows expanduser
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        result = check_tool(tool_name, install_path="~")
        assert result.passed is True

    def test_which_fallback_when_install_path_misses(self):
        """Even with install_path set, falls back to which for system tools."""
        result = check_tool("python3", install_path="/nonexistent/path")
        assert result.passed is True
        assert "found at" in result.message


class TestRunInstall:
    def test_success(self):
        ok, output = run_install("echo ok")
        assert ok is True

    def test_failure(self):
        ok, output = run_install("false")
        assert ok is False

    def test_output_captured(self):
        ok, output = run_install("echo hello")
        assert ok is True
        assert "hello" in output
