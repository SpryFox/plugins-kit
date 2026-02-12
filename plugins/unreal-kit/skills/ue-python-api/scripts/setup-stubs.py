#!/usr/bin/env python3
"""
Download Unreal Engine Python API stubs for offline reference.

Downloads the 'unreal-stub' package from PyPI and extracts the unreal.py stub
file into the skill's stubs/ directory. No project venv required.

Usage:
    python setup-stubs.py
    python setup-stubs.py --from-project "C:/path/to/UEProject"
"""

import argparse
import io
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError
except ImportError:
    print("ERROR: urllib not available", file=sys.stderr)
    sys.exit(1)

SKILL_DIR = Path(__file__).resolve().parent.parent
STUBS_DIR = SKILL_DIR / "stubs"
PYPI_PACKAGE = "unreal-stub"
PYPI_JSON_URL = f"https://pypi.org/pypi/{PYPI_PACKAGE}/json"


def get_latest_wheel_url():
    """Query PyPI for the latest wheel URL of unreal-stub."""
    print(f"Querying PyPI for {PYPI_PACKAGE}...")
    try:
        import json
        req = Request(PYPI_JSON_URL, headers={"Accept": "application/json"})
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        version = data["info"]["version"]
        print(f"Latest version: {version}")

        # Find wheel or sdist
        for entry in data["urls"]:
            if entry["packagetype"] == "bdist_wheel":
                return entry["url"], version
        # Fallback to sdist
        for entry in data["urls"]:
            if entry["packagetype"] == "sdist":
                return entry["url"], version

        print("ERROR: No downloadable distribution found", file=sys.stderr)
        return None, version
    except (URLError, Exception) as e:
        print(f"ERROR: Failed to query PyPI: {e}", file=sys.stderr)
        return None, None


def download_and_extract_wheel(url):
    """Download a wheel and extract unreal.py from it."""
    print(f"Downloading {url}...")
    try:
        with urlopen(url, timeout=120) as resp:
            wheel_bytes = resp.read()
        print(f"Downloaded {len(wheel_bytes) / 1024 / 1024:.1f} MB")
    except (URLError, Exception) as e:
        print(f"ERROR: Download failed: {e}", file=sys.stderr)
        return False

    # Wheel is a zip file
    try:
        with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as zf:
            # Find all .py/.pyi files and pick the largest (the actual stub)
            # The package has unreal/__init__.py (tiny) and unreal/unreal.py (the real stub)
            py_files = [n for n in zf.namelist() if n.endswith(('.py', '.pyi'))]
            if not py_files:
                print("ERROR: No Python files found in wheel", file=sys.stderr)
                return False

            # Sort by size descending — the stub is the largest file by far
            sizes = [(n, zf.getinfo(n).file_size) for n in py_files]
            sizes.sort(key=lambda x: x[1], reverse=True)
            print(f"Files in wheel: {[(n, s) for n, s in sizes]}")

            # Pick the largest file as the stub
            candidate = sizes[0][0]
            if sizes[0][1] < 1000:
                print(f"WARNING: Largest file is only {sizes[0][1]} bytes — may not be the real stub")

            STUBS_DIR.mkdir(parents=True, exist_ok=True)
            target = STUBS_DIR / "unreal.py"
            print(f"Extracting {candidate} -> {target}")
            with zf.open(candidate) as src, open(target, 'wb') as dst:
                dst.write(src.read())
            size_mb = target.stat().st_size / 1024 / 1024
            print(f"Extracted: {target} ({size_mb:.1f} MB)")
            return True

    except zipfile.BadZipFile:
        # Maybe it's an sdist (tar.gz)
        print("Not a wheel, trying as sdist...")
        return download_and_extract_sdist(wheel_bytes)

    return False


def download_and_extract_sdist(archive_bytes):
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
                print("ERROR: No stub file found in sdist", file=sys.stderr)
                return False

            STUBS_DIR.mkdir(parents=True, exist_ok=True)
            target = STUBS_DIR / "unreal.py"
            with tf.extractfile(candidates[0]) as src:
                with open(target, 'wb') as dst:
                    dst.write(src.read())
            size_mb = target.stat().st_size / 1024 / 1024
            print(f"Extracted: {target} ({size_mb:.1f} MB)")
            return True
    except Exception as e:
        print(f"ERROR: Failed to extract sdist: {e}", file=sys.stderr)
        return False


def copy_from_project(project_path):
    """Copy the generated stub from a UE project's Intermediate directory."""
    project = Path(project_path)
    stub = project / "Intermediate" / "PythonStub" / "unreal.py"

    if not stub.exists():
        print(f"ERROR: Stub not found at {stub}", file=sys.stderr)
        print("Make sure Developer Mode is enabled in Editor Preferences → Plugins → Python")
        print("and you've restarted the editor at least once.")
        return False

    STUBS_DIR.mkdir(parents=True, exist_ok=True)
    target = STUBS_DIR / "unreal.py"
    shutil.copy2(stub, target)
    size_mb = target.stat().st_size / 1024 / 1024
    print(f"Copied project stub: {target} ({size_mb:.1f} MB)")
    print("NOTE: This stub includes project-specific types — more complete than the generic PyPI stub.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Download UE Python API stubs")
    parser.add_argument("--from-project", type=str,
                       help="Copy stub from a UE project's Intermediate/PythonStub/ instead of PyPI")
    args = parser.parse_args()

    if args.from_project:
        success = copy_from_project(args.from_project)
    else:
        url, version = get_latest_wheel_url()
        if not url:
            print("\nFallback: You can copy the stub from your UE project instead:")
            print(f'  python "{__file__}" --from-project "C:/path/to/YourProject"')
            sys.exit(1)
        success = download_and_extract_wheel(url)

    if success:
        stubs_file = STUBS_DIR / "unreal.py"
        print(f"\nStubs ready at: {stubs_file}")
        print(f"Search with: grep -i 'pattern' \"{stubs_file}\"")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
