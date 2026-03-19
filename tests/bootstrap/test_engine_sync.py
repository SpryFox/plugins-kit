"""Tests for sync_to_data engine feature."""

import json
import os

import pytest

from bootstrap_lib.engine import _process_manifest


class TestSyncToData:
    def test_sync_copies_directory(self, tmp_path):
        """Files from src are copied to dst in data_dir."""
        plugin_root = tmp_path / "plugin"
        data_dir = tmp_path / "data"
        plugin_root.mkdir()
        data_dir.mkdir()

        # Create source lib directory with files
        src_lib = plugin_root / "lib"
        src_lib.mkdir()
        (src_lib / "bootstrap.py").write_text("# bootstrap module")
        (src_lib / "helper.py").write_text("# helper module")

        manifest = {"sync_to_data": [{"src": "lib", "dst": "lib"}]}
        action_entries = []
        ok_entries = []
        failures = _process_manifest(
            manifest, "windows", str(data_dir), str(plugin_root),
            action_entries, ok_entries,
        )

        assert (data_dir / "lib" / "bootstrap.py").exists()
        assert (data_dir / "lib" / "helper.py").exists()
        assert (data_dir / "lib" / "bootstrap.py").read_text() == "# bootstrap module"
        assert failures == []
        assert any("sync" in e.lower() and "ok" in e for e in ok_entries)

    def test_sync_overwrites_existing(self, tmp_path):
        """Sync overwrites old content in dst."""
        plugin_root = tmp_path / "plugin"
        data_dir = tmp_path / "data"
        plugin_root.mkdir()
        data_dir.mkdir()

        # Pre-populate dst with old content
        dst_lib = data_dir / "lib"
        dst_lib.mkdir()
        (dst_lib / "bootstrap.py").write_text("# old content")

        # Create source with new content
        src_lib = plugin_root / "lib"
        src_lib.mkdir()
        (src_lib / "bootstrap.py").write_text("# new content")

        manifest = {"sync_to_data": [{"src": "lib", "dst": "lib"}]}
        action_entries = []
        ok_entries = []
        _process_manifest(
            manifest, "windows", str(data_dir), str(plugin_root),
            action_entries, ok_entries,
        )

        assert (dst_lib / "bootstrap.py").read_text() == "# new content"

    def test_sync_source_missing_fails(self, tmp_path):
        """Missing source directory produces a failure entry."""
        plugin_root = tmp_path / "plugin"
        data_dir = tmp_path / "data"
        plugin_root.mkdir()
        data_dir.mkdir()

        manifest = {"sync_to_data": [{"src": "lib", "dst": "lib"}]}
        action_entries = []
        ok_entries = []
        failures = _process_manifest(
            manifest, "windows", str(data_dir), str(plugin_root),
            action_entries, ok_entries,
        )

        assert not (data_dir / "lib").exists()
        assert len(failures) == 1
        assert failures[0]["type"] == "sync_to_data"
        assert any("FAILED" in e for e in action_entries)

    def test_sync_custom_dst(self, tmp_path):
        """Custom dst mapping places files at the correct location."""
        plugin_root = tmp_path / "plugin"
        data_dir = tmp_path / "data"
        plugin_root.mkdir()
        data_dir.mkdir()

        src = plugin_root / "src" / "modules"
        src.mkdir(parents=True)
        (src / "mod.py").write_text("# module")

        manifest = {"sync_to_data": [{"src": "src/modules", "dst": "vendor/modules"}]}
        action_entries = []
        ok_entries = []
        failures = _process_manifest(
            manifest, "windows", str(data_dir), str(plugin_root),
            action_entries, ok_entries,
        )

        assert (data_dir / "vendor" / "modules" / "mod.py").exists()
        assert (data_dir / "vendor" / "modules" / "mod.py").read_text() == "# module"
        assert failures == []
