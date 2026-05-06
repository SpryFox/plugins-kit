#!/usr/bin/env python3
"""report.py -- generate a location- and type-grouped roster of SKILL.md files.

Walks three sets of roots:
  - User skills    ~/.claude/skills/
  - Project skills <cwd>/.claude/skills/
  - Plugin skills  per ~/.claude/plugins/installed_plugins.json (active install per plugin)

For each SKILL.md, parses the YAML frontmatter and the first fenced YAML block in
the body (the type contract). Renders a markdown report grouped first by location,
then by skill-type. Per-type implied frontmatter is declared once at the top of
its group so per-skill rows do not duplicate it.

Stdlib + PyYAML (a skills-kit dependency).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

import yaml


CONTRACT_ROOTS = (
    "reference_skill",
    "pattern_skill",
    "technique_skill",
    "discipline_skill",
    "domain_skill",
    "capability_skill",
)

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)^---\s*\n", re.DOTALL | re.MULTILINE)
YAML_FENCE_RE = re.compile(r"```yaml\s*\n(.*?)```", re.DOTALL)


def parse_skill_md(path: Path) -> dict | None:
    """Return {frontmatter, body, path} or None on read failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    fm: dict = {}
    body_text = text
    m = FRONTMATTER_RE.match(text)
    if m:
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
        body_text = text[m.end():]

    body_yaml: dict | None = None
    bm = YAML_FENCE_RE.search(body_text)
    if bm:
        try:
            body_yaml = yaml.safe_load(bm.group(1))
        except yaml.YAMLError:
            body_yaml = None

    return {"frontmatter": fm, "body": body_yaml, "path": path}


def detect_skill_type(skill: dict) -> tuple[str, str]:
    """Return (skill_type, variant). variant is 'user-only' / 'auto' for technique-skill, else ''."""
    fm = skill.get("frontmatter") or {}
    body = skill.get("body") or {}

    declared = (fm.get("skill-type") or "").strip().lower()

    body_type = ""
    if isinstance(body, dict):
        for root in CONTRACT_ROOTS:
            if root in body:
                body_type = root.replace("_", "-")
                break

    skill_type = declared or body_type or "(unknown)"

    variant = ""
    if skill_type == "technique-skill":
        block = body.get("technique_skill") if isinstance(body, dict) else None
        trigger = ""
        if isinstance(block, dict):
            trigger = (block.get("trigger_model") or "").strip().lower()
        variant = "user-only" if trigger == "user-only" else "auto"

    return skill_type, variant


def implied_flags(skill_type: str, variant: str) -> dict:
    """Frontmatter values implied by the (type, variant) contract.

    Only entries with implied=True are surfaced as 'implied' in the report header;
    per-skill rows show flags only when their value differs from this map.
    """
    if skill_type == "technique-skill" and variant == "user-only":
        return {"disable-model-invocation": True, "user-invocable": True}
    return {"disable-model-invocation": False, "user-invocable": False}


def enumerate_user(home: Path) -> list[Path]:
    root = home / ".claude" / "skills"
    return sorted(root.rglob("SKILL.md")) if root.is_dir() else []


def enumerate_project(cwd: Path) -> list[Path]:
    root = cwd / ".claude" / "skills"
    return sorted(root.rglob("SKILL.md")) if root.is_dir() else []


def enumerate_plugins(home: Path) -> list[tuple[str, str, str, list[Path]]]:
    manifest = home / ".claude" / "plugins" / "installed_plugins.json"
    if not manifest.is_file():
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    out: list[tuple[str, str, str, list[Path]]] = []
    for key, installs in data.get("plugins", {}).items():
        if "@" in key:
            plugin_name, marketplace = key.split("@", 1)
        else:
            plugin_name, marketplace = key, "(unknown)"
        for install in installs:
            install_path = Path(install.get("installPath", ""))
            version = install.get("version", "")
            skills_root = install_path / "skills"
            if not skills_root.is_dir():
                continue
            paths = sorted(skills_root.rglob("SKILL.md"))
            out.append((plugin_name, marketplace, version, paths))
    return out


def build_groups(paths: list[Path]) -> OrderedDict:
    """Group skill records by (skill_type, variant); each group sorted by name."""
    bucket: dict[tuple[str, str], list[dict]] = {}
    for p in paths:
        sk = parse_skill_md(p)
        if sk is None:
            continue
        key = detect_skill_type(sk)
        bucket.setdefault(key, []).append(sk)

    for lst in bucket.values():
        lst.sort(key=lambda s: ((s.get("frontmatter") or {}).get("name") or s["path"].name).lower())

    ordered = OrderedDict()
    for k in sorted(bucket.keys()):
        ordered[k] = bucket[k]
    return ordered


def fmt_flag(name: str, value) -> str:
    return f"`{name}: {str(value).lower()}`"


def render_skill_row(sk: dict, implied: dict) -> list[str]:
    fm = sk.get("frontmatter") or {}
    name = fm.get("name") or sk["path"].name
    desc = (fm.get("description") or "").strip()
    author = fm.get("author")

    tag = f" [author: {author}]" if author else ""
    line = f"- **{name}**{tag}"
    if desc:
        line += f" -- {desc}"
    rows = [line]

    extras: list[str] = []
    for flag in ("disable-model-invocation", "user-invocable"):
        if flag in fm:
            actual = bool(fm[flag])
            expected = bool(implied.get(flag, False))
            if actual != expected:
                extras.append(fmt_flag(flag, fm[flag]))
    if extras:
        rows.append(f"  - {', '.join(extras)}")
    return rows


def render(report: OrderedDict) -> str:
    lines: list[str] = ["# Skill Report", ""]
    lines.append(f"Generated {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")

    for loc_name, groups in report.items():
        lines.append(f"## {loc_name}")
        lines.append("")
        if not groups:
            lines.append("(no skills found)")
            lines.append("")
            continue
        for (skill_type, variant), skills in groups.items():
            heading = skill_type if not variant else f"{skill_type} ({variant})"
            lines.append(f"### {heading}")
            lines.append("")
            implied = implied_flags(skill_type, variant)
            implied_pairs = [fmt_flag(k, v) for k, v in implied.items() if v]
            if implied_pairs:
                lines.append(f"_Implied frontmatter: {', '.join(implied_pairs)}_")
                lines.append("")
            for sk in skills:
                lines.extend(render_skill_row(sk, implied))
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a skill inventory report.")
    parser.add_argument("--out", help="Write report to this path instead of stdout.")
    parser.add_argument("--cwd", default=os.getcwd(), help="Project root (default: cwd).")
    args = parser.parse_args()

    home = Path.home()
    cwd = Path(args.cwd).resolve()

    report: OrderedDict[str, OrderedDict] = OrderedDict()
    report[f"User (~/.claude/skills)"] = build_groups(enumerate_user(home))
    report[f"Project ({cwd}/.claude/skills)"] = build_groups(enumerate_project(cwd))
    for plugin_name, marketplace, version, paths in enumerate_plugins(home):
        label = f"Plugin: {plugin_name} ({marketplace}, v{version})"
        report[label] = build_groups(paths)

    out = render(report)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
    else:
        sys.stdout.write(out)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
