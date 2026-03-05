"""PyPI package download and extraction for bootstrap manifests.

Downloads a wheel from PyPI and extracts a specific file. Uses stdlib only
(urllib + zipfile). No pip required.
"""

import fnmatch
import io
import json
import zipfile
from pathlib import Path
from typing import NamedTuple, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


class PypiCheckResult(NamedTuple):
    passed: bool
    package: str
    message: str


def check_pypi_package(
    package: str,
    extract_to: str,
) -> PypiCheckResult:
    """Check if the extracted file already exists.

    Args:
        package: PyPI package name
        extract_to: Target path for the extracted file

    Returns:
        PypiCheckResult with pass/fail
    """
    target = Path(extract_to)
    if target.is_file():
        return PypiCheckResult(
            passed=True, package=package,
            message=f"exists at {extract_to}",
        )
    return PypiCheckResult(
        passed=False, package=package,
        message="not found, needs download",
    )


def download_and_extract(
    package: str,
    extract_to: str,
    extract_pattern: Optional[str] = None,
) -> PypiCheckResult:
    """Download a wheel from PyPI and extract a file.

    Args:
        package: PyPI package name
        extract_to: Target path for the extracted file
        extract_pattern: Optional glob pattern to match files in the wheel
            (e.g. "*.py"). If None, extracts the largest .py/.pyi file.

    Returns:
        PypiCheckResult with pass/fail and descriptive message
    """
    # Query PyPI for latest wheel URL
    url = _get_wheel_url(package)
    if url is None:
        return PypiCheckResult(
            passed=False, package=package,
            message="failed to find wheel on PyPI",
        )

    # Download the wheel
    try:
        req = Request(url, headers={"User-Agent": "plugins-kit-bootstrap/1.0"})
        with urlopen(req, timeout=120) as resp:
            wheel_bytes = resp.read()
    except (URLError, OSError) as e:
        return PypiCheckResult(
            passed=False, package=package,
            message=f"download failed: {e}",
        )

    # Extract file from wheel
    try:
        with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as zf:
            if extract_pattern:
                py_files = [n for n in zf.namelist()
                            if fnmatch.fnmatch(Path(n).name, extract_pattern)]
            else:
                py_files = [n for n in zf.namelist() if n.endswith((".py", ".pyi"))]
            if not py_files:
                return PypiCheckResult(
                    passed=False, package=package,
                    message="no Python files found in wheel",
                )

            # Pick the largest file
            sizes = [(n, zf.getinfo(n).file_size) for n in py_files]
            sizes.sort(key=lambda x: x[1], reverse=True)
            candidate = sizes[0][0]

            target = Path(extract_to)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(candidate) as src, open(target, "wb") as dst:
                dst.write(src.read())

            size_kb = target.stat().st_size / 1024
            return PypiCheckResult(
                passed=True, package=package,
                message=f"extracted {candidate} ({size_kb:.0f} KB)",
            )
    except zipfile.BadZipFile:
        return PypiCheckResult(
            passed=False, package=package,
            message="downloaded file is not a valid wheel/zip",
        )


def _get_wheel_url(package: str) -> Optional[str]:
    """Query PyPI JSON API for the latest wheel URL."""
    pypi_url = f"https://pypi.org/pypi/{package}/json"
    try:
        req = Request(pypi_url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())

        # Prefer wheel over sdist
        for entry in data.get("urls", []):
            if entry.get("packagetype") == "bdist_wheel":
                return entry["url"]
        for entry in data.get("urls", []):
            if entry.get("packagetype") == "sdist":
                return entry["url"]
    except Exception:
        pass
    return None
