#!/usr/bin/env python3
"""classify.py -- infer a SKILL.md's type from its YAML contract or content shape.

Usage:
    python classify.py <path-to-SKILL.md>
    python classify.py <path-to-SKILL.md> --json

Two-path classification:

1. YAML-contract path (preferred): if the SKILL.md carries a fenced YAML
   block with a recognized contract root key (reference_skill,
   pattern_skill, technique_skill, discipline_skill, domain_skill), that
   root key is the deterministic type. Multiple roots = mixed-type.
   Frontmatter `skill-type:` is checked for agreement.

2. Heuristic fallback: for legacy / not-yet-migrated skills without a
   YAML contract block, score the body against each canonical type.
   Highest score wins; multiple high scorers = mixed-type.

Useful for organic skills that haven't adopted the framework yet.
The agent reviews the suggestion and applies it via tag.py.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from _shared import parse_frontmatter, parse_body, type_signals

try:
    import yaml as _pyyaml
    HAVE_YAML = True
except ImportError:
    _pyyaml = None
    HAVE_YAML = False


MIXED_THRESHOLD = 2  # number of types scoring this high or above => flag mixed

CONTRACT_ROOT_TO_TYPE = {
    "reference_skill": "reference-skill",
    "pattern_skill": "pattern-skill",
    "technique_skill": "technique-skill",
    "discipline_skill": "discipline-skill",
    "domain_skill": "domain-skill",
    "capability_skill": "capability-skill",
}

_YAML_BLOCK_RE = re.compile(r"^```ya?ml\s*\n(.*?)^```", re.MULTILINE | re.DOTALL)


def extract_yaml_roots(body_text: str) -> list[str]:
    """Return the list of canonical contract root keys present in any fenced
    YAML block in the body. Empty list when no YAML block parses or no
    recognized root key is present.
    """
    if not HAVE_YAML:
        # Regex fallback: detect contract root keys without parsing
        roots: list[str] = []
        for m in _YAML_BLOCK_RE.finditer(body_text):
            text = m.group(1)
            for root in CONTRACT_ROOT_TO_TYPE:
                if re.search(rf"^{root}\s*:", text, re.MULTILINE) and root not in roots:
                    roots.append(root)
        return roots

    roots = []
    for m in _YAML_BLOCK_RE.finditer(body_text):
        text = m.group(1)
        try:
            data = _pyyaml.safe_load(text)
        except Exception:
            continue
        if isinstance(data, dict):
            for root in CONTRACT_ROOT_TO_TYPE:
                if root in data and root not in roots:
                    roots.append(root)
    return roots


def classify(skill_md_path: Path) -> dict:
    if not skill_md_path.exists():
        return {"error": f"file not found: {skill_md_path}"}
    content = skill_md_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)
    body = parse_body(content)

    declared = fm.fields.get("skill-type") if fm else None
    yaml_roots = extract_yaml_roots(body.text)

    if len(yaml_roots) >= 2:
        canonical_types = [CONTRACT_ROOT_TO_TYPE[r] for r in yaml_roots]
        return {
            "path": str(skill_md_path),
            "declared_type": declared,
            "suggested_type": None,
            "verdict": "mixed-type",
            "reason": (
                f"YAML contract block contains multiple type roots: "
                + ", ".join(yaml_roots)
                + ". Split the skill along type boundaries."
            ),
            "source": "yaml-contract",
            "yaml_roots": yaml_roots,
            "canonical_types": canonical_types,
            "scores": {},
        }

    if len(yaml_roots) == 1:
        root = yaml_roots[0]
        suggested = CONTRACT_ROOT_TO_TYPE[root]
        if declared and declared != suggested:
            return {
                "path": str(skill_md_path),
                "declared_type": declared,
                "suggested_type": suggested,
                "verdict": "frontmatter-disagreement",
                "reason": (
                    f"YAML contract root '{root}' implies type '{suggested}', "
                    f"but frontmatter declares skill-type: '{declared}'. "
                    "Align the frontmatter and the YAML root."
                ),
                "source": "yaml-contract",
                "yaml_roots": yaml_roots,
                "scores": {},
            }
        return {
            "path": str(skill_md_path),
            "declared_type": declared,
            "suggested_type": suggested,
            "verdict": "single-type",
            "reason": f"YAML contract root '{root}' identifies type deterministically.",
            "source": "yaml-contract",
            "yaml_roots": yaml_roots,
            "scores": {},
        }

    # No YAML contract block; fall back to heuristic scoring.
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
        "source": "heuristic-fallback",
        "yaml_roots": [],
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
    lines.append(f"source:         {report.get('source', 'heuristic-fallback')}")
    lines.append(f"reason:         {report['reason']}")
    if report.get("yaml_roots"):
        lines.append(f"yaml_roots:     {report['yaml_roots']}")
    if report.get("scores"):
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
