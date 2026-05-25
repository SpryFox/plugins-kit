"""Pre-commit consistency hook.

Loads the kit's component schemas + entity-type defs and every example
pipeline's instance yamls, then runs `validate_all`. Exits 1 on any error so
the commit is rejected; exits 0 otherwise.

Usage:
    python scripts/precommit_consistency.py [--plugin-root PATH] [--examples-root PATH]

Defaults assume the script is run from the plugin root.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _resolve_lib_on_path() -> None:
    here = Path(__file__).resolve().parent
    plugin_root = here.parent
    sys.path.insert(0, str(plugin_root))


_resolve_lib_on_path()


from agent_glue_lib import (  # noqa: E402
    load_instances,
    load_kit,
    validate_all,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plugin-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Path to the agent-glue plugin root.",
    )
    parser.add_argument(
        "--examples-root",
        default=None,
        help="Optional path to the examples/ directory; every *.yaml under it "
        "is considered for instance loading.",
    )
    args = parser.parse_args(argv)

    plugin_root = Path(args.plugin_root)
    catalog = load_kit(plugin_root)

    examples_root = (
        Path(args.examples_root)
        if args.examples_root is not None
        else plugin_root / "examples"
    )
    if examples_root.exists():
        catalog.entities = load_instances(examples_root)

    errors = validate_all(catalog)
    if errors:
        sys.stderr.write(
            f"agent-glue: pre-commit consistency check failed with "
            f"{len(errors)} error(s):\n"
        )
        for msg in errors:
            sys.stderr.write(f"  - {msg}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
