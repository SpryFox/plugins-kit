"""PATH entry verification."""

import os
from typing import NamedTuple


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
