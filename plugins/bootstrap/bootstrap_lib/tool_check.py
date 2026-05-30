"""Tool installation verification."""

import os
import shutil
import subprocess
import sys
from typing import NamedTuple, Optional


class CheckResult(NamedTuple):
    name: str
    passed: bool
    message: str
    install_cmd: Optional[str] = None
    path: Optional[str] = None  # absolute path to the resolved binary, when passed=True


def check_tool(name: str, install_cmds: Optional[dict] = None, current_os: Optional[str] = None, install_path: Optional[str] = None) -> CheckResult:
    """Check if a CLI tool is installed via shutil.which() or install_path.

    Args:
        name: Tool name (e.g. "uv", "git")
        install_cmds: Platform-keyed install commands (e.g. {"macos": "brew install git"})
        current_os: Current OS string from detect_os()
        install_path: Directory where the tool binary lives (supports ~ expansion).
                      Checked before falling back to shutil.which().

    Returns:
        CheckResult with pass/fail and optional install command
    """
    # Check install_path first (covers tools not yet in PATH)
    if install_path:
        expanded = os.path.expanduser(install_path)
        candidates = [os.path.join(expanded, name)]
        if sys.platform == "win32" or "MSYSTEM" in os.environ:
            candidates.append(os.path.join(expanded, name + ".exe"))
        for candidate in candidates:
            if os.path.isfile(candidate):
                return CheckResult(
                    name=name,
                    passed=True,
                    message=f"found at {candidate}",
                    path=candidate,
                )

    path = shutil.which(name)
    if path:
        return CheckResult(
            name=name,
            passed=True,
            message=f"found at {path}",
            path=path,
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

    On Windows, explicitly uses bash (from Git for Windows) so that install
    commands can use Unix syntax ($HOME, &&, curl pipes, etc.) regardless of
    whether Claude Code was launched from PowerShell or cmd.

    Returns:
        (success, output) — success=True if returncode==0
    """
    try:
        if sys.platform == "win32" or "MSYSTEM" in os.environ:
            bash = shutil.which("bash")
            if bash:
                result = subprocess.run(
                    [bash, "-c", install_cmd],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            else:
                result = subprocess.run(
                    install_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
        else:
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
