"""Tests for time-based caching in plugins/bootstrap/lib/cache.py."""

import os
import time

import pytest

from bootstrap_lib.cache import check_time_cache, write_time_cache


class TestTimeCache:
    def test_no_cache_returns_false(self, tmp_path):
        assert check_time_cache(str(tmp_path), "test_key", 3600) is False

    def test_fresh_cache_returns_true(self, tmp_path):
        data_dir = str(tmp_path)
        write_time_cache(data_dir, "test_key")
        assert check_time_cache(data_dir, "test_key", 3600) is True

    def test_expired_cache_returns_false(self, tmp_path):
        data_dir = str(tmp_path)
        # Write a cache entry with a timestamp 2 hours ago
        cache_file = os.path.join(data_dir, "bootstrap_time_cache.txt")
        os.makedirs(data_dir, exist_ok=True)
        with open(cache_file, "w") as f:
            f.write(f"test_key\t{time.time() - 7200}\n")

        assert check_time_cache(data_dir, "test_key", 3600) is False

    def test_different_keys_independent(self, tmp_path):
        data_dir = str(tmp_path)
        write_time_cache(data_dir, "key_a")
        assert check_time_cache(data_dir, "key_a", 3600) is True
        assert check_time_cache(data_dir, "key_b", 3600) is False

    def test_overwrite_updates_timestamp(self, tmp_path):
        data_dir = str(tmp_path)
        # Write an expired entry
        cache_file = os.path.join(data_dir, "bootstrap_time_cache.txt")
        os.makedirs(data_dir, exist_ok=True)
        with open(cache_file, "w") as f:
            f.write(f"test_key\t{time.time() - 7200}\n")

        assert check_time_cache(data_dir, "test_key", 3600) is False

        # Overwrite with fresh timestamp
        write_time_cache(data_dir, "test_key")
        assert check_time_cache(data_dir, "test_key", 3600) is True

    def test_multiple_keys_preserved(self, tmp_path):
        data_dir = str(tmp_path)
        write_time_cache(data_dir, "key_a")
        write_time_cache(data_dir, "key_b")

        assert check_time_cache(data_dir, "key_a", 3600) is True
        assert check_time_cache(data_dir, "key_b", 3600) is True
