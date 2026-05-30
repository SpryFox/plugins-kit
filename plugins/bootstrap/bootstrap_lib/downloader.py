"""Download bootstrap-managed tool binaries into ~/.local/bin.

Phase 2 of the tool-resolution redesign (see
docs/planning/bootstrap/tool-resolution-redesign.md). The engine calls
download_and_install() when a tool entry has a `download` block; the
result is an absolute path on disk in a location bootstrap controls.

Stdlib-only. urllib for fetch, hashlib for verification, zipfile/tarfile
for archive extraction.
"""

import hashlib
import os
import shutil
import stat
import sys
import tarfile
import tempfile
import zipfile
from typing import NamedTuple, Optional
from urllib.request import urlopen


class DownloadResult(NamedTuple):
    ok: bool
    path: Optional[str]   # absolute path to the installed binary on success
    message: str          # human-readable status/error


def install_dir():
    """The canonical install directory for bootstrap-managed binaries."""
    return os.path.expanduser("~/.local/bin")


def _detect_archive_type(url: str, explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit
    lower = url.lower().split("?", 1)[0]
    if lower.endswith(".zip"):
        return "zip"
    if lower.endswith((".tar.gz", ".tgz")):
        return "tar.gz"
    if lower.endswith((".tar.xz", ".txz")):
        return "tar.xz"
    if lower.endswith(".tar"):
        return "tar"
    return None  # treat as a raw single-file download


def _fetch(url: str, dest_path: str) -> str:
    """Stream `url` to `dest_path`, returning the hex sha256 of the bytes."""
    h = hashlib.sha256()
    with urlopen(url) as resp, open(dest_path, "wb") as out:
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            h.update(chunk)
            out.write(chunk)
    return h.hexdigest()


def _extract_from_archive(archive_path: str, archive_type: str, inner_path: str, dest_path: str):
    """Extract a single file `inner_path` from the archive to `dest_path`."""
    if archive_type == "zip":
        with zipfile.ZipFile(archive_path) as z:
            with z.open(inner_path) as src, open(dest_path, "wb") as out:
                shutil.copyfileobj(src, out)
        return
    if archive_type in ("tar", "tar.gz", "tar.xz"):
        mode = {
            "tar":    "r:",
            "tar.gz": "r:gz",
            "tar.xz": "r:xz",
        }[archive_type]
        with tarfile.open(archive_path, mode) as t:
            member = t.getmember(inner_path)
            extracted = t.extractfile(member)
            if extracted is None:
                raise ValueError(f"{inner_path!r} in archive is not a regular file")
            with extracted as src, open(dest_path, "wb") as out:
                shutil.copyfileobj(src, out)
        return
    raise ValueError(f"unsupported archive type: {archive_type!r}")


def _make_executable(path: str):
    if sys.platform == "win32":
        return  # Windows executable bit is implicit from extension
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def download_and_install(
    tool_name: str,
    url: str,
    sha256: str,
    *,
    binary_name: Optional[str] = None,
    archive_path: Optional[str] = None,
    archive_type: Optional[str] = None,
    target_dir: Optional[str] = None,
) -> DownloadResult:
    """Fetch `url`, verify sha256, install the binary at <target_dir>/<binary_name>.

    Single-file downloads: omit `archive_path`. The fetched bytes ARE the binary.
    Archive downloads: pass `archive_path` (path inside the archive). `archive_type`
    autodetects from the URL extension when omitted.

    On success: returns (ok=True, path=<absolute path on disk>, message=...).
    On failure: returns (ok=False, path=None, message=<reason>). Never raises
    for "expected" failures (network, hash mismatch, missing inner path);
    re-raises only for genuine internals (programmer errors).
    """
    bin_dir = target_dir or install_dir()
    os.makedirs(bin_dir, exist_ok=True)

    final_name = binary_name or tool_name
    if sys.platform == "win32" and not final_name.lower().endswith(".exe"):
        final_name += ".exe"
    final_path = os.path.join(bin_dir, final_name)

    detected_type = _detect_archive_type(url, archive_type)
    is_archive = bool(archive_path) or detected_type is not None

    with tempfile.TemporaryDirectory(prefix="bootstrap-dl-") as tmp:
        download_path = os.path.join(tmp, "download.bin")
        try:
            actual_hash = _fetch(url, download_path)
        except Exception as e:
            return DownloadResult(False, None, f"fetch failed: {e}")

        if actual_hash.lower() != sha256.lower():
            return DownloadResult(
                False, None,
                f"sha256 mismatch: expected {sha256}, got {actual_hash}",
            )

        # Stage to a temp path next to the final destination so the rename
        # into place is atomic.
        staged = os.path.join(tmp, final_name)
        try:
            if is_archive:
                if not archive_path:
                    return DownloadResult(
                        False, None,
                        "download is an archive but no archive_path supplied",
                    )
                if detected_type is None:
                    return DownloadResult(
                        False, None,
                        "archive_path supplied but archive_type couldn't be detected from URL",
                    )
                _extract_from_archive(download_path, detected_type, archive_path, staged)
            else:
                shutil.copyfile(download_path, staged)
        except Exception as e:
            return DownloadResult(False, None, f"extract failed: {e}")

        _make_executable(staged)

        try:
            os.replace(staged, final_path)
        except OSError as e:
            return DownloadResult(False, None, f"install to {final_path} failed: {e}")

    return DownloadResult(True, final_path, f"installed at {final_path}")
