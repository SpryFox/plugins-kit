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
