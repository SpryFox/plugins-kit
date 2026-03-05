"""Tests for plugins/bootstrap/lib/json_check.py."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "bootstrap", "lib"))

from json_check import check_json_entries, merge_json_entries


class TestCheckJsonEntries:
    def test_matching_fields(self, tmp_path):
        ref = tmp_path / "ref.json"
        target = tmp_path / "target.json"
        ref.write_text(json.dumps({"source": "local", "path": "/foo"}))
        target.write_text(json.dumps({"source": "local", "path": "/foo", "extra": True}))

        result = check_json_entries(str(ref), str(target), ["source", "path"])
        assert result.passed is True

    def test_mismatched_field(self, tmp_path):
        ref = tmp_path / "ref.json"
        target = tmp_path / "target.json"
        ref.write_text(json.dumps({"source": "local"}))
        target.write_text(json.dumps({"source": "remote"}))

        result = check_json_entries(str(ref), str(target), ["source"])
        assert result.passed is False
        assert "source" in result.message

    def test_target_missing(self, tmp_path):
        ref = tmp_path / "ref.json"
        ref.write_text(json.dumps({"source": "local"}))

        result = check_json_entries(str(ref), str(tmp_path / "missing.json"), ["source"])
        assert result.passed is False
        assert "does not exist" in result.message

    def test_reference_missing(self, tmp_path):
        target = tmp_path / "target.json"
        target.write_text(json.dumps({"source": "local"}))

        result = check_json_entries(str(tmp_path / "missing.json"), str(target), ["source"])
        assert result.passed is False
        assert "reference" in result.message


class TestMergeJsonEntries:
    def test_merge_creates_target(self, tmp_path):
        ref = tmp_path / "ref.json"
        target = tmp_path / "out" / "target.json"
        ref.write_text(json.dumps({"source": "local", "autoUpdate": True}))

        result = merge_json_entries(str(ref), str(target), ["source", "autoUpdate"])
        assert result.passed is True
        assert target.is_file()

        data = json.loads(target.read_text())
        assert data["source"] == "local"
        assert data["autoUpdate"] is True

    def test_merge_preserves_fields(self, tmp_path):
        ref = tmp_path / "ref.json"
        target = tmp_path / "target.json"
        ref.write_text(json.dumps({"source": "local", "autoUpdate": True}))
        target.write_text(json.dumps({"source": "remote", "lastUpdated": "2026-01-01"}))

        result = merge_json_entries(
            str(ref), str(target),
            merge_fields=["source", "autoUpdate"],
            preserve_fields=["lastUpdated"],
        )
        assert result.passed is True

        data = json.loads(target.read_text())
        assert data["source"] == "local"  # Merged from ref
        assert data["autoUpdate"] is True  # Merged from ref
        assert data["lastUpdated"] == "2026-01-01"  # Preserved from target

    def test_deep_merge_dicts(self, tmp_path):
        ref = tmp_path / "ref.json"
        target = tmp_path / "target.json"
        ref.write_text(json.dumps({"plugins": {"a": True, "b": True}}))
        target.write_text(json.dumps({"plugins": {"c": True}}))

        result = merge_json_entries(str(ref), str(target), ["plugins"])
        assert result.passed is True

        data = json.loads(target.read_text())
        # Deep merge: ref entries override, target extras kept
        assert data["plugins"]["a"] is True
        assert data["plugins"]["b"] is True
        assert data["plugins"]["c"] is True

    def test_reference_missing(self, tmp_path):
        target = tmp_path / "target.json"
        result = merge_json_entries(str(tmp_path / "missing.json"), str(target), ["source"])
        assert result.passed is False
