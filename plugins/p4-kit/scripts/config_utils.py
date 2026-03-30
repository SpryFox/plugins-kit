"""Shared config utilities for p4-kit scripts.

Stdlib-only — works even if the venv is broken.
"""

import os


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
