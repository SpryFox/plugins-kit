"""Custom bootstrap script for unreal-kit.

Two entry points:
- autodetect(config, config_path): Discovers .uproject and engine_dir from CWD
- bootstrap(ctx): Copies project-specific stubs if available (upgrade from PyPI stubs)
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict


def autodetect(config: Dict[str, Any], config_path: str) -> bool:
    """Discover .uproject and engine_dir from CWD.

    Uses ue_discovery.py from the unreal-kit skill. Returns True if any
    config values were updated.
    """
    # Add ue_discovery to path
    skill_lib = os.path.join(
        os.path.dirname(__file__), "skills", "ue-python-api", "lib"
    )
    if skill_lib not in sys.path:
        sys.path.insert(0, skill_lib)

    from ue_discovery import find_uproject_from_cwd, find_engine_dir

    changed = False

    if not config.get("uproject"):
        uproject = find_uproject_from_cwd()
        if uproject:
            config["uproject"] = str(uproject)
            changed = True

    if not config.get("engine_dir") and config.get("uproject"):
        uproject_path = Path(config["uproject"])
        if uproject_path.is_file():
            engine = find_engine_dir(uproject_path)
            if engine:
                config["engine_dir"] = str(engine)
                changed = True

    return changed


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
