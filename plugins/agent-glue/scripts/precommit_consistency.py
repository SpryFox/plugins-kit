"""Pre-commit consistency hook for agent-glue.

Loads the full kit (every subsystem's `components/` and `entities/`) and any consuming-project
instance yamls under `examples/`, runs the combined validator, and exits nonzero on any error.

The script is a thin facade over `agent_glue_lib.core`; tests target the library, not this file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

from agent_glue_lib.core import (  # noqa: E402
    LoaderError,
    load_catalog,
    load_instances,
    validate_all,
)


SUBSYSTEMS = ("core", "claude-work-queue", "work-system", "graph-system")


def _kit_dirs(plugin_root: Path) -> tuple[list[Path], list[Path]]:
    component_dirs: list[Path] = []
    entity_dirs: list[Path] = []
    for sub in SUBSYSTEMS:
        component_dirs.append(plugin_root / sub / "components")
        entity_dirs.append(plugin_root / sub / "entities")
    return component_dirs, entity_dirs


def _instance_roots(plugin_root: Path, extra: list[Path]) -> list[Path]:
    """Roots under which to scan for entity-instance yamls.

    Default: `examples/` if present (post-v1 pipeline samples).
    Extra roots can be passed on the CLI for the tests / consumer projects.
    """
    roots: list[Path] = []
    examples = plugin_root / "examples"
    if examples.exists():
        roots.append(examples)
    roots.extend(extra)
    return roots


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the agent-glue kit for consistency.")
    parser.add_argument(
        "--plugin-root",
        type=Path,
        default=PLUGIN_ROOT,
        help="Plugin root directory (default: this script's parent's parent).",
    )
    parser.add_argument(
        "--instances",
        type=Path,
        action="append",
        default=[],
        help="Additional roots under which to scan for entity-instance yamls (repeatable).",
    )
    args = parser.parse_args(argv)

    plugin_root: Path = args.plugin_root
    component_dirs, entity_dirs = _kit_dirs(plugin_root)

    try:
        catalog = load_catalog(component_dirs, entity_dirs)
    except LoaderError as exc:
        print(f"kit failed to load: {exc}", file=sys.stderr)
        return 2

    instances = []
    skip_dirs = []
    for sub in SUBSYSTEMS:
        skip_dirs.append(plugin_root / sub / "components")
        skip_dirs.append(plugin_root / sub / "entities")
    for root in _instance_roots(plugin_root, args.instances):
        try:
            instances.extend(load_instances(root, skip=skip_dirs))
        except LoaderError as exc:
            print(f"instances failed to load under {root}: {exc}", file=sys.stderr)
            return 2

    errors = validate_all(catalog, instances)
    if errors:
        print(f"agent-glue kit is inconsistent ({len(errors)} error(s)):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(
        f"agent-glue kit OK: {len(catalog.component_schemas)} components, "
        f"{len(catalog.entity_types)} entity types, {len(instances)} instances."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
