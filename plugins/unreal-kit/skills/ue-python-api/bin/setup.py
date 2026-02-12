#!/usr/bin/env python3
"""
UE Python API — One-shot setup script.

Auto-discovers the UE project, configures paths, enables editor settings,
and downloads API stubs. No user input required.

Usage:
    python setup.py                  # Full setup
    python setup.py --refresh-stubs  # Re-copy stubs from project (after editor restart)

Dependencies: Python stdlib only (no pip packages).
"""

import io
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SKILL_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = SKILL_DIR / "lib"
STUBS_DIR = SKILL_DIR / "stubs"
STATUS_FILE = SKILL_DIR / "setup-status.yaml"

# Add lib/ to import path
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from ue_discovery import find_engine_dir, find_uproject_from_skill
from ue_ini import read_ini_bool, write_ini_setting

# Config path (matches ue_runner_config.py)
LOCAL_CONFIG_PATH = Path.home() / ".claude" / ".local-data" / "skills" / "ue-python-api" / "project.yaml"

INI_SECTION = "[/Script/PythonScriptPlugin.PythonScriptPluginSettings]"

PYPI_PACKAGE = "unreal-stub"
PYPI_JSON_URL = f"https://pypi.org/pypi/{PYPI_PACKAGE}/json"


# ---------------------------------------------------------------------------
# Step 1-2: Discover project and engine
# ---------------------------------------------------------------------------

def discover_project() -> tuple[Path | None, Path | None]:
    """Find the .uproject and engine directory from the skill's location."""
    print("[setup] Discovering UE project...")

    uproject = find_uproject_from_skill(SKILL_DIR)
    if not uproject:
        print("[setup] ERROR: No .uproject file found walking up from skill directory.")
        print(f"[setup]   Searched from: {SKILL_DIR}")
        return None, None

    print(f"[setup]   OK  uproject: {uproject}")

    engine_dir = find_engine_dir(uproject)
    if not engine_dir:
        print(f"[setup]   WARN  Could not find Engine/ directory relative to {uproject}")
        print(f"[setup]         (Looked for Engine/Binaries/Win64/UnrealEditor-Cmd.exe)")
    else:
        print(f"[setup]   OK  engine:   {engine_dir}")

    return uproject, engine_dir


# ---------------------------------------------------------------------------
# Step 3: Write project.yaml
# ---------------------------------------------------------------------------

def write_project_config(uproject: Path, engine_dir: Path | None) -> Path | None:
    """Write project.yaml for the runner config system."""
    config_path = LOCAL_CONFIG_PATH

    # Build YAML content with simple string formatting (no pyyaml needed)
    # Use forward slashes — backslashes in YAML double-quoted strings
    # are escape sequences and break pyyaml parsing on Windows.
    lines = []
    if engine_dir:
        lines.append(f'engine_dir: "{str(engine_dir).replace(chr(92), "/")}"')
    lines.append(f'uproject: "{str(uproject).replace(chr(92), "/")}"')

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[setup]   WROTE {config_path}")
    return config_path


# ---------------------------------------------------------------------------
# Step 4-5: Enable editor settings in UserEngine.ini
# ---------------------------------------------------------------------------

def configure_editor_settings(uproject: Path) -> list[str]:
    """Enable bRemoteExecution and bIsDeveloperMode in UserEngine.ini."""
    project_dir = uproject.parent
    default_ini = project_dir / "Config" / "DefaultEngine.ini"
    user_ini = project_dir / "Config" / "UserEngine.ini"

    settings = [
        ("bRemoteExecution", "Enables remote script execution from terminal"),
        ("bIsDeveloperMode", "Enables Python API stub generation"),
    ]

    written = []

    for key, description in settings:
        default_value = read_ini_bool(default_ini, INI_SECTION, key)
        user_value = read_ini_bool(user_ini, INI_SECTION, key)
        effective = user_value if user_value is not None else default_value

        if effective is True:
            source = "UserEngine.ini" if user_value is True else "DefaultEngine.ini"
            print(f"[setup]   OK  {key}=True (from {source})")
        else:
            write_ini_setting(user_ini, INI_SECTION, key, "True")
            print(f"[setup]   WROTE {key}=True to {user_ini}")
            print(f"[setup]         ({description})")
            written.append(key)

    return written


