"""Gather review context for a git diff range.

Usage:
    prepare_review.py                   # auto-detect range from workspace state
    prepare_review.py <ref>             # review <ref>..HEAD
    prepare_review.py <a>..<b>          # review the given range
    prepare_review.py <a>...<b>         # review the symmetric difference (merge-base..b)
    prepare_review.py --staged          # review index vs HEAD
    prepare_review.py --working         # review working tree vs HEAD (uncommitted)

Auto-detect resolution order:
    1. Mid-merge (MERGE_HEAD present)            -> review the in-progress merge
    2. Mid-rebase (rebase-merge/-apply present)  -> review the in-progress rebase
    3. HEAD has upstream                         -> @{upstream}..HEAD
    4. origin/main exists                        -> origin/main..HEAD
    5. origin/master exists                      -> origin/master..HEAD
    6. local main exists                         -> main..HEAD
    7. local master exists                       -> master..HEAD
    Else exit non-zero with a hint to pass an explicit range.

Outputs a JSON bundle on stdout AND persists `bundle.json` next to the
per-file chunk fragments at:
    ~/.claude/plugins/data/plugins-kit/git-kit/reviews/<safe-range-name>/

The diff is partitioned into chunks <=MAX_CHUNK_BYTES at file boundaries
(directory transitions preferred) so reviewer subagents can Read one
chunk per agent and fan out across a large diff. Chunking, CLAUDE.md
ancestor walk, and submit-gate parsing live in bootstrap_lib.code_review
and are shared with p4-kit's p4-code-review skill.

Output schema:
    {
      "vcs": "git",
      "range": "<the diff range we reviewed, e.g. origin/main..HEAD>",
      "head_sha": "<short sha of HEAD>",
      "branch": "<current branch name or 'DETACHED'>",
      "auto_detected_reason": "<human-readable reason chosen, omitted if explicit>",
      "description": "<one or more commit subjects joined by '; '>",
      "bundle_dir": "<absolute path to bundle directory>",
      "diff_chunks": [
        {"index": 0, "path": "chunks/chunk-000.diff",
         "files": ["<repo-relative path>", ...], "bytes": <int>}
      ],
      "changed_files": [
        {"path": "<repo-relative path>", "local": "<absolute path>",
         "status": "A"|"M"|"D"|"R"|"C"|"T",
         "chunk_index": <int or null>,
         "claude_mds": ["<absolute path>", ...]}
      ],
      "unique_claude_mds": ["<absolute path>", ...],
      "untracked_or_unstaged": [
        {"local": "<absolute path>", "path": "<repo-relative>",
         "kind": "untracked"|"unstaged_modified"|"unstaged_deleted"|"staged_uncommitted"}
      ],
      "merge_conflicts": [
        {"path": "<repo-relative>", "local": "<absolute path>"}
      ],
      "submit_gates": [
        {"source": "<absolute path to CLAUDE.md>",
         "summary": "<one-line imperative>",
         "scope_paths": ["<prefix or glob>", ...],
         "matched_files": ["<local path>", ...],
         "rationale": "<optional prose, may be empty>",
         "line_no": <int>}
      ]
    }

Stderr-only diagnostics. Non-zero exit on hard failure.
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from bootstrap_lib.path_repair import repair_path  # noqa: E402
repair_path()

from bootstrap_lib.code_review.chunking import (  # noqa: E402
    partition_sections_into_chunks,
    write_chunks,
)
from bootstrap_lib.code_review.claude_mds import (  # noqa: E402
    collect_claude_mds,
    collect_submit_gates,
)


# Mirror p4-kit's choice for the same reason -- Read tool refuses files
# beyond some unpublished threshold (a 1.4 MB plain-text diff fails).
# 1 MB leaves ~40% headroom and keeps chunk counts close to 1 for typical
# diffs. Tune downward if a Read failure surfaces.
MAX_CHUNK_BYTES = 1024 * 1024

DEFAULT_BUNDLE_ROOT = (
    Path.home() / ".claude" / "plugins" / "data"
    / "plugins-kit" / "git-kit" / "reviews"
)

# git diff section header: `diff --git a/path/to/file b/path/to/file`
# For renames the a-side and b-side differ; the b-side is the post-image
# and is the canonical identifier for the changed file.
_GIT_FILE_HEADER = re.compile(r"^diff --git a/(\S+) b/(\S+)\s*$")

# Status letters in `git diff --name-status` and `git status --porcelain`.
_STATUS_CHARS = set("AMDRCT")


def run_git(args: list[str], cwd: Optional[Path] = None) -> tuple[int, str, str]:
    """Run a git command, return (returncode, stdout, stderr).

    Forces UTF-8 decoding for the same reasons p4-kit does -- non-Latin-1
    file content (CJK, emoji) in diffs would abort the subprocess reader
    on Windows under cp1252.
    """
    proc = subprocess.run(
        ["git", *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd) if cwd else None,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


# ---------------------------------------------------------------------------
# Workspace state detection -- pick a sensible default range
# ---------------------------------------------------------------------------


def get_git_dir() -> Optional[Path]:
    """Resolve `.git` (or the worktree's gitdir) for the current cwd."""
    rc, out, _ = run_git(["rev-parse", "--git-dir"])
    if rc != 0:
        return None
    return Path(out.strip())


def get_repo_root() -> Optional[Path]:
    rc, out, _ = run_git(["rev-parse", "--show-toplevel"])
    if rc != 0:
        return None
    return Path(out.strip())


def get_current_branch() -> Optional[str]:
    """Return the current branch name, or None if HEAD is detached."""
    rc, out, _ = run_git(["symbolic-ref", "-q", "HEAD"])
    if rc != 0:
        return None
    return out.strip().replace("refs/heads/", "", 1) or None


def ref_exists(ref: str) -> bool:
    rc, _, _ = run_git(["rev-parse", "--verify", "--quiet", ref])
    return rc == 0


def detect_default_range() -> tuple[str, str]:
    """Pick a default diff range from workspace state.

    Returns (range_spec, reason). Raises ValueError if no sensible default
    exists (detached HEAD with no upstream and no main/master fallback).

    `range_spec` is a string that `git diff` accepts directly (e.g.
    `origin/main..HEAD`) OR one of the sentinel strings `__merge_in_progress__`,
    `__rebase_in_progress__`, `__working_tree__`, `__staged__` for non-range
    modes -- callers route those through different git commands.
    """
    git_dir = get_git_dir()
    if git_dir is None:
        raise ValueError("not inside a git repository (cwd: cannot resolve .git)")

    if (git_dir / "MERGE_HEAD").exists():
        return ("__merge_in_progress__", "MERGE_HEAD present -- reviewing the in-progress merge")
    if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
        return ("__rebase_in_progress__", "rebase in progress -- reviewing the in-progress rebase")

    branch = get_current_branch()
    if branch is None:
        # Detached HEAD. Try a sensible fallback to main/master; fail if none.
        for fb in ["origin/main", "origin/master", "main", "master"]:
            if ref_exists(fb):
                return (f"{fb}..HEAD", f"detached HEAD; falling back to {fb}..HEAD")
        raise ValueError(
            "HEAD is detached and no main/master ref found. Pass an explicit range "
            "(e.g. `prepare_review.py <base-ref>`)."
        )

    # Try upstream first.
    rc, out, _ = run_git(["rev-parse", "--symbolic-full-name", "@{upstream}"])
    if rc == 0 and out.strip():
        upstream = out.strip()
        return (f"{upstream}..HEAD", f"@{{upstream}} = {upstream}")

    # Fallback chain. Skip a fallback if it IS the current branch (no-op diff).
    for fb in ["origin/main", "origin/master", "main", "master"]:
        if fb.endswith(branch):
            continue
        if ref_exists(fb):
            return (f"{fb}..HEAD", f"no @{{upstream}} set; falling back to {fb}..HEAD")

    raise ValueError(
        f"branch '{branch}' has no @{{upstream}} and no main/master ref exists. "
        f"Pass an explicit range (e.g. `prepare_review.py <base-ref>`)."
    )


# ---------------------------------------------------------------------------
# Diff fetch + parse
# ---------------------------------------------------------------------------


def fetch_diff(range_spec: str) -> str:
    """Return the raw `git diff` output for `range_spec`.

    Sentinels:
    - __working_tree__: `git diff` (worktree vs HEAD, including unstaged)
    - __staged__:       `git diff --cached`
    - __merge_in_progress__: `git diff --cc HEAD` (combined diff for merge)
    - __rebase_in_progress__: `git diff HEAD` (current state vs HEAD)

    Otherwise: `git diff <range_spec>`.
    """
    if range_spec == "__working_tree__":
        cmd = ["diff", "HEAD"]
    elif range_spec == "__staged__":
        cmd = ["diff", "--cached"]
    elif range_spec == "__merge_in_progress__":
        cmd = ["diff", "--cc", "HEAD"]
    elif range_spec == "__rebase_in_progress__":
        cmd = ["diff", "HEAD"]
    else:
        cmd = ["diff", range_spec]
    rc, out, err = run_git(cmd)
    if rc != 0:
        raise ValueError(f"git diff failed: {err.strip() or 'no output'}")
    return out


def fetch_changed_files(range_spec: str) -> list[tuple[str, str]]:
    """Return [(status, path), ...] for files changed in `range_spec`.

    `status` is a single letter (A/M/D/R/C/T). For renames the path is
    the post-rename b-side. Empty list if no changes.
    """
    if range_spec == "__working_tree__":
        cmd = ["diff", "--name-status", "HEAD"]
    elif range_spec == "__staged__":
        cmd = ["diff", "--name-status", "--cached"]
    elif range_spec in ("__merge_in_progress__", "__rebase_in_progress__"):
        cmd = ["diff", "--name-status", "HEAD"]
    else:
        cmd = ["diff", "--name-status", range_spec]
    rc, out, _ = run_git(cmd)
    if rc != 0:
        return []
    files: list[tuple[str, str]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0][:1]
        if status in _STATUS_CHARS:
            # For R / C, parts is [status, old, new]; take new (b-side).
            path = parts[-1].strip()
            if path:
                files.append((status, path))
    return files


def fetch_description(range_spec: str) -> str:
    """Pick a human-readable description for the range.

    For a real <a>..<b> range: concatenate commit subjects (newest first),
    up to ~5; ellipsis if more. For working-tree / staged / merge / rebase
    modes: a fixed marker string.
    """
    if range_spec == "__working_tree__":
        return "(uncommitted working-tree changes)"
    if range_spec == "__staged__":
        return "(staged-but-uncommitted changes)"
    if range_spec == "__merge_in_progress__":
        return "(in-progress merge)"
    if range_spec == "__rebase_in_progress__":
        return "(in-progress rebase)"
    rc, out, _ = run_git(["log", "--no-merges", "--format=%s", "-n", "6", range_spec])
    if rc != 0:
        return ""
    subjects = [s.strip() for s in out.splitlines() if s.strip()]
    if not subjects:
        return ""
    if len(subjects) > 5:
        return "; ".join(subjects[:5]) + f"; (+{len(subjects) - 5} more)"
    return "; ".join(subjects)


def split_git_diff_sections(diff_text: str) -> tuple[str, list[dict]]:
    """Split git-diff output into (preamble, [{path, header, body}, ...])."""
    preamble_lines: list[str] = []
    sections: list[dict] = []
    current: Optional[dict] = None
    for line in diff_text.splitlines(keepends=True):
        m = _GIT_FILE_HEADER.match(line.rstrip("\n"))
        if m:
            if current is not None:
                sections.append(current)
            # Use b-side (post-image) path as the identifier.
            current = {"path": m.group(2), "header": line, "body": ""}
        elif current is None:
            preamble_lines.append(line)
        else:
            current["body"] += line
    if current is not None:
        sections.append(current)
    return "".join(preamble_lines), sections


def _git_diff_to_sections(diff_text: str) -> tuple[str, list[dict]]:
    """Adapter: git-format diff -> (preamble, [DiffSection])."""
    preamble, sections = split_git_diff_sections(diff_text)
    return preamble, [
        {"identifier": s["path"], "text": s["header"] + s["body"]}
        for s in sections
    ]


# ---------------------------------------------------------------------------
# Workspace hygiene checks (analogs of p4-kit's unreconciled/unresolved)
# ---------------------------------------------------------------------------


def find_untracked_or_unstaged(
    repo_root: Path, touched_dirs: list[Path]
) -> list[dict]:
    """`git status --porcelain` filtered to files inside touched_dirs.

    Each entry: {"local": <abs path>, "path": <repo-rel>, "kind": ...}.
    `kind` distinguishes:
      - "untracked"            -- ?? in status
      - "unstaged_modified"    -- worktree differs from index
      - "unstaged_deleted"     -- file removed from worktree but still tracked
      - "staged_uncommitted"   -- index differs from HEAD (different from the diff range we're reviewing)
    """
    rc, out, _ = run_git(["status", "--porcelain", "-uall"], cwd=repo_root)
    if rc != 0:
        return []
    touched_resolved = []
    for d in touched_dirs:
        try:
            touched_resolved.append(d.resolve())
        except OSError:
            continue

    items: list[dict] = []
    for raw in out.splitlines():
        if len(raw) < 3:
            continue
        index_st = raw[0]
        worktree_st = raw[1]
        path_part = raw[3:].strip()
        # Renames: "R  old -> new" -- use the new (post-rename) path
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1]
        path_part = path_part.strip().strip('"')

        local = (repo_root / path_part).resolve()
        try:
            local_dir = local.parent
        except OSError:
            continue
        # Only surface files inside the directories the review touches.
        if not any(
            local_dir == td or td in local_dir.parents for td in touched_resolved
        ):
            continue

        if index_st == "?" and worktree_st == "?":
            kind = "untracked"
        elif worktree_st == "M":
            kind = "unstaged_modified"
        elif worktree_st == "D":
            kind = "unstaged_deleted"
        elif index_st in "AMDRCT":
            kind = "staged_uncommitted"
        else:
            continue
        items.append({"local": str(local), "path": path_part, "kind": kind})
    return items


