"""Tests for bootstrap lib/path_check.py."""

import os
from unittest.mock import MagicMock, patch

from bootstrap_lib.path_check import check_path_entry, _add_path_to_windows_registry


class TestCheckPathEntry:
    def test_existing_path_passes(self):
        # Use a directory known to be in PATH on both macOS/Linux and Windows
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        assert len(path_dirs) > 0, "PATH is empty"
        known_dir = path_dirs[0]
        result = check_path_entry(known_dir)
        assert result.passed is True
        assert result.path == known_dir

    def test_missing_path_fails(self):
        result = check_path_entry("/nonexistent/path/xyz")
        assert result.passed is False
        assert "/nonexistent/path/xyz" in result.message

    def test_tilde_expansion(self):
        home = os.path.expanduser("~")
        # Add ~/.local/bin to PATH for this test if not present
        original_path = os.environ.get("PATH", "")
        local_bin = os.path.join(home, ".local", "bin")
        os.environ["PATH"] = local_bin + os.pathsep + original_path
        try:
            result = check_path_entry("~/.local/bin")
            assert result.passed is True
        finally:
            os.environ["PATH"] = original_path


class TestAddPathToWindowsRegistry:
    """Tests for _add_path_to_windows_registry (mocked PowerShell)."""

    @patch("subprocess.run")
    def test_adds_new_entry(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="added\n")

        ok, msg = _add_path_to_windows_registry("~/.local/bin")
        assert ok is True
        assert "added" in msg
        assert "registry" in msg
        assert mock_run.call_args[0][0][0] == "powershell.exe"

    @patch("subprocess.run")
    def test_already_present(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="already_present\n")

        ok, msg = _add_path_to_windows_registry("~/.local/bin")
        assert ok is True
        assert "already" in msg

    @patch("subprocess.run")
    def test_powershell_failure(self, mock_run):
        mock_run.side_effect = FileNotFoundError("powershell.exe not found")

        ok, msg = _add_path_to_windows_registry("~/.local/bin")
        assert ok is False
        assert "failed" in msg

    @patch("subprocess.run")
    def test_powershell_nonzero_exit(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="some error")

        ok, msg = _add_path_to_windows_registry("~/.local/bin")
        assert ok is False
        assert "exit 1" in msg


class TestAddPathToShellConfigWindowsIntegration:
    """Test that add_path_to_shell_config calls registry on Windows."""

    @patch("bootstrap_lib.path_check._add_path_to_windows_registry")
    def test_calls_registry_on_windows(self, mock_registry, tmp_path):
        from bootstrap_lib.path_check import add_path_to_shell_config
        mock_registry.return_value = (True, "added to registry")
        # Use a fake RC file path to prevent writing to real ~/.bashrc
        fake_bashrc = str(tmp_path / ".bashrc")
        with patch.dict(os.environ, {"MSYSTEM": "MINGW64"}), \
             patch("bootstrap_lib.path_check.os.path.expanduser", side_effect=lambda p: str(tmp_path / p.lstrip("~/")) if p.startswith("~") else p):
            ok, msg = add_path_to_shell_config("/tmp/test_path_xyz_" + str(os.getpid()))
        mock_registry.assert_called_once()

    @patch("bootstrap_lib.path_check._add_path_to_windows_registry")
    def test_skips_registry_on_non_windows(self, mock_registry, tmp_path):
        from bootstrap_lib.path_check import add_path_to_shell_config
        # Ensure MSYSTEM is not set and sys.platform is not win32
        env = {k: v for k, v in os.environ.items() if k != "MSYSTEM"}
        with patch.dict(os.environ, env, clear=True), \
             patch("bootstrap_lib.path_check.sys") as mock_sys, \
             patch("bootstrap_lib.path_check.os.path.expanduser", side_effect=lambda p: str(tmp_path / p.lstrip("~/")) if p.startswith("~") else p):
            mock_sys.platform = "linux"
            add_path_to_shell_config("/tmp/test_path_xyz_" + str(os.getpid()))
        mock_registry.assert_not_called()
