"""Gather review context for a Perforce changelist.

Usage: prepare_review.py <CL>

Runs `p4 describe -du <CL>` (with `-S` fallback for shelved CLs), parses the
changed depot files, resolves them to local workspace paths via `p4 where`,
walks each file's parent directories up to the workspace root collecting any
ancestor CLAUDE.md files, and emits a JSON bundle on stdout.

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
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


_FILE_HEADER = re.compile(r"^==== (//[^#]+)#\d+ \(.*\) ====\s*$")


def run_p4(args: list[str]) -> tuple[int, str, str]:
    """Run a p4 command, return (returncode, stdout, stderr)."""
    proc = subprocess.run(["p4", *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def has_diff_content(output: str) -> bool:
    """True if p4 describe output contains an actual diff (not just headers)."""
    if "Differences ..." not in output:
        return False
    after = output.split("Differences ...", 1)[1]
    return "@@" in after


def fetch_describe(cl: str) -> str:
    """Return `p4 describe -du` output for CL, with shelved (`-S`) fallback."""
    rc, out, _ = run_p4(["describe", "-du", cl])
    if rc == 0 and has_diff_content(out):
        return out
    rc, out, _ = run_p4(["describe", "-du", "-S", cl])
    if rc == 0 and has_diff_content(out):
        return out
    raise ValueError(f"no diff found for CL {cl} (tried committed and shelved)")


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


def extract_diff(describe_output: str) -> str:
    """Return everything from `Differences ...` onward (stripped of the marker line)."""
    if "Differences ..." not in describe_output:
        return ""
    return describe_output.split("Differences ...", 1)[1].lstrip("\n")


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
    describe = fetch_describe(cl)
    description = parse_description(describe)
    diff = extract_diff(describe)
    depot_files = parse_depot_files(describe)
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
