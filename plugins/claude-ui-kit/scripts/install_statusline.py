"""Bootstrap script: install claude-ui-kit's default statusLine into settings.json.

Behavior:
- If no statusLine is configured in any settings.json layer, install ours.
  The target is the project's .claude/settings.local.json (per-user,
  gitignored/p4ignored — safe in source-controlled projects). If there is
  no project context, fall back to ~/.claude/settings.json.
- If the existing statusLine is already claude-ui-kit's (matches our path
  prefix), refresh it to point at the current installed location. This handles
  plugin upgrades and reinstalls transparently.
- If the existing statusLine is something else, leave it alone and surface a
  fix-all message asking the user to type "replace my status line" if they
  want to switch.

The script is idempotent: re-running on every SessionStart is a no-op once
installed.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional, Tuple


PLUGIN_NAME = "claude-ui-kit"
INSTALLED_SCRIPT_RELPATH = "scripts/statusline.sh"
CUSTOMIZED_FLAG = "customized.flag"


def install(ctx) -> None:
    # The /statusline skill writes this marker when the user customizes, so the
    # install script stays quiet on subsequent SessionStarts instead of nagging
    # about a "conflicting" statusLine the user intentionally chose.
    if (Path(ctx.data_dir) / CUSTOMIZED_FLAG).exists():
        ctx.log("statusline: user customized (skipping)")
        return

    installed_script = _resolve_installed_script(ctx.data_dir)
    if installed_script is None:
        ctx.log("statusline: FAILED - synced script not found at "
                f"{Path(ctx.data_dir) / INSTALLED_SCRIPT_RELPATH}")
        return

    expected_command = _posix(installed_script)

    # Use the engine's canonical project_dir (Claude Code's launch CWD).
    # Never walk up looking for .claude/ — Claude Code itself does not, so any
    # parent .claude/ we'd find is a directory Claude Code never reads. Older
    # versions of this script walked up and silently wrote into the wrong file
    # (and worse, created stray .claude/ dirs that polluted sibling projects).
    project_dir_str = getattr(ctx, "project_dir", None)
    project_root = Path(project_dir_str).resolve() if project_dir_str else None

    # Search layers from highest to lowest precedence so the user-visible
    # statusLine is the one we compare against.
    candidate_paths = []
    if project_root is not None:
        candidate_paths.append(project_root / ".claude" / "settings.local.json")
        candidate_paths.append(project_root / ".claude" / "settings.json")
    candidate_paths.append(Path.home() / ".claude" / "settings.json")

    existing = _find_existing_statusline(candidate_paths)

    if existing is None:
        # Target settings.local.json in projects (per-user, not source-controlled);
        # ~/.claude/settings.json otherwise.
        target = (project_root / ".claude" / "settings.local.json"
                  if project_root is not None
                  else Path.home() / ".claude" / "settings.json")
        _write_statusline(target, expected_command)
        ctx.log(f"statusline: installed to {_posix(target)}")
        return

    settings_path, current_command = existing

    if current_command == expected_command:
        ctx.log("statusline: already installed (no-op)")
        return

    if _is_ours(current_command):
        # Plugin path moved (upgrade, version bump, scope change). Refresh.
        _write_statusline(settings_path, expected_command)
        ctx.log(f"statusline: refreshed path in {_posix(settings_path)}")
        return

    # User has a custom statusLine. Don't touch it without explicit consent.
    ctx.add_failure(
        "statusline_conflict",
        settings_path=_posix(settings_path),
        existing_command=current_command,
        new_command=expected_command,
        user_msg=(
            f"claude-ui-kit found an existing statusLine in "
            f"{_posix(settings_path)} and will not overwrite it. To switch "
            f"to claude-ui-kit's default, type 'replace my status line'."
        ),
        agent_msg=(
            f"The user has a custom statusLine configured in "
            f"{_posix(settings_path)} with command: {current_command}\n"
            f"DO NOT modify it. If and only if the user explicitly says "
            f"'replace my status line' (or clearly equivalent intent), "
            f"update {_posix(settings_path)} so that "
            f"statusLine.command = {expected_command} (keep "
            f"statusLine.type = 'command'). Otherwise, leave it alone and "
            f"explain that claude-ui-kit is installed but not active because "
            f"a custom statusLine takes precedence."
        ),
    )


def _resolve_installed_script(data_dir: str) -> Optional[Path]:
    p = Path(data_dir) / INSTALLED_SCRIPT_RELPATH
    return p if p.is_file() else None


def _find_existing_statusline(paths) -> Optional[Tuple[Path, str]]:
    """Return (path, command) of the highest-precedence layer with a statusLine."""
    for path in paths:
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        sl = data.get("statusLine")
        if isinstance(sl, dict) and isinstance(sl.get("command"), str):
            return path, sl["command"]
    return None


def _is_ours(command: str) -> bool:
    return f"/{PLUGIN_NAME}/" in command.replace("\\", "/")


def _write_statusline(settings_path: Path, command: str) -> None:
    data = _load_json(settings_path) or {}
    if not isinstance(data, dict):
        data = {}
    data["statusLine"] = {"type": "command", "command": command}
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _posix(p: Path) -> str:
    return str(p).replace("\\", "/")
