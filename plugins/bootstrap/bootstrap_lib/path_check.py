"""PATH entry verification and persistent remediation."""

import os
import sys
from typing import NamedTuple, Tuple


class CheckResult(NamedTuple):
    path: str
    passed: bool
    message: str


def check_path_entry(path_entry: str) -> CheckResult:
    """Check if a directory is present in PATH.

    Args:
        path_entry: Directory path to check (supports ~ expansion)

    Returns:
        CheckResult with pass/fail
    """
    expanded = os.path.expanduser(path_entry)
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)

    # Normalize for comparison
    expanded_norm = os.path.normpath(expanded)
    for d in path_dirs:
        if os.path.normpath(d) == expanded_norm:
            return CheckResult(
                path=path_entry,
                passed=True,
                message=f"{path_entry} is in PATH",
            )

    return CheckResult(
        path=path_entry,
        passed=False,
        message=f"{path_entry} ({expanded}) is not in PATH",
    )


def add_path_to_shell_config(path_entry: str) -> Tuple[bool, str]:
    """Persistently add a path entry to shell RC files and Windows User PATH.

    Appends `export PATH="<path>:$PATH"` to the appropriate RC file(s).
    On Windows, also writes to the Windows User PATH (registry) so the entry
    is visible to all new processes regardless of shell.
    Idempotent: skips files/registry where the path is already declared.

    Returns:
        (success, message) tuple
    """
    expanded = os.path.expanduser(path_entry)

    # On Windows, write to the User PATH registry key (affects all new processes)
    registry_msg = ""
    if sys.platform == "win32" or "MSYSTEM" in os.environ:
        _reg_ok, registry_msg = _add_path_to_windows_registry(path_entry)

    # Build portable export line using $HOME where possible
    home = os.path.expanduser("~")
    if expanded.startswith(home):
        path_expr = '"$HOME' + expanded[len(home):] + ':$PATH"'
    else:
        path_expr = f'"{expanded}:$PATH"'
    export_line = f'export PATH={path_expr}'

    # Determine RC files by platform
    if sys.platform == "darwin":
        rc_files = [os.path.expanduser("~/.zshrc"), os.path.expanduser("~/.bashrc")]
    else:
        # Linux and Windows (Git Bash)
        rc_files = [os.path.expanduser("~/.bashrc")]

    written = []
    for rc_file in rc_files:
        try:
            if os.path.exists(rc_file):
                content = open(rc_file).read()
                # Skip if already declared (check both expanded and unexpanded forms)
                if expanded in content or path_entry in content:
                    continue
            with open(rc_file, "a") as f:
                f.write(f'\n# Added by bootstrap\n{export_line}\n')
            written.append(os.path.basename(rc_file))
        except OSError:
            pass

    parts = []
    if written:
        parts.append(f"added to {', '.join(written)}")
    if registry_msg:
        parts.append(registry_msg)
    if parts:
        return True, "; ".join(parts)
    return True, "already declared in shell config"


def _add_path_to_windows_registry(path_entry: str) -> Tuple[bool, str]:
    """Add a path entry to the Windows User PATH (HKCU\\Environment).

    Uses PowerShell's [Environment]::SetEnvironmentVariable with 'User' scope.
    Reads from 'User' scope only (not $env:Path which merges system+user).
    Does NOT use setx (truncates at 1024 chars).

    Returns:
        (success, message) tuple
    """
    import subprocess

    # The registry is global state — it ignores HOME/USERPROFILE redirection,
    # so tests that point HOME at a tmp dir would otherwise leak permanent
    # entries into the real user's PATH. Tests set this var to opt out.
    if os.environ.get("BOOTSTRAP_SKIP_REGISTRY"):
        return True, "skipped Windows registry write (BOOTSTRAP_SKIP_REGISTRY set)"

    expanded = os.path.expanduser(path_entry)
    # Convert Unix-style path to Windows-style for the registry
    win_path = expanded.replace("/", "\\")

    ps_script = (
        "$entry = '" + win_path + "'\n"
        "$current = [Environment]::GetEnvironmentVariable('Path', 'User')\n"
        "if (-not $current) { $current = '' }\n"
        "$parts = $current -split ';' | Where-Object { $_ -ne '' }\n"
        "$norm = $entry.TrimEnd('\\\\')\n"
        "$found = $false\n"
        "foreach ($p in $parts) {\n"
        "  if ($p.TrimEnd('\\\\') -ieq $norm) { $found = $true; break }\n"
        "}\n"
        "if (-not $found) {\n"
        "  $newPath = ($entry + ';' + $current).TrimEnd(';')\n"
        "  [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')\n"
        "  Write-Output 'added'\n"
        "} else {\n"
        "  Write-Output 'already_present'\n"
        "}\n"
    )

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output == "added":
                return True, f"added {win_path} to Windows User PATH (registry)"
            elif output == "already_present":
                return True, f"{win_path} already in Windows User PATH"
        return False, f"powershell exit {result.returncode}: {result.stderr.strip()}"
    except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
        return False, f"failed to write Windows User PATH: {e}"