# ---------------------------------------------------------------------------
# Step 6: Download stubs from PyPI
# ---------------------------------------------------------------------------

def download_stubs_from_pypi() -> bool:
    """Download the unreal-stub package from PyPI and extract the stub file."""
    print("[setup] Downloading API stubs from PyPI...")

    # Get latest wheel URL
    try:
        req = Request(PYPI_JSON_URL, headers={"Accept": "application/json"})
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, Exception) as e:
        print(f"[setup]   WARN  Could not query PyPI: {e}")
        print("[setup]         Stubs can be set up later. See references/project-setup.md")
        return False

    version = data["info"]["version"]
    print(f"[setup]   Found version: {version}")

    # Find wheel URL
    wheel_url = None
    for entry in data["urls"]:
        if entry["packagetype"] == "bdist_wheel":
            wheel_url = entry["url"]
            break
    if not wheel_url:
        for entry in data["urls"]:
            if entry["packagetype"] == "sdist":
                wheel_url = entry["url"]
                break

    if not wheel_url:
        print("[setup]   WARN  No downloadable distribution found on PyPI")
        return False

    # Download
    try:
        with urlopen(wheel_url, timeout=120) as resp:
            archive_bytes = resp.read()
        size_mb = len(archive_bytes) / 1024 / 1024
        print(f"[setup]   Downloaded {size_mb:.1f} MB")
    except (URLError, Exception) as e:
        print(f"[setup]   WARN  Download failed: {e}")
        return False

    # Extract from wheel (zip format)
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
            py_files = [n for n in zf.namelist() if n.endswith(('.py', '.pyi'))]
            if not py_files:
                print("[setup]   WARN  No Python files found in package")
                return False

            # Pick the largest file — the real stub
            sizes = [(n, zf.getinfo(n).file_size) for n in py_files]
            sizes.sort(key=lambda x: x[1], reverse=True)
            candidate = sizes[0][0]

            STUBS_DIR.mkdir(parents=True, exist_ok=True)
            target = STUBS_DIR / "unreal.py"
            with zf.open(candidate) as src, open(target, 'wb') as dst:
                dst.write(src.read())

            stub_mb = target.stat().st_size / 1024 / 1024
            print(f"[setup]   OK  Stubs: {target} ({stub_mb:.1f} MB)")
            return True

    except zipfile.BadZipFile:
        # Try as sdist (tar.gz)
        return _extract_sdist(archive_bytes)


def _extract_sdist(archive_bytes: bytes) -> bool:
    """Extract unreal.py from a tar.gz sdist."""
    import tarfile
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode='r:gz') as tf:
            candidates = [m for m in tf.getmembers()
                         if m.name.endswith('unreal.py') or m.name.endswith('unreal.pyi')]
            if not candidates:
                py_files = [m for m in tf.getmembers() if m.name.endswith(('.py', '.pyi'))]
                if py_files:
                    py_files.sort(key=lambda m: m.size, reverse=True)
                    candidates = [py_files[0]]

            if not candidates:
                print("[setup]   WARN  No stub file found in package")
                return False

            STUBS_DIR.mkdir(parents=True, exist_ok=True)
            target = STUBS_DIR / "unreal.py"
            with tf.extractfile(candidates[0]) as src:
                with open(target, 'wb') as dst:
                    dst.write(src.read())
            stub_mb = target.stat().st_size / 1024 / 1024
            print(f"[setup]   OK  Stubs: {target} ({stub_mb:.1f} MB)")
            return True
    except Exception as e:
        print(f"[setup]   WARN  Failed to extract stubs: {e}")
        return False


