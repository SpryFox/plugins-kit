"""Tests for p4-kit scripts/prepare_review.py."""

import json
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
# parse_file_actions
# ---------------------------------------------------------------------------


class TestParseFileActions:
    def test_affected_files_section(self):
        out = (
            "Change 100 by u@c on 2026/01/01\n"
            "\n"
            "\tdesc\n"
            "\n"
            "Affected files ...\n"
            "\n"
            "... //depot/a.cpp#3 edit\n"
            "... //depot/new.py#1 add\n"
            "... //depot/gone.py#2 delete\n"
            "\n"
            "Differences ...\n"
            "==== //depot/a.cpp#3 (text) ====\n"
        )
        assert pr.parse_file_actions(out) == {
            "//depot/a.cpp": ("3", "edit"),
            "//depot/new.py": ("1", "add"),
            "//depot/gone.py": ("2", "delete"),
        }

    def test_shelved_files_section(self):
        out = (
            "Shelved files ...\n"
            "\n"
            "... //depot/x.py#1 add\n"
            "\n"
            "Differences ...\n"
        )
        assert pr.parse_file_actions(out) == {"//depot/x.py": ("1", "add")}

    def test_move_actions(self):
        out = (
            "Affected files ...\n"
            "... //depot/new.py#1 move/add\n"
            "... //depot/old.py#5 move/delete\n"
            "Differences ...\n"
        )
        assert pr.parse_file_actions(out) == {
            "//depot/new.py": ("1", "move/add"),
            "//depot/old.py": ("5", "move/delete"),
        }

    def test_empty(self):
        assert pr.parse_file_actions("") == {}


# ---------------------------------------------------------------------------
# split_diff_sections
# ---------------------------------------------------------------------------


class TestSplitDiffSections:
    def test_splits_by_file_header(self):
        diff = (
            "==== //depot/a.cpp#1 (text) ====\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
            "==== //depot/b.cpp#2 (text) ====\n"
            "@@ -5 +5 @@\n"
            "-foo\n"
            "+bar\n"
        )
        preamble, sections = pr.split_diff_sections(diff)
        assert preamble == ""
        assert len(sections) == 2
        assert sections[0]["depot"] == "//depot/a.cpp"
        assert sections[0]["rev"] == "1"
        assert "@@ -1 +1 @@" in sections[0]["body"]
        assert sections[1]["depot"] == "//depot/b.cpp"
        assert sections[1]["rev"] == "2"

    def test_empty_body_for_add(self):
        diff = (
            "==== //depot/edit.py#2 (text) ====\n"
            "@@ -1 +1 @@\n"
            "-a\n"
            "+b\n"
            "==== //depot/new.py#1 (text) ====\n"
            "\n"
        )
        _, sections = pr.split_diff_sections(diff)
        assert len(sections) == 2
        assert "@@" in sections[0]["body"]
        assert "@@" not in sections[1]["body"]

    def test_preamble_before_first_header(self):
        diff = "some preamble text\n==== //depot/a.cpp#1 (text) ====\n@@ -1 +1 @@\n"
        preamble, sections = pr.split_diff_sections(diff)
        assert "preamble" in preamble
        assert len(sections) == 1


# ---------------------------------------------------------------------------
# synthesize_add_hunk / synthesize_delete_hunk
# ---------------------------------------------------------------------------


class TestSynthesizeHunks:
    def test_add_hunk_prefixes_plus(self):
        content = "line one\nline two\nline three\n"
        hunk = pr.synthesize_add_hunk(content)
        assert "@@ -0,0 +1,3 @@" in hunk
        assert "+line one" in hunk
        assert "+line three" in hunk

    def test_add_hunk_empty_content(self):
        assert pr.synthesize_add_hunk("") == ""

    def test_delete_hunk_prefixes_minus(self):
        content = "old a\nold b\n"
        hunk = pr.synthesize_delete_hunk(content)
        assert "@@ -1,2 +0,0 @@" in hunk
        assert "-old a" in hunk
        assert "-old b" in hunk


# ---------------------------------------------------------------------------
# fetch_file_content — p4 print spec selection
# ---------------------------------------------------------------------------


