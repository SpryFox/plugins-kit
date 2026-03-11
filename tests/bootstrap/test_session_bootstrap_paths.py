"""Tests for session-bootstrap.sh path correctness."""

import re
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).parent.parent.parent
    / "plugins"
    / "bootstrap"
    / "hooks"
    / "sessionstart"
    / "session-bootstrap.sh"
)


class TestStandalonePythonPath:
    """Verify STANDALONE_PYTHON is set to the correct path in the shell script.

    The astral-sh standalone Python archive (install_only_stripped.tar.gz)
    extracts to python/bin/python3, NOT python/install/bin/python3.
    If the path includes 'install/', the symlink created in ~/.local/bin will
    always be broken, causing Python to be re-downloaded every session.
    """

    def _unix_standalone_python_suffix(self, content: str) -> str:
        """Extract the STANDALONE_PYTHON path suffix from the Unix (else) branch."""
        # The Unix branch is in the else clause; it ends with python3 (not .exe)
        match = re.search(
            r'STANDALONE_PYTHON="\$\{STANDALONE_DIR\}(/[^"]+python3)"', content
        )
        assert match, "Could not find Unix STANDALONE_PYTHON assignment in script"
        return match.group(1)

    def test_standalone_python_path_no_install_subdir(self) -> None:
        """STANDALONE_PYTHON must not include the non-existent install/ subdirectory."""
        content = SCRIPT_PATH.read_text()
        path_suffix = self._unix_standalone_python_suffix(content)
        assert "/install/" not in path_suffix, (
            f"STANDALONE_PYTHON contains non-existent 'install/' subdirectory: "
            f"${{STANDALONE_DIR}}{path_suffix}\n"
            f"The archive extracts to python/bin/python3, not python/install/bin/python3."
        )

    def test_standalone_python_path_is_correct(self) -> None:
        """STANDALONE_PYTHON must point to python/bin/python3."""
        content = SCRIPT_PATH.read_text()
        path_suffix = self._unix_standalone_python_suffix(content)
        assert path_suffix == "/python/bin/python3", (
            f"Expected STANDALONE_PYTHON suffix '/python/bin/python3', got '{path_suffix}'"
        )
