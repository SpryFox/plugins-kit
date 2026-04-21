"""Tests for p4-kit scripts/prepare_review.py."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import prepare_review as pr


# ---------------------------------------------------------------------------
# parse_description
# ---------------------------------------------------------------------------


class TestParseDescription:
    def test_single_line(self):
        out = (
            "Change 12345 by user@client on 2026/01/01 12:00:00 *pending*\n"
            "\n"
            "\tAdd inventory overflow check\n"
            "\n"
            "Affected files ...\n"
        )
        assert pr.parse_description(out) == "Add inventory overflow check"

    def test_multi_line(self):
        out = (
            "Change 12345 by user@client on 2026/01/01 12:00:00\n"
            "\n"
            "\tFix race in quest item pickup\n"
            "\t\n"
            "\tThe inventory lock was being released early.\n"
            "\n"
            "Affected files ...\n"
        )
        result = pr.parse_description(out)
        assert "Fix race in quest item pickup" in result
        assert "inventory lock was being released early" in result

    def test_no_description(self):
        assert pr.parse_description("") == ""


# ---------------------------------------------------------------------------
# parse_depot_files
# ---------------------------------------------------------------------------


class TestParseDepotFiles:
    def test_extracts_depot_paths(self):
        out = (
            "Differences ...\n"
            "\n"
            "==== //depot/foo/bar.cpp#3 (text) ====\n"
            "@@ -1,3 +1,4 @@\n"
            "==== //depot/foo/baz.h#1 (text) ====\n"
            "@@ -10,5 +10,6 @@\n"
        )
        assert pr.parse_depot_files(out) == [
            "//depot/foo/bar.cpp",
            "//depot/foo/baz.h",
        ]

    def test_no_files(self):
        assert pr.parse_depot_files("Change 1 ...\n") == []

    def test_ignores_non_header_lines(self):
        out = (
            "==== //depot/a.cpp#1 (text) ====\n"
            "+ ==== fake header in diff ====\n"
            "==== //depot/b.cpp#2 (text) ====\n"
        )
        assert pr.parse_depot_files(out) == ["//depot/a.cpp", "//depot/b.cpp"]


# ---------------------------------------------------------------------------
# extract_diff
# ---------------------------------------------------------------------------


class TestExtractDiff:
    def test_returns_content_after_marker(self):
        out = "header\n\nDifferences ...\n\n==== //a#1 (text) ====\n@@ -1 +1 @@\n"
        result = pr.extract_diff(out)
        assert result.startswith("==== //a#1")

    def test_no_differences_section(self):
        assert pr.extract_diff("just a header\n") == ""


# ---------------------------------------------------------------------------
# has_diff_content
# ---------------------------------------------------------------------------


class TestHasDiffContent:
    def test_true_when_marker_and_hunk(self):
        assert pr.has_diff_content("Differences ...\n@@ -1 +1 @@\n")

    def test_false_when_marker_only(self):
        assert not pr.has_diff_content("Differences ...\n(no diff)\n")

    def test_false_when_no_marker(self):
        assert not pr.has_diff_content("Affected files ...\n@@ -1 +1 @@\n")


# ---------------------------------------------------------------------------
# fetch_describe — shelved fallback
# ---------------------------------------------------------------------------


class TestFetchDescribe:
    def test_committed_returns_first(self):
        committed_out = "Differences ...\n@@ -1 +1 @@\nfoo\n"
        with patch.object(pr, "run_p4", return_value=(0, committed_out, "")) as mock:
            assert pr.fetch_describe("123") == committed_out
            assert mock.call_count == 1
            assert mock.call_args_list[0][0][0] == ["describe", "-du", "123"]

    def test_shelved_fallback_used(self):
        empty = "Affected files ...\n... //depot/a.cpp#1 edit\n"
        shelved = "Differences ...\n@@ -1 +1 @@\nfoo\n"

        def side(args):
            if "-S" in args:
                return (0, shelved, "")
            return (0, empty, "")

        with patch.object(pr, "run_p4", side_effect=side) as mock:
            assert pr.fetch_describe("123") == shelved
            assert mock.call_count == 2

    def test_raises_when_neither_has_diff(self):
        empty = "Affected files ...\n"
        with patch.object(pr, "run_p4", return_value=(0, empty, "")):
            with pytest.raises(ValueError, match="no diff found"):
                pr.fetch_describe("123")


# ---------------------------------------------------------------------------
# resolve_local_paths
# ---------------------------------------------------------------------------


class TestResolveLocalPaths:
    def test_parses_ztag_where_output(self):
        out = (
            "... depotFile //depot/a.cpp\n"
            "... clientFile //ws/a.cpp\n"
            "... path C:\\workspace\\a.cpp\n"
            "\n"
            "... depotFile //depot/b.h\n"
            "... clientFile //ws/b.h\n"
            "... path C:\\workspace\\b.h\n"
        )
        with patch.object(pr, "run_p4", return_value=(0, out, "")):
            result = pr.resolve_local_paths(["//depot/a.cpp", "//depot/b.h"])
        assert result == {
            "//depot/a.cpp": "C:\\workspace\\a.cpp",
            "//depot/b.h": "C:\\workspace\\b.h",
        }

    def test_empty_input(self):
        assert pr.resolve_local_paths([]) == {}

    def test_p4_failure_returns_none_for_each(self):
        with patch.object(pr, "run_p4", return_value=(1, "", "error")):
            result = pr.resolve_local_paths(["//depot/a.cpp"])
        assert result == {"//depot/a.cpp": None}


# ---------------------------------------------------------------------------
# collect_claude_mds
# ---------------------------------------------------------------------------


class TestCollectClaudeMds:
    def test_walks_to_workspace_root(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("root rule\n")
        sub = tmp_path / "src" / "module"
        sub.mkdir(parents=True)
        (sub.parent / "CLAUDE.md").write_text("src rule\n")
        target = sub / "file.cpp"
        target.write_text("code\n")

        result = pr.collect_claude_mds(target, tmp_path)
        # Nearest first
        assert len(result) == 2
        assert Path(result[0]).read_text() == "src rule\n"
        assert Path(result[1]).read_text() == "root rule\n"

    def test_no_claude_md(self, tmp_path):
        sub = tmp_path / "src"
        sub.mkdir()
        target = sub / "file.cpp"
        target.write_text("")
        assert pr.collect_claude_mds(target, tmp_path) == []

    def test_stops_at_workspace_root(self, tmp_path):
        # CLAUDE.md ABOVE workspace root should not be collected
        outer = tmp_path / "outer"
        outer.mkdir()
        (tmp_path / "CLAUDE.md").write_text("outer rule\n")  # outside workspace
        ws_root = outer / "ws"
        ws_root.mkdir()
        (ws_root / "CLAUDE.md").write_text("ws rule\n")
        sub = ws_root / "src"
        sub.mkdir()
        target = sub / "file.cpp"
        target.write_text("")

        result = pr.collect_claude_mds(target, ws_root)
        assert len(result) == 1
        assert Path(result[0]).read_text() == "ws rule\n"

    def test_no_workspace_root_walks_to_fs_root(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("rule\n")
        sub = tmp_path / "src"
        sub.mkdir()
        target = sub / "file.cpp"
        target.write_text("")
        result = pr.collect_claude_mds(target, None)
        # At minimum, should find tmp_path/CLAUDE.md
        assert any(Path(r).read_text() == "rule\n" for r in result)


# ---------------------------------------------------------------------------
# build_bundle — integration
# ---------------------------------------------------------------------------


class TestBuildBundle:
    def test_full_pipeline(self, tmp_path, monkeypatch):
        # Set up a fake workspace with one file and one CLAUDE.md
        ws = tmp_path / "ws"
        src = ws / "src"
        src.mkdir(parents=True)
        (ws / "CLAUDE.md").write_text("workspace rule\n")
        local_file = src / "foo.cpp"
        local_file.write_text("int x = 1;\n")

        describe_out = (
            "Change 999 by user@client on 2026/01/01 12:00:00 *pending*\n"
            "\n"
            "\tFix the thing\n"
            "\n"
            "Shelved files ...\n"
            "\n"
            "Differences ...\n"
            "\n"
            f"==== //depot/src/foo.cpp#1 (text) ====\n"
            "@@ -1 +1 @@\n"
            "-int x = 0;\n"
            "+int x = 1;\n"
        )
        where_out = (
            "... depotFile //depot/src/foo.cpp\n"
            f"... path {local_file}\n"
        )
        info_out = f"... clientRoot {ws}\n"

        def fake_run_p4(args):
            if args[:2] == ["describe", "-du"]:
                return (0, describe_out, "")
            if args[:2] == ["-ztag", "where"]:
                return (0, where_out, "")
            if args[:2] == ["-ztag", "info"]:
                return (0, info_out, "")
            return (1, "", "")

        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            bundle = pr.build_bundle("999")

        assert bundle["cl"] == "999"
        assert bundle["description"] == "Fix the thing"
        assert "==== //depot/src/foo.cpp#1" in bundle["diff"]
        assert len(bundle["changed_files"]) == 1
        cf = bundle["changed_files"][0]
        assert cf["depot"] == "//depot/src/foo.cpp"
        assert Path(cf["local"]) == local_file
        assert len(cf["claude_mds"]) == 1
        assert Path(cf["claude_mds"][0]).read_text() == "workspace rule\n"
        assert len(bundle["unique_claude_mds"]) == 1


# ---------------------------------------------------------------------------
# main — CLI
# ---------------------------------------------------------------------------


class TestMain:
    def test_no_args_returns_2(self, capsys):
        rc = pr.main(["prepare_review.py"])
        assert rc == 2
        assert "Usage" in capsys.readouterr().err

    def test_value_error_returns_1(self, capsys):
        with patch.object(pr, "build_bundle", side_effect=ValueError("nope")):
            rc = pr.main(["prepare_review.py", "123"])
        assert rc == 1
        assert "nope" in capsys.readouterr().err

    def test_success_prints_json(self, capsys):
        with patch.object(pr, "build_bundle", return_value={"cl": "123"}):
            rc = pr.main(["prepare_review.py", "123"])
        assert rc == 0
        captured = capsys.readouterr()
        assert json.loads(captured.out) == {"cl": "123"}
