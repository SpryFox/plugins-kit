"""Plugin path resolution from installed_plugins.json registry."""

import json
import os
from typing import List, NamedTuple, Optional


class PluginInfo(NamedTuple):
    name: str
    install_path: str  # Absolute path
    version: str


def parse_plugin_ref(plugin_ref: str) -> tuple:
    """Parse a plugin ref into (marketplace, plugin_name).

    Format: 'marketplace:plugin' (e.g. 'plugins-kit:bootstrap').
    Returns ('', plugin_ref) if no colon separator found.
    """
    if ":" in plugin_ref:
        marketplace, plugin_name = plugin_ref.split(":", 1)
        return marketplace, plugin_name
    return "", plugin_ref


def resolve_plugin(registry_path: str, plugin_ref: str, base_dir: str) -> Optional[PluginInfo]:
    """Resolve a plugin reference to its install path.

    Args:
        registry_path: Path to installed_plugins.json
        plugin_ref: Plugin key (e.g. "plugins-kit:test-plugin")
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

    # Extract plugin name from ref (part after :)
    _, name = parse_plugin_ref(plugin_ref)

    return PluginInfo(name=name, install_path=install_path, version=version)


def list_enabled_plugins(config: dict, registry_path: str, base_dir: str):
    """Auto-discover plugins that have bootstrap.json.

    Uses no_bootstrap for opt-out and bootstrap_cache to avoid repeated filesystem scans.

    Args:
        config: Bootstrap config dict (with "no_bootstrap" and "bootstrap_cache" lists)
        registry_path: Path to installed_plugins.json
        base_dir: Base directory for resolving relative paths

    Returns:
        Tuple of (List[PluginInfo], cache_changed: bool)
    """
    try:
        with open(registry_path, "r") as f:
            registry = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return [], False

    plugins = registry.get("plugins", {})
    no_bootstrap = config.get("no_bootstrap", [])
    bootstrap_cache = config.setdefault("bootstrap_cache", [])

    cache_changed = False
    results = []

    # Purge stale cache entries for plugins no longer in the registry (uninstalled)
    current_refs = set(plugins.keys())
    stale = [ref for ref in bootstrap_cache if ref not in current_refs]
    for ref in stale:
        bootstrap_cache.remove(ref)
        cache_changed = True

    for ref, entries in plugins.items():
        if not entries or not isinstance(entries, list):
            continue

        # Skip plugins opted out of bootstrapping
        if ref in no_bootstrap:
            continue

        # Resolve install path
        entry = entries[0]
        install_path = entry.get("installPath", "")
        version = entry.get("version", "0.0.0")
        if install_path.startswith("./") or install_path.startswith("../"):
            install_path = os.path.normpath(os.path.join(base_dir, install_path))
        else:
            install_path = os.path.normpath(install_path)

        _, name = parse_plugin_ref(ref)
        plugin_info = PluginInfo(name=name, install_path=install_path, version=version)
        bootstrap_json = os.path.join(install_path, "bootstrap.json")

        if ref in bootstrap_cache:
            # Cached: verify bootstrap.json still exists (plugin may have been updated)
            if os.path.isfile(bootstrap_json):
                results.append(plugin_info)
            else:
                bootstrap_cache.remove(ref)
                cache_changed = True
        else:
            # Not cached: check filesystem
            if os.path.isfile(bootstrap_json):
                bootstrap_cache.append(ref)
                cache_changed = True
                results.append(plugin_info)

    return results, cache_changed