def refresh_stubs_from_project(uproject: Path) -> bool:
    """Copy project-generated stubs (more complete, includes project-specific types)."""
    stub_source = uproject.parent / "Intermediate" / "PythonStub" / "unreal.py"
    if not stub_source.exists():
        print(f"[setup]   WARN  Project stubs not found at {stub_source}")
        print("[setup]         Make sure bIsDeveloperMode is enabled and the editor has been restarted.")
        return False

    STUBS_DIR.mkdir(parents=True, exist_ok=True)
    target = STUBS_DIR / "unreal.py"
    shutil.copy2(stub_source, target)
    stub_mb = target.stat().st_size / 1024 / 1024
    print(f"[setup]   OK  Project stubs: {target} ({stub_mb:.1f} MB)")
    print("[setup]         (Includes project-specific types — more complete than PyPI stubs)")
    return True


# ---------------------------------------------------------------------------
# Step 7: Write status marker
# ---------------------------------------------------------------------------

def write_status(
    uproject: Path,
    engine_dir: Path | None,
    stubs_source: str,
    settings_written: list[str],
):
    """Write setup-status.yaml as a success marker."""
    timestamp = datetime.now(timezone.utc).isoformat()

    lines = [
        f'status: complete',
        f'timestamp: "{timestamp}"',
        f'uproject: "{str(uproject).replace(chr(92), "/")}"',
    ]
    if engine_dir:
        lines.append(f'engine_dir: "{str(engine_dir).replace(chr(92), "/")}"')
    lines.append(f'stubs: {stubs_source}')

    if settings_written:
        lines.append("settings_written:")
        for s in settings_written:
            lines.append(f"  - {s}")

    STATUS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[setup]   WROTE {STATUS_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_setup(refresh_stubs: bool = False) -> bool:
    """Run the full setup sequence. Returns True if all steps succeeded."""
    print()
    print("=" * 60)
    print("  UE Python API — Setup")
    print("=" * 60)
    print()

    # Discover project
    uproject, engine_dir = discover_project()
    if not uproject:
        return False

    if refresh_stubs:
        # Just refresh stubs from the project and update status
        print()
        ok = refresh_stubs_from_project(uproject)
        if ok:
            write_status(uproject, engine_dir, "project", [])
        return ok

    # Write project config
    print()
    print("[setup] Writing project config...")
    write_project_config(uproject, engine_dir)

    # Configure editor settings
    print()
    print("[setup] Checking editor settings...")
    settings_written = configure_editor_settings(uproject)

    # Download stubs
    print()
    stubs_source = "none"
    # Prefer project stubs if they exist already
    project_stubs = uproject.parent / "Intermediate" / "PythonStub" / "unreal.py"
    if project_stubs.exists():
        if refresh_stubs_from_project(uproject):
            stubs_source = "project"
    if stubs_source == "none":
        if download_stubs_from_pypi():
            stubs_source = "pypi"

    # Write status marker
    print()
    print("[setup] Writing status marker...")
    write_status(uproject, engine_dir, stubs_source, settings_written)

    # Summary
    print()
    print("=" * 60)
    print("  Setup complete!")
    print("=" * 60)
    print()
    if settings_written:
        print("  ACTION REQUIRED: Restart UE Editor for these settings to take effect:")
        for s in settings_written:
            print(f"    - {s}")
        print()
        print("  After restarting, optionally run with --refresh-stubs to get")
        print("  project-specific stubs (more complete than generic PyPI stubs).")
    elif stubs_source == "pypi":
        print("  TIP: Run with --refresh-stubs after an editor restart to get")
        print("  project-specific stubs (more complete than generic PyPI stubs).")
    print()

    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="UE Python API — Setup")
    parser.add_argument(
        "--refresh-stubs", action="store_true",
        help="Re-copy stubs from the project (after editor restart with Developer Mode)",
    )
    args = parser.parse_args()

    ok = run_setup(refresh_stubs=args.refresh_stubs)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
