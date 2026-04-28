#!/usr/bin/env python3
"""classify.py -- infer a SKILL.md's type from its content shape.

Usage:
    python classify.py <path-to-SKILL.md>
    python classify.py <path-to-SKILL.md> --json

Reads a SKILL.md and scores it against each of the five canonical
skill types (reference / pattern / technique / discipline / domain).
Outputs the highest-scoring type as the suggested `skill-type:` value,
or flags the skill as mixed-type when multiple types tie or when
multiple types score above a confidence threshold.

Useful for organic skills that haven't adopted the framework yet.
The agent reviews the suggestion and applies it via tag.py.
"""

import argparse
import json
import sys
from pathlib import Path

from _shared import parse_frontmatter, parse_body, type_signals


MIXED_THRESHOLD = 2  # number of types scoring this high or above => flag mixed


def classify(skill_md_path: Path) -> dict:
    if not skill_md_path.exists():
        return {"error": f"file not found: {skill_md_path}"}
    content = skill_md_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)
    body = parse_body(content)

    declared = fm.fields.get("skill-type") if fm else None
    scores = type_signals(body.text, fm)

    sorted_types = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_type, top_score = sorted_types[0]
    runner_up_score = sorted_types[1][1] if len(sorted_types) > 1 else 0

    high_scoring = [t for t, s in sorted_types if s >= MIXED_THRESHOLD]
    suggestion = top_type if top_score > 0 else None

    if len(high_scoring) >= 2:
        verdict = "mixed-type"
        reason = (
            f"multiple types score >= {MIXED_THRESHOLD}: "
            + ", ".join(f"{t}={scores[t]}" for t in high_scoring)
        )
    elif top_score == 0:
        verdict = "indeterminate"
        reason = "no canonical-type signals detected"
    elif top_score == runner_up_score:
        verdict = "ambiguous"
        reason = (
            f"top types tie at {top_score}: "
            + ", ".join(f"{t}={scores[t]}" for t, s in sorted_types if s == top_score)
        )
    else:
        verdict = "single-type"
        reason = f"top={top_type} with score={top_score}, runner-up={runner_up_score}"

    return {
        "path": str(skill_md_path),
        "declared_type": declared,
        "suggested_type": suggestion,
        "verdict": verdict,
        "reason": reason,
        "scores": scores,
    }


def render_text(report: dict) -> str:
    if "error" in report:
        return report["error"]
    lines = []
    lines.append(f"classify: {report['path']}")
    lines.append(f"declared_type:  {report['declared_type']}")
    lines.append(f"suggested_type: {report['suggested_type']}")
    lines.append(f"verdict:        {report['verdict']}")
    lines.append(f"reason:         {report['reason']}")
    lines.append("")
    lines.append("scores:")
    for t, s in sorted(report["scores"].items(), key=lambda kv: kv[1], reverse=True):
        lines.append(f"  {t:<20} {s}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Classify a SKILL.md by inferring its type from content shape.",
    )
    parser.add_argument("path", help="Path to SKILL.md")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args(argv)

    report = classify(Path(args.path))
    if "error" in report:
        print(report["error"], file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
