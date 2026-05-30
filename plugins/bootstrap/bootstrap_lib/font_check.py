"""Per-user font detection and installation for the bootstrap engine.

Bootstrap can ensure a font (e.g. a Nerd Font for statusline glyphs) is present
without ever needing administrator rights. Every supported platform has an
unprivileged per-user font location, so this runs cleanly inside the
non-interactive SessionStart hook — no UAC prompt, no `sudo`:

  Windows : %LOCALAPPDATA%\\Microsoft\\Windows\\Fonts  + HKCU font registration
  macOS   : ~/Library/Fonts
  Linux   : ~/.local/share/fonts                        + fc-cache refresh

Detection scans both the per-user and system font directories so a font the
user already installed by any means is recognised and never re-downloaded.

Stdlib-only. The actual archive fetch/extract lives in downloader.py; this
module owns the OS-specific "where do fonts live and how are they registered"
knowledge.
"""

import fnmatch
import os
import subprocess
import sys
from typing import List, NamedTuple, Optional


class FontCheckResult(NamedTuple):
    passed: bool
    matched: Optional[str]   # basename of the matching font file, if found
    message: str


class FontInstallResult(NamedTuple):
    ok: bool
    files: List[str]         # absolute paths of installed font files
    message: str


def user_font_dir() -> str:
    """The per-user (unprivileged) font install directory for this OS."""
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        return os.path.join(local, "Microsoft", "Windows", "Fonts")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Fonts")
    return os.path.expanduser("~/.local/share/fonts")


def _scan_dirs() -> List[str]:
    """All directories to scan when deciding whether a font is already present
    (per-user install dir first, then system locations)."""
    dirs = [user_font_dir()]
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR")
        if windir:
            dirs.append(os.path.join(windir, "Fonts"))
    elif sys.platform == "darwin":
        dirs.append("/Library/Fonts")
        dirs.append("/System/Library/Fonts")
    else:
        dirs.append("/usr/share/fonts")
        dirs.append("/usr/local/share/fonts")
    return dirs


def find_installed_font(match: str) -> Optional[str]:
    """Return the basename of the first installed font file matching `match`
    (a case-insensitive glob, e.g. ``*JetBrainsMono*NerdFont*``), or None.

    Matching is done on the file basename, recursively, since system font
    trees (notably on Linux) nest fonts in per-family subdirectories.
    """
    pattern = match.lower()
    for d in _scan_dirs():
        if not os.path.isdir(d):
            continue
        try:
            for root, _dirs, files in os.walk(d):
                for fname in files:
                    if fnmatch.fnmatch(fname.lower(), pattern):
                        return fname
        except OSError:
            continue
    return None


def check_font(match: str) -> FontCheckResult:
    """Detect whether a font matching `match` is installed."""
    found = find_installed_font(match)
    if found:
        return FontCheckResult(True, found, f"found {found}")
    return FontCheckResult(False, None, f"no font matching {match!r}")


def _register_fonts_windows(paths: List[str]) -> None:
    """Register per-user fonts so Windows (and apps like Windows Terminal)
    enumerate them. Per-user fonts are recorded under HKCU with their full
    path; placing the file in the Fonts dir alone is not enough — Windows
    discovers fonts via the registry, not by scanning the directory.

    Best-effort: any failure is swallowed (the file copy already happened, and
    a later session can retry). Also calls AddFontResourceW so already-running
    processes can pick the font up without a reboot.
    """
    import winreg  # noqa: PLC0415 — Windows-only, imported lazily

    key_path = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"
    try:
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
    except OSError:
        key = None
    try:
        for path in paths:
            stem, ext = os.path.splitext(os.path.basename(path))
            kind = "OpenType" if ext.lower() == ".otf" else "TrueType"
            value_name = f"{stem} ({kind})"
            if key is not None:
                try:
                    winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, path)
                except OSError:
                    pass
            try:
                import ctypes  # noqa: PLC0415
                ctypes.windll.gdi32.AddFontResourceW(path)
            except Exception:
                pass
    finally:
        if key is not None:
            try:
                winreg.CloseKey(key)
            except OSError:
                pass
    # Notify running apps that the font table changed (best-effort).
    try:
        import ctypes  # noqa: PLC0415
        HWND_BROADCAST = 0xFFFF
        WM_FONTCHANGE = 0x001D
        SMTO_ABORTIFHUNG = 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_FONTCHANGE, 0, 0, SMTO_ABORTIFHUNG, 1000, None
        )
    except Exception:
        pass


def _refresh_font_cache_linux() -> None:
    """Refresh the fontconfig cache so newly-copied fonts are resolvable.
    Best-effort: silently skipped if fc-cache isn't on PATH."""
    import shutil  # noqa: PLC0415
    fc = shutil.which("fc-cache")
    if not fc:
        return
    try:
        subprocess.run([fc, "-f", user_font_dir()], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def register_fonts(paths: List[str]) -> None:
    """Make freshly-installed font files usable by the OS / applications.

    Windows needs explicit HKCU registration; Linux needs an fc-cache refresh;
    macOS needs nothing beyond the file living in ~/Library/Fonts.
    """
    if not paths:
        return
    if sys.platform == "win32":
        _register_fonts_windows(paths)
    elif sys.platform != "darwin":
        _refresh_font_cache_linux()


def install_font(
    url: str,
    sha256: str,
    *,
    archive_type: Optional[str] = None,
) -> FontInstallResult:
    """Download a font archive, extract its faces into the per-user font dir,
    and register them. Unprivileged on every platform.
    """
    from .downloader import download_fonts  # lazy: avoid import cycle

    dest = user_font_dir()
    result = download_fonts(url, sha256, dest, archive_type=archive_type)
    if not result.ok:
        return FontInstallResult(False, [], result.message)

    register_fonts(result.files)
    return FontInstallResult(True, result.files, f"installed {len(result.files)} files to {dest}")
