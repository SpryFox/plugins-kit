#!/usr/bin/env python3
"""Setup script for unreal-kit config management.

Stdlib-only — works even if the venv is broken.

Modes:
  --check --data-dir <path>              Exit 0 if config valid, 1 if needs setup
  --describe --data-dir <path>           Print field descriptions as YAML
  --apply --data-dir <path> --set K=V    Write config values
  --init-defaults --data-dir <path> --source <path>  Auto-detect from CWD, fallback to template

Per-project config lives at <project_root>/.claude/unreal-kit.yaml.
The --data-dir config is a mirror used by the bootstrap engine for variable resolution.

Exit codes: 0=success, 1=needs setup, 2=error
"""

import json
import os
import sys

PROJECT_CONFIG_NAME = ".claude/unreal-kit.yaml"

# --- Config schema (single source of truth) ---

REQUIRED_FIELDS = {
    "engine_dir": {
        "description": "Path to UE Engine directory (contains Binaries/, Content/, etc.)",
        "default": "",
        "example": "C:/Program Files/Epic Games/UE_5.5/Engine",
    },
    "uproject": {
        "description": "Path to the .uproject file for your game project",
        "default": "",
        "example": "D:/Projects/MyGame/MyGame.uproject",
    },
}


# --- Minimal YAML reader (hand-rolled, stdlib only) ---

def read_config(config_path):
    """Read simple key: "value" YAML into a dict."""
    result = {}
    if not os.path.isfile(config_path):
        return result
    with open(config_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            # Strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            result[key] = value
    return result


def write_config(config_path, data):
    """Write a dict as simple key: "value" YAML."""
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        for key, value in data.items():
            # Use forward slashes — backslashes in YAML break parsing
            safe_value = str(value).replace("\\", "/")
            f.write(f'{key}: "{safe_value}"\n')


# --- Auto-detection ---

def _auto_detect():
    """Try to find uproject and engine_dir from CWD.

    Returns (engine_dir, uproject) or (None, None) if not found.
    Imports ue_discovery from the skill's lib/ directory.
    """
    # Find lib/ relative to this script: scripts/ -> ../lib/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.join(script_dir, "..", "lib")
    lib_dir = os.path.normpath(lib_dir)

    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)

    try:
        from ue_discovery import find_uproject_from_cwd, find_engine_dir
    except ImportError:
        return None, None

    uproject = find_uproject_from_cwd()
    if not uproject:
        return None, None

    engine_dir = find_engine_dir(uproject)
    return (str(engine_dir) if engine_dir else None, str(uproject))


# --- Mode handlers ---

def do_check(data_dir):
    """Check if config exists and has all required fields with non-empty values."""
    config_path = os.path.join(data_dir, "config.yaml")
    config = read_config(config_path)

    missing = []
    for field in REQUIRED_FIELDS:
        if field not in config or not config[field]:
            missing.append(field)

    if not missing:
        return 0

    # Output missing fields as JSON for the bootstrap script to parse
    print(json.dumps({
        "status": "needs_setup",
        "missing_fields": missing,
        "config_path": config_path,
    }))
    return 1


def do_describe(data_dir):
    """Print field descriptions with current values."""
    config_path = os.path.join(data_dir, "config.yaml")
    current = read_config(config_path)

    print("# unreal-kit configuration fields")
    print(f"# Config location: {config_path}")
    print()
    for field, info in REQUIRED_FIELDS.items():
        current_val = current.get(field, "(not set)")
        print(f"{field}:")
        print(f'  description: "{info["description"]}"')
        print(f'  default: "{info["default"]}"')
        print(f'  example: "{info["example"]}"')
        print(f'  current: "{current_val}"')
    return 0


