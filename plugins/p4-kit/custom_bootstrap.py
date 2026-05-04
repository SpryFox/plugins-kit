"""Autodetect entry point for p4-kit bootstrap.

autodetect() — discovers P4PORT/P4USER from `p4 set` or env vars.
Called by the engine's project_config primitive (no arguments).
Returns dict of discovered values, or None if nothing found.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

# Restore registry-canonical PATH before shelling out to p4 — see
# lib/path_repair.py for the cmd.exe overflow failure mode this guards.
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from path_repair import repair_path  # noqa: E402
repair_path()


_P4_ANNOTATION = re.compile(r"\s*\([^)]*\)\s*$")


def _strip_annotation(value: str) -> str:
    """Strip trailing `p4 set` source annotations like `(set)`, `(config '...')`, `(enviro)`."""
    return _P4_ANNOTATION.sub("", value).strip()


def autodetect() -> Optional[Dict[str, str]]:
    result: Dict[str, str] = {}

    try:
        proc = subprocess.run(
            ["p4", "set"], capture_output=True, text=True, timeout=5
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                for field in ("P4PORT", "P4USER"):
                    if line.startswith(f"{field}="):
                        value = _strip_annotation(line.split("=", 1)[1])
                        if value:
                            result[field] = value
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    for field in ("P4PORT", "P4USER"):
        if field not in result:
            env_val = os.environ.get(field)
            if env_val:
                result[field] = env_val

    return result if result else None
