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

Output schema:
    {
      "cl": "<CL>",
      "description": "<change description>",
      "diff": "<full diff text>",
      "changed_files": [
        {"depot": "<depot path>", "local": "<local path>",
         "claude_mds": ["<absolute path>", ...]}
      ],
      "unique_claude_mds": ["<absolute path>", ...]
    }

Stderr-only diagnostics. Non-zero exit on hard failure.
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


_FILE_HEADER = re.compile(r"^==== (//[^#]+)#(\d+) \([^)]*\) ====\s*$")
_AFFECTED_LINE = re.compile(r"^\.\.\. (//[^#]+)#(\d+) ([\w/]+)\s*$")

_ADD_ACTIONS = {"add", "branch", "move/add", "import"}
_DELETE_ACTIONS = {"delete", "move/delete", "purge"}


def run_p4(args: list[str]) -> tuple[int, str, str]:
    """Run a p4 command, return (returncode, stdout, stderr)."""
    proc = subprocess.run(["p4", *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def has_describe_content(output: str) -> bool:
    """True if p4 describe output has a Differences section with at least one file header."""
    if "Differences ..." not in output:
        return False
    after = output.split("Differences ...", 1)[1]
    return any(_FILE_HEADER.match(line) for line in after.splitlines())


def fetch_describe(cl: str) -> tuple[str, bool]:
    """Return (`p4 describe -du` output, is_shelved) for CL, with shelved (`-S`) fallback."""
    rc, out, _ = run_p4(["describe", "-du", cl])
    if rc == 0 and has_describe_content(out):
        return out, False
    rc, out, _ = run_p4(["describe", "-du", "-S", cl])
    if rc == 0 and has_describe_content(out):
        return out, True
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


def resolve_local_paths(depot_paths: list[str]) -> dict[str, Optional[str]]:
    """Map each depot path to a local workspace path via `p4 -ztag where`.

    Returns {depot_path: local_path_or_None}. Files not in the workspace map to None.
    """
    result: dict[str, Optional[str]] = {p: None for p in depot_paths}
    if not depot_paths:
        return result
    rc, out, _ = run_p4(["-ztag", "where", *depot_paths])
    if rc != 0:
        return result

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


def get_workspace_root() -> Optional[Path]:
    """Get the local workspace root via `p4 -ztag info` → `clientRoot`."""
    rc, out, _ = run_p4(["-ztag", "info"])
    if rc != 0:
        return None
    for line in out.splitlines():
        if line.startswith("... clientRoot "):
            return Path(line[len("... clientRoot "):].strip())
    return None


def collect_claude_mds(file_path: Path, workspace_root: Optional[Path]) -> list[str]:
    """Walk parents of file_path collecting CLAUDE.md ancestors.

    Stops at workspace_root (inclusive) if provided, otherwise at filesystem root.
    Returns absolute paths, ordered nearest-ancestor first.
    """
    try:
        file_path = file_path.resolve()
    except OSError:
        return []
    root = workspace_root.resolve() if workspace_root else None

    found: list[str] = []
    seen: set[str] = set()
    current = file_path.parent
    while True:
        candidate = current / "CLAUDE.md"
        if candidate.is_file():
            ap = str(candidate)
            if ap not in seen:
                found.append(ap)
                seen.add(ap)
        if root is not None and current == root:
            break
        parent = current.parent
        if parent == current:
            break
        if root is not None and parent != root and root not in parent.parents:
            break
        current = parent
    return found


def build_bundle(cl: str) -> dict:
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
        changed_files.append({"depot": depot, "local": local, "claude_mds": claude_mds})

    return {
        "cl": cl,
        "description": description,
        "diff": diff,
        "changed_files": changed_files,
        "unique_claude_mds": unique,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: prepare_review.py <CL>", file=sys.stderr)
        return 2
    cl = argv[1]
    try:
        bundle = build_bundle(cl)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    json.dump(bundle, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
