"""OS and architecture detection for bootstrap operations."""

import platform
import sys


def detect_os() -> str:
    """Detect the current operating system.

    Returns one of: "macos", "windows", "ubuntu"
    """
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    elif system == "linux":
        # Check for Ubuntu specifically, fall back to generic linux
        try:
            with open("/etc/os-release") as f:
                content = f.read().lower()
                if "ubuntu" in content:
                    return "ubuntu"
        except (FileNotFoundError, PermissionError):
            pass
        return "ubuntu"  # Default Linux to ubuntu for install commands
    else:
        return system


def detect_arch() -> str:
    """Detect the current CPU architecture.

    Returns one of: "amd64" (x86_64), "arm64" (aarch64), or platform.machine()
    lowercased for less-common values. Normalizes Intel/Apple/Linux naming
    differences so download-recipe keys can be a single canonical token.
    """
    m = platform.machine().lower()
    if m in ("amd64", "x86_64", "x64"):
        return "amd64"
    if m in ("arm64", "aarch64"):
        return "arm64"
    return m


def detect_os_arch() -> str:
    """Convenience: 'macos-arm64', 'windows-amd64', etc."""
    return f"{detect_os()}-{detect_arch()}"
