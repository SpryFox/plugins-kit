"""Autodetect entry point for local-review-kit bootstrap."""

import os
import subprocess


def autodetect(config, config_path):
    """Try to auto-detect P4 settings. Returns True if config was changed."""
    changed = False

    # Try p4 set for P4PORT and P4USER
    if not config.get("P4PORT") or not config.get("P4USER"):
        try:
            result = subprocess.run(
                ["p4", "set"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    for field in ("P4PORT", "P4USER"):
                        if line.startswith(f"{field}=") and not config.get(field):
                            value = line.split("=", 1)[1].strip()
                            if " (set)" in value:
                                value = value.rsplit(" (set)", 1)[0]
                            if value:
                                config[field] = value
                                changed = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Try environment variables as fallback
    for field in ("P4PORT", "P4USER"):
        if not config.get(field):
            env_val = os.environ.get(field)
            if env_val:
                config[field] = env_val
                changed = True

    return changed
