"""
UE project discovery — find .uproject files and engine directories.

Used by both setup.py and ue_runner.py. Pure stdlib, no external dependencies.
"""

import json
from pathlib import Path


def find_uproject_files(root: Path, max_depth: int = 4) -> list[Path]:
    """Find .uproject files under root, limited to max_depth."""
    results = []
    if not root.is_dir():
        return results

    def _walk(directory: Path, depth: int):
        if depth > max_depth:
            return
        try:
            for entry in directory.iterdir():
                if entry.is_file() and entry.suffix == ".uproject":
                    if is_game_project(entry):
                        results.append(entry)
                elif entry.is_dir() and not entry.name.startswith("."):
                    _walk(entry, depth + 1)
        except PermissionError:
            pass

    _walk(root, 0)
    results.sort(key=lambda p: len(p.parts))
    return results


def is_game_project(uproject: Path) -> bool:
    """Check if a .uproject file is a real game project (has a Modules array)."""
    try:
        data = json.loads(uproject.read_text(encoding="utf-8"))
        return bool(data.get("Modules"))
    except Exception:
        return False


def find_engine_dir(uproject: Path) -> Path | None:
    """Find the Engine/ directory by walking up from the .uproject location.

    Looks for Engine/Binaries/Win64/UnrealEditor-Cmd.exe to confirm it's valid.
    """
    current = uproject.parent
    for _ in range(5):
        engine_candidate = current / "Engine"
        exe = engine_candidate / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"
        if exe.is_file():
            return engine_candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def find_uproject_from_cwd() -> Path | None:
    """Find the nearest .uproject file by searching CWD and its parents.

    Used when the skill lives in the plugin cache (not inside the project tree),
    so walking up from the skill directory won't reach the project. Instead,
    searches from CWD — which is the project root when Claude Code is launched
    from there.
    """
    current = Path.cwd().resolve()
    for _ in range(6):  # safety limit
        found = find_uproject_files(current, max_depth=2)
        if found:
            return found[0]
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def find_uproject_from_skill(skill_dir: Path) -> Path | None:
    """Walk up from the skill directory to find the nearest .uproject file.

    The skill lives at <project>/.claude/skills/ue-python-api/, so walking
    up should find the project's .uproject within a few levels. At each level,
    searches up to 2 levels deep (the .uproject may be in a subdirectory).
    """
    current = skill_dir.resolve()
    for _ in range(10):  # safety limit
        # Search this directory and its immediate children for .uproject files
        found = find_uproject_files(current, max_depth=2)
        if found:
            return found[0]  # sorted by path length — nearest first

        parent = current.parent
        if parent == current:
            break
        current = parent
    return None