def do_apply(data_dir, set_args):
    """Validate and write config values."""
    config_path = os.path.join(data_dir, "config.yaml")

    # Parse KEY=VALUE pairs
    values = {}
    for arg in set_args:
        if "=" not in arg:
            print(f"Error: Invalid --set argument (expected KEY=VALUE): {arg}", file=sys.stderr)
            return 2
        key, _, value = arg.partition("=")
        key = key.strip()
        value = value.strip()
        if key not in REQUIRED_FIELDS:
            print(f"Error: Unknown field: {key}", file=sys.stderr)
            print(f"Valid fields: {', '.join(REQUIRED_FIELDS.keys())}", file=sys.stderr)
            return 2
        values[key] = value

    if not values:
        print("Error: No --set arguments provided", file=sys.stderr)
        return 2

    # Merge with existing config
    existing = read_config(config_path)
    existing.update(values)
    write_config(config_path, existing)

    # Also write per-project config if uproject is known
    uproject = existing.get("uproject")
    if uproject and os.path.isfile(uproject):
        try:
            _write_per_project_config(uproject, existing)
        except OSError:
            pass  # Non-fatal

    print(json.dumps({
        "status": "ok",
        "config_path": config_path,
        "fields_written": list(values.keys()),
    }))
    return 0


def _write_per_project_config(uproject, data):
    """Write per-project config to <project_root>/.claude/unreal-kit.yaml."""
    from pathlib import Path
    project_root = Path(uproject).parent
    config_path = project_root / PROJECT_CONFIG_NAME
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        for key, value in data.items():
            safe_value = str(value).replace("\\", "/")
            f.write(f'{key}: "{safe_value}"\n')
    return str(config_path)


def do_init_defaults(data_dir, source_path):
    """Auto-detect from CWD, falling back to template copy.

    Unlike test-plugin which just copies defaults, this tries CWD-based
    auto-detection first so config is created silently when Claude Code
    is launched from a project root. Also writes per-project config at
    <project_root>/.claude/unreal-kit.yaml.
    """
    config_path = os.path.join(data_dir, "config.yaml")

    # Try auto-detection from CWD
    engine_dir, uproject = _auto_detect()
    if engine_dir and uproject:
        data = {"engine_dir": engine_dir, "uproject": uproject}
        write_config(config_path, data)
        _write_per_project_config(uproject, data)
        print(json.dumps({
            "status": "ok",
            "config_path": config_path,
            "source": "auto_detected",
            "engine_dir": engine_dir,
            "uproject": uproject,
        }))
        return 0

    # Auto-detect found uproject but no engine dir — still write what we have
    if uproject:
        data = {"engine_dir": "", "uproject": uproject}
        write_config(config_path, data)
        _write_per_project_config(uproject, {"uproject": uproject})
        print(json.dumps({
            "status": "partial",
            "config_path": config_path,
            "source": "auto_detected",
            "uproject": uproject,
            "missing": ["engine_dir"],
        }))
        return 1

    # Fall back to copying template
    source_config = os.path.join(source_path, "config.yaml")
    if not os.path.isfile(source_config):
        print(f"Error: Source config not found: {source_config}", file=sys.stderr)
        return 2

    config = read_config(source_config)
    write_config(config_path, config)

    print(json.dumps({
        "status": "needs_setup",
        "config_path": config_path,
        "source": "template",
        "fields_initialized": list(config.keys()),
    }))
    return 1


# --- CLI entry point ---

def main():
    args = sys.argv[1:]

    # Parse arguments
    mode = None
    data_dir = None
    source_path = None
    set_args = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--check", "--describe", "--apply", "--init-defaults"):
            mode = arg.lstrip("-").replace("-", "_")
        elif arg == "--data-dir" and i + 1 < len(args):
            i += 1
            data_dir = args[i]
        elif arg == "--source" and i + 1 < len(args):
            i += 1
            source_path = args[i]
        elif arg == "--set" and i + 1 < len(args):
            i += 1
            set_args.append(args[i])
        else:
            print(f"Error: Unknown argument: {arg}", file=sys.stderr)
            return 2
        i += 1

    if not mode:
        print("Error: No mode specified (--check, --describe, --apply, --init-defaults)", file=sys.stderr)
        return 2

    if not data_dir:
        print("Error: --data-dir is required", file=sys.stderr)
        return 2

    if mode == "check":
        return do_check(data_dir)
    elif mode == "describe":
        return do_describe(data_dir)
    elif mode == "apply":
        return do_apply(data_dir, set_args)
    elif mode == "init_defaults":
        if not source_path:
            print("Error: --source is required for --init-defaults", file=sys.stderr)
            return 2
        return do_init_defaults(data_dir, source_path)
    else:
        print(f"Error: Unknown mode: {mode}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