def find_merge_conflicts(repo_root: Path) -> list[dict]:
    """`git ls-files -u` returns unmerged paths (one row per stage).

    We collapse to one entry per path. Empty list when no merge in progress.
    """
    rc, out, _ = run_git(["ls-files", "-u"], cwd=repo_root)
    if rc != 0 or not out.strip():
        return []
    seen: set[str] = set()
    items: list[dict] = []
    for line in out.splitlines():
        # Format: "100644 abcdef 1\tpath/to/file"
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        path = parts[1].strip()
        if path in seen:
            continue
        seen.add(path)
        items.append({"path": path, "local": str((repo_root / path).resolve())})
    return items


# ---------------------------------------------------------------------------
# Bundle assembly
# ---------------------------------------------------------------------------


def _safe_dir_name(range_spec: str) -> str:
    """Filesystem-safe directory name for a range spec.

    e.g. `origin/main..HEAD` -> `origin-main..HEAD`; `__working_tree__`
    stays as-is (underscore is safe).
    """
    return re.sub(r"[^A-Za-z0-9._-]+", "-", range_spec).strip("-")


def parse_range_arg(arg: str) -> str:
    """Normalize a user-provided range argument.

    Bare ref `<ref>` becomes `<ref>..HEAD`. `<a>..<b>` and `<a>...<b>`
    pass through. `--staged` and `--working` map to sentinels.
    """
    if arg == "--staged":
        return "__staged__"
    if arg == "--working":
        return "__working_tree__"
    if ".." in arg:
        return arg
    return f"{arg}..HEAD"


