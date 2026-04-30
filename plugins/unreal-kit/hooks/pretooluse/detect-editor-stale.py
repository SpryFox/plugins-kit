#!/usr/bin/env python3
"""Background detector for unreal-kit editor staleness.

Reads the PreToolUse hook JSON from stdin (for cwd), reads
${cwd}/.claude/unreal-kit.yaml for engine_dir, compares
UnrealEditor-BuildSettings.dll mtime vs Engine/Build/Build.version mtime, and
writes or removes the marker file accordingly.

Latency is not foreground-critical: this runs detached after the PreToolUse
hook has already returned. The marker it writes is consumed by subsequent
PreToolUse invocations.

Defensive: any failure to locate the config or referenced files results in a
no-op (preserves prior marker state). The hook is advisory, not safety-critical.
"""
import json
import os
import sys


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


def main() -> int:
    if len(sys.argv) < 2:
        return 0
    marker = sys.argv[1]

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    cwd = payload.get("cwd")
    if not cwd:
        return 0

    engine_dir = read_engine_dir(os.path.join(cwd, ".claude", "unreal-kit.yaml"))
    if not engine_dir:
        return 0

    dll = os.path.join(engine_dir, "Binaries", "Win64", "UnrealEditor-BuildSettings.dll")
    version_file = os.path.join(engine_dir, "Build", "Build.version")
    if not os.path.isfile(dll) or not os.path.isfile(version_file):
        return 0

    is_stale = os.path.getmtime(dll) < os.path.getmtime(version_file)

    os.makedirs(os.path.dirname(marker), exist_ok=True)
    if is_stale:
        with open(marker, "a"):
            pass
        os.utime(marker, None)
    elif os.path.isfile(marker):
        try:
            os.remove(marker)
        except OSError:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
