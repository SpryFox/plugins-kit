#!/usr/bin/env python3
"""discover.py -- enumerate SKILL.md files visible from the current working directory.

Usage:
    python discover.py
    python discover.py --json

Walks downward from cwd up to a depth limit, collecting all SKILL.md files.
Outputs a numbered list (or JSON) with the skill name and declared type when
visible from frontmatter.

Stdlib-only.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


DESCEND_MAX_DEPTH = 8
SKIP_DIR_NAMES = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
                  "Intermediate", "Saved", "Binaries", "DerivedDataCache", "Build", "tmp"}


_NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)
_TYPE_RE = re.compile(r"^skill-type:\s*(.+?)\s*$", re.MULTILINE)


def parse_frontmatter_basic(content: str) -> dict[str, str]:
    if not content.startswith("---"):
        return {}
    end_idx = content.find("\n---", 3)
    if end_idx < 0:
        return {}
    fm_text = content[3:end_idx]
    out: dict[str, str] = {}
    name_m = _NAME_RE.search(fm_text)
    type_m = _TYPE_RE.search(fm_text)
    if name_m:
        out["name"] = name_m.group(1)
    if type_m:
        out["skill-type"] = type_m.group(1)
    return out


def collect_skill_md(cwd: Path) -> list[tuple[Path, str, str]]:
    """Walk cwd downward; return (path, name, skill_type) tuples."""
    out: list[tuple[Path, str, str]] = []
    for current_root, dirs, files in os.walk(cwd):
        current_path = Path(current_root)
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith(".")
                   or d == ".claude"]
        try:
            rel = current_path.relative_to(cwd)
            depth = len(rel.parts)
        except ValueError:
            depth = DESCEND_MAX_DEPTH + 1
        if depth > DESCEND_MAX_DEPTH:
            dirs[:] = []
            continue
        if "SKILL.md" in files:
            path = current_path / "SKILL.md"
            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                content = ""
            fm = parse_frontmatter_basic(content)
            out.append((path, fm.get("name", "?"), fm.get("skill-type", "?")))
    out.sort(key=lambda x: str(x[0]))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--cwd", default=None, help="override cwd (for testing)")
    args = parser.parse_args()

    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd().resolve()
    results = collect_skill_md(cwd)

    if args.json:
        print(json.dumps([{"index": i + 1, "path": str(p), "name": name, "skill_type": skill_type}
                          for i, (p, name, skill_type) in enumerate(results)], indent=2))
        return 0

    if not results:
        print(f"No SKILL.md files found under {cwd}.")
        return 0

    print(f"SKILL.md files visible from {cwd}:\n")
    for i, (path, name, skill_type) in enumerate(results, start=1):
        try:
            display = path.relative_to(cwd)
        except ValueError:
            display = path
        print(f"  {i:>3}. [{skill_type:<18}] {name:<24} {display}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
