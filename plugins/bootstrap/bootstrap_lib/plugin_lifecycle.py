"""Plugin lifecycle operations for bootstrap manifests.

Check, register, enable, and remove plugins in the installed_plugins.json
registry and bootstrap config.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, NamedTuple, Optional


class PluginCheckResult(NamedTuple):
    passed: bool
    ref: str
    message: str


def check_plugin_registered(registry_path: str, plugin_ref: str) -> PluginCheckResult:
    """Check if a plugin is registered in installed_plugins.json.

    Args:
        registry_path: Path to installed_plugins.json
        plugin_ref: Plugin reference (e.g. "plugins-kit:unreal-kit")

    Returns:
        PluginCheckResult with pass/fail
    """
    registry = _load_registry(registry_path)
    if registry is None:
        return PluginCheckResult(
            passed=False, ref=plugin_ref,
            message="registry file not found",
        )

    plugins = registry.get("plugins", {})
    if plugin_ref in plugins:
        return PluginCheckResult(
            passed=True, ref=plugin_ref,
            message="registered",
        )

    return PluginCheckResult(
        passed=False, ref=plugin_ref,
        message="not registered",
    )


def register_plugin(
    registry_path: str,
    plugin_ref: str,
    install_path: str,
    version: str = "0.1.0",
) -> PluginCheckResult:
    """Register a plugin in installed_plugins.json.

    Args:
        registry_path: Path to installed_plugins.json
        plugin_ref: Plugin reference (e.g. "plugins-kit:unreal-kit")
        install_path: Relative or absolute install path
        version: Plugin version string

    Returns:
        PluginCheckResult with pass/fail
    """
    registry = _load_registry(registry_path) or {"plugins": {}}

    plugins = registry.setdefault("plugins", {})
    plugins[plugin_ref] = [{"installPath": install_path, "version": version}]

    Path(registry_path).parent.mkdir(parents=True, exist_ok=True)
    with open(registry_path, "w") as f:
        json.dump(registry, f, indent=2)
        f.write("\n")

    return PluginCheckResult(
        passed=True, ref=plugin_ref,
        message="registered",
    )


def unregister_plugin(registry_path: str, plugin_ref: str) -> PluginCheckResult:
    """Remove a plugin from installed_plugins.json.

    Args:
        registry_path: Path to installed_plugins.json
        plugin_ref: Plugin reference to remove

    Returns:
        PluginCheckResult with pass/fail
    """
    registry = _load_registry(registry_path)
    if registry is None:
        return PluginCheckResult(
            passed=False, ref=plugin_ref,
            message="registry file not found",
        )

    plugins = registry.get("plugins", {})
    if plugin_ref not in plugins:
        return PluginCheckResult(
            passed=True, ref=plugin_ref,
            message="already not registered",
        )

    del plugins[plugin_ref]

    with open(registry_path, "w") as f:
        json.dump(registry, f, indent=2)
        f.write("\n")

    return PluginCheckResult(
        passed=True, ref=plugin_ref,
        message="unregistered",
    )


def check_plugin_enabled(
    config_path: str,
    plugin_ref: str,
) -> PluginCheckResult:
    """Check if a plugin is in the bootstrap config's enabled_plugins list.

    Args:
        config_path: Path to bootstrap config.json
        plugin_ref: Plugin reference

    Returns:
        PluginCheckResult with pass/fail
    """
    config = _load_json(config_path)
    if config is None:
        return PluginCheckResult(
            passed=False, ref=plugin_ref,
            message="config file not found",
        )

    enabled = config.get("enabled_plugins", [])
    if plugin_ref in enabled:
        return PluginCheckResult(passed=True, ref=plugin_ref, message="enabled")

    return PluginCheckResult(passed=False, ref=plugin_ref, message="not enabled")


def enable_plugin(config_path: str, plugin_ref: str) -> PluginCheckResult:
    """Add a plugin to the bootstrap config's enabled_plugins list.

    Args:
        config_path: Path to bootstrap config.json
        plugin_ref: Plugin reference to enable

    Returns:
        PluginCheckResult with pass/fail
    """
    config = _load_json(config_path) or {}

    enabled = config.setdefault("enabled_plugins", [])
    if plugin_ref not in enabled:
        enabled.append(plugin_ref)

    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    return PluginCheckResult(passed=True, ref=plugin_ref, message="enabled")


def disable_plugin(config_path: str, plugin_ref: str) -> PluginCheckResult:
    """Remove a plugin from the bootstrap config's enabled_plugins list.

    Args:
        config_path: Path to bootstrap config.json
        plugin_ref: Plugin reference to disable

    Returns:
        PluginCheckResult with pass/fail
    """
    config = _load_json(config_path)
    if config is None:
        return PluginCheckResult(
            passed=False, ref=plugin_ref,
            message="config file not found",
        )

    enabled = config.get("enabled_plugins", [])
    if plugin_ref in enabled:
        enabled.remove(plugin_ref)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    return PluginCheckResult(passed=True, ref=plugin_ref, message="disabled")


def _load_registry(path: str) -> Optional[Dict[str, Any]]:
    """Load installed_plugins.json. Returns None if not found."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    """Load a JSON file. Returns None if not found."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
