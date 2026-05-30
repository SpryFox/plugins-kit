#!/usr/bin/env python3
"""Regenerate .claude-plugin/marketplace.json from per-plugin plugin.json files.

Marketplace.json is treated as derived data:
- Top-level fields ($schema, name, description, owner) are preserved verbatim.
- The plugins[] array is rebuilt from plugins/<name>/.claude-plugin/plugin.json,
  filtered by the "published" field (missing = true; false = excluded).

Existing plugin ordering in marketplace.json is preserved; new plugins (newly
"published": true) are appended alphabetically.

Usage:
  python scripts/regen_marketplace.py            # rewrite marketplace.json
  python scripts/regen_marketplace.py --check    # exit non-zero on drift
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
PLUGINS_DIR = REPO_ROOT / "plugins"

TOP_LEVEL_KEYS = ("$schema", "name", "description", "owner")
DEFAULT_CATEGORY = "development"


def _load_plugin_manifests() -> dict[str, dict]:
    """Return {plugin_name: manifest_dict} for every plugin on disk."""
    manifests = {}
    for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        pj_path = plugin_dir / ".claude-plugin" / "plugin.json"
        if not pj_path.is_file():
            continue
        try:
            data = json.loads(pj_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"error: {pj_path}: {e}", file=sys.stderr)
            sys.exit(1)
        name = data.get("name") or plugin_dir.name
        data["__dir"] = plugin_dir.name
        manifests[name] = data
    return manifests


def _build_entry(manifest: dict) -> dict:
    """Project a plugin.json into a marketplace.json plugins[] entry."""
    entry = {
        "name": manifest["name"],
        "description": manifest.get("description", ""),
        "version": manifest.get("version", ""),
        "author": manifest.get("author", {"name": ""}),
        "source": f"./plugins/{manifest['__dir']}",
        "category": manifest.get("category", DEFAULT_CATEGORY),
    }
    # Propagate inter-plugin dependencies so they are declared in both plugin.json
    # and the marketplace entry (the spec accepts either location).
    if manifest.get("dependencies"):
        entry["dependencies"] = manifest["dependencies"]
    return entry


def _is_published(manifest: dict) -> bool:
    return manifest.get("published", True) is not False


def regenerate() -> dict:
    """Return the regenerated marketplace.json contents."""
    if not MARKETPLACE_JSON.is_file():
        print(f"error: {MARKETPLACE_JSON} not found", file=sys.stderr)
        sys.exit(1)
    current = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
    manifests = _load_plugin_manifests()

    published = {name: m for name, m in manifests.items() if _is_published(m)}

    # Preserve existing order from marketplace.json; append new published plugins
    # alphabetically. Plugins flipped to published: false drop out silently.
    existing_order = [p.get("name") for p in current.get("plugins", [])]
    seen: set[str] = set()
    ordered_names: list[str] = []
    for name in existing_order:
        if name in published and name not in seen:
            ordered_names.append(name)
            seen.add(name)
    for name in sorted(published):
        if name not in seen:
            ordered_names.append(name)
            seen.add(name)

    out = {}
    for k in TOP_LEVEL_KEYS:
        if k in current:
            out[k] = current[k]
    out["plugins"] = [_build_entry(published[name]) for name in ordered_names]
    return out


def _serialize(data: dict) -> str:
    """Stable JSON serialization matching repo conventions (2-space indent, trailing newline)."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    check_only = "--check" in argv

    regenerated = regenerate()
    new_text = _serialize(regenerated)
    current_text = MARKETPLACE_JSON.read_text(encoding="utf-8")

    if check_only:
        if new_text != current_text:
            print(
                "marketplace.json is out of sync with plugin.json sources.\n"
                "Run: python scripts/regen_marketplace.py",
                file=sys.stderr,
            )
            return 1
        return 0

    if new_text == current_text:
        print("marketplace.json already up to date.")
        return 0
    MARKETPLACE_JSON.write_text(new_text, encoding="utf-8")
    print(f"wrote {MARKETPLACE_JSON.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
