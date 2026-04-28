#!/usr/bin/env python3
"""audit.py -- run deterministic contract checks against a SKILL.md.

Usage:
    python audit.py <path-to-SKILL.md>
    python audit.py <path-to-SKILL.md> --json

Emits a per-row verdict: pass / fail / judgment-required / n/a. Rows
flagged judgment-required are not deterministic at this level; the
agent runs them by hand against the contract in
references/framework.md.

Stdlib-only.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from _shared import (
    CANONICAL_TYPES,
    Body,
    Frontmatter,
    count_ordered_steps,
    has_companion_declaration,
    has_conditional_loading,
    has_counter_example,
    has_excuse_reality_table,
    has_heading,
    has_lookup_table,
    has_recognition_marker,
    has_red_flags_list,
    has_red_green_refactor,
    has_tickbox_list,
    has_yaml_block,
    is_user_only,
    parse_body,
    parse_frontmatter,
    strip_code_fences,
)


RESERVED_NAMES = {"anthropic", "claude"}

PASS = "pass"
FAIL = "fail"
JUDGMENT = "judgment-required"
NA = "n/a"


@dataclass
class CheckResult:
    row: str
    verdict: str
    note: str = ""


def has_identity_sentence(body_text: str) -> bool:
    after_h1 = re.split(r"^#\s+\S.+$", body_text, maxsplit=1, flags=re.MULTILINE)
    if len(after_h1) < 2:
        return False
    rest = after_h1[1].lstrip()
    first_para = rest.split("\n\n", 1)[0].strip()
    return bool(first_para) and "." in first_para and len(first_para) < 600


def check_universal(fm: Frontmatter | None, body: Body, skill_dir: Path) -> list[CheckResult]:
    out: list[CheckResult] = []
    if fm is None:
        out.append(CheckResult("frontmatter present", FAIL, "no leading --- block"))
        return out
    out.append(CheckResult("frontmatter present", PASS))

    if "name" not in fm.fields:
        out.append(CheckResult("frontmatter.name present", FAIL))
    else:
        name = fm.fields["name"]
        out.append(CheckResult("frontmatter.name present", PASS))
        out.append(CheckResult("name <= 64 chars", PASS if len(name) <= 64 else FAIL, f"len={len(name)}"))
        out.append(CheckResult(
            "name charset (lowercase/digits/hyphens)",
            PASS if re.fullmatch(r"[a-z0-9-]+", name) else FAIL,
            name,
        ))
        out.append(CheckResult("name not reserved", PASS if name not in RESERVED_NAMES else FAIL, name))

    if "description" not in fm.fields:
        out.append(CheckResult("frontmatter.description present", FAIL))
    else:
        desc = fm.fields["description"]
        out.append(CheckResult("frontmatter.description present", PASS))
        out.append(CheckResult(
            "description <= 160 chars",
            PASS if len(desc) <= 160 else FAIL,
            f"len={len(desc)}",
        ))
        desc_lc = desc.lower().lstrip()
        directive = desc_lc.startswith("use when") or desc_lc.startswith("invoke when")
        out.append(CheckResult(
            "directive form ('Use when...' / 'Invoke when...')",
            PASS if directive else FAIL,
            "description should open with 'Use when...' or 'Invoke when...'" if not directive else "",
        ))
        excl = bool(re.search(r"\bdo not use\b|\bdon'?t use\b", desc, re.IGNORECASE))
        out.append(CheckResult(
            "exclusion clause (Do NOT use for...)",
            PASS if excl else FAIL,
            "no 'do not use' phrase in description" if not excl else "",
        ))

    if "skill-type" not in fm.fields:
        out.append(CheckResult(
            "skill-type advisory tag",
            JUDGMENT,
            "no skill-type frontmatter; agent infers type from content",
        ))
    else:
        val = fm.fields["skill-type"]
        if val in CANONICAL_TYPES:
            out.append(CheckResult("skill-type value valid", PASS, val))
        else:
            out.append(CheckResult(
                "skill-type value valid",
                FAIL,
                f"got '{val}', expected one of {sorted(CANONICAL_TYPES)}",
            ))

    out.append(CheckResult("SKILL.md line count", PASS, str(body.lines)))
    out.append(CheckResult("SKILL.md token count (approx)", PASS, str(body.tokens_approx)))

    has_references = (skill_dir / "references").exists()
    body_too_big = body.lines > 500 or body.tokens_approx > 3000
    if not body_too_big:
        out.append(CheckResult(
            "progressive disclosure (conditional)",
            NA,
            f"lines={body.lines}, tokens~{body.tokens_approx}",
        ))
    elif has_references:
        out.append(CheckResult(
            "progressive disclosure (conditional)",
            PASS,
            f"body large (lines={body.lines}, tokens~{body.tokens_approx}); references/ exists",
        ))
    else:
        out.append(CheckResult(
            "progressive disclosure (conditional)",
            FAIL,
            f"body large (lines={body.lines}, tokens~{body.tokens_approx}) but no references/",
        ))

    refs_dir = skill_dir / "references"
    if not refs_dir.exists():
        out.append(CheckResult("references one-hop-deep (ADP)", NA, "no references/ directory"))
    else:
        nested = list(refs_dir.glob("*/*.md"))
        if nested:
            rel = [str(p.relative_to(skill_dir)) for p in nested]
            out.append(CheckResult("references one-hop-deep (ADP)", FAIL, f"nested: {rel}"))
        else:
            out.append(CheckResult("references one-hop-deep (ADP)", PASS))

    cited = set(re.findall(r"references/([a-zA-Z0-9_\-]+\.md)", body.text))
    if not cited:
        out.append(CheckResult("references cited in body all exist", NA, "no references cited in body"))
    else:
        missing = [name for name in cited if not (skill_dir / "references" / name).exists()]
        if missing:
            out.append(CheckResult("references cited in body all exist", FAIL, f"missing: {missing}"))
        else:
            out.append(CheckResult("references cited in body all exist", PASS, f"checked {len(cited)} references"))

    return out


def check_reference_skill(body: Body, skill_dir: Path) -> list[CheckResult]:
    out: list[CheckResult] = []
    out.append(CheckResult(
        ">=1 example block",
        PASS if has_heading(body.text, "Example", "Examples") else JUDGMENT,
        "no 'Example' heading detected" if not has_heading(body.text, "Example", "Examples") else "",
    ))
    out.append(CheckResult(
        ">=1 gotcha block",
        PASS if has_heading(body.text, "Gotcha", "Gotchas", "Known gotchas") else JUDGMENT,
        "no 'Gotcha' heading detected" if not has_heading(body.text, "Gotcha", "Gotchas", "Known gotchas") else "",
    ))
    discipline_hit = has_red_green_refactor(body.text) or has_excuse_reality_table(body.text)
    out.append(CheckResult(
        "prohibited: discipline content (rule+counter, RED/GREEN/REFACTOR)",
        FAIL if discipline_hit else PASS,
        "discipline markers detected" if discipline_hit else "",
    ))
    out.append(CheckResult(
        "prohibited: workflow checklist",
        FAIL if has_tickbox_list(body.text) else PASS,
        "tickbox list present" if has_tickbox_list(body.text) else "",
    ))
    return out


def check_pattern_skill(body: Body, skill_dir: Path) -> list[CheckResult]:
    out: list[CheckResult] = []
    out.append(CheckResult(
        "recognition criteria block",
        PASS if has_recognition_marker(body.text) else JUDGMENT,
        "no 'recognize/recognition/applies when' marker" if not has_recognition_marker(body.text) else "",
    ))
    out.append(CheckResult(
        "counter-example(s) block",
        PASS if has_counter_example(body.text) else JUDGMENT,
        "no 'counter-example' or 'do NOT apply' marker" if not has_counter_example(body.text) else "",
    ))
    bundle_present = (skill_dir / "scripts").exists() or (skill_dir / "bin").exists()
    out.append(CheckResult(
        "prohibited: utility bundle",
        FAIL if bundle_present else PASS,
        "scripts/ or bin/ present" if bundle_present else "",
    ))
    out.append(CheckResult(
        "prohibited: workflow checklist",
        FAIL if has_tickbox_list(body.text) else PASS,
    ))
    out.append(CheckResult(
        "prohibited: rule + counter pairs",
        FAIL if has_excuse_reality_table(body.text) else PASS,
        "rationalization/excuse->reality detected" if has_excuse_reality_table(body.text) else "",
    ))
    return out


def check_technique_skill(body: Body, skill_dir: Path, fm: Frontmatter | None) -> list[CheckResult]:
    out: list[CheckResult] = []
    step_count = count_ordered_steps(body.text)
    user_only = is_user_only(fm)
    if user_only:
        out.append(CheckResult(
            "ordered-step body (conditional, IF NOT user-only)",
            NA,
            "user-only (disable-model-invocation: true); the technique IS the slash-command",
        ))
    else:
        out.append(CheckResult(
            "ordered-step body (conditional, IF NOT user-only)",
            PASS if step_count >= 1 else FAIL,
            f"{step_count} ordered-step entries detected",
        ))
    if step_count > 3:
        out.append(CheckResult(
            "workflow checklist (conditional, IF >3 steps)",
            PASS if has_tickbox_list(body.text) else FAIL,
            f"{step_count} steps; tickbox checklist {'present' if has_tickbox_list(body.text) else 'missing'}",
        ))
    else:
        out.append(CheckResult(
            "workflow checklist (conditional, IF >3 steps)",
            NA,
            f"only {step_count} steps",
        ))
    out.append(CheckResult(
        "prohibited: adversarial pressure testing",
        FAIL if has_red_green_refactor(body.text) else PASS,
        "RED/GREEN/REFACTOR markers present" if has_red_green_refactor(body.text) else "",
    ))
    return out


def check_discipline_skill(body: Body, skill_dir: Path) -> list[CheckResult]:
    out: list[CheckResult] = []
    out.append(CheckResult(
        ">=1 rule + counter pair",
        PASS if has_excuse_reality_table(body.text) else FAIL,
        "no rule+counter / rationalization markers" if not has_excuse_reality_table(body.text) else "",
    ))
    out.append(CheckResult(
        "red flags list",
        PASS if has_red_flags_list(body.text) else FAIL,
        "no 'Red flags' heading" if not has_red_flags_list(body.text) else "",
    ))
    if has_red_green_refactor(body.text):
        out.append(CheckResult(
            "adversarial pressure testing applied",
            JUDGMENT,
            "RED/GREEN/REFACTOR markers present; agent must verify pressure testing was applied to this skill's own rules",
        ))
    else:
        out.append(CheckResult(
            "adversarial pressure testing applied",
            FAIL,
            "no RED/GREEN/REFACTOR markers",
        ))
    return out


def check_domain_skill(body: Body, skill_dir: Path) -> list[CheckResult]:
    out: list[CheckResult] = []
    out.append(CheckResult(
        "identity sentence",
        PASS if has_identity_sentence(body.text) else JUDGMENT,
        "no clear single-sentence identity after H1" if not has_identity_sentence(body.text) else "",
    ))
    out.append(CheckResult(
        "companion declaration",
        PASS if has_companion_declaration(body.text) else FAIL,
        "no 'Companion declaration' heading or 'no sibling' / 'companion domains' phrase" if not has_companion_declaration(body.text) else "",
    ))
    h2_count = len(re.findall(r"^##\s+\S", body.text, re.MULTILINE))
    out.append(CheckResult(
        "orientation content (>=1 H2 beyond index)",
        PASS if h2_count >= 2 else FAIL,
        f"{h2_count} H2 sections",
    ))
    out.append(CheckResult(
        "reference index (Conditional Loading)",
        PASS if has_conditional_loading(body.text) else FAIL,
    ))
    if h2_count == 1 and has_conditional_loading(body.text):
        out.append(CheckResult(
            "prohibited: index without orientation",
            FAIL,
            "only Conditional Loading H2; no orientation content",
        ))
    else:
        out.append(CheckResult(
            "prohibited: index without orientation",
            PASS,
        ))
    return out


def mixed_type_signal(body_text: str) -> tuple[int, list[str]]:
    """Detect cross-type signals on the narrative body (code fences stripped).

    Skill bodies can include structured data inside fenced code blocks (yaml,
    json, python). That structured data is reference content for machine
    comprehension, not narrative or procedure -- it must not raise the mixed-
    type score by its internal shape. We strip fences before counting any
    narrative-driven signal, and treat the presence of a YAML block itself as
    a reference-content marker (not technique).
    """
    narrative = strip_code_fences(body_text)
    signals: list[str] = []
    if has_excuse_reality_table(narrative) or has_red_green_refactor(narrative):
        signals.append("discipline-content (rule+counter or RED/GREEN/REFACTOR)")
    if has_recognition_marker(narrative) or has_counter_example(narrative):
        signals.append("pattern-content (recognition / counter-example)")
    if count_ordered_steps(narrative) >= 1:
        signals.append("technique-content (ordered steps)")
    if has_lookup_table(narrative) or has_yaml_block(body_text):
        signals.append("reference-content (lookup tables / YAML blocks)")
    if has_conditional_loading(narrative):
        signals.append("domain-content (Conditional Loading index)")
    return len(signals), signals


TYPE_RUNNERS = {
    "reference-skill": check_reference_skill,
    "pattern-skill": check_pattern_skill,
    "technique-skill": check_technique_skill,
    "discipline-skill": check_discipline_skill,
    "domain-skill": check_domain_skill,
}


def audit(skill_md_path: Path) -> dict[str, Any]:
    if not skill_md_path.exists():
        return {"error": f"file not found: {skill_md_path}"}
    content = skill_md_path.read_text(encoding="utf-8")
    skill_dir = skill_md_path.parent

    fm = parse_frontmatter(content)
    body = parse_body(content)

    universal = check_universal(fm, body, skill_dir)
    declared_type = fm.fields.get("skill-type") if fm else None
    type_specific: list[CheckResult] = []
    if declared_type in TYPE_RUNNERS:
        if declared_type == "technique-skill":
            type_specific = check_technique_skill(body, skill_dir, fm)
        else:
            type_specific = TYPE_RUNNERS[declared_type](body, skill_dir)

    score, signals = mixed_type_signal(body.text)
    if score >= 2:
        mixed = CheckResult(
            "mixed-type signal",
            JUDGMENT,
            f"score={score}: {signals}",
        )
    else:
        mixed = CheckResult("mixed-type signal", PASS, f"score={score}")

    return {
        "path": str(skill_md_path),
        "declared_type": declared_type,
        "universal": [asdict(r) for r in universal],
        "type_specific": [asdict(r) for r in type_specific],
        "mixed_type": asdict(mixed),
    }


def render_text(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"audit: {report['path']}")
    lines.append(f"declared_type: {report['declared_type']}")
    lines.append("")
    lines.append("== Universal ==")
    for r in report["universal"]:
        suffix = f" -- {r['note']}" if r["note"] else ""
        lines.append(f"  [{r['verdict']}] {r['row']}{suffix}")
    lines.append("")
    lines.append(f"== Type-specific ({report['declared_type']}) ==")
    if not report["type_specific"]:
        lines.append("  (no recognized skill-type; type-specific checks skipped)")
    for r in report["type_specific"]:
        suffix = f" -- {r['note']}" if r["note"] else ""
        lines.append(f"  [{r['verdict']}] {r['row']}{suffix}")
    lines.append("")
    lines.append("== Mixed-type ==")
    mt = report["mixed_type"]
    suffix = f" -- {mt['note']}" if mt["note"] else ""
    lines.append(f"  [{mt['verdict']}] {mt['row']}{suffix}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Audit a SKILL.md against the skill-authoring framework.",
    )
    parser.add_argument("path", help="Path to SKILL.md")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of formatted text")
    args = parser.parse_args(argv)

    report = audit(Path(args.path))
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
