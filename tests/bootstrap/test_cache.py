"""Tests for bootstrap lib/cache.py."""

import os

from bootstrap_lib.cache import check_cache, write_cache, compute_current_hash, check_cache_fast


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


class TestComputeCurrentHash:
    def test_writes_hash_file(self, data_dir, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text('{"tools": []}')

        result = compute_current_hash(data_dir, [str(manifest)])
        assert isinstance(result, str)
        assert len(result) == 64  # SHA256 hex digest

        hash_file = os.path.join(data_dir, "bootstrap_current.sha256")
        assert os.path.isfile(hash_file)
        with open(hash_file) as f:
            assert f.read().strip() == result

    def test_creates_data_dir(self, tmp_path):
        data_dir = str(tmp_path / "nonexistent" / "data")
        manifest = tmp_path / "manifest.json"
        manifest.write_text('{"tools": []}')

        compute_current_hash(data_dir, [str(manifest)])
        assert os.path.isdir(data_dir)

    def test_hash_changes_with_content(self, data_dir, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text('{"tools": []}')
        hash1 = compute_current_hash(data_dir, [str(manifest)])

        manifest.write_text('{"tools": ["git"]}')
        hash2 = compute_current_hash(data_dir, [str(manifest)])

        assert hash1 != hash2


class TestCheckCacheFast:
    def test_returns_none_when_no_current_hash(self, data_dir):
        assert check_cache_fast(data_dir) is None

    def test_returns_false_when_no_cache_file(self, data_dir, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text('{"tools": []}')
        compute_current_hash(data_dir, [str(manifest)])

        # No cache file written yet
        assert check_cache_fast(data_dir) is False

    def test_returns_true_when_hashes_match(self, data_dir, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text('{"tools": []}')
        paths = [str(manifest)]

        compute_current_hash(data_dir, paths)
        write_cache(data_dir, paths)

        assert check_cache_fast(data_dir) is True

    def test_returns_false_when_hashes_differ(self, data_dir, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text('{"tools": []}')
        paths = [str(manifest)]

        # Write cache with original content
        write_cache(data_dir, paths)

        # Change content and recompute current hash
        manifest.write_text('{"tools": ["git"]}')
        compute_current_hash(data_dir, paths)

        assert check_cache_fast(data_dir) is False

    def test_returns_none_distinguishes_from_false(self, data_dir, tmp_path):
        """None means 'SessionStart missed', False means 'cache miss'."""
        # No current hash file at all
        result_no_file = check_cache_fast(data_dir)
        assert result_no_file is None

        # Current hash exists but no cache file
        manifest = tmp_path / "manifest.json"
        manifest.write_text('{"tools": []}')
        compute_current_hash(data_dir, [str(manifest)])
        result_no_cache = check_cache_fast(data_dir)
        assert result_no_cache is False

        # Both None and False are falsy but semantically different
        assert result_no_file is not result_no_cache
