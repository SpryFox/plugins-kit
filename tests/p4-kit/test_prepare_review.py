"""Tests for p4-kit scripts/prepare_review.py."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

import prepare_review as pr


def _concat_diff_from_chunks(bundle: dict) -> str:
    """Read all chunk files for a bundle and concatenate -- the historical
    bundle["diff"] string, reconstructed from on-disk chunks.

    Tests that used to assert `bundle["diff"]` should call this instead.
    """
    bundle_dir = Path(bundle["bundle_dir"])
    return "".join(
        (bundle_dir / entry["path"]).read_text(encoding="utf-8")
        for entry in bundle["diff_chunks"]
    )


# ---------------------------------------------------------------------------
# run_p4 — subprocess invocation
# ---------------------------------------------------------------------------


class TestRunP4:
    def test_forces_utf8_decoding(self):
        """On Windows, default text decoding is cp1252 — CJK bytes abort the reader.

        `run_p4` must pin encoding to utf-8 with errors='replace' so diffs with
        non-Latin-1 content (CJK, emoji) decode cleanly on any platform.
        """
        captured: dict = {}

        def fake_run(cmd, **kwargs):
            captured.update(kwargs)
            result = subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
            return result

        with patch.object(subprocess, "run", side_effect=fake_run):
            pr.run_p4(["describe", "-du", "123"])

        assert captured.get("encoding") == "utf-8"
        assert captured.get("errors") == "replace"
        assert captured.get("capture_output") is True
        # Must NOT pass text=True alongside encoding (the combination is fine
        # but text=True alone — without encoding — is the original bug).
        assert captured.get("text") is not True or captured.get("encoding") == "utf-8"

    def test_coalesces_none_stdout_to_empty_string(self):
        """If the subprocess produced no output, callers should see '' not None."""
        fake = subprocess.CompletedProcess(["p4"], 0, stdout=None, stderr=None)
        with patch.object(subprocess, "run", return_value=fake):
            rc, out, err = pr.run_p4(["info"])
        assert rc == 0
        assert out == ""
        assert err == ""

    def test_decodes_cjk_content(self, tmp_path):
        """End-to-end: a p4-like command emitting UTF-8 CJK bytes decodes cleanly."""
        # Use python itself as a stand-in for `p4` to emit known UTF-8 bytes.
        # We can't easily reroute the argv[0]="p4" inside run_p4, so patch
        # subprocess.run to simulate the Popen/read path with real bytes decoding.
        payload = "差分 diff with emoji 🧪 and CJK 互動\n"
        fake = subprocess.CompletedProcess(["p4"], 0, stdout=payload, stderr="")
        with patch.object(subprocess, "run", return_value=fake):
            rc, out, _ = pr.run_p4(["describe", "-du", "1"])
        assert rc == 0
        assert "互動" in out
        assert "🧪" in out


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

    def test_mixed_cl_adds_missing_from_differences_synthesized(self):
        """Mixed CL: pure-adds listed in Shelved files but omitted from Differences.

        Real p4 behavior on some servers: `p4 describe -du -S` for a shelved mixed
        CL emits `==== ...====` headers ONLY for edits. Pure-add files appear only
        in the Shelved files listing, never in the Differences section. The script
        must still synthesize sections (header + hunk) for these missing files,
        not drop them silently.
        """
        describe = (
            "Shelved files ...\n"
            "... //depot/edit.cpp#3 edit\n"
            "... //depot/add1.cpp#1 add\n"
            "... //depot/add2.cpp#1 add\n"
            "Differences ...\n"
            "\n"
            "==== //depot/edit.cpp#3 (text) ====\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        actions = pr.parse_file_actions(describe)

        def fake_run_p4(args):
            if args == ["print", "-q", "//depot/add1.cpp@=99"]:
                return (0, "content of add1\n", "")
            if args == ["print", "-q", "//depot/add2.cpp@=99"]:
                return (0, "content of add2\n", "")
            return (1, "", f"unexpected: {args}")

        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            diff = pr.extract_diff(describe, actions, cl="99", is_shelved=True)

        # All three files must appear in the diff
        assert "==== //depot/edit.cpp#3" in diff
        assert "==== //depot/add1.cpp#1" in diff
        assert "==== //depot/add2.cpp#1" in diff
        # Edit preserved
        assert "-old" in diff
        assert "+new" in diff
        # Adds synthesized
        assert "+content of add1" in diff
        assert "+content of add2" in diff

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
# partition_diff_into_chunks + write_chunks
# ---------------------------------------------------------------------------


def _make_section(depot: str, body_bytes: int) -> str:
    """Build a single ==== file section padded to roughly `body_bytes` bytes."""
    header = f"==== {depot}#1 (text) ====\n"
    # @@ hunk + lines. Pad with `+x` lines so the section is ~body_bytes.
    line = "+xxxxxxxx\n"  # 10 bytes per line
    n = max(1, body_bytes // len(line))
    body = "@@ -0,0 +1,{n} @@\n".format(n=n) + (line * n)
    return header + body


class TestPartitionDiffIntoChunks:
    def test_single_small_file_fits_one_chunk(self):
        diff = _make_section("//d/a/foo.cpp", 100)
        chunks = pr.partition_diff_into_chunks(diff, max_bytes=1024 * 1024)
        assert len(chunks) == 1
        assert chunks[0]["files"] == ["//d/a/foo.cpp"]
        assert chunks[0]["text"].startswith("==== //d/a/foo.cpp")

    def test_empty_diff_returns_no_chunks(self):
        assert pr.partition_diff_into_chunks("", max_bytes=1024) == []

    def test_balances_when_total_exceeds_max(self):
        """K = ceil(total / max). Two files of ~600B each with max=1000 -> K=2 chunks of ~600B each.

        The greedy fill-to-max alternative would put both into one 1200B chunk
        (over cap) or one full + one tiny -- both worse than balanced halves.
        """
        diff = (
            _make_section("//d/a/file1.cpp", 600)
            + _make_section("//d/b/file2.cpp", 600)
        )
        chunks = pr.partition_diff_into_chunks(diff, max_bytes=1000)
        assert len(chunks) == 2
        # Each chunk got exactly one file.
        assert chunks[0]["files"] == ["//d/a/file1.cpp"]
        assert chunks[1]["files"] == ["//d/b/file2.cpp"]
        # Both well-balanced, well under max.
        assert all(c["bytes"] < 1000 for c in chunks)

    def test_never_splits_a_file_even_when_oversized(self):
        """A single file larger than max_bytes lands alone in an oversized chunk.

        We can't split a file mid-hunk -- the section is atomic. Caller accepts
        the breach for that one chunk; oversize is bounded by file size.
        """
        diff = _make_section("//d/huge.bin", 2048)
        chunks = pr.partition_diff_into_chunks(diff, max_bytes=512)
        assert len(chunks) == 1
        assert chunks[0]["bytes"] >= 2048
        assert chunks[0]["files"] == ["//d/huge.bin"]

    def test_prefers_directory_boundary_for_split(self):
        """When the chunk is past target, close at a directory transition, not mid-dir.

        Files in dirA/ should stay together; the split happens between dirA and dirB.
        """
        sections = (
            _make_section("//d/dirA/f1.cpp", 300)
            + _make_section("//d/dirA/f2.cpp", 300)
            + _make_section("//d/dirA/f3.cpp", 300)
            + _make_section("//d/dirB/g1.cpp", 300)
            + _make_section("//d/dirB/g2.cpp", 300)
            + _make_section("//d/dirB/g3.cpp", 300)
        )
        # K = ceil(1800 / 1500) = 2. Target = 900.
        # Without the directory preference, the boundary would fall after f3
        # (cur ~900). With the preference it also falls there since f3 -> g1
        # IS a dir transition; this test verifies the boundary doesn't cut
        # mid-directory when the size hits target mid-way.
        chunks = pr.partition_diff_into_chunks(sections, max_bytes=1500)
        assert len(chunks) == 2
        # Each chunk holds exactly one directory's files.
        assert chunks[0]["files"] == [
            "//d/dirA/f1.cpp", "//d/dirA/f2.cpp", "//d/dirA/f3.cpp",
        ]
        assert chunks[1]["files"] == [
            "//d/dirB/g1.cpp", "//d/dirB/g2.cpp", "//d/dirB/g3.cpp",
        ]

    def test_holds_off_close_until_directory_transition(self):
        """When target is hit mid-directory, keep packing until we cross a dir boundary.

        20 files in dirA + 10 in dirB, ~131 B each. Total ~3930 B, max=3000
        forces K=2, target=1965. Naive close-at-target would close after
        ~15 dirA files (mid-directory). The directory-aware logic holds off
        until the first dirA -> dirB transition, putting all 20 dirA files
        in chunk0 (~2620 B, still under max) and all 10 dirB files in chunk1.
        """
        sections = "".join(
            _make_section(f"//d/dirA/f{i}.cpp", 80) for i in range(20)
        ) + "".join(
            _make_section(f"//d/dirB/g{i}.cpp", 80) for i in range(10)
        )
        chunks = pr.partition_diff_into_chunks(sections, max_bytes=3000)
        assert len(chunks) == 2
        # All dirA files land in chunk0, all dirB files in chunk1 -- no dir splits.
        assert all("/dirA/" in f for f in chunks[0]["files"])
        assert all("/dirB/" in f for f in chunks[1]["files"])
        assert len(chunks[0]["files"]) == 20
        assert len(chunks[1]["files"]) == 10

    def test_hard_cap_forces_close_even_within_directory(self):
        """When the next file would breach max, close even if still in the same dir.

        Hard cap wins over the dir-coherence preference -- we can't let a
        chunk grow past the Read tool's threshold just to keep a directory
        together.
        """
        sections = (
            _make_section("//d/dirA/f1.cpp", 700)
            + _make_section("//d/dirA/f2.cpp", 700)
            + _make_section("//d/dirA/f3.cpp", 700)
        )
        chunks = pr.partition_diff_into_chunks(sections, max_bytes=1000)
        # Each file alone is 700+, two files together would be 1400 > 1000.
        # So each file gets its own chunk.
        assert len(chunks) == 3
        for c in chunks:
            assert len(c["files"]) == 1

    def test_preamble_kept_with_first_chunk(self):
        """Diff preamble (before any ==== header) attaches to the first chunk."""
        diff = "preamble line\n" + _make_section("//d/a.cpp", 100)
        chunks = pr.partition_diff_into_chunks(diff, max_bytes=1024 * 1024)
        assert len(chunks) == 1
        assert chunks[0]["text"].startswith("preamble line\n")


class TestWriteChunks:
    def test_writes_files_and_returns_index(self, tmp_path):
        chunks = [
            {"text": "chunk0 text\n", "files": ["//d/a.cpp"], "bytes": 12},
            {"text": "chunk1 text\n", "files": ["//d/b.cpp", "//d/c.cpp"], "bytes": 12},
        ]
        index = pr.write_chunks(chunks, tmp_path)
        assert (tmp_path / "chunks" / "chunk-000.diff").read_text() == "chunk0 text\n"
        assert (tmp_path / "chunks" / "chunk-001.diff").read_text() == "chunk1 text\n"
        assert index == [
            {"index": 0, "path": "chunks/chunk-000.diff", "files": ["//d/a.cpp"], "bytes": 12},
            {"index": 1, "path": "chunks/chunk-001.diff", "files": ["//d/b.cpp", "//d/c.cpp"], "bytes": 12},
        ]

    def test_removes_stale_chunks_from_prior_run(self, tmp_path):
        """A re-run that produces fewer chunks must not leave orphaned chunk files behind."""
        chunks_dir = tmp_path / "chunks"
        chunks_dir.mkdir()
        (chunks_dir / "chunk-000.diff").write_text("stale 0\n")
        (chunks_dir / "chunk-001.diff").write_text("stale 1\n")
        (chunks_dir / "chunk-099.diff").write_text("stale 99\n")

        new_chunks = [{"text": "fresh\n", "files": ["//d/x.cpp"], "bytes": 6}]
        pr.write_chunks(new_chunks, tmp_path)

        survivors = sorted(p.name for p in chunks_dir.glob("chunk-*.diff"))
        assert survivors == ["chunk-000.diff"]
        assert (chunks_dir / "chunk-000.diff").read_text() == "fresh\n"

    def test_empty_chunks_writes_no_files(self, tmp_path):
        index = pr.write_chunks([], tmp_path)
        assert index == []
        # Directory created (empty), no chunk files.
        assert (tmp_path / "chunks").is_dir()
        assert list((tmp_path / "chunks").iterdir()) == []


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

    def test_true_for_pure_add_with_only_affected_files_section(self):
        """Pure-add CLs may emit no Differences-section headers at all.

        Perforce gives pure-add CLs no `==== ====` headers under
        `Differences ...` because there is no prior version to diff against.
        The synthesizable add action listed under `Affected files ...`
        is enough to mark the describe as reviewable -- extract_diff
        will fill in the diff body via p4 print.
        """
        out = (
            "Affected files ...\n"
            "\n"
            "... //depot/new.py#1 add\n"
            "\n"
            "Differences ...\n"
        )
        assert pr.has_describe_content(out)

    def test_true_for_pure_delete_with_only_shelved_files_section(self):
        out = (
            "Shelved files ...\n"
            "\n"
            "... //depot/old.py#3 delete\n"
            "\n"
            "Differences ...\n"
        )
        assert pr.has_describe_content(out)

    def test_false_for_edit_only_section_without_differences_headers(self):
        """Edits cannot be synthesized -- they need real diff bodies.

        A describe that lists only edits in Affected files but has no
        Differences-section headers means the diff is genuinely missing
        (e.g. a pending edit that hasn't been shelved yet). Reject it so
        callers fall through to the shelved fallback.
        """
        out = (
            "Affected files ...\n"
            "\n"
            "... //depot/changed.py#5 edit\n"
            "\n"
        )
        assert not pr.has_describe_content(out)


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

    def test_accepts_submitted_pure_add_with_no_differences_headers(self):
        """Submitted pure-add CLs whose `==== ====` headers are missing under Differences.

        Some Perforce describe responses for submitted pure-add CLs list the
        adds in `Affected files ...` but emit an empty `Differences ...`
        section -- there is nothing to diff against. extract_diff can still
        synthesize hunks via `p4 print #<rev>`, so fetch_describe should
        accept this output rather than rejecting it.
        """
        submitted_pure_add = (
            "Change 999 by user@client on 2026/01/01 12:00:00\n"
            "\n"
            "\tdesc\n"
            "\n"
            "Affected files ...\n"
            "\n"
            "... //depot/new.py#1 add\n"
            "\n"
            "Differences ...\n"
        )
        with patch.object(pr, "run_p4", return_value=(0, submitted_pure_add, "")) as mock:
            out, is_shelved = pr.fetch_describe("999")
        assert is_shelved is False
        # No fallback to -S needed since the submitted output is reviewable.
        assert mock.call_count == 1

    def test_pending_pure_add_routed_to_shelved_path(self):
        """Pending pure-add CLs must be read via -S so synthesis uses @=<CL>.

        Going through the regular describe would return is_shelved=False,
        and `p4 print #1` for a pending add would fail (no submitted rev
        exists). Forcing the -S path returns is_shelved=True so synthesis
        uses the shelved spec @=<CL>, which works.
        """
        pending_unshelved = (
            "Change 144098 by user@client on 2026/01/01 12:00:00 *pending*\n"
            "\n"
            "\tdesc\n"
            "\n"
            "Affected files ...\n"
            "\n"
            "... //depot/new.py#1 add\n"
            "\n"
        )
        pending_shelved = (
            "Change 144098 by user@client on 2026/01/01 12:00:00 *pending*\n"
            "\n"
            "\tdesc\n"
            "\n"
            "Shelved files ...\n"
            "\n"
            "... //depot/new.py#1 add\n"
            "\n"
            "Differences ...\n"
        )

        def side(args):
            if "-S" in args:
                return (0, pending_shelved, "")
            return (0, pending_unshelved, "")

        with patch.object(pr, "run_p4", side_effect=side) as mock:
            out, is_shelved = pr.fetch_describe("144098")
        assert is_shelved is True
        assert out == pending_shelved
        assert mock.call_count == 2

    def test_pending_unshelved_raises_with_shelve_hint(self):
        """A pending CL with no shelved content gets a useful error.

        Synthesis of pending adds requires shelved content (@=<CL>); a
        pending CL with no shelf cannot be reviewed. The error must point
        the caller at `p4 shelve` rather than emitting a generic 'no
        describe content' message.
        """
        pending_unshelved = (
            "Change 144098 by user@client on 2026/01/01 12:00:00 *pending*\n"
            "\n"
            "\tdesc\n"
            "\n"
            "Affected files ...\n"
            "\n"
            "... //depot/new.py#1 add\n"
            "\n"
        )
        empty_shelved = (
            "Change 144098 by user@client on 2026/01/01 12:00:00 *pending*\n"
        )

        def side(args):
            if "-S" in args:
                return (0, empty_shelved, "")
            return (0, pending_unshelved, "")

        with patch.object(pr, "run_p4", side_effect=side):
            with pytest.raises(ValueError, match=r"shelve.*144098"):
                pr.fetch_describe("144098")


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
# compute_minimal_dirs
# ---------------------------------------------------------------------------


class TestComputeMinimalDirs:
    def test_collapses_descendants(self, tmp_path):
        a = tmp_path / "a"
        ab = a / "b"
        c = tmp_path / "c"
        ab.mkdir(parents=True)
        c.mkdir()
        files = [str(a / "f1.cpp"), str(ab / "f2.cpp"), str(c / "f3.cpp")]
        result = pr.compute_minimal_dirs(files)
        # /a covers /a/b → only /a and /c remain, both recursive
        assert {(p.resolve(), r) for p, r in result} == {
            (a.resolve(), True),
            (c.resolve(), True),
        }

    def test_skips_none_and_missing(self, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        files = [None, str(real / "x.cpp"), str(tmp_path / "ghost" / "y.cpp")]
        result = pr.compute_minimal_dirs(files)
        assert {(p.resolve(), r) for p, r in result} == {(real.resolve(), True)}

    def test_empty(self):
        assert pr.compute_minimal_dirs([]) == []

    def test_unique_dir_kept(self, tmp_path):
        a = tmp_path / "a"
        a.mkdir()
        files = [str(a / "x.cpp"), str(a / "y.cpp"), str(a / "z.cpp")]
        result = pr.compute_minimal_dirs(files)
        assert len(result) == 1
        assert result[0][0].resolve() == a.resolve()
        assert result[0][1] is True

    def test_sibling_dirs_both_kept(self, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        files = [str(a / "x.cpp"), str(b / "y.cpp")]
        result = pr.compute_minimal_dirs(files)
        assert {(p.resolve(), r) for p, r in result} == {
            (a.resolve(), True),
            (b.resolve(), True),
        }

    def test_workspace_root_does_not_absorb_descendants(self, tmp_path):
        """A CL touching a workspace-root file plus a deep file must NOT collapse
        to a recursive scan of the entire workspace. The root is kept as a
        non-recursive scan target (`<root>/*`); the deep dir keeps its own
        recursive scan separately. See module docstring for rationale."""
        ws = tmp_path / "ws"
        deep = ws / "plugins" / "p4-kit" / "scripts"
        deep.mkdir(parents=True)
        files = [str(ws / "CLAUDE.md"), str(deep / "prepare_review.py")]
        result = pr.compute_minimal_dirs(files, workspace_root=ws)
        assert {(p.resolve(), r) for p, r in result} == {
            (ws.resolve(), False),
            (deep.resolve(), True),
        }

    def test_workspace_root_only_is_non_recursive(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        files = [str(ws / "CLAUDE.md"), str(ws / "marketplace.json")]
        result = pr.compute_minimal_dirs(files, workspace_root=ws)
        assert result == [(ws.resolve(), False)]

    def test_no_workspace_root_arg_preserves_old_collapse(self, tmp_path):
        """When workspace_root is None, the function still collapses ancestors."""
        a = tmp_path / "a"
        ab = a / "b"
        ab.mkdir(parents=True)
        files = [str(a / "x.cpp"), str(ab / "y.cpp")]
        result = pr.compute_minimal_dirs(files)
        assert {(p.resolve(), r) for p, r in result} == {(a.resolve(), True)}


# ---------------------------------------------------------------------------
# find_unreconciled
# ---------------------------------------------------------------------------


class TestFindUnreconciled:
    def test_parses_ztag_output(self, tmp_path):
        d = tmp_path / "src"
        d.mkdir()
        out = (
            "... depotFile //depot/src/new.cpp\n"
            "... clientFile /ws/src/new.cpp\n"
            "... rev 1\n"
            "... action add\n"
            "... type text\n"
            "\n"
            "... depotFile //depot/src/edited.cpp\n"
            "... clientFile /ws/src/edited.cpp\n"
            "... rev 3\n"
            "... action edit\n"
            "... type text\n"
            "\n"
            "... depotFile //depot/src/gone.cpp\n"
            "... clientFile /ws/src/gone.cpp\n"
            "... rev 2\n"
            "... action delete\n"
            "... type text\n"
        )
        with patch.object(pr, "run_p4", return_value=(0, out, "")):
            result = pr.find_unreconciled([(d, True)])
        assert result == [
            {"local": "/ws/src/new.cpp", "depot": "//depot/src/new.cpp", "action": "add"},
            {"local": "/ws/src/edited.cpp", "depot": "//depot/src/edited.cpp", "action": "edit"},
            {"local": "/ws/src/gone.cpp", "depot": "//depot/src/gone.cpp", "action": "delete"},
        ]

    def test_uses_recursive_dir_specs(self, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        captured: list[list[str]] = []

        def fake_run_p4(args):
            captured.append(args)
            return (0, "", "")

        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            pr.find_unreconciled([(a, True), (b, True)])

        assert captured[0][:3] == ["-ztag", "reconcile", "-n"]
        # Each dir is passed as a recursive `<dir>/...` spec.
        specs = captured[0][3:]
        assert any(s.endswith("/...") and str(a) in s for s in specs)
        assert any(s.endswith("/...") and str(b) in s for s in specs)

    def test_non_recursive_dir_uses_star_spec(self, tmp_path):
        """A `(dir, False)` entry must scan with `<dir>/*` (immediate children only),
        not `<dir>/...` -- this is what bounds the workspace-root scan."""
        root = tmp_path / "ws"
        deep = root / "plugins" / "scripts"
        deep.mkdir(parents=True)
        captured: list[list[str]] = []

        def fake_run_p4(args):
            captured.append(args)
            return (0, "", "")

        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            pr.find_unreconciled([(root, False), (deep, True)])

        specs = captured[0][3:]
        assert f"{root}/*" in specs
        assert f"{deep}/..." in specs
        # The recursive workspace-root spec must NOT appear.
        assert f"{root}/..." not in specs

    def test_empty_dirs_returns_empty(self):
        # No p4 call should be made when there's nothing to scan.
        with patch.object(pr, "run_p4") as mock:
            assert pr.find_unreconciled([]) == []
        assert mock.call_count == 0

    def test_no_files_to_reconcile_treated_as_empty(self, tmp_path):
        d = tmp_path / "x"
        d.mkdir()
        with patch.object(
            pr,
            "run_p4",
            return_value=(1, "", "/ws/x - no file(s) to reconcile.\n"),
        ):
            assert pr.find_unreconciled([(d, True)]) == []

    def test_p4_failure_returns_empty_with_warning(self, tmp_path, capsys):
        d = tmp_path / "x"
        d.mkdir()
        with patch.object(pr, "run_p4", return_value=(1, "", "fatal: bad workspace\n")):
            assert pr.find_unreconciled([(d, True)]) == []
        err = capsys.readouterr().err
        assert "reconcile check failed" in err

    def test_skips_entries_missing_required_fields(self, tmp_path):
        # Defensive: an incomplete record (no action, or no clientFile) is dropped.
        d = tmp_path / "x"
        d.mkdir()
        out = (
            "... depotFile //depot/orphan.cpp\n"
            "... rev 1\n"
            "\n"
            "... clientFile /ws/no-action.cpp\n"
            "... depotFile //depot/no-action.cpp\n"
            "\n"
            "... depotFile //depot/good.cpp\n"
            "... clientFile /ws/good.cpp\n"
            "... action add\n"
        )
        with patch.object(pr, "run_p4", return_value=(0, out, "")):
            result = pr.find_unreconciled([(d, True)])
        assert len(result) == 1
        assert result[0]["local"] == "/ws/good.cpp"


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
            if args[:3] == ["-ztag", "reconcile", "-n"]:
                return (1, "", "no file(s) to reconcile.\n")
            return (1, "", "")

        bundle_dir = tmp_path / "bundle"
        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            bundle = pr.build_bundle("999", bundle_dir)

        assert bundle["cl"] == "999"
        assert bundle["description"] == "Fix the thing"
        assert bundle["bundle_dir"] == str(bundle_dir)
        # Diff content lives in chunk files on disk now; no inline `diff` field.
        assert "diff" not in bundle
        assert len(bundle["diff_chunks"]) >= 1
        assert "==== //depot/src/foo.cpp#1" in _concat_diff_from_chunks(bundle)
        assert len(bundle["changed_files"]) == 1
        cf = bundle["changed_files"][0]
        assert cf["depot"] == "//depot/src/foo.cpp"
        assert Path(cf["local"]) == local_file
        # The single-file CL should land in a single chunk (index 0).
        assert cf["chunk_index"] == 0
        assert len(cf["claude_mds"]) == 1
        assert Path(cf["claude_mds"][0]).read_text() == "workspace rule\n"
        assert len(bundle["unique_claude_mds"]) == 1
        assert bundle["unreconciled"] == []

    def test_unreconciled_files_surfaced(self, tmp_path):
        """build_bundle reports files missing from the CL via `p4 reconcile -n`."""
        ws = tmp_path / "ws"
        src = ws / "src"
        src.mkdir(parents=True)
        local_file = src / "foo.cpp"
        local_file.write_text("int x = 1;\n")
        # A sibling file that exists on disk but isn't in the CL.
        forgotten = src / "forgot.cpp"
        forgotten.write_text("int y = 2;\n")

        describe_out = (
            "Change 1000 by user@client on 2026/01/01\n"
            "\n"
            "\tEdit foo\n"
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
        reconcile_out = (
            "... depotFile //depot/src/forgot.cpp\n"
            f"... clientFile {forgotten}\n"
            "... rev 1\n"
            "... action add\n"
            "... type text\n"
        )

        def fake_run_p4(args):
            if args[:2] == ["describe", "-du"]:
                return (0, describe_out, "")
            if args[:2] == ["-ztag", "where"]:
                return (0, where_out, "")
            if args[:2] == ["-ztag", "info"]:
                return (0, info_out, "")
            if args[:3] == ["-ztag", "reconcile", "-n"]:
                return (0, reconcile_out, "")
            return (1, "", f"unexpected: {args}")

        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            bundle = pr.build_bundle("1000", tmp_path / "bundle")

        assert len(bundle["unreconciled"]) == 1
        u = bundle["unreconciled"][0]
        assert u["action"] == "add"
        assert u["depot"] == "//depot/src/forgot.cpp"
        assert Path(u["local"]) == forgotten

    def test_root_level_cl_file_does_not_trigger_recursive_root_scan(self, tmp_path):
        """Regression: a CL touching a workspace-root file (e.g. CLAUDE.md) plus a
        deep file used to collapse to `<root>/...`, recursively scanning every
        untracked dir in the workspace (Binaries/, Intermediate/, IDE files, etc.
        that may not all be in .p4ignore). The fix bounds root to `<root>/*`."""
        ws = tmp_path / "ws"
        deep = ws / "plugins" / "p4-kit" / "scripts"
        deep.mkdir(parents=True)
        root_file = ws / "CLAUDE.md"
        root_file.write_text("rules\n")
        deep_file = deep / "prepare_review.py"
        deep_file.write_text("# code\n")

        describe_out = (
            "Change 7 by u@c on 2026/01/01\n"
            "\n"
            "\tEdit\n"
            "\n"
            "Affected files ...\n"
            "... //depot/CLAUDE.md#1 edit\n"
            "... //depot/plugins/p4-kit/scripts/prepare_review.py#1 edit\n"
            "\n"
            "Differences ...\n"
            "\n"
            "==== //depot/CLAUDE.md#1 (text) ====\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
            "==== //depot/plugins/p4-kit/scripts/prepare_review.py#1 (text) ====\n"
            "@@ -1 +1 @@\n"
            "-a\n"
            "+b\n"
        )
        where_out = (
            "... depotFile //depot/CLAUDE.md\n"
            f"... path {root_file}\n"
            "\n"
            "... depotFile //depot/plugins/p4-kit/scripts/prepare_review.py\n"
            f"... path {deep_file}\n"
        )
        info_out = f"... clientRoot {ws}\n"
        captured_reconcile_specs: list[str] = []

        def fake_run_p4(args):
            if args[:2] == ["describe", "-du"]:
                return (0, describe_out, "")
            if args[:2] == ["-ztag", "where"]:
                return (0, where_out, "")
            if args[:2] == ["-ztag", "info"]:
                return (0, info_out, "")
            if args[:3] == ["-ztag", "reconcile", "-n"]:
                captured_reconcile_specs.extend(args[3:])
                return (1, "", "no file(s) to reconcile.\n")
            return (1, "", f"unexpected: {args}")

        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            pr.build_bundle("7", tmp_path / "bundle")

        ws_resolved = ws.resolve()
        deep_resolved = deep.resolve()
        # Root scanned non-recursively
        assert f"{ws_resolved}/*" in captured_reconcile_specs
        # Recursive root scan must NOT appear (this was the bug)
        assert f"{ws_resolved}/..." not in captured_reconcile_specs
        # Deep dir keeps its own recursive scan (not absorbed by root)
        assert f"{deep_resolved}/..." in captured_reconcile_specs

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
            if args[:3] == ["-ztag", "reconcile", "-n"]:
                return (1, "", "no file(s) to reconcile.\n")
            if args == ["print", "-q", "//depot/new.py#1"]:
                return (0, "def brief():\n    pass\n", "")
            return (1, "", f"unexpected: {args}")

        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            bundle = pr.build_bundle("144072", tmp_path / "bundle")

        # Both files in changed_files
        depots = [f["depot"] for f in bundle["changed_files"]]
        assert "//depot/edit.py" in depots
        assert "//depot/new.py" in depots

        diff = _concat_diff_from_chunks(bundle)
        # Edit hunk intact
        assert "+x = 2" in diff
        # Add hunk synthesized
        assert "@@ -0,0 +1,2 @@" in diff
        assert "+def brief():" in diff

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
            if args[:3] == ["-ztag", "reconcile", "-n"]:
                return (1, "", "no file(s) to reconcile.\n")
            if args == ["print", "-q", "//depot/a.py@=1"]:
                return (0, "content of a\n", "")
            if args == ["print", "-q", "//depot/b.py@=1"]:
                return (0, "content of b\n", "")
            return (1, "", f"unexpected: {args}")

        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            bundle = pr.build_bundle("1", tmp_path / "bundle")

        assert bundle["description"] == "Add new modules"
        diff = _concat_diff_from_chunks(bundle)
        assert "+content of a" in diff
        assert "+content of b" in diff

    def test_mixed_cl_adds_omitted_from_differences(self, tmp_path):
        """Regression (Spirit Crossing CL 144098): on some p4 servers, `describe -du -S`
        for a shelved mixed CL emits ==== headers ONLY for edits. Pure-adds appear only
        in the Shelved files listing. Previously these were silently dropped.
        """
        ws = tmp_path / "ws"
        ws.mkdir()

        committed_out = "Change 144098 by u@c on 2026/01/01 *pending*\n"
        shelved_out = (
            "Change 144098 by u@c on 2026/01/01 *pending*\n"
            "\n"
            "\tModule + facade wiring\n"
            "\n"
            "Shelved files ...\n"
            "\n"
            "... //depot/facade.cpp#4 edit\n"
            "... //depot/mod_a.cpp#1 add\n"
            "... //depot/mod_b.cpp#1 add\n"
            "... //depot/mod_c.cpp#1 add\n"
            "\n"
            "Differences ...\n"
            "\n"
            "==== //depot/facade.cpp#4 (text) ====\n"
            "@@ -1 +1 @@\n"
            "-wire_old();\n"
            "+wire_new();\n"
        )

        def fake_run_p4(args):
            if args[:2] == ["describe", "-du"] and "-S" not in args:
                return (0, committed_out, "")
            if args[:3] == ["describe", "-du", "-S"]:
                return (0, shelved_out, "")
            if args[:2] == ["-ztag", "where"]:
                return (0, "", "")
            if args[:2] == ["-ztag", "info"]:
                return (0, f"... clientRoot {ws}\n", "")
            if args[:3] == ["-ztag", "reconcile", "-n"]:
                return (1, "", "no file(s) to reconcile.\n")
            if args == ["print", "-q", "//depot/mod_a.cpp@=144098"]:
                return (0, "mod_a contents\n", "")
            if args == ["print", "-q", "//depot/mod_b.cpp@=144098"]:
                return (0, "mod_b contents\n", "")
            if args == ["print", "-q", "//depot/mod_c.cpp@=144098"]:
                return (0, "mod_c contents\n", "")
            return (1, "", f"unexpected: {args}")

        with patch.object(pr, "run_p4", side_effect=fake_run_p4):
            bundle = pr.build_bundle("144098", tmp_path / "bundle")

        # All four files in changed_files — not just the edit
        depots = [f["depot"] for f in bundle["changed_files"]]
        assert depots == [
            "//depot/facade.cpp",
            "//depot/mod_a.cpp",
            "//depot/mod_b.cpp",
            "//depot/mod_c.cpp",
        ]

        diff = _concat_diff_from_chunks(bundle)
        # Edit preserved
        assert "+wire_new();" in diff
        # Adds synthesized with full content, even though they had no ==== header in Differences
        assert "==== //depot/mod_a.cpp#1" in diff
        assert "==== //depot/mod_b.cpp#1" in diff
        assert "==== //depot/mod_c.cpp#1" in diff
        assert "+mod_a contents" in diff
        assert "+mod_b contents" in diff
        assert "+mod_c contents" in diff


# ---------------------------------------------------------------------------
# main — CLI
# ---------------------------------------------------------------------------


class TestMain:
    def test_no_args_returns_2(self, capsys):
        rc = pr.main(["prepare_review.py"])
        assert rc == 2
        assert "Usage" in capsys.readouterr().err

    def test_value_error_returns_1(self, capsys, tmp_path):
        with patch.object(pr, "DEFAULT_BUNDLE_ROOT", tmp_path / "reviews"), \
                patch.object(pr, "build_bundle", side_effect=ValueError("nope")):
            rc = pr.main(["prepare_review.py", "123"])
        assert rc == 1
        assert "nope" in capsys.readouterr().err

    def test_success_prints_json_and_persists_bundle(self, capsys, tmp_path):
        """main() prints the bundle to stdout AND persists bundle.json next to chunks."""
        reviews_root = tmp_path / "reviews"
        fake_bundle = {"cl": "123", "bundle_dir": str(reviews_root / "123")}
        with patch.object(pr, "DEFAULT_BUNDLE_ROOT", reviews_root), \
                patch.object(pr, "build_bundle", return_value=fake_bundle):
            rc = pr.main(["prepare_review.py", "123"])
        assert rc == 0
        captured = capsys.readouterr()
        assert json.loads(captured.out) == fake_bundle
        persisted = json.loads((reviews_root / "123" / "bundle.json").read_text())
        assert persisted == fake_bundle
