"""Plugin path resolution from installed_plugins.json registry."""

import json
import os
from typing import List, NamedTuple, Optional


class PluginInfo(NamedTuple):
    name: str
    install_path: str  # Absolute path
    version: str


def resolve_plugin(registry_path: str, plugin_ref: str, base_dir: str) -> Optional[PluginInfo]:
    """Resolve a plugin reference to its install path.

    Args:
        registry_path: Path to installed_plugins.json
        plugin_ref: Plugin key (e.g. "test-plugin@plugins-kit")
        base_dir: Base directory for resolving relative paths (the plugins/ dir)

    Returns:
        PluginInfo if found, None otherwise
    """
    try:
        with open(registry_path, "r") as f:
            registry = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    plugins = registry.get("plugins", {})
    entries = plugins.get(plugin_ref)
    if not entries or not isinstance(entries, list):
        return None

    entry = entries[0]  # Use first entry
    install_path = entry.get("installPath", "")
    version = entry.get("version", "0.0.0")

    # Resolve relative paths against base_dir
    if install_path.startswith("./") or install_path.startswith("../"):
        install_path = os.path.normpath(os.path.join(base_dir, install_path))
    else:
        install_path = os.path.normpath(install_path)

    # Extract plugin name from ref (part before @)
    name = plugin_ref.split("@")[0] if "@" in plugin_ref else plugin_ref

    return PluginInfo(name=name, install_path=install_path, version=version)


def list_enabled_plugins(config: dict, registry_path: str, base_dir: str) -> List[PluginInfo]:
    """Resolve all enabled plugins from config.

    Args:
        config: Bootstrap config dict (with "enabled_plugins" list)
        registry_path: Path to installed_plugins.json
        base_dir: Base directory for resolving relative paths

    Returns:
        List of resolved PluginInfo objects (skips unresolvable refs)
    """
    enabled = config.get("enabled_plugins", [])
    results = []
    for ref in enabled:
        info = resolve_plugin(registry_path, ref, base_dir)
        if info is not None:
            results.append(info)
    return results
