"""Custom bootstrap script for unreal-kit.

Two entry points:
- autodetect(): Discovers .uproject and engine_dir from CWD (no-arg, returns dict | None)
- bootstrap(ctx): Copies project-specific stubs if available (upgrade from PyPI stubs)
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def autodetect() -> Optional[Dict[str, str]]:
    """Discover .uproject and engine_dir from CWD.

    Returns dict of discovered field values, or None if no project found.
    Called by the engine's project_config primitive (no arguments).
    """
    skill_lib = os.path.join(os.path.dirname(__file__), "lib")
    if skill_lib not in sys.path:
        sys.path.insert(0, skill_lib)

    from ue_discovery import find_uproject_files, find_engine_dir

    # Search CWD only (no walk-up) — autodetect runs from the project root,
    # so walking up would find unrelated .uproject files in parent dirs.
    found = find_uproject_files(Path.cwd().resolve(), max_depth=2)
    uproject = found[0] if found else None
    if not uproject:
        return None

    result: Dict[str, str] = {"uproject": str(uproject)}
    engine = find_engine_dir(uproject)
    if engine:
        result["engine_dir"] = str(engine)
    return result


def bootstrap(ctx: Any) -> None:
    """Post-manifest bootstrap: copy project-specific stubs if available.

    If the UE project has Developer Mode enabled and has generated stubs
    (Intermediate/PythonStub/unreal.py), copy those over the PyPI generic
    stubs since they include project-specific types.
    """
    uproject = ctx.config.get("uproject")
    if not uproject:
        return

    project_dir = Path(uproject).parent
    project_stub = project_dir / "Intermediate" / "PythonStub" / "unreal.py"

    if not project_stub.is_file():
        return

    # Target is where PyPI stubs get extracted
    target = Path(ctx.plugin_root) / "skills" / "ue-python-api" / "stubs" / "unreal.py"

    # Only upgrade if project stub is larger (more complete)
    if target.is_file() and project_stub.stat().st_size <= target.stat().st_size:
        return

    import shutil
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(project_stub, target)
    ctx.log(f"stubs: upgraded to project-specific stubs ({project_stub.stat().st_size / 1024:.0f} KB)")
