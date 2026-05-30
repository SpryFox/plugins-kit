#!/usr/bin/env python3
"""discover.py -- enumerate CLAUDE.md and CLAUDE.local.md files visible from the
current working directory.

Usage:
    python discover.py
    python discover.py --json

Walks upward from cwd to the filesystem root collecting ancestor CLAUDE.md and
CLAUDE.local.md files, then walks downward up to a depth limit collecting
descendants. Outputs a numbered list (or JSON) with role classification:

    role values:
      root       -- CLAUDE.md at cwd, when no CLAUDE.md exists above it (claude
                    was launched at the project top)
      ancestor   -- CLAUDE.md above cwd
      child      -- CLAUDE.md below cwd, OR at cwd when an ancestor CLAUDE.md
                    exists above it (a subordinate file, not the project root)
      local      -- CLAUDE.local.md at any of the above locations

Stdlib-only.
"""

import argparse
import json
import os
import sys
from pathlib import Path


DESCEND_MAX_DEPTH = 6
SKIP_DIR_NAMES = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
                  "Intermediate", "Saved", "Binaries", "DerivedDataCache", "Build",
                  ".claude/plugins", "tmp"}


def is_skipped(path: Path, cwd: Path) -> bool:
    rel_parts = path.relative_to(cwd).parts if path.is_relative_to(cwd) else path.parts
    for part in rel_parts:
        if part in SKIP_DIR_NAMES or part.startswith("."):
            if part not in (".claude",):  # .claude is the one dotdir we descend into
                return True
    return False


def collect_ancestors(cwd: Path) -> list[tuple[Path, str]]:
    """Walk upward from cwd to root, collecting CLAUDE.md and CLAUDE.local.md.
    Returns list of (path, role) tuples ordered root-most-first.
    """
    out: list[tuple[Path, str]] = []
    current = cwd.parent
    while current != current.parent:
        for name, role in (("CLAUDE.md", "ancestor"), ("CLAUDE.local.md", "local")):
            candidate = current / name
            if candidate.exists():
                out.append((candidate, role))
        current = current.parent
    out.reverse()
    return out


def collect_at_cwd(cwd: Path, has_ancestor_root: bool = False) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    # The cwd CLAUDE.md is `root` only when it is the project top. If a CLAUDE.md
    # was found above cwd, claude was launched inside a larger project, so this
    # file is a subordinate (`child`) -- the project-root-only hygiene checks
    # (H1/H2/H3) belong to the real root above, not to the launch-dir file.
    cwd_role = "child" if has_ancestor_root else "root"
    for name, role in (("CLAUDE.md", cwd_role), ("CLAUDE.local.md", "local")):
        candidate = cwd / name
        if candidate.exists():
            out.append((candidate, role))
    return out


def collect_descendants(cwd: Path) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for current_root, dirs, files in os.walk(cwd):
        current_path = Path(current_root)
        # in-place filter to skip noise dirs
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith(".")
                   or d == ".claude"]
        # depth check
        try:
            rel = current_path.relative_to(cwd)
            depth = len(rel.parts)
        except ValueError:
            depth = DESCEND_MAX_DEPTH + 1
        if depth > DESCEND_MAX_DEPTH:
            dirs[:] = []
            continue
        if current_path == cwd:
            continue
        for name, role in (("CLAUDE.md", "child"), ("CLAUDE.local.md", "local")):
            if name in files:
                out.append((current_path / name, role))
    out.sort(key=lambda x: str(x[0]))
    return out


def discover(cwd: Path) -> list[tuple[Path, str]]:
    ancestors = collect_ancestors(cwd)
    # A CLAUDE.md ancestor (not a personal CLAUDE.local.md) above cwd means cwd
    # is not the project top, so the cwd CLAUDE.md is classified `child`.
    has_ancestor_root = any(role == "ancestor" for _, role in ancestors)
    out: list[tuple[Path, str]] = []
    out.extend(ancestors)
    out.extend(collect_at_cwd(cwd, has_ancestor_root))
    out.extend(collect_descendants(cwd))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a numbered list")
    parser.add_argument("--cwd", default=None, help="override cwd (for testing)")
    args = parser.parse_args()

    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd().resolve()
    results = discover(cwd)

    if args.json:
        print(json.dumps([{"index": i + 1, "path": str(p), "role": role}
                          for i, (p, role) in enumerate(results)], indent=2))
        return 0

    if not results:
        print(f"No CLAUDE.md or CLAUDE.local.md files found at or near {cwd}.")
        return 0

    print(f"CLAUDE.md files visible from {cwd}:\n")
    for i, (path, role) in enumerate(results, start=1):
        try:
            display = path.relative_to(cwd)
        except ValueError:
            display = path
        print(f"  {i:>3}. [{role:<8}] {display}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
