"""OS detection for bootstrap operations."""

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