class TestFetchFileContent:
    def test_shelved_add_uses_at_equals_cl(self):
        with patch.object(pr, "run_p4", return_value=(0, "content\n", "")) as mock:
            pr.fetch_file_content("//depot/x.py", "1", "12345", is_shelved=True, is_delete=False)
        assert mock.call_args_list[0][0][0] == ["print", "-q", "//depot/x.py@=12345"]

    def test_submitted_add_uses_hash_rev(self):
        with patch.object(pr, "run_p4", return_value=(0, "content\n", "")) as mock:
            pr.fetch_file_content("//depot/x.py", "7", "12345", is_shelved=False, is_delete=False)
        assert mock.call_args_list[0][0][0] == ["print", "-q", "//depot/x.py#7"]

    def test_submitted_delete_uses_prior_rev(self):
        with patch.object(pr, "run_p4", return_value=(0, "content\n", "")) as mock:
            pr.fetch_file_content("//depot/x.py", "5", "12345", is_shelved=False, is_delete=True)
        assert mock.call_args_list[0][0][0] == ["print", "-q", "//depot/x.py#4"]

    def test_submitted_delete_at_rev_1_returns_none(self):
        # No rev 0 to fetch — pre-history has no content.
        with patch.object(pr, "run_p4") as mock:
            result = pr.fetch_file_content(
                "//depot/x.py", "1", "12345", is_shelved=False, is_delete=True
            )
        assert result is None
        assert mock.call_count == 0

    def test_shelved_delete_uses_head(self):
        with patch.object(pr, "run_p4", return_value=(0, "content\n", "")) as mock:
            pr.fetch_file_content(
                "//depot/x.py", "3", "12345", is_shelved=True, is_delete=True
            )
        assert mock.call_args_list[0][0][0] == ["print", "-q", "//depot/x.py#head"]

    def test_p4_failure_returns_none(self):
        with patch.object(pr, "run_p4", return_value=(1, "", "error")):
            result = pr.fetch_file_content(
                "//depot/x.py", "1", "12345", is_shelved=False, is_delete=False
            )
        assert result is None


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

    def test_no_actions_returns_raw(self):
        out = "Differences ...\n==== //a.cpp#1 (text) ====\n@@ -1 +1 @@\n"
        # actions=None → behave like a passthrough
        result = pr.extract_diff(out, actions=None)
        assert "==== //a.cpp#1" in result

    def test_synthesizes_add_hunk_for_pure_add(self):
        describe = (
            "Affected files ...\n"
            "... //depot/edit.py#2 edit\n"
            "... //depot/new.py#1 add\n"
            "Differences ...\n"
            "\n"
            "==== //depot/edit.py#2 (text) ====\n"
            "@@ -1 +1 @@\n"
            "-a\n"
            "+b\n"
            "==== //depot/new.py#1 (text) ====\n"
            "\n"
        )
        actions = pr.parse_file_actions(describe)

        def fake_run_p4(args):
            if args == ["print", "-q", "//depot/new.py#1"]:
                return (0, "def foo():\n    return 42\n", "")
            return (1, "", "unexpected p4 call")

        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            diff = pr.extract_diff(describe, actions, cl="100", is_shelved=False)

        # Both files present in output
        assert "==== //depot/edit.py#2" in diff
        assert "==== //depot/new.py#1" in diff
        # Edit file's hunk preserved
        assert "@@ -1 +1 @@" in diff
        assert "-a" in diff
        assert "+b" in diff
        # Add file's synthesized hunk present
        assert "@@ -0,0 +1,2 @@" in diff
        assert "+def foo():" in diff
        assert "+    return 42" in diff

    def test_synthesizes_delete_hunk_for_delete(self):
        describe = (
            "Affected files ...\n"
            "... //depot/gone.py#5 delete\n"
            "Differences ...\n"
            "\n"
            "==== //depot/gone.py#5 (text) ====\n"
            "\n"
        )
        actions = pr.parse_file_actions(describe)

        def fake_run_p4(args):
            if args == ["print", "-q", "//depot/gone.py#4"]:
                return (0, "old line 1\nold line 2\n", "")
            return (1, "", "unexpected")

        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            diff = pr.extract_diff(describe, actions, cl="200", is_shelved=False)

        assert "@@ -1,2 +0,0 @@" in diff
        assert "-old line 1" in diff
        assert "-old line 2" in diff

    def test_shelved_add_uses_at_equals_cl(self):
        describe = (
            "Shelved files ...\n"
            "... //depot/new.py#1 add\n"
            "Differences ...\n"
            "\n"
            "==== //depot/new.py#1 (text) ====\n"
            "\n"
        )
        actions = pr.parse_file_actions(describe)

        calls: list[list[str]] = []

        def fake_run_p4(args):
            calls.append(args)
            if args == ["print", "-q", "//depot/new.py@=144072"]:
                return (0, "hello\n", "")
            return (1, "", "")

        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            diff = pr.extract_diff(describe, actions, cl="144072", is_shelved=True)

        assert ["print", "-q", "//depot/new.py@=144072"] in calls
        assert "+hello" in diff

    def test_warns_on_unhandled_add_to_stderr(self, capsys):
        describe = (
            "Affected files ...\n"
            "... //depot/new.py#1 add\n"
            "Differences ...\n"
            "==== //depot/new.py#1 (text) ====\n"
            "\n"
        )
        actions = pr.parse_file_actions(describe)
        with patch.object(pr, "run_p4", return_value=(1, "", "no such file")):
            pr.extract_diff(describe, actions, cl="300", is_shelved=False)
        err = capsys.readouterr().err
        assert "could not synthesize" in err
        assert "//depot/new.py" in err

    def test_stderr_notes_synthesized_files(self, capsys):
        describe = (
            "Affected files ...\n"
            "... //depot/new.py#1 add\n"
            "Differences ...\n"
            "==== //depot/new.py#1 (text) ====\n"
            "\n"
        )
        actions = pr.parse_file_actions(describe)
        with patch.object(pr, "run_p4", return_value=(0, "x\n", "")):
            pr.extract_diff(describe, actions, cl="400", is_shelved=False)
        err = capsys.readouterr().err
        assert "synthesized add hunks" in err
        assert "//depot/new.py" in err


