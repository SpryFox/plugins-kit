"""Tests for bootstrap lib/path_check.py."""

import os

from path_check import check_path_entry


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
