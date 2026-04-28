#!/usr/bin/env python3
"""tag.py -- write a `skill-type:` value into SKILL.md frontmatter.

Usage:
    python tag.py <path-to-SKILL.md> <skill-type>
    python tag.py <path-to-SKILL.md> <skill-type> --check

Idempotent. If the file already has the requested `skill-type:` value,
the script is a no-op. If the file has a different `skill-type:` value,
the script refuses unless --force is passed.

Skills without YAML frontmatter are flagged, never patched. Inventing
frontmatter would silently regularize a skill the framework expects to
treat as flagged.
"""

import argparse
import re
import sys
from pathlib import Path

from _shared import (
    FRONTMATTER_RE,
    CANONICAL_TYPES,
    parse_frontmatter,
)


SKILL_TYPE_LINE_RE = re.compile(r"^skill-type\s*:\s*(.+?)\s*$", re.MULTILINE)


def tag(skill_md_path: Path, new_type: str, force: bool, check_only: bool) -> dict:
    if not skill_md_path.exists():
        return {"ok": False, "error": f"file not found: {skill_md_path}"}
    if new_type not in CANONICAL_TYPES:
        return {
            "ok": False,
            "error": f"invalid skill-type '{new_type}'; expected one of {sorted(CANONICAL_TYPES)}",
        }

    content = skill_md_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)
    if fm is None:
        return {
            "ok": False,
            "error": "no YAML frontmatter; flagged for manual authoring (tag.py never invents frontmatter)",
            "action": "flag",
        }

    current = fm.fields.get("skill-type")
    if current == new_type:
        return {"ok": True, "action": "no-op", "skill-type": current}
    if current is not None and current != new_type and not force:
        return {
            "ok": False,
            "action": "refused",
            "error": f"existing skill-type '{current}' differs from requested '{new_type}'; pass --force to overwrite",
            "current": current,
            "requested": new_type,
        }

    if check_only:
        return {
            "ok": True,
            "action": "would-add" if current is None else "would-replace",
            "current": current,
            "requested": new_type,
        }

    m = FRONTMATTER_RE.match(content)
    fm_block = m.group(1)
    if current is None:
        new_fm_block = fm_block.rstrip() + f"\nskill-type: {new_type}"
    else:
        new_fm_block = SKILL_TYPE_LINE_RE.sub(f"skill-type: {new_type}", fm_block, count=1)

    new_content = content[: m.start(1)] + new_fm_block + content[m.end(1):]
    skill_md_path.write_text(new_content, encoding="utf-8")
    return {
        "ok": True,
        "action": "added" if current is None else "replaced",
        "previous": current,
        "current": new_type,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Tag a SKILL.md with a skill-type advisory frontmatter value.",
    )
    parser.add_argument("path", help="Path to SKILL.md")
    parser.add_argument("skill_type", help=f"One of: {sorted(CANONICAL_TYPES)}")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing skill-type value")
    parser.add_argument("--check", action="store_true", help="Report what would happen without writing")
    args = parser.parse_args(argv)

    result = tag(Path(args.path), args.skill_type, args.force, args.check)
    if not result.get("ok"):
        msg = result.get("error", "tag failed")
        print(msg, file=sys.stderr)
        return 1

    action = result.get("action")
    if action == "no-op":
        print(f"no-op: skill-type already '{result['skill-type']}'")
    elif action == "added":
        print(f"added skill-type: {result['current']}")
    elif action == "replaced":
        print(f"replaced skill-type: {result['previous']} -> {result['current']}")
    elif action == "would-add":
        print(f"would add skill-type: {result['requested']}")
    elif action == "would-replace":
        print(f"would replace skill-type: {result['current']} -> {result['requested']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
