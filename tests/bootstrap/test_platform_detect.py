"""Tests for bootstrap lib/platform_detect.py."""

from bootstrap_lib.platform_detect import detect_os


class TestDetectOs:
    def test_returns_known_os(self):
        result = detect_os()
        assert result in ("macos", "windows", "ubuntu")