def build_bundle(range_spec: str, bundle_dir: Path, auto_reason: Optional[str] = None) -> dict:
    """Gather context for `range_spec`, write chunks to disk, return the index bundle."""
    repo_root = get_repo_root()
    if repo_root is None:
        raise ValueError("not inside a git repository")

    diff = fetch_diff(range_spec)
    changed = fetch_changed_files(range_spec)
    description = fetch_description(range_spec)

    rc, head_out, _ = run_git(["rev-parse", "--short", "HEAD"])
    head_sha = head_out.strip() if rc == 0 else ""
    branch = get_current_branch() or "DETACHED"

    bundle_dir.mkdir(parents=True, exist_ok=True)
    preamble, sections = _git_diff_to_sections(diff)
    chunks = partition_sections_into_chunks(
        sections, MAX_CHUNK_BYTES, preamble=preamble
    )
    diff_chunks = write_chunks(chunks, bundle_dir)

    path_to_chunk: dict[str, int] = {}
    for entry in diff_chunks:
        for p in entry["files"]:
            path_to_chunk[p] = entry["index"]

    changed_files: list[dict] = []
    unique: list[str] = []
    seen: set[str] = set()
    for status, path in changed:
        local = (repo_root / path).resolve()
        claude_mds = collect_claude_mds(local, repo_root)
        for cm in claude_mds:
            if cm not in seen:
                unique.append(cm)
                seen.add(cm)
        changed_files.append(
            {
                "path": path,
                "local": str(local),
                "status": status,
                "chunk_index": path_to_chunk.get(path),
                "claude_mds": claude_mds,
            }
        )

    # Touched parent dirs for the untracked/unstaged scan.
    touched_dirs: list[Path] = []
    seen_dirs: set[Path] = set()
    for cf in changed_files:
        d = Path(cf["local"]).parent
        if d not in seen_dirs:
            seen_dirs.add(d)
            touched_dirs.append(d)

    untracked_or_unstaged = find_untracked_or_unstaged(repo_root, touched_dirs)
    merge_conflicts = find_merge_conflicts(repo_root)
    submit_gates = collect_submit_gates(
        unique, [cf["local"] for cf in changed_files], repo_root
    )

    bundle: dict = {
        "vcs": "git",
        "range": range_spec,
        "head_sha": head_sha,
        "branch": branch,
        "description": description,
        "bundle_dir": str(bundle_dir),
        "diff_chunks": diff_chunks,
        "changed_files": changed_files,
        "unique_claude_mds": unique,
        "untracked_or_unstaged": untracked_or_unstaged,
        "merge_conflicts": merge_conflicts,
        "submit_gates": submit_gates,
    }
    if auto_reason:
        bundle["auto_detected_reason"] = auto_reason
    return bundle


def main(argv: list[str]) -> int:
    auto_reason: Optional[str] = None
    if len(argv) == 1:
        try:
            range_spec, auto_reason = detect_default_range()
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    elif len(argv) == 2:
        range_spec = parse_range_arg(argv[1])
    else:
        print(
            "Usage: prepare_review.py [<ref>|<a>..<b>|<a>...<b>|--staged|--working]",
            file=sys.stderr,
        )
        return 2

    bundle_dir = DEFAULT_BUNDLE_ROOT / _safe_dir_name(range_spec)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    try:
        bundle = build_bundle(range_spec, bundle_dir, auto_reason=auto_reason)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    (bundle_dir / "bundle.json").write_text(
        json.dumps(bundle, indent=2) + "\n", encoding="utf-8"
    )
    json.dump(bundle, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
