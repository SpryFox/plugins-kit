#!/usr/bin/env python3
import json
import os
import sys

plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
if not plugin_root:
    print("Running <unknown>@<unknown> (CLAUDE_PLUGIN_ROOT unset)", file=sys.stderr)
    sys.exit(0)

manifest_path = os.path.join(plugin_root, ".claude-plugin", "plugin.json")
try:
    with open(manifest_path, "r", encoding="utf-8") as f:
        d = json.load(f)
except OSError as exc:
    print(f"Running <unknown>@<unknown> (cannot read {manifest_path}: {exc})")
    sys.exit(0)

print(f"Running {d.get('name', '<unnamed>')}@{d.get('version', '<unversioned>')}")

# Soft bootstrap-provisioning check. Never exit -- the banner above must always
# print. Kept stdlib-only since this script runs under a bare/uv interpreter.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from bootstrap_guard import is_provisioned

    if not is_provisioned("skills-kit"):
        print(
            "[skills-kit] bootstrap has not provisioned skills-kit -- schema "
            "validation and helper scripts are unavailable. Install/enable the "
            "'plugins-kit:bootstrap' plugin and start a new session.",
            file=sys.stderr,
        )
except Exception:
    pass
