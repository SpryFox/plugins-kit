"""Corpus-level audit checks.

These checks operate over the union of (registry, file-system) rather than
a single SKILL.md. The per-SKILL audit lives in audit.py; this module is
for checks that walk the registry against owner docs and cross-source rules.

The owner-doc check is the primary anti-drift guard: every registered schema
declares an owner_doc, and this check asserts each owner doc contains a valid
instance of its schema. If the schema changes incompatibly, the owner doc's
example fails; if the owner doc drifts from the schema, validation flags it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .document_walker import collect_yaml_units
from .schema_engine import validate
from .schema_registry import OWNER_DOCS, SCHEMAS_BY_ROOT


@dataclass
class OwnerDocResult:
    root: str
    owner_doc: str
    status: str  # pass | missing-file | missing-instance | invalid-instance
    message: str = ""
    fails: list = None

    def __post_init__(self):
        if self.fails is None:
            self.fails = []


def plugin_root() -> Path:
    """Resolve the plugin-root path (one level above skills_kit_lib/)."""
    return Path(__file__).resolve().parent.parent


def check_schema_owner_docs_validate(root: Path | None = None) -> list[OwnerDocResult]:
    """For each registered schema with an owner_doc, assert the owner doc
    contains a valid instance of the schema's root key.

    Returns one OwnerDocResult per registered schema with an owner_doc.
    """
    root = root or plugin_root()
    results: list[OwnerDocResult] = []

    for unit_root, owner_doc in OWNER_DOCS.items():
        schema = SCHEMAS_BY_ROOT.get(unit_root)
        if schema is None:
            continue
        path = root / owner_doc
        if not path.exists():
            results.append(OwnerDocResult(
                root=unit_root,
                owner_doc=owner_doc,
                status="missing-file",
                message=f"owner_doc path does not exist: {path}",
            ))
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            results.append(OwnerDocResult(
                root=unit_root,
                owner_doc=owner_doc,
                status="missing-file",
                message=f"could not read owner_doc: {e}",
            ))
            continue

        units, _ = collect_yaml_units(text)
        instances = [data for (r, data) in units if r == unit_root]
        if not instances:
            results.append(OwnerDocResult(
                root=unit_root,
                owner_doc=owner_doc,
                status="missing-instance",
                message=f"owner_doc contains no `{unit_root}:` block",
            ))
            continue

        # Validate each instance; require all to pass.
        all_fails: list = []
        for i, inst in enumerate(instances):
            fails, _ = validate(inst, schema)
            for path_, msg in fails:
                all_fails.append((f"instance[{i}].{path_}", msg))

        if all_fails:
            results.append(OwnerDocResult(
                root=unit_root,
                owner_doc=owner_doc,
                status="invalid-instance",
                message=f"{len(all_fails)} validation failures across {len(instances)} instance(s)",
                fails=all_fails,
            ))
        else:
            results.append(OwnerDocResult(
                root=unit_root,
                owner_doc=owner_doc,
                status="pass",
                message=f"{len(instances)} instance(s) validate",
            ))

    return results


def render_owner_doc_results(results: list[OwnerDocResult]) -> str:
    """Format owner-doc results as a human-readable text report."""
    lines: list[str] = []
    lines.append("== Schema owner-doc validation ==")
    for r in results:
        suffix = f" -- {r.message}" if r.message else ""
        lines.append(f"  [{r.status}] {r.root} <- {r.owner_doc}{suffix}")
        for path, msg in r.fails:
            lines.append(f"      {path}: {msg}")
    return "\n".join(lines)
