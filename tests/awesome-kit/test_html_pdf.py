"""Tests for awesome-kit's html-pdf converter pure helpers.

The module is imported by file path so the test does not depend on the plugin
being on sys.path. The conversion itself needs Playwright + Chromium and is not
unit-tested here; these tests cover the pure, OS-/browser-free logic:
output-path defaulting and Windows default-browser command parsing.
"""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins" / "awesome-kit" / "skills" / "html-pdf" / "scripts" / "html_to_pdf.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("awesome_html_to_pdf", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


html_to_pdf = _load_module()


class TestDefaultOutputPath:
    def test_swaps_html_suffix_for_pdf(self):
        assert html_to_pdf.default_output_path("a/b/page.html") == Path("a/b/page.pdf")

    def test_handles_uppercase_suffix(self):
        assert html_to_pdf.default_output_path("X.HTML") == Path("X.pdf")

    def test_no_suffix_gets_pdf(self):
        assert html_to_pdf.default_output_path("report") == Path("report.pdf")


class TestExeFromCommand:
    def test_quoted_path_with_args(self):
        cmd = r'"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --single-argument %1'
        assert (
            html_to_pdf.exe_from_command(cmd)
            == r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        )

    def test_unquoted_path_no_spaces(self):
        cmd = r"C:\Windows\system32\rundll32.exe shell,Open %1"
        assert html_to_pdf.exe_from_command(cmd) == r"C:\Windows\system32\rundll32.exe"

    def test_unterminated_quote_returns_none(self):
        assert html_to_pdf.exe_from_command('"C:\\broken\\path %1') is None

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_empty_returns_none(self, value):
        assert html_to_pdf.exe_from_command(value) is None
