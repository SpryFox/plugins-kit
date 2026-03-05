"""Tests for bootstrap lib/tool_check.py."""

import sys

from tool_check import check_tool, run_install


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


class TestRunInstall:
    def test_success(self):
        cmd = f"{sys.executable} -c 'pass'"
        ok, output = run_install(cmd)
        assert ok is True

    def test_failure(self):
        cmd = f"{sys.executable} -c 'import sys; sys.exit(1)'"
        ok, output = run_install(cmd)
        assert ok is False

    def test_output_captured(self):
        cmd = f"{sys.executable} -c 'print(\"hello\")'"
        ok, output = run_install(cmd)
        assert ok is True
        assert "hello" in output
