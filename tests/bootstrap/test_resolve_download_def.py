"""Tests for engine._resolve_download_def selector."""

from unittest.mock import patch

from bootstrap_lib.engine import _resolve_download_def


class TestResolveDownloadDef:
    def test_prefers_os_arch_when_both_keys_exist(self):
        block = {
            "macos":       {"url": "fallback"},
            "macos-arm64": {"url": "specific"},
        }
        with patch("bootstrap_lib.platform_detect.detect_arch", return_value="arm64"):
            assert _resolve_download_def(block, "macos") == {"url": "specific"}

    def test_falls_back_to_os_when_no_arch_key(self):
        block = {"macos": {"url": "fallback"}}
        with patch("bootstrap_lib.platform_detect.detect_arch", return_value="arm64"):
            assert _resolve_download_def(block, "macos") == {"url": "fallback"}

    def test_returns_none_when_no_match(self):
        block = {"ubuntu-amd64": {"url": "x"}}
        with patch("bootstrap_lib.platform_detect.detect_arch", return_value="amd64"):
            assert _resolve_download_def(block, "windows") is None

    def test_empty_or_non_dict_returns_none(self):
        assert _resolve_download_def({}, "macos") is None
        assert _resolve_download_def(None, "macos") is None
        assert _resolve_download_def("not a dict", "macos") is None

    def test_arch_specific_only(self):
        block = {
            "windows-amd64": {"url": "win"},
            "macos-arm64":   {"url": "mac-arm"},
            "macos-amd64":   {"url": "mac-x86"},
        }
        with patch("bootstrap_lib.platform_detect.detect_arch", return_value="arm64"):
            assert _resolve_download_def(block, "macos") == {"url": "mac-arm"}
        with patch("bootstrap_lib.platform_detect.detect_arch", return_value="amd64"):
            assert _resolve_download_def(block, "macos") == {"url": "mac-x86"}
