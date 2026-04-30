#!/usr/bin/env python3
"""Background detector for unreal-kit editor staleness.

Reads the PreToolUse hook JSON from stdin (for cwd), reads
${cwd}/.claude/unreal-kit.yaml for engine_dir, compares
UnrealEditor-BuildSettings.dll mtime vs Engine/Build/Build.version mtime, and
writes or removes the per-project marker plus the claude-ui-kit system message.

Marker path:  <cwd>/.local-data/unreal-kit/editor-stale.flag
System msg:   <cwd>/.local-data/claude-ui-kit/systemmessage.unreal-kit.txt

Latency is not foreground-critical: this runs detached after the PreToolUse
hook has already returned. The marker it writes is consumed by subsequent
PreToolUse invocations.

Defensive: any failure to locate the config or referenced files results in a
no-op (preserves prior marker state). The hook is advisory, not safety-critical.
"""
import json
import os
import sys

SYSMSG_TEXT = "Editor needs rebuild"


def read_engine_dir(config_path: str) -> str | None:
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("engine_dir:"):
                    value = line[len("engine_dir:"):].strip()
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    return value or None
    except OSError:
        return None
    return None


def _touch(path: str, content: str | None = None) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if content is None:
        with open(path, "a"):
            pass
        os.utime(path, None)
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def _remove(path: str) -> None:
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    cwd = payload.get("cwd")
    if not cwd:
        return 0

    marker = os.path.join(cwd, ".local-data", "unreal-kit", "editor-stale.flag")
    sysmsg = os.path.join(cwd, ".local-data", "claude-ui-kit", "systemmessage.unreal-kit.txt")

    engine_dir = read_engine_dir(os.path.join(cwd, ".claude", "unreal-kit.yaml"))
    if not engine_dir:
        return 0

    dll = os.path.join(engine_dir, "Binaries", "Win64", "UnrealEditor-BuildSettings.dll")
    version_file = os.path.join(engine_dir, "Build", "Build.version")
    if not os.path.isfile(dll) or not os.path.isfile(version_file):
        return 0

    is_stale = os.path.getmtime(dll) < os.path.getmtime(version_file)

    if is_stale:
        _touch(marker)
        _touch(sysmsg, SYSMSG_TEXT)
    else:
        _remove(marker)
        _remove(sysmsg)

    return 0


if __name__ == "__main__":
    sys.exit(main())
