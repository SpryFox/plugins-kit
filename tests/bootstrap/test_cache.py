"""Tests for bootstrap lib/cache.py."""

import os

from cache import check_cache, write_cache


class TestCache:
    def test_cache_miss_on_empty(self, data_dir, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text('{"tools": []}')
        assert check_cache(data_dir, [str(manifest)]) is False

    def test_cache_hit_after_write(self, data_dir, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text('{"tools": []}')
        paths = [str(manifest)]

        write_cache(data_dir, paths)
        assert check_cache(data_dir, paths) is True

    def test_cache_miss_after_content_change(self, data_dir, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text('{"tools": []}')
        paths = [str(manifest)]

        write_cache(data_dir, paths)
        assert check_cache(data_dir, paths) is True

        # Modify the file
        manifest.write_text('{"tools": ["git"]}')
        assert check_cache(data_dir, paths) is False

    def test_cache_miss_on_missing_file(self, data_dir, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text('{"tools": []}')
        paths = [str(manifest)]

        write_cache(data_dir, paths)
        assert check_cache(data_dir, paths) is True

        # Delete the hashed file
        manifest.unlink()
        assert check_cache(data_dir, paths) is False
