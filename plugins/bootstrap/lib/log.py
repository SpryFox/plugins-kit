"""File-based logging for bootstrap operations."""

import os
from datetime import datetime, timezone
from typing import List


LOG_FILENAME = "bootstrap.log"
MAX_LOG_LINES = 500


def write_session_header(data_dir: str) -> None:
    """Write a session separator line to bootstrap.log.

    Called once at the start of each engine run so sessions are visually
    distinct when tailing the log across multiple Claude Code startups.

    Args:
        data_dir: Directory containing the log file
    """
    os.makedirs(data_dir, exist_ok=True)
    log_file = os.path.join(data_dir, LOG_FILENAME)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(log_file, "a") as f:
        f.write(f"--- Session {timestamp} ---\n")
    _trim_log(log_file)


def write_log(data_dir: str, entries: List[str]) -> None:
    """Append timestamped log entries to bootstrap.log.

    Args:
        data_dir: Directory containing the log file
        entries: List of log messages to append
    """
    os.makedirs(data_dir, exist_ok=True)
    log_file = os.path.join(data_dir, LOG_FILENAME)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = []
    for entry in entries:
        lines.append(f"[{timestamp}] {entry}\n")

    # Append to log
    with open(log_file, "a") as f:
        f.writelines(lines)

    # Trim if too long
    _trim_log(log_file)


def _trim_log(log_file: str) -> None:
    """Keep only the last MAX_LOG_LINES lines."""
    try:
        with open(log_file, "r") as f:
            all_lines = f.readlines()
        if len(all_lines) > MAX_LOG_LINES:
            with open(log_file, "w") as f:
                f.writelines(all_lines[-MAX_LOG_LINES:])
    except (FileNotFoundError, PermissionError):
        pass
