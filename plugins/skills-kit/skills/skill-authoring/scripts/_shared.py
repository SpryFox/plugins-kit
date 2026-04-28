"""Shared helpers for audit.py / classify.py / tag.py.

Stdlib-only. Heuristic detectors for SKILL.md structural shape.
"""

import re
from dataclasses import dataclass, field


FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
FIELD_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:\s*(.+?)\s*$", re.MULTILINE)

CANONICAL_TYPES = {
    "reference-skill",
    "pattern-skill",
    "technique-skill",
    "discipline-skill",
    "domain-skill",
}


@dataclass
class Frontmatter:
    raw: str
    fields: dict = field(default_factory=dict)


@dataclass
class Body:
    text: str
    lines: int
    tokens_approx: int


def parse_frontmatter(content: str):
    m = FRONTMATTER_RE.match(content)
    if not m:
        return None
    raw = m.group(1)
    fm = Frontmatter(raw=raw)
    for name, val in FIELD_RE.findall(raw):
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        fm.fields[name] = val
    return fm


def parse_body(content: str) -> Body:
    m = FRONTMATTER_RE.match(content)
    body_text = content[m.end():] if m else content
    lines = body_text.splitlines()
    words = body_text.split()
    tokens_approx = int(len(words) * 1.3)
    return Body(text=body_text, lines=len(lines), tokens_approx=tokens_approx)


def has_heading(body_text: str, *names: str) -> bool:
    pattern = r"^#{1,6}\s+(?:" + "|".join(re.escape(n) for n in names) + r")\b"
    return bool(re.search(pattern, body_text, re.MULTILINE | re.IGNORECASE))


def count_ordered_steps(body_text: str) -> int:
    return len(re.findall(r"^\s*\d+\.\s+\S", body_text, re.MULTILINE))


def has_tickbox_list(body_text: str) -> bool:
    return bool(re.search(r"^\s*-\s*\[\s?\]", body_text, re.MULTILINE))


def has_excuse_reality_table(body_text: str) -> bool:
    if re.search(r"\|\s*excuse\s*\|.*\|\s*reality\s*\|", body_text, re.IGNORECASE):
        return True
    if "rationalization" in body_text.lower():
        return True
    return False


def has_red_green_refactor(body_text: str) -> bool:
    return bool(re.search(r"\bRED\s*[-/>]+\s*GREEN\s*[-/>]+\s*REFACTOR\b", body_text, re.IGNORECASE))


def has_red_flags_list(body_text: str) -> bool:
    return has_heading(body_text, "Red flags", "Red Flags")


def has_conditional_loading(body_text: str) -> bool:
    return has_heading(body_text, "Conditional Loading", "Conditional loading")


def has_companion_declaration(body_text: str) -> bool:
    if re.search(
        r"^#{1,6}\s+(?:Companion declaration|Companion Declaration|Companions?)\b",
        body_text,
        re.MULTILINE,
    ):
        return True
    if re.search(r"\bno sibling\s+domains?\b", body_text, re.IGNORECASE):
        return True
    if re.search(r"\bcompanion\s+domains?\b", body_text, re.IGNORECASE):
        return True
    return False


def has_recognition_marker(body_text: str) -> bool:
    return bool(re.search(r"\b(recogn(?:ize|ition)|applies\s+when)\b", body_text, re.IGNORECASE))


def has_counter_example(body_text: str) -> bool:
    return bool(re.search(r"\bcounter[- ]example|\bdo\s+NOT\s+apply", body_text, re.IGNORECASE))


def has_lookup_table(body_text: str) -> bool:
    """Detect a markdown table with at least 3 columns (suggests reference-style lookup)."""
    return bool(re.search(r"^\|.+\|.+\|.+\|$", body_text, re.MULTILINE))


def type_signals(body_text: str) -> dict:
    """Score each canonical skill type based on structural markers in the body.

    Returns a dict mapping each of the five canonical type names to an integer
    score. Higher = more evidence the skill is that type.
    """
    scores = {t: 0 for t in CANONICAL_TYPES}

    # discipline signals
    if has_excuse_reality_table(body_text):
        scores["discipline-skill"] += 2
    if has_red_green_refactor(body_text):
        scores["discipline-skill"] += 2
    if has_red_flags_list(body_text):
        scores["discipline-skill"] += 1

    # pattern signals
    if has_recognition_marker(body_text):
        scores["pattern-skill"] += 1
    if has_counter_example(body_text):
        scores["pattern-skill"] += 2

    # technique signals
    steps = count_ordered_steps(body_text)
    if steps >= 1:
        scores["technique-skill"] += 1
    if steps > 3:
        scores["technique-skill"] += 1
    if has_tickbox_list(body_text):
        scores["technique-skill"] += 1

    # reference signals
    if has_lookup_table(body_text):
        scores["reference-skill"] += 1
    if has_heading(body_text, "Gotcha", "Gotchas", "Known gotchas"):
        scores["reference-skill"] += 1
    if has_heading(body_text, "Example", "Examples"):
        scores["reference-skill"] += 1

    # domain signals
    if has_conditional_loading(body_text):
        scores["domain-skill"] += 2
    if has_companion_declaration(body_text):
        scores["domain-skill"] += 2

    return scores
