"""
UE .ini file read/write utilities.

Used by both setup.py and ue_runner.py. Pure stdlib, no external dependencies.
"""

from pathlib import Path


def read_ini_bool(ini_path: Path, section: str, key: str) -> bool | None:
    """Read a boolean value from a UE .ini file. Returns None if not found."""
    if not ini_path.is_file():
        return None
    in_section = False
    with open(ini_path, "r") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("["):
                in_section = stripped == section
                continue
            if in_section and "=" in stripped:
                k, _, v = stripped.partition("=")
                if k.strip() == key:
                    return v.strip().lower() in ("true", "1")
    return None


def write_ini_setting(ini_path: Path, section: str, key: str, value: str):
    """Write a setting to a UE config file (creates file and parent dirs if needed)."""
    lines = []
    if ini_path.is_file():
        with open(ini_path, "r") as f:
            lines = f.readlines()

    # Try to find and update existing key in the target section
    in_section = False
    section_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("["):
            in_section = stripped == section
            if in_section:
                section_idx = i
            continue
        if in_section and "=" in stripped:
            k, _, _ = stripped.partition("=")
            if k.strip() == key:
                lines[i] = f"{key}={value}\n"
                ini_path.parent.mkdir(parents=True, exist_ok=True)
                with open(ini_path, "w") as f:
                    f.writelines(lines)
                return

    # Key not found — append to section or create section
    if section_idx is not None:
        lines.insert(section_idx + 1, f"{key}={value}\n")
    else:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(f"{section}\n")
        lines.append(f"{key}={value}\n")

    ini_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ini_path, "w") as f:
        f.writelines(lines)
