#!/usr/bin/env python3
"""Setup script for local-review-kit config management.

Stdlib-only — works even if the venv is broken.

Modes:
  --check --data-dir <path>              Exit 0 if config valid, 1 if needs setup
  --describe --data-dir <path>           Print field descriptions as YAML
  --apply --data-dir <path> --set K=V    Write config values
  --init-defaults --data-dir <path> --source <path>  Copy template config

Exit codes: 0=success, 1=needs setup, 2=error
"""

import json
import os
import sys


# --- Config schema (single source of truth) ---
# "none" is a valid value for API keys — means the user explicitly
# declined to provide one.  Empty string means "not yet configured".

REQUIRED_FIELDS = {
    "OPENAI_API_KEY": {
        "description": "OpenAI API key for OpenAI-based agents (set 'none' if not used)",
        "default": "",
        "example": "sk-...",
    },
    "OPENROUTER_API_KEY": {
        "description": "OpenRouter API key for OpenRouter-based agents (set 'none' if not used)",
        "default": "",
        "example": "sk-or-...",
    },
    "P4PORT": {
        "description": "Perforce server address",
        "default": "",
        "example": "ssl:perforce.example.com:1666",
    },
    "P4USER": {
        "description": "Perforce username",
        "default": "",
        "example": "jdoe",
    },
    "DEFAULT_AGENT": {
        "description": "Default agent for reviews",
        "default": "claude-opus",
        "example": "claude-haiku",
    },
}

# Fields where "none" is a valid explicit value (meaning: user has no key)
NONE_ALLOWED_FIELDS = {"OPENAI_API_KEY", "OPENROUTER_API_KEY"}


def _is_set(value):
    """True if a field has been explicitly configured (non-empty, including 'none')."""
    return bool(value)


def _has_real_key(value):
    """True if a field has a real API key (non-empty and not 'none')."""
    return bool(value) and value.lower() != "none"


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
            f.write(f'{key}: "{value}"\n')


# --- Mode handlers ---

def do_check(data_dir):
    """Check if config exists and has all required fields."""
    config_path = os.path.join(data_dir, "config.yaml")
    config = read_config(config_path)

    missing = []
    for field in REQUIRED_FIELDS:
        value = config.get(field, "")
        if not _is_set(value):
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
    """Print field descriptions."""
    config_path = os.path.join(data_dir, "config.yaml")
    current = read_config(config_path)

    print("# local-review-kit configuration fields")
    print(f"# Config location: {config_path}")
    print()
    for field, info in REQUIRED_FIELDS.items():
        current_val = current.get(field, "(not set)")
        print(f"{field}:")
        print(f"  description: \"{info['description']}\"")
        print(f"  default: \"{info['default']}\"")
        print(f"  example: \"{info['example']}\"")
        print(f"  current: \"{current_val}\"")
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

    print(json.dumps({
        "status": "ok",
        "config_path": config_path,
        "fields_written": list(values.keys()),
    }))
    return 0


def do_init_defaults(data_dir, source_path):
    """Copy template config from source to data dir."""
    config_path = os.path.join(data_dir, "config.yaml")
    source_config = os.path.join(source_path, "config.yaml")

    if not os.path.isfile(source_config):
        print(f"Error: Source config not found: {source_config}", file=sys.stderr)
        return 2

    # Read source and write to data dir
    config = read_config(source_config)
    write_config(config_path, config)

    print(json.dumps({
        "status": "ok",
        "config_path": config_path,
        "fields_initialized": list(config.keys()),
    }))
    return 0


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
