"""Tests for bootstrap lib/platform_detect.py."""

from unittest.mock import patch

from bootstrap_lib import platform_detect
from bootstrap_lib.platform_detect import detect_os


class TestDetectOs:
    def test_returns_known_os(self):
        result = detect_os()
        assert result in ("macos", "windows", "ubuntu")


class TestDetectArch:
    def test_amd64_variants_normalize(self):
        for raw in ("x86_64", "AMD64", "amd64", "x64"):
            with patch("platform.machine", return_value=raw):
                assert platform_detect.detect_arch() == "amd64"

    def test_arm64_variants_normalize(self):
        for raw in ("arm64", "aarch64", "ARM64"):
            with patch("platform.machine", return_value=raw):
                assert platform_detect.detect_arch() == "arm64"

    def test_unknown_arch_returned_lowercased(self):
        with patch("platform.machine", return_value="riscv64"):
            assert platform_detect.detect_arch() == "riscv64"


class TestDetectOsArch:
    def test_combines_with_dash(self):
        with patch("bootstrap_lib.platform_detect.detect_os", return_value="macos"), \
             patch("bootstrap_lib.platform_detect.detect_arch", return_value="arm64"):
            assert platform_detect.detect_os_arch() == "macos-arm64"
