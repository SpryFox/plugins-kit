"""Autodetect entry point for p4-kit bootstrap.

autodetect() — discovers P4PORT/P4USER from `p4 set` or env vars.
Called by the engine's project_config primitive (no arguments).
Returns dict of discovered values, or None if nothing found.
"""

import os
import subprocess
from typing import Dict, Optional


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
                        value = line.split("=", 1)[1].strip()
                        if " (set)" in value:
                            value = value.rsplit(" (set)", 1)[0]
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
