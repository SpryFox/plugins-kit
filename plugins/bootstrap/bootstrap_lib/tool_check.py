"""Tool installation verification."""

import shutil
import subprocess
from typing import NamedTuple, Optional


class CheckResult(NamedTuple):
    name: str
    passed: bool
    message: str
    install_cmd: Optional[str] = None


def check_tool(name: str, install_cmds: Optional[dict] = None, current_os: Optional[str] = None) -> CheckResult:
    """Check if a CLI tool is installed via shutil.which().

    Args:
        name: Tool name (e.g. "uv", "git")
        install_cmds: Platform-keyed install commands (e.g. {"macos": "brew install git"})
        current_os: Current OS string from detect_os()

    Returns:
        CheckResult with pass/fail and optional install command
    """
    path = shutil.which(name)
    if path:
        return CheckResult(
            name=name,
            passed=True,
            message=f"found at {path}",
        )

    install_cmd = None
    if install_cmds and current_os:
        install_cmd = install_cmds.get(current_os)

    return CheckResult(
        name=name,
        passed=False,
        message=f"not found in PATH",
        install_cmd=install_cmd,
    )


def run_install(install_cmd: str) -> tuple[bool, str]:
    """Run a platform-specific install command.

    Returns:
        (success, output) — success=True if returncode==0
    """
    try:
        result = subprocess.run(
            install_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "install timed out after 120s"
    except Exception as e:
        return False, str(e)
