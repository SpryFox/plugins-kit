"""Gather review context for a Perforce changelist.

Usage: prepare_review.py <CL>

Runs `p4 describe -du <CL>` (with `-S` fallback for shelved CLs), parses the
changed depot files, resolves them to local workspace paths via `p4 where`,
walks each file's parent directories up to the workspace root collecting any
ancestor CLAUDE.md files, and emits a JSON bundle on stdout.

`p4 describe -du` emits no `@@` hunks for `add` or `delete` actions. To ensure
reviewers see the full introduced/removed code, this script synthesizes
new-file / deleted-file hunks for those actions by fetching content via
`p4 print`. Supports both shelved (`@=<CL>`) and submitted (`#<rev>`) forms.

Also runs `p4 reconcile -n` recursively over the minimal covering set of
directories containing CL files, and reports any unreconciled files
(untracked adds, unopened edits, missing deletes) that the user may have
forgotten to include in the CL. `.p4ignore` is honored by p4 itself; files
already opened in any pending CL are skipped by reconcile.

Also runs `p4 resolve -n -c <CL>` to report any files in the CL with
pending merge/integrate resolves. These are informational: the diff still
goes to reviewers (conflict markers in the file content are themselves
a legitimate review observation), but the user is warned that the CL is
not submittable until each unresolved file is run through `p4 resolve`.

The workspace root is intentionally excluded from recursive scans -- if a
CL touches a root-level file, the root is scanned non-recursively (`/*`)
and deeper CL directories keep their recursive (`/...`) scans separately.
Recursing from the workspace root would crawl every untracked directory
in the tree (Binaries/, Intermediate/, build outputs, IDE files, etc.)
even when `.p4ignore` doesn't list them all -- a blast radius the review
prep doesn't need.

Scans every ancestor CLAUDE.md collected above for `**Submit gate:**` blocks.
Each gate names a list of scope paths (prefixes if no glob chars, fnmatch globs
otherwise); a gate fires when at least one file in the CL falls within any of
its scope paths. Gates are deterministic reminders the author must act on
locally before submit (e.g. build a binary, regenerate a derived file, run a
validator) -- not in-diff issues. Authoring format:

    **Submit gate:** <imperative>.
    Applies to:
    - <path prefix or glob>
    - <path prefix or glob>

    <optional rationale paragraph>

Diff text is NOT inlined in the bundle. It is partitioned into chunks of
<= MAX_CHUNK_BYTES each, written to <bundle_dir>/chunks/chunk-NNN.diff,
and indexed by `diff_chunks`. Each `changed_files` entry carries the
`chunk_index` that contains its diff. Reviewer subagents Read one chunk
per agent -- one large CL fans out across multiple agents in parallel
instead of forcing every reviewer to ingest the full diff. The bundle
itself (also written to <bundle_dir>/bundle.json) is small enough to
inline through stdout.

Output schema:
    {
      "cl": "<CL>",
      "description": "<change description>",
      "bundle_dir": "<absolute path to bundle directory>",
      "diff_chunks": [
        {"index": 0, "path": "chunks/chunk-000.diff",
         "files": ["<depot path>", ...], "bytes": <int>}
      ],
      "changed_files": [
        {"depot": "<depot path>", "local": "<local path>",
         "chunk_index": <int or null if absent from diff>,
         "claude_mds": ["<absolute path>", ...]}
      ],
      "unique_claude_mds": ["<absolute path>", ...],
      "unreconciled": [
        {"local": "<local path>", "depot": "<depot path>", "action": "add"|"edit"|"delete"}
      ],
      "unresolved": [
        {"local": "<local path>", "depot": "<depot path>",
         "resolve_type": "<p4 resolveType, e.g. content/branch/delete>",
         "from_file": "<source depot path, may be empty>"}
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

# Repair PATH before any subprocess fan-out. On Windows, a bloated
# launching-shell PATH can overrun cmd.exe's variable size limit during
# venv activation and leave this Python with a stripped PATH that
# breaks `subprocess.run(["p4", ...])` with FileNotFoundError. Pulling
# the registry-canonical PATH back in restores p4 visibility.
from bootstrap_lib.path_repair import repair_path  # noqa: E402
repair_path()

# Shared code-review primitives -- VCS-neutral chunking, CLAUDE.md walk,
# submit-gate parsing/matching. See bootstrap_lib/code_review/.
from bootstrap_lib.code_review.chunking import (  # noqa: E402
    partition_sections_into_chunks,
    write_chunks,
)
from bootstrap_lib.code_review.claude_mds import (  # noqa: E402
    collect_claude_mds,
    collect_submit_gates,
)


_FILE_HEADER = re.compile(r"^==== (//[^#]+)#(\d+) \([^)]*\) ====\s*$")
_AFFECTED_LINE = re.compile(r"^\.\.\. (//[^#]+)#(\d+) ([\w/]+)\s*$")
_RECONCILE_ACTIONS = {"add", "edit", "delete"}

_ADD_ACTIONS = {"add", "branch", "move/add", "import"}
_DELETE_ACTIONS = {"delete", "move/delete", "purge"}

# Cap each `p4 ... <paths>` invocation. Windows' CreateProcess limits the
# combined command line to ~32 KB; bulk CLs (asset reconciles, regen passes)
# can easily push 500+ depot paths totalling 70+ KB into one call and trip
# `FileNotFoundError: [WinError 206] The filename or extension is too long`.
# 100 keeps each batch well under any platform's limit with room to spare.
_P4_PATH_BATCH = 100

# Max bytes per per-chunk diff file. Sized for the Read tool: large CLs
# fail with "file too large" above some unpublished threshold (a 1.4 MB
# diff hit it on CL 148623, 119 files). 1 MB leaves ~40% headroom under
# the only known failure point and keeps chunk counts close to 1 for
# typical CLs. Tune downward if a Read failure surfaces.
MAX_CHUNK_BYTES = 1024 * 1024

# Where bundles land on disk. <CL> directory holds bundle.json and
# chunks/. Overwritten on each prepare_review run for the same CL.
DEFAULT_BUNDLE_ROOT = (
    Path.home() / ".claude" / "plugins" / "data"
    / "plugins-kit" / "p4-kit" / "reviews"
)


def run_p4(args: list[str]) -> tuple[int, str, str]:
    """Run a p4 command, return (returncode, stdout, stderr).

    Forces UTF-8 decoding so non-Latin-1 content (CJK, emoji) in diffs doesn't
    abort the subprocess reader thread on Windows, whose default text decoder
    is the system ANSI codepage (cp1252 on en-US/en-GB).
    """
    proc = subprocess.run(
        ["p4", *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def has_describe_content(output: str) -> bool:
    """True if p4 describe output has reviewable content.

    Reviewable means EITHER:
    - the Differences section has at least one ==== file header (which
      extract_diff parses directly), OR
    - the Affected/Shelved files section lists at least one synthesizable
      action (add/delete), since pure-add and pure-delete CLs have empty
      Differences sections but extract_diff can fill them in via p4 print.

    A describe with only `edit` actions and no Differences headers is not
    reviewable here -- edits need real diff bodies, not synthesis.
    """
    if "Differences ..." in output:
        after = output.split("Differences ...", 1)[1]
        if any(_FILE_HEADER.match(line) for line in after.splitlines()):
            return True
    actions = parse_file_actions(output)
    return any(
        action in _ADD_ACTIONS or action in _DELETE_ACTIONS
        for _, action in actions.values()
    )


def _is_pending(output: str) -> bool:
    """True if the first `Change ...` header line marks the CL as `*pending*`."""
    for line in output.splitlines():
        if line.startswith("Change "):
            return "*pending*" in line
    return False


def fetch_describe(cl: str) -> tuple[str, bool]:
    """Return (`p4 describe -du` output, is_shelved) for CL.

    Routing:
    - Submitted CLs come back from the regular describe with `is_shelved=False`
      so synthesis fetches via `#<rev>`.
    - Pending CLs are routed to the shelved (`-S`) describe with `is_shelved=True`
      so synthesis fetches via `@=<CL>`. Going through `#<rev>` would fail for
      pending adds because no submitted revision exists yet.
    - Pending CLs that have not been shelved fail with a hint to shelve first.
    """
    rc, out, _ = run_p4(["describe", "-du", cl])
    if rc == 0 and not _is_pending(out) and has_describe_content(out):
        return out, False

    rc_s, out_s, _ = run_p4(["describe", "-du", "-S", cl])
    if rc_s == 0 and has_describe_content(out_s):
        return out_s, True

    if rc == 0 and _is_pending(out):
        raise ValueError(
            f"pending CL {cl} has no shelved content to review. "
            f"Shelve the CL first so the review tool can read its diff: "
            f"`p4 shelve -c {cl}`"
        )
    raise ValueError(f"no describe content found for CL {cl} (tried committed and shelved)")


def parse_description(describe_output: str) -> str:
    """Extract the indented description block following the `Change ...` header."""
    lines = describe_output.splitlines()
    desc_lines: list[str] = []
    in_desc = False
    for line in lines:
        if not in_desc:
            if line.startswith("Change "):
                in_desc = True
            continue
        if line.startswith("\t"):
            desc_lines.append(line[1:])
        elif desc_lines:
            break
    return "\n".join(desc_lines).strip()


def parse_depot_files(describe_output: str) -> list[str]:
    """Extract depot paths from `==== //depot/path#rev (type) ====` headers."""
    files: list[str] = []
    for line in describe_output.splitlines():
        m = _FILE_HEADER.match(line)
        if m:
            files.append(m.group(1))
    return files


def parse_file_actions(describe_output: str) -> dict[str, tuple[str, str]]:
    """Map depot path → (rev, action) from 'Affected files ...' / 'Shelved files ...' sections.

    Lines look like: `... //depot/path#rev action` (action e.g. `add`, `edit`, `delete`, `move/add`).
    Stops parsing when `Differences ...` is reached.
    """
    actions: dict[str, tuple[str, str]] = {}
    in_section = False
    for line in describe_output.splitlines():
        if line.startswith("Affected files ...") or line.startswith("Shelved files ..."):
            in_section = True
            continue
        if not in_section:
            continue
        if line.startswith("Differences ..."):
            break
        m = _AFFECTED_LINE.match(line)
        if m:
            actions[m.group(1)] = (m.group(2), m.group(3))
    return actions


def split_diff_sections(diff_text: str) -> tuple[str, list[dict]]:
    """Split diff text into (preamble, [{depot, rev, header, body}, ...]) by file header."""
    preamble_lines: list[str] = []
    sections: list[dict] = []
    current: Optional[dict] = None

    for line in diff_text.splitlines(keepends=True):
        m = _FILE_HEADER.match(line.rstrip("\n"))
        if m:
            if current is not None:
                sections.append(current)
            current = {
                "depot": m.group(1),
                "rev": m.group(2),
                "header": line,
                "body": "",
            }
        elif current is None:
            preamble_lines.append(line)
        else:
            current["body"] += line
    if current is not None:
        sections.append(current)

    return "".join(preamble_lines), sections


def fetch_file_content(
    depot_path: str, rev: str, cl: str, is_shelved: bool, is_delete: bool
) -> Optional[str]:
    """Fetch file content via `p4 print -q`.

    - Shelved add/edit: `//depot/path@=<CL>` (shelved content at this CL)
    - Shelved delete:   `//depot/path#head` (head rev is the content about to be deleted)
    - Submitted add:    `//depot/path#<rev>` (content at the submitted rev)
    - Submitted delete: `//depot/path#<rev-1>` (content prior to deletion)
    """
    if is_shelved:
        spec = f"{depot_path}#head" if is_delete else f"{depot_path}@={cl}"
    elif is_delete:
        try:
            rev_num = int(rev)
        except ValueError:
            return None
        if rev_num <= 1:
            return None
        spec = f"{depot_path}#{rev_num - 1}"
    else:
        spec = f"{depot_path}#{rev}"

    rc, out, _ = run_p4(["print", "-q", spec])
    if rc != 0:
        return None
    return out


def synthesize_add_hunk(content: str) -> str:
    """Produce a synthetic `@@ -0,0 +1,N @@` new-file hunk with `+` prefix on each line."""
    lines = content.splitlines()
    if not lines:
        return ""
    body = "\n".join(f"+{line}" for line in lines)
    return f"@@ -0,0 +1,{len(lines)} @@\n{body}\n"


def synthesize_delete_hunk(content: str) -> str:
    """Produce a synthetic `@@ -1,N +0,0 @@` deleted-file hunk with `-` prefix on each line."""
    lines = content.splitlines()
    if not lines:
        return ""
    body = "\n".join(f"-{line}" for line in lines)
    return f"@@ -1,{len(lines)} +0,0 @@\n{body}\n"


def extract_diff(
    describe_output: str,
    actions: Optional[dict[str, tuple[str, str]]] = None,
    cl: str = "",
    is_shelved: bool = False,
) -> str:
    """Return diff content after `Differences ...`, synthesizing hunks for add/delete files.

    If `actions` is provided, file sections whose body has no `@@` hunk are filled with a
    synthesized new-file (for add-style actions) or deleted-file (for delete-style actions)
    hunk, by fetching content via `p4 print`. A warning is emitted to stderr naming any
    files we could not synthesize.
    """
    if "Differences ..." not in describe_output:
        return ""
    raw = describe_output.split("Differences ...", 1)[1].lstrip("\n")
    if not actions:
        return raw

    preamble, sections = split_diff_sections(raw)
    result_parts: list[str] = [preamble] if preamble else []
    synthesized_adds: list[str] = []
    synthesized_deletes: list[str] = []
    unhandled: list[tuple[str, str]] = []
    seen_depots: set[str] = set()

    for sec in sections:
        depot = sec["depot"]
        rev = sec["rev"]
        header = sec["header"]
        body = sec["body"]
        seen_depots.add(depot)

        if "@@" in body:
            result_parts.append(header + body)
            continue

        action_info = actions.get(depot)
        if action_info is None:
            result_parts.append(header + body)
            continue

        _, action = action_info
        if action in _ADD_ACTIONS:
            content = fetch_file_content(depot, rev, cl, is_shelved, is_delete=False)
            if content is not None:
                hunk = synthesize_add_hunk(content)
                result_parts.append(header + body + hunk)
                synthesized_adds.append(depot)
                continue
            unhandled.append((depot, action))
        elif action in _DELETE_ACTIONS:
            content = fetch_file_content(depot, rev, cl, is_shelved, is_delete=True)
            if content is not None:
                hunk = synthesize_delete_hunk(content)
                result_parts.append(header + body + hunk)
                synthesized_deletes.append(depot)
                continue
            unhandled.append((depot, action))

        result_parts.append(header + body)

    # Synthesize complete sections for files in `actions` that were omitted from
    # the Differences section entirely (e.g. mixed shelved CLs where pure-adds
    # only appear in "Shelved files ..." and never get a ==== header).
    for depot, (rev, action) in actions.items():
        if depot in seen_depots:
            continue
        synthesized_header = f"==== {depot}#{rev} (text) ====\n"
        if action in _ADD_ACTIONS:
            content = fetch_file_content(depot, rev, cl, is_shelved, is_delete=False)
            if content is not None:
                result_parts.append(synthesized_header + synthesize_add_hunk(content))
                synthesized_adds.append(depot)
                continue
            unhandled.append((depot, action))
        elif action in _DELETE_ACTIONS:
            content = fetch_file_content(depot, rev, cl, is_shelved, is_delete=True)
            if content is not None:
                result_parts.append(synthesized_header + synthesize_delete_hunk(content))
                synthesized_deletes.append(depot)
                continue
            unhandled.append((depot, action))

    if synthesized_adds:
        print(
            f"prepare_review: synthesized add hunks for {len(synthesized_adds)} file(s): "
            + ", ".join(synthesized_adds),
            file=sys.stderr,
        )
    if synthesized_deletes:
        print(
            f"prepare_review: synthesized delete hunks for {len(synthesized_deletes)} file(s): "
            + ", ".join(synthesized_deletes),
            file=sys.stderr,
        )
    if unhandled:
        items = ", ".join(f"{p} ({a})" for p, a in unhandled)
        print(
            f"prepare_review: WARNING: could not synthesize hunks for: {items}",
            file=sys.stderr,
        )

    return "".join(result_parts)


def _p4_diff_to_sections(diff_text: str) -> tuple[str, list[dict]]:
    """Adapter: p4-format diff string -> generic (preamble, [DiffSection]).

    The shared chunker in bootstrap_lib.code_review takes a list of vendor-
    neutral `{identifier, text}` dicts. p4's `==== //depot/path#rev ====`
    headers carry the depot path as the identifier; the full section text
    (header + hunks) becomes `text`.
    """
    preamble, sections = split_diff_sections(diff_text)
    return preamble, [
        {"identifier": s["depot"], "text": s["header"] + s["body"]}
        for s in sections
    ]


def resolve_local_paths(depot_paths: list[str]) -> dict[str, Optional[str]]:
    """Map each depot path to a local workspace path via `p4 -ztag where`.

    Returns {depot_path: local_path_or_None}. Files not in the workspace map to None.

    Batched in chunks of `_P4_PATH_BATCH` so bulk CLs don't trip the Windows
    CreateProcess command-line length limit (~32 KB).
    """
    result: dict[str, Optional[str]] = {p: None for p in depot_paths}
    if not depot_paths:
        return result

    for i in range(0, len(depot_paths), _P4_PATH_BATCH):
        chunk = depot_paths[i:i + _P4_PATH_BATCH]
        rc, out, _ = run_p4(["-ztag", "where", *chunk])
        if rc != 0:
            continue
        current_depot: Optional[str] = None
        for line in out.splitlines():
            if line.startswith("... depotFile "):
                current_depot = line[len("... depotFile "):].strip()
            elif line.startswith("... path ") and current_depot:
                result[current_depot] = line[len("... path "):].strip()
                current_depot = None
            elif line.strip() == "":
                current_depot = None
    return result


def compute_minimal_dirs(
    local_paths: list[Optional[str]],
    workspace_root: Optional[Path] = None,
) -> list[tuple[Path, bool]]:
    """Collapse parent directories of `local_paths` to the minimal covering set.

    Returns a list of (directory, recursive) pairs. `recursive=True` means scan
    `<dir>/...`; `recursive=False` means scan `<dir>/*` (immediate children only).

    Given file paths, returns the set of containing directories with descendants
    removed: e.g. {/a, /a/b, /c} collapses to [(/a, True), (/c, True)]. A single
    recursive `p4 reconcile -n <dir>/...` over each then covers everything.

    The workspace root is treated specially: it never absorbs descendants, and
    if it appears in the parent set it is returned with `recursive=False`. This
    prevents `p4 reconcile -n <root>/...` from crawling every untracked tree in
    the workspace when a CL happens to touch a root-level file.

    Non-existent paths and `None` entries are skipped (e.g. files outside the
    workspace, or whose parent directory was deleted as part of the CL).
    """
    ws_root = workspace_root.resolve() if workspace_root else None

    dirs: set[Path] = set()
    for p in local_paths:
        if not p:
            continue
        try:
            d = Path(p).parent.resolve()
        except OSError:
            continue
        if d.is_dir():
            dirs.add(d)
    if not dirs:
        return []

    root_present = ws_root in dirs
    # Exclude the workspace root from the descendant-collapse pass. Letting it
    # absorb deeper dirs would expand a single root-level file into a recursive
    # scan of the whole workspace.
    collapsable = [d for d in dirs if d != ws_root]

    # Sort shallowest-first so a kept ancestor is checked before its descendants.
    sorted_dirs = sorted(collapsable, key=lambda d: len(d.parts))
    minimal: list[tuple[Path, bool]] = []
    kept_paths: list[Path] = []
    for d in sorted_dirs:
        if any(kept == d or kept in d.parents for kept in kept_paths):
            continue
        kept_paths.append(d)
        minimal.append((d, True))

    if root_present:
        minimal.append((ws_root, False))
    return minimal


def find_unreconciled(dir_specs: list[tuple[Path, bool]]) -> list[dict]:
    """Run `p4 -ztag reconcile -n` over `dir_specs` and return unreconciled files.

    `dir_specs` is a list of (directory, recursive) pairs. Recursive entries are
    scanned as `<dir>/...`; non-recursive entries as `<dir>/*` (immediate
    children only -- used for the workspace root to avoid crawling the whole
    tree).

    Each result entry: {"local": <path>, "depot": <path>, "action": "add"|"edit"|"delete"}.
    `.p4ignore` is honored by p4. Files already opened in any pending CL are skipped.
    A single p4 invocation handles all specs at once.

    On failure (p4 error, no workspace, etc.) returns []; the review still proceeds.
    """
    if not dir_specs:
        return []
    specs = [f"{d}/..." if recursive else f"{d}/*" for d, recursive in dir_specs]

    items: list[dict] = []
    for i in range(0, len(specs), _P4_PATH_BATCH):
        chunk = specs[i:i + _P4_PATH_BATCH]
        rc, out, err = run_p4(["-ztag", "reconcile", "-n", *chunk])
        # rc != 0 with "no file(s) to reconcile" means nothing to report -- not an error.
        if rc != 0 and "no file(s) to reconcile" not in (err + out):
            print(
                f"prepare_review: reconcile check failed (rc={rc}): {err.strip() or out.strip()}",
                file=sys.stderr,
            )
            continue
        items.extend(_parse_reconcile_output(out))
    return items


def _parse_reconcile_output(out: str) -> list[dict]:
    items: list[dict] = []
    current: dict = {}
    for line in out.splitlines():
        if line.startswith("... depotFile "):
            current["depot"] = line[len("... depotFile "):].strip()
        elif line.startswith("... clientFile "):
            current["local"] = line[len("... clientFile "):].strip()
        elif line.startswith("... action "):
            current["action"] = line[len("... action "):].strip()
        elif line.strip() == "":
            if current.get("action") in _RECONCILE_ACTIONS and current.get("local"):
                items.append(
                    {
                        "local": current["local"],
                        "depot": current.get("depot", ""),
                        "action": current["action"],
                    }
                )
            current = {}
    if current.get("action") in _RECONCILE_ACTIONS and current.get("local"):
        items.append(
            {
                "local": current["local"],
                "depot": current.get("depot", ""),
                "action": current["action"],
            }
        )
    return items


def find_unresolved(cl: str) -> list[dict]:
    """Run `p4 -ztag resolve -n -c <CL>` and return unresolved files in this CL.

    Each result entry: {"local": <path>, "depot": <path>,
                        "resolve_type": <p4 resolveType>, "from_file": <source>}.

    p4 exits non-zero with "no file(s) to resolve" when the CL is clean -- that
    isn't an error. On other failures, returns [] and logs to stderr; the
    review still proceeds.
    """
    rc, out, err = run_p4(["-ztag", "resolve", "-n", "-c", cl])
    if rc != 0 and "no file(s) to resolve" not in (err + out):
        print(
            f"prepare_review: resolve check failed (rc={rc}): {err.strip() or out.strip()}",
            file=sys.stderr,
        )
        return []

    items: list[dict] = []
    current: dict = {}

    def flush() -> None:
        if current.get("local") or current.get("depot"):
            items.append(
                {
                    "local": current.get("local", ""),
                    "depot": current.get("depot", ""),
                    "resolve_type": current.get("resolve_type", ""),
                    "from_file": current.get("from_file", ""),
                }
            )

    for line in out.splitlines():
        if line.startswith("... clientFile "):
            current["local"] = line[len("... clientFile "):].strip()
        elif line.startswith("... toFile "):
            current["depot"] = line[len("... toFile "):].strip()
        elif line.startswith("... fromFile "):
            current["from_file"] = line[len("... fromFile "):].strip()
        elif line.startswith("... resolveType "):
            current["resolve_type"] = line[len("... resolveType "):].strip()
        elif line.strip() == "":
            if current:
                flush()
                current = {}
    if current:
        flush()
    return items


def get_workspace_root() -> Optional[Path]:
    """Get the local workspace root via `p4 -ztag info` → `clientRoot`."""
    rc, out, _ = run_p4(["-ztag", "info"])
    if rc != 0:
        return None
    for line in out.splitlines():
        if line.startswith("... clientRoot "):
            return Path(line[len("... clientRoot "):].strip())
    return None


def build_bundle(cl: str, bundle_dir: Path) -> dict:
    """Gather CL context, partition diff into chunks on disk, return the index bundle.

    Writes per-file diff fragments under `<bundle_dir>/chunks/chunk-NNN.diff`
    (created if missing; stale chunks removed). The returned dict carries
    `bundle_dir`, `diff_chunks` index, and per-`changed_files` `chunk_index`
    -- the diff text itself is NOT inlined, so the bundle stays small enough
    for downstream stdout / consumer ingestion.
    """
    describe, is_shelved = fetch_describe(cl)
    description = parse_description(describe)
    actions = parse_file_actions(describe)
    diff = extract_diff(describe, actions, cl, is_shelved)
    # `actions` is the canonical per-file list (Affected/Shelved files section).
    # Pure-add files in mixed shelved CLs may be absent from the Differences
    # section entirely, so deriving the file list from ==== headers undercounts.
    depot_files = list(actions.keys())
    local_map = resolve_local_paths(depot_files)
    workspace_root = get_workspace_root()

    bundle_dir.mkdir(parents=True, exist_ok=True)
    preamble, sections = _p4_diff_to_sections(diff)
    chunks = partition_sections_into_chunks(
        sections, MAX_CHUNK_BYTES, preamble=preamble
    )
    diff_chunks = write_chunks(chunks, bundle_dir)

    # depot -> chunk index, for tagging changed_files entries.
    depot_to_chunk: dict[str, int] = {}
    for entry in diff_chunks:
        for d in entry["files"]:
            depot_to_chunk[d] = entry["index"]

    changed_files: list[dict] = []
    unique: list[str] = []
    seen: set[str] = set()
    for depot in depot_files:
        local = local_map.get(depot)
        claude_mds: list[str] = []
        if local:
            claude_mds = collect_claude_mds(Path(local), workspace_root)
            for cm in claude_mds:
                if cm not in seen:
                    unique.append(cm)
                    seen.add(cm)
        changed_files.append(
            {
                "depot": depot,
                "local": local,
                "chunk_index": depot_to_chunk.get(depot),
                "claude_mds": claude_mds,
            }
        )

    minimal_dirs = compute_minimal_dirs(
        [f["local"] for f in changed_files], workspace_root
    )
    unreconciled = find_unreconciled(minimal_dirs)
    unresolved = find_unresolved(cl)

    submit_gates = collect_submit_gates(
        unique, [f["local"] for f in changed_files if f["local"]], workspace_root
    )

    return {
        "cl": cl,
        "description": description,
        "bundle_dir": str(bundle_dir),
        "diff_chunks": diff_chunks,
        "changed_files": changed_files,
        "unique_claude_mds": unique,
        "unreconciled": unreconciled,
        "unresolved": unresolved,
        "submit_gates": submit_gates,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: prepare_review.py <CL>", file=sys.stderr)
        return 2
    cl = argv[1]
    bundle_dir = DEFAULT_BUNDLE_ROOT / cl
    bundle_dir.mkdir(parents=True, exist_ok=True)
    try:
        bundle = build_bundle(cl, bundle_dir)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    # Persist alongside the chunks so the skill (or a human) can re-read
    # without re-running prepare_review.
    (bundle_dir / "bundle.json").write_text(
        json.dumps(bundle, indent=2) + "\n", encoding="utf-8"
    )
    json.dump(bundle, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