# ---------------------------------------------------------------------------
# has_describe_content
# ---------------------------------------------------------------------------


class TestHasDescribeContent:
    def test_true_when_marker_and_file_header(self):
        out = "Differences ...\n==== //depot/a.cpp#1 (text) ====\n"
        assert pr.has_describe_content(out)

    def test_true_when_add_only_has_header_no_hunk(self):
        # The bug fix: pure-add sections have no @@ but we still want to accept the describe.
        out = "Differences ...\n==== //depot/new.py#1 (text) ====\n\n"
        assert pr.has_describe_content(out)

    def test_false_when_no_differences_section(self):
        assert not pr.has_describe_content("Affected files ...\n")

    def test_false_when_differences_empty(self):
        assert not pr.has_describe_content("Differences ...\n(no files)\n")


# ---------------------------------------------------------------------------
# fetch_describe — shelved fallback
# ---------------------------------------------------------------------------


class TestFetchDescribe:
    def test_committed_returns_first_with_is_shelved_false(self):
        committed_out = "Differences ...\n==== //a.cpp#1 (text) ====\n@@ -1 +1 @@\n"
        with patch.object(pr, "run_p4", return_value=(0, committed_out, "")) as mock:
            out, is_shelved = pr.fetch_describe("123")
            assert out == committed_out
            assert is_shelved is False
            assert mock.call_count == 1
            assert mock.call_args_list[0][0][0] == ["describe", "-du", "123"]

    def test_shelved_fallback_used(self):
        empty = "Affected files ...\n... //depot/a.cpp#1 edit\n"
        shelved = "Differences ...\n==== //a.cpp#1 (text) ====\n@@ -1 +1 @@\n"

        def side(args):
            if "-S" in args:
                return (0, shelved, "")
            return (0, empty, "")

        with patch.object(pr, "run_p4", side_effect=side) as mock:
            out, is_shelved = pr.fetch_describe("123")
            assert out == shelved
            assert is_shelved is True
            assert mock.call_count == 2

    def test_raises_when_neither_has_differences(self):
        empty = "Affected files ...\n"
        with patch.object(pr, "run_p4", return_value=(0, empty, "")):
            with pytest.raises(ValueError, match="no describe content"):
                pr.fetch_describe("123")

    def test_accepts_add_only_cl_without_hunks(self):
        # An add-only CL has file headers but no @@ — should still succeed.
        add_only = (
            "Differences ...\n"
            "==== //depot/new.py#1 (text) ====\n"
            "\n"
        )
        with patch.object(pr, "run_p4", return_value=(0, add_only, "")):
            out, is_shelved = pr.fetch_describe("123")
        assert out == add_only
        assert is_shelved is False


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
    def test_full_pipeline(self, tmp_path):
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
            "Affected files ...\n"
            "... //depot/src/foo.cpp#1 edit\n"
            "\n"
            "Differences ...\n"
            "\n"
            "==== //depot/src/foo.cpp#1 (text) ====\n"
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

    def test_mixed_edit_and_add_synthesizes_add_hunk(self, tmp_path):
        """Regression: a CL with edits + pure adds must include synthesized hunks for adds."""
        ws = tmp_path / "ws"
        ws.mkdir()
        edit_local = ws / "edit.py"
        add_local = ws / "new.py"
        edit_local.write_text("x = 2\n")
        add_local.write_text("")  # not needed; content comes from p4 print mock

        describe_out = (
            "Change 144072 by user@client on 2026/01/01\n"
            "\n"
            "\tMixed edit + add CL\n"
            "\n"
            "Affected files ...\n"
            "... //depot/edit.py#3 edit\n"
            "... //depot/new.py#1 add\n"
            "\n"
            "Differences ...\n"
            "\n"
            "==== //depot/edit.py#3 (text) ====\n"
            "@@ -1 +1 @@\n"
            "-x = 1\n"
            "+x = 2\n"
            "==== //depot/new.py#1 (text) ====\n"
            "\n"
        )
        where_out = (
            "... depotFile //depot/edit.py\n"
            f"... path {edit_local}\n"
            "\n"
            "... depotFile //depot/new.py\n"
            f"... path {add_local}\n"
        )
        info_out = f"... clientRoot {ws}\n"

        def fake_run_p4(args):
            if args[:2] == ["describe", "-du"] and "-S" not in args:
                return (0, describe_out, "")
            if args[:2] == ["-ztag", "where"]:
                return (0, where_out, "")
            if args[:2] == ["-ztag", "info"]:
                return (0, info_out, "")
            if args == ["print", "-q", "//depot/new.py#1"]:
                return (0, "def brief():\n    pass\n", "")
            return (1, "", f"unexpected: {args}")

        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            bundle = pr.build_bundle("144072")

        # Both files in changed_files
        depots = [f["depot"] for f in bundle["changed_files"]]
        assert "//depot/edit.py" in depots
        assert "//depot/new.py" in depots

        # Edit hunk intact
        assert "+x = 2" in bundle["diff"]
        # Add hunk synthesized
        assert "@@ -0,0 +1,2 @@" in bundle["diff"]
        assert "+def brief():" in bundle["diff"]

    def test_add_only_shelved_cl(self, tmp_path):
        """A shelved CL containing only adds (no edits) must bundle full content."""
        ws = tmp_path / "ws"
        ws.mkdir()

        # Committed describe finds no Differences section → shelved fallback.
        committed_out = "Change 1 by u@c on 2026/01/01\n\n\tdesc\n\nShelved files ...\n"
        shelved_out = (
            "Change 1 by u@c on 2026/01/01\n"
            "\n"
            "\tAdd new modules\n"
            "\n"
            "Shelved files ...\n"
            "\n"
            "... //depot/a.py#1 add\n"
            "... //depot/b.py#1 add\n"
            "\n"
            "Differences ...\n"
            "\n"
            "==== //depot/a.py#1 (text) ====\n"
            "\n"
            "==== //depot/b.py#1 (text) ====\n"
            "\n"
        )

        def fake_run_p4(args):
            if args[:2] == ["describe", "-du"] and "-S" not in args:
                return (0, committed_out, "")
            if args[:3] == ["describe", "-du", "-S"]:
                return (0, shelved_out, "")
            if args[:2] == ["-ztag", "where"]:
                return (0, "", "")  # no local mapping needed for this test
            if args[:2] == ["-ztag", "info"]:
                return (0, f"... clientRoot {ws}\n", "")
            if args == ["print", "-q", "//depot/a.py@=1"]:
                return (0, "content of a\n", "")
            if args == ["print", "-q", "//depot/b.py@=1"]:
                return (0, "content of b\n", "")
            return (1, "", f"unexpected: {args}")

        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            bundle = pr.build_bundle("1")

        assert bundle["description"] == "Add new modules"
        assert "+content of a" in bundle["diff"]
        assert "+content of b" in bundle["diff"]


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
