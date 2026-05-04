#!/usr/bin/env python3
"""Bootstrap engine — processes bootstrap manifests and emits hook responses.

Usage:
    python3 -m bootstrap_lib.engine --plugin-root /path/to/bootstrap --data-dir /path/to/data

    Or via console script entry point:
    bootstrap-engine --plugin-root /path/to/bootstrap --data-dir /path/to/data

Exit behavior:
    Emits hook JSON to stdout with systemMessage showing new log entries.
    On failure, additionalContext includes remediation instructions for the agent.
    Silent exit (no stdout) when there are no new log entries to display.
"""

import argparse
import json
import os
import stat
import sys
from datetime import datetime, timedelta, timezone


def main():
    start_time = datetime.now(timezone.utc)

    parser = argparse.ArgumentParser(description="Bootstrap engine")
    parser.add_argument("--plugin-root", required=True, help="Path to bootstrap plugin root")
    parser.add_argument("--data-dir", required=True, help="Path to bootstrap data directory")
    parser.add_argument("--hook-start-epoch", type=int, default=0, help="(unused, kept for backward compat)")
    parser.add_argument("--project-dir", default=None, help="Project root directory (for layered bootstrap.json)")
    parser.add_argument("--verbose", action="store_true", help="Write ok/cached entries to the log file (never shown in hook output)")
    parser.add_argument("--console", action="store_true", help="Plain text output, no JSON/log writes")
    parser.add_argument("--background", action="store_true",
        help="Write display output to bootstrap_display.json instead of stdout")
    args = parser.parse_args()

    # --console implies --verbose
    if args.console:
        args.verbose = True

    plugin_root = args.plugin_root
    data_dir = args.data_dir

    from .config import load_config
    from .log import write_log_block
    from .path_repair import repair_path
    from .tool_check import check_tool
    from .path_check import check_path_entry
    from .platform_detect import detect_os
    from .plugin_resolve import list_enabled_plugins
    from .venv_check import check_venv
    from .git_dep_check import check_git_dep

    # Repair PATH before any subprocess fan-out. On Windows, a bloated
    # launching-shell PATH can trip cmd.exe's variable-size limit during
    # venv activation and leave this Python with a stripped PATH that
    # fails tool_check / git_dep_check / etc.
    path_repair_result = repair_path()

    # Step 1: Load/migrate config
    defaults_dir = os.path.join(plugin_root, "defaults")
    config = load_config(data_dir, defaults_dir)

    current_os = detect_os()
    log_success = config.get("log_success_checks", False) or args.verbose
    all_failures = []
    # Bootstrap's own entries (self-bootstrap + user) — written to bootstrap's log
    bootstrap_action_entries = []
    bootstrap_ok_entries = []
    # Display sections: list of (header, action_entries, ok_entries)
    display_sections = []

    if path_repair_result.changed:
        details = []
        if path_repair_result.deduped:
            details.append(f"deduped {path_repair_result.deduped}")
        if path_repair_result.restored:
            details.append(f"restored {path_repair_result.restored} from registry")
        bootstrap_action_entries.append(
            f"PATH repaired: {path_repair_result.before_entries} -> "
            f"{path_repair_result.after_entries} entries "
            f"({', '.join(details)})"
        )

    # Detect plugins directory (where installed_plugins.json lives)
    # Dev layout: ~/Dev/<marketplace>/plugins/bootstrap → one up
    # Cache layout: ~/.claude/plugins/cache/<marketplace>/bootstrap/<ver> → walk up to ~/.claude/plugins/
    plugins_dir = _find_plugins_dir(plugin_root)
    # Marketplace name: go 2 levels up from plugin_root and take basename.
    # Dev: plugins-kit/plugins/bootstrap → up 2 → plugins-kit
    # Cache: cache/plugins-kit/bootstrap/0.5.0 → up 2 → plugins-kit
    marketplace_name = os.path.basename(os.path.normpath(os.path.join(plugin_root, "..", "..")))
    plugin_json_path = os.path.join(plugin_root, ".claude-plugin", "plugin.json")
    boot_plugin_name = "bootstrap"
    version = ""
    try:
        with open(plugin_json_path, "r") as f:
            pj = json.load(f)
            boot_plugin_name = pj.get("name", "bootstrap")
            version = pj.get("version", "")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    version_suffix = f"@{version}" if version else ""
    bootstrap_label = f"{marketplace_name}:{boot_plugin_name}{version_suffix}" if marketplace_name else f"{boot_plugin_name}{version_suffix}"

    # Step 2b: Version change detection
    action_entries = []
    ok_entries = []
    if version:
        last_version_file = os.path.join(data_dir, "last_version")
        try:
            with open(last_version_file, "r") as f:
                last_version = f.read().strip()
        except FileNotFoundError:
            last_version = ""
        if last_version and last_version != version:
            action_entries.append(f"updated: {last_version} -> {version}")
        elif not last_version:
            action_entries.append(f"installed: {version}")
        os.makedirs(data_dir, exist_ok=True)
        with open(last_version_file, "w") as f:
            f.write(version)
    bootstrap_action_entries.extend(action_entries)

    # Step 3: Self-setup (tools, PATH, venv from config.self_setup) — runs every session
    self_setup = config.get("self_setup", {})
    action_entries = []
    ok_entries = []
    failures = _process_self_setup(
        self_setup, current_os, data_dir, plugin_root,
        action_entries, ok_entries, plugin_name=boot_plugin_name,
    )
    bootstrap_action_entries.extend(action_entries)
    bootstrap_ok_entries.extend(ok_entries)

    if failures:
        all_failures.extend(failures)

    # Step 3b: Activate bootstrap venv site-packages so PyYAML is available
    _activate_bootstrap_venv(data_dir)

    # Step 3c: Process layered bootstrap manifests (user + project level)
    # Deprecation: warn if legacy user-bootstrap.json exists
    legacy_path = os.path.join(data_dir, "user-bootstrap.json")
    if os.path.isfile(legacy_path):
        bootstrap_action_entries.append(
            "DEPRECATED: user-bootstrap.json found in data dir. "
            "Migrate to ~/.claude/bootstrap.json (still processed this session)."
        )

    layered_manifest, layered_parse_errors = _load_layered_manifests(args.project_dir, data_dir)
    for pe in layered_parse_errors:
        bootstrap_action_entries.append(
            f"layered manifest {pe['path']}: PARSE FAILED - {pe['error']}"
        )
        all_failures.append({
            "type": "manifest_parse",
            "path": pe["path"],
            "message": pe["error"],
            "agent_msg": (
                f"The bootstrap manifest at {pe['path']} failed to parse "
                f"({pe['error']}). Open the file, fix the JSON syntax, and "
                "ask the user to type 'fix-all' to re-run bootstrap. Common "
                "causes: missing/extra commas, unquoted keys, trailing commas."
            ),
            "plugin": "bootstrap",
            "persist_across_sessions": True,
        })
    if layered_manifest:
        action_entries = []
        ok_entries = []
        failures = _process_manifest(
            layered_manifest, current_os, data_dir, plugin_root,
            action_entries, ok_entries, plugin_name="config",
            project_dir=args.project_dir,
        )
        prefixed_action = [f"config: {e}" for e in action_entries]
        prefixed_ok = [f"config: {e}" for e in ok_entries]
        bootstrap_action_entries.extend(prefixed_action)
        bootstrap_ok_entries.extend(prefixed_ok)
        if failures:
            all_failures.extend(failures)

    # Step 3d: Process project_venv from layered manifest (needs --project-dir)
    project_venv_def = layered_manifest.get("project_venv") if layered_manifest else None
    if project_venv_def and args.project_dir:
        pv_action, pv_ok, pv_failures = _process_project_venv(
            project_venv_def, args.project_dir)
        bootstrap_action_entries.extend(f"config: {e}" for e in pv_action)
        bootstrap_ok_entries.extend(f"config: {e}" for e in pv_ok)
        all_failures.extend(pv_failures)

    # Add bootstrap's own section to display
    display_sections.append((bootstrap_label, list(bootstrap_action_entries), list(bootstrap_ok_entries)))

    # Step 4: Process enabled plugins (auto-discovered via bootstrap.json presence)
    registry_path = os.path.join(plugins_dir, "installed_plugins.json")

    # In dev layout the registry lists all repo plugins, not just enabled ones.
    # Build an enabled_refs filter from settings.json + production registry so only
    # actively-enabled plugins are bootstrapped. Production layout is unaffected
    # (its registry is already authoritative).
    home = os.environ.get("HOME") or os.path.expanduser("~")
    prod_registry = os.path.normpath(os.path.join(home, ".claude", "plugins", "installed_plugins.json"))
    is_dev_layout = os.path.normpath(registry_path) != prod_registry
    enabled_refs = _load_enabled_refs(args.project_dir) if is_dev_layout else None

    enabled_plugins, cache_changed = list_enabled_plugins(config, registry_path, plugins_dir, enabled_refs)
    if cache_changed:
        from .config import save_config
        save_config(data_dir, config)

    # Sort: bootstrap plugin first, then same-marketplace plugins, then others
    def _plugin_sort_key(pi):
        if pi.name == boot_plugin_name and pi.marketplace == marketplace_name:
            return (0, pi.name)
        if pi.marketplace == marketplace_name:
            return (1, pi.name)
        return (2, pi.name)

    enabled_plugins.sort(key=_plugin_sort_key)
    deferred_plugin_logs = []
    processed_plugin_refs = set()

    for plugin_info in enabled_plugins:
        ref = f"{plugin_info.marketplace}:{plugin_info.name}" if plugin_info.marketplace else plugin_info.name
        processed_plugin_refs.add(ref)
        _bootstrap_single_plugin(
            plugin_info, current_os, data_dir, all_failures,
            log_success, display_sections, deferred_plugin_logs, args,
        )

    # Step 4b: Re-scan for plugins installed during Steps 3c/4
    # (e.g. a layered bootstrap.json declared a plugin to install via `claude plugin install`)
    phase2_plugins, phase2_cache_changed = list_enabled_plugins(config, registry_path, plugins_dir, enabled_refs)
    if phase2_cache_changed:
        from .config import save_config
        save_config(data_dir, config)

    new_plugins = [
        pi for pi in phase2_plugins
        if (f"{pi.marketplace}:{pi.name}" if pi.marketplace else pi.name)
           not in processed_plugin_refs
    ]
    new_plugins.sort(key=_plugin_sort_key)
    for plugin_info in new_plugins:
        _bootstrap_single_plugin(
            plugin_info, current_os, data_dir, all_failures,
            log_success, display_sections, deferred_plugin_logs, args,
        )

    # Step 5: Read shell log entries BEFORE writing any engine entries to the log.
    # Plugin log writes are deferred to step 6 to avoid the bootstrap plugin's
    # ok_entries leaking back through shell_content (its data_dir == engine data_dir).
    if not args.console:
        shell_content = _read_new_log_entries(data_dir, start_time=start_time)
    else:
        shell_content = ""  # Console mode: shell already printed its entries

    # Step 6: Write log entries (bootstrap + plugins) — after reading shell entries
    # Skip in console mode — no file writes.
    # Only include ok_entries when log_success is true — otherwise they leak back
    # through shell_content on the next run (the log reader can't distinguish
    # ok vs action entries, so they bypass the log_success display filter).
    bootstrap_log_entries = bootstrap_action_entries + (bootstrap_ok_entries if log_success else [])
    if bootstrap_log_entries and not args.console:
        write_log_block(data_dir, bootstrap_label, bootstrap_log_entries, start_time=start_time)
    for plugin_data_dir, plugin_label, plugin_log_entries in deferred_plugin_logs:
        if plugin_log_entries and not args.console:
            write_log_block(plugin_data_dir, plugin_label, plugin_log_entries, start_time=start_time)

    # Step 7: Build display from sections — actions only, never ok entries.
    # ok entries are written to the log file (gated by log_success) for debugging
    # via `tail bootstrap.log`, but never surface in the user-facing hook output.
    display_lines = []
    for header, actions, _oks in display_sections:
        if actions:
            display_lines.append(f"--- {header} ---")
            display_lines.extend(actions)

    if args.console:
        # Console mode: plain text to stdout, no JSON
        for line in display_lines:
            print(line)
        if all_failures:
            print(f"\n{bootstrap_label} -> {len(all_failures)} failure(s):")
            for f in all_failures:
                print(f"  - [{f['type']}] {f.get('name', f.get('message', ''))}")
        return

    # Build final display: shell entries + section entries
    parts = []
    if shell_content:
        parts.append(shell_content)
    parts.extend(display_lines)
    display_content = "\n".join(parts)

    # Update the log display marker
    _update_display_marker(data_dir)

    # Step 8: Emit results
    output_file = os.path.join(data_dir, "bootstrap_display.pending") if args.background else None
    persistent_alert_path = os.path.join(data_dir, "bootstrap_alert.json")
    has_persistent = any(f.get("persist_across_sessions") for f in all_failures)
    persistent_output_file = persistent_alert_path if (args.background and has_persistent) else None

    if all_failures:
        emit_failure_response(
            all_failures, current_os, display_content,
            label=bootstrap_label, output_file=output_file,
            persistent_output_file=persistent_output_file,
        )
    elif display_content:
        emit_success_response(display_content, label=bootstrap_label, output_file=output_file)
    # else: nothing to show — silent exit (no file written in background mode)

    # Clean up stale persistent alert file when no persistent failures remain.
    # This is what makes the alert disappear once the user fixes the underlying
    # issue and the engine confirms the fix on a subsequent run.
    if not has_persistent:
        try:
            os.remove(persistent_alert_path)
        except FileNotFoundError:
            pass
        except OSError:
            pass


def _bootstrap_single_plugin(
    plugin_info, current_os, data_dir, all_failures,
    log_success, display_sections, deferred_plugin_logs, args,
):
    """Process a single plugin's bootstrap.json manifest.

    Extracted from the Step 4 loop body to allow reuse in Step 4b (Phase 2 re-scan).
    Mutates the shared containers in place (same pattern as the original inline code).
    """
    plugin_manifest_path = os.path.join(plugin_info.install_path, "bootstrap.json")
    if not os.path.isfile(plugin_manifest_path):
        return

    # Per-plugin data dir and cache
    plugin_data_dir = os.path.join(
        os.path.dirname(data_dir), plugin_info.name
    )
    os.makedirs(plugin_data_dir, exist_ok=True)

    with open(plugin_manifest_path, "r") as f:
        plugin_manifest = json.load(f)

    # Per-plugin entry lists (written to plugin's own log)
    plugin_action_entries = []
    plugin_ok_entries = []

    # Version change detection
    if plugin_info.version:
        last_version_file = os.path.join(plugin_data_dir, "last_version")
        try:
            with open(last_version_file, "r") as f:
                last_version = f.read().strip()
        except FileNotFoundError:
            last_version = ""
        if last_version and last_version != plugin_info.version:
            plugin_action_entries.append(f"updated: {last_version} -> {plugin_info.version}")
        elif not last_version:
            plugin_action_entries.append(f"installed: {plugin_info.version}")
        with open(last_version_file, "w") as f:
            f.write(plugin_info.version)

    # Project config phase (per-CWD discovery, before config phase)
    # project_detected: True when project found or no project_config section (non-gated plugin)
    project_detected = True
    project_config_section = plugin_manifest.get("project_config")
    if project_config_section:
        project_config_failures = []
        project_detected = _process_project_config(
            project_config_section, plugin_data_dir, plugin_info.install_path,
            plugin_action_entries, ok_entries=plugin_ok_entries, plugin_name=plugin_info.name,
            failures=project_config_failures,
        )
        if project_config_failures:
            all_failures.extend(project_config_failures)

    # Config phase
    config_section = plugin_manifest.get("config")
    if config_section:
        config_failures = _process_config(
            config_section, plugin_data_dir, plugin_info.install_path,
            plugin_action_entries, ok_entries=plugin_ok_entries, plugin_name=plugin_info.name,
            project_detected=project_detected,
        )
        if config_failures:
            all_failures.extend(config_failures)

    action_entries = []
    ok_entries = []
    failures = _process_manifest(
        plugin_manifest, current_os, plugin_data_dir, plugin_info.install_path,
        action_entries, ok_entries, plugin_name=plugin_info.name,
        project_dir=getattr(args, 'project_dir', None),
        project_detected=project_detected,
    )
    plugin_action_entries.extend(action_entries)
    plugin_ok_entries.extend(ok_entries)

    if failures:
        all_failures.extend(failures)

    # Collect plugin log info (deferred — written after reading shell entries)
    plugin_label = f"{plugin_info.name}@{plugin_info.version}" if plugin_info.version else plugin_info.name
    plugin_log_entries = plugin_action_entries + (plugin_ok_entries if log_success else [])
    deferred_plugin_logs.append((plugin_data_dir, plugin_label, plugin_log_entries))

    # Add plugin section to display
    plugin_display_header = f"{plugin_info.marketplace}:{plugin_info.name}@{plugin_info.version}" if plugin_info.marketplace else plugin_label
    display_sections.append((plugin_display_header, list(plugin_action_entries), list(plugin_ok_entries)))


def _load_enabled_refs(project_dir=None):
    """Build the set of enabled plugin refs from Claude Code settings + production registry.

    Reads settings files in precedence order (later overrides earlier):
      1. ~/.claude/settings.json         (user scope)
      2. ~/.claude/settings.local.json   (user local overrides)
      3. <project_dir>/.claude/settings.json        (project scope)
      4. <project_dir>/.claude/settings.local.json  (project local overrides)

    A plugin is enabled if its enabledPlugins entry has a final value of True.
    Also includes all plugins found in the production installed_plugins.json registry.

    Scope is handled naturally: user-scoped plugins appear in user settings (always
    included); project-scoped plugins appear in project settings (included only when
    that project is the active --project-dir).

    Returns:
        Set of normalized refs (plugin@marketplace), or None if no sources exist
        (falls back to no filter to preserve the original behavior).
    """
    from .plugin_resolve import parse_plugin_ref

    def _normalize(ref):
        marketplace, name = parse_plugin_ref(ref)
        return f"{name}@{marketplace}" if marketplace else name

    # Collect settings files in ascending precedence
    home = os.environ.get("HOME") or os.path.expanduser("~")
    claude_home = os.path.join(home, ".claude")
    settings_paths = [
        os.path.join(claude_home, "settings.json"),
        os.path.join(claude_home, "settings.local.json"),
    ]
    if project_dir:
        project_claude = os.path.join(project_dir, ".claude")
        settings_paths.append(os.path.join(project_claude, "settings.json"))
        settings_paths.append(os.path.join(project_claude, "settings.local.json"))

    merged_enabled = {}
    any_settings_found = False
    for path in settings_paths:
        try:
            with open(path, "r") as f:
                data = json.load(f)
            ep = data.get("enabledPlugins", {})
            if isinstance(ep, dict):
                merged_enabled.update(ep)
                any_settings_found = True
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    refs = {_normalize(ref) for ref, val in merged_enabled.items() if val}

    # Also include all plugins in the production registry as a secondary source.
    # Use the same home resolution as above so test isolation via HOME env var works.
    prod_registry_path = os.path.join(home, ".claude", "plugins", "installed_plugins.json")
    try:
        with open(prod_registry_path, "r") as f:
            registry = json.load(f)
        for ref in registry.get("plugins", {}):
            refs.add(_normalize(ref))
        any_settings_found = True
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    # If no sources found at all, return None to preserve original (no-filter) behavior
    return refs if any_settings_found else None


def _load_layered_manifests(project_dir, data_dir=None):
    """Load and merge bootstrap manifests from user and project layers.

    Priority (highest wins):
        4. <project>/.claude/bootstrap.local.json
        3. <project>/.claude/bootstrap.json
        2. ~/.claude/bootstrap.local.json
        1. ~/.claude/bootstrap.json
        0. <data_dir>/user-bootstrap.json  (legacy, lowest priority)

    Returns (merged_manifest, parse_errors) where parse_errors is a list of
    {"path": <path>, "error": <message>} dicts for any layer that failed to load.
    Layers that fail to parse are skipped (the merge continues with the rest).
    """
    from .manifest_merge import merge_manifests

    # Collect candidate paths in priority order (lowest first)
    candidates = []

    # Legacy user-bootstrap.json (lowest priority — deprecated)
    if data_dir:
        legacy = os.path.join(data_dir, "user-bootstrap.json")
        candidates.append(legacy)

    # User-level (HOME is preferred, USERPROFILE is the Windows fallback)
    home = os.environ.get("HOME") or os.path.expanduser("~")
    claude_home = os.path.join(home, ".claude")
    candidates.append(os.path.join(claude_home, "bootstrap.json"))
    candidates.append(os.path.join(claude_home, "bootstrap.local.json"))

    # Project-level
    if project_dir:
        project_claude = os.path.join(project_dir, ".claude")
        candidates.append(os.path.join(project_claude, "bootstrap.json"))
        candidates.append(os.path.join(project_claude, "bootstrap.local.json"))

    merged = {}
    parse_errors = []
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r") as f:
                layer = json.load(f)
        except json.JSONDecodeError as e:
            parse_errors.append({"path": path, "error": f"JSON parse error: {e}"})
            continue
        except OSError as e:
            parse_errors.append({"path": path, "error": f"read error: {e}"})
            continue
        merged = merge_manifests(merged, layer)

    return merged, parse_errors


def _activate_bootstrap_venv(data_dir):
    """Add bootstrap venv site-packages to sys.path so PyYAML is importable."""
    import glob as globmod
    venv_path = os.path.join(data_dir, ".venv")
    # Look for site-packages in both Unix and Windows layouts
    patterns = [
        os.path.join(venv_path, "lib", "python*", "site-packages"),
        os.path.join(venv_path, "Lib", "site-packages"),
    ]
    for pattern in patterns:
        matches = globmod.glob(pattern)
        for sp in matches:
            if sp not in sys.path:
                sys.path.insert(0, sp)


def _process_self_setup(self_setup, current_os, data_dir, plugin_root, action_entries, ok_entries, plugin_name="bootstrap"):
    """Process engine self-setup: tools, path_entries, venv.

    Only these 3 phases — the minimum needed to make the engine runnable.
    Always runs `uv sync` to keep the venv current (~100ms no-op when up to date).
    Returns list of failures.
    """
    from .tool_check import check_tool
    from .path_check import check_path_entry
    from .venv_check import check_venv, export_venv_env_var

    failures = []
    p = "[bootstrap-setup] "

    # Check tools
    for tool_def in self_setup.get("tools", []):
        name = tool_def["name"]
        install_cmds = tool_def.get("install", {})
        tool_install_path = tool_def.get("installPath")
        result = check_tool(name, install_cmds, current_os, install_path=tool_install_path)

        if result.passed:
            ok_entries.append(f"{p}{result.name}: ok - {result.message}")
            continue

        if result.install_cmd:
            action_entries.append(f"{p}{result.name}: not found, attempting install")
            from .tool_check import run_install
            ok, _output = run_install(result.install_cmd)
            if ok:
                recheck = check_tool(name, install_cmds, current_os, install_path=tool_install_path)
                if recheck.passed:
                    action_entries.append(f"{p}{result.name}: installed - ran `{result.install_cmd}`, now {recheck.message}")
                    continue
            action_entries.append(f"{p}{result.name}: FAILED - install attempted but still not found")
        else:
            action_entries.append(f"{p}{result.name}: FAILED - {result.message}")

        failures.append({
            "type": "tool",
            "name": result.name,
            "message": result.message,
            "install_cmd": result.install_cmd,
            "plugin": "bootstrap",
        })

    # Check path entries
    for path_entry in self_setup.get("path_entries", []):
        expanded = os.path.expanduser(path_entry)
        result = check_path_entry(path_entry)
        if result.passed:
            ok_entries.append(f"{p}PATH {result.path}: ok - {result.message}")
        else:
            from .path_check import add_path_to_shell_config
            ok, msg = add_path_to_shell_config(path_entry)
            action_entries.append(f"{p}PATH {result.path}: not in PATH, added to shell config - {msg}")
        current_path = os.environ.get("PATH", "")
        if os.path.normpath(expanded) not in [os.path.normpath(d) for d in current_path.split(os.pathsep)]:
            os.environ["PATH"] = expanded + os.pathsep + current_path

    # Check for Python stubs shadowing the standalone python (Windows-only check)
    stub_def = self_setup.get("python_stub_check")
    if stub_def:
        from .python_stub_check import check_python_stub, write_fix_script
        good_python_dir = stub_def.get("good_python_dir", "~/.local/share/python-standalone/python")
        stub_markers = stub_def.get("stub_markers", ["WindowsApps"])
        script_output_dir = stub_def.get("script_output_dir", "~/Desktop")

        stub_result = check_python_stub(good_python_dir, stub_markers)
        if stub_result.passed:
            ok_entries.append(f"{p}python stub: ok - {stub_result.message}")
        else:
            ok_write, write_msg, script_path = write_fix_script(good_python_dir, script_output_dir)
            if ok_write:
                # User-visible action entry (also written into the bootstrap log)
                action_entries.append(
                    f"{p}python stub: detected {stub_result.bad_python}; "
                    f"wrote fix script to {script_path}"
                )
                # Focused user-facing and Claude-facing messages.
                user_msg = (
                    "Claude needs your help! Run the fix_python_path script that is on "
                    "your desktop as administrator to make python accessible to Claude."
                )
                agent_msg = (
                    "A Microsoft Store Python stub is shadowing the standalone Python "
                    "that plugins-kit installed, blocking Claude's access to a working "
                    f"python.exe. Detected stub at: {stub_result.bad_python}. A fix script "
                    f"has been written to the user's desktop at {script_path}. The user "
                    "must double-click it (it self-elevates via UAC) or right-click and "
                    "choose 'Run as administrator'. The script prepends the standalone "
                    "Python directory to the System PATH and then deletes itself. After "
                    "the user runs it successfully, they need to start a new Claude Code "
                    "session for the new System PATH to take effect. If the user asks for "
                    "help, walk them through these steps. Do NOT attempt to run the script "
                    "yourself — it requires interactive UAC consent."
                )
                failures.append({
                    "type": "python_stub",
                    "name": "python_stub",
                    "user_msg": user_msg,
                    "agent_msg": agent_msg,
                    "message": user_msg,  # legacy field for general consumers
                    "bad_python": stub_result.bad_python,
                    "script_path": script_path,
                    "plugin": "bootstrap",
                    "persist_across_sessions": True,
                })
            else:
                action_entries.append(
                    f"{p}python stub: detected {stub_result.bad_python}, "
                    f"could not write fix script: {write_msg}"
                )
                user_msg = (
                    "Claude needs your help! A bad python is shadowing the standalone "
                    f"python plugins-kit installed, and the fix script could not be "
                    f"written automatically. Manually prepend {stub_result.good_python_dir} "
                    "to your System PATH."
                )
                agent_msg = (
                    f"A Microsoft Store Python stub at {stub_result.bad_python} is shadowing "
                    f"the standalone Python, and the fix script could not be written: "
                    f"{write_msg}. The user must manually prepend "
                    f"{stub_result.good_python_dir} to their System PATH (Windows Settings -> "
                    "Edit the system environment variables -> Environment Variables -> System "
                    "variables -> Path -> New -> move to top), then start a new Claude Code "
                    "session."
                )
                failures.append({
                    "type": "python_stub",
                    "name": "python_stub",
                    "user_msg": user_msg,
                    "agent_msg": agent_msg,
                    "message": user_msg,
                    "bad_python": stub_result.bad_python,
                    "script_path": None,
                    "plugin": "bootstrap",
                    "persist_across_sessions": True,
                })

    # Check venv — always run uv sync to keep deps current (~100ms no-op when up to date)
    venv_def = self_setup.get("venv")
    if venv_def:
        check_imports = venv_def.get("check_imports", [])
        result = check_venv(data_dir, plugin_root, check_imports)

        # Run uv sync unconditionally — the import check is for diagnostics/logging only
        import shutil
        import subprocess as _sp
        venv_path = os.path.join(data_dir, ".venv")

        local_bin = os.path.expanduser("~/.local/bin")
        uv_bin = shutil.which("uv")
        if not uv_bin:
            for name in ("uv", "uv.exe", "uv.EXE"):
                candidate = os.path.join(local_bin, name)
                if os.path.isfile(candidate):
                    uv_bin = candidate
                    break

        if uv_bin:
            uv_cmd = f"uv sync --project {plugin_root}"
            env = dict(os.environ, UV_PROJECT_ENVIRONMENT=venv_path)
            if local_bin not in env.get("PATH", ""):
                env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")
            try:
                proc = _sp.run(
                    [uv_bin, "sync", "--project", plugin_root],
                    env=env, capture_output=True, timeout=120,
                )
                if proc.returncode != 0:
                    stderr_text = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
                    action_entries.append(f"{p}venv: uv sync failed (exit {proc.returncode}): {stderr_text[:200]}")
                elif not result.passed:
                    action_entries.append(f"{p}venv: synced via `{uv_cmd}`")
                # Re-check after sync
                result = check_venv(data_dir, plugin_root, check_imports)
            except (_sp.SubprocessError, OSError) as exc:
                action_entries.append(f"{p}venv: uv sync error: {exc}")
        else:
            action_entries.append(f"{p}venv: uv not found on PATH or in ~/.local/bin")

        if result.passed:
            ok_entries.append(f"{p}venv: ok - {result.message}")
            exported = export_venv_env_var(plugin_name, data_dir)
            if exported:
                ok_entries.append(f"{p}venv: exported {exported} to CLAUDE_ENV_FILE")
        else:
            action_entries.append(f"{p}venv: FAILED - {result.message}")
            failures.append({
                "type": "venv",
                "message": result.message,
                "remediation_cmd": result.remediation_cmd,
                "plugin": "bootstrap",
            })

    return failures


def _process_project_venv(venv_def, project_dir):
    """Process project_venv: ensure the project's own .venv is ready.

    Unlike the plugin venv (which lives in data_dir), this targets
    <project_dir>/.venv using the project's own pyproject.toml.

    Args:
        venv_def: Dict with optional 'extras' (list) and 'check_imports' (list).
        project_dir: Absolute path to the project root.

    Returns:
        (action_entries, ok_entries, failures) tuple.
    """
    from .venv_check import check_venv

    action_entries = []
    ok_entries = []
    failures = []

    extras = venv_def.get("extras", [])
    check_imports = venv_def.get("check_imports", [])

    # project_dir serves as both data_dir (.venv location) and plugin_root (pyproject.toml location)
    result = check_venv(project_dir, project_dir, check_imports)

    if not result.passed:
        extra_flags = " ".join(f"--extra {e}" for e in extras)
        uv_cmd = f"uv sync --project {project_dir}"
        if extra_flags:
            uv_cmd += f" {extra_flags}"
        action_entries.append(f"project_venv: not ready, running `{uv_cmd}`")

        import shutil
        import subprocess as _sp

        local_bin = os.path.expanduser("~/.local/bin")
        uv_bin = shutil.which("uv")
        if not uv_bin:
            for name in ("uv", "uv.exe", "uv.EXE"):
                candidate = os.path.join(local_bin, name)
                if os.path.isfile(candidate):
                    uv_bin = candidate
                    break

        if uv_bin:
            cmd = [uv_bin, "sync", "--project", project_dir]
            for e in extras:
                cmd.extend(["--extra", e])
            env = dict(os.environ)
            if local_bin not in env.get("PATH", ""):
                env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")
            try:
                _sp.run(cmd, env=env, capture_output=True, timeout=120)
                result = check_venv(project_dir, project_dir, check_imports)
                if result.passed:
                    action_entries.append("project_venv: created")
            except (_sp.SubprocessError, OSError):
                pass

    if result.passed:
        ok_entries.append(f"project_venv: ok - {result.message}")
    else:
        action_entries.append(f"project_venv: FAILED - {result.message}")
        failures.append({
            "type": "project_venv",
            "message": result.message,
            "remediation_cmd": result.remediation_cmd,
            "plugin": "config",
        })

    return action_entries, ok_entries, failures


def _process_config(config_section, plugin_data_dir, plugin_root, action_entries, ok_entries=None, plugin_name="", project_detected=True):
    """Process the config section of a plugin manifest.

    Runs outside the cache gate — config can change between sessions.
    Returns list of failures (missing config fields).

    When project_detected is False, still copies defaults and runs autodetect,
    but skips required_fields validation (no project = no config failures).
    """
    from .config_check import config_init, config_validate, run_autodetect, load_yaml_config, save_yaml_config

    config_file = config_section["file"]
    defaults_source = config_section.get("defaults_source")

    # 1. Config init: copy defaults if config doesn't exist
    if defaults_source:
        config_path = config_init(plugin_data_dir, plugin_root, defaults_source, config_file)
    else:
        config_path = os.path.join(plugin_data_dir, config_file)

    if not os.path.isfile(config_path):
        return []

    # 2. Load config
    config = load_yaml_config(config_path)

    required_fields = config_section.get("required_fields", {})

    # 3. Autodetect (optional): always run when declared
    autodetect_spec = config_section.get("autodetect")
    if autodetect_spec:
        try:
            changed, ad_actions, ad_ok = run_autodetect(plugin_root, autodetect_spec, config, config_path)
            action_entries.extend(ad_actions)
            if ok_entries is not None:
                ok_entries.extend(ad_ok)
            else:
                action_entries.extend(ad_ok)
            if changed:
                save_yaml_config(config_path, config)
                if not ad_actions:
                    action_entries.append("config autodetect updated values")
        except Exception:
            pass  # Autodetect errors are non-fatal

    # 4. Validate required fields (apply defaults, collect missing)
    # Skip validation when no project detected — required fields are project-scoped
    if not project_detected:
        if ok_entries is not None:
            ok_entries.append("config: skipped required_fields (no project detected)")
        else:
            action_entries.append("config: skipped required_fields (no project detected)")
        return []

    config, missing = config_validate(config, required_fields, config_path)

    # Write back if defaults were applied
    if any(f.get("default") is not None for f in required_fields.values()):
        # Re-check if any defaults were actually applied (config may have changed)
        current_on_disk = load_yaml_config(config_path)
        if config != current_on_disk:
            save_yaml_config(config_path, config)

    if not missing:
        if ok_entries is not None:
            ok_entries.append("config ok")
        else:
            action_entries.append("config ok")
        return []

    # 5. Fix-all: aggregate missing fields into failure directives
    failures = []
    for m in missing:
        failures.append({
            "type": "config",
            "field": m["field"],
            "user_msg": m["user_msg"],
            "agent_msg": m["agent_msg"],
            "plugin": plugin_name,
        })

    return failures


def _normalize_project_required_fields(required_fields):
    """Normalize required_fields to dict form.

    Accepts either:
    - list of field names (strings) — legacy flat form, each becomes {}
    - dict keyed by field name, values are {user_msg, agent_msg, default?} — dict form

    Returns a dict mapping field name -> field spec (dict).
    """
    if isinstance(required_fields, dict):
        return {
            name: (spec if isinstance(spec, dict) else {})
            for name, spec in required_fields.items()
        }
    # Treat as iterable of names (list/tuple)
    return {name: {} for name in required_fields}


def _legacy_remove(path):
    """Delete a file, clearing the read-only bit if the OS rejects the first try.

    Windows surfaces P4-tracked files as read-only on disk, so a plain os.remove
    raises PermissionError. Cleanup is intentional in the migration flow, so
    relax the mode and retry once. Any second failure propagates.
    """
    try:
        os.remove(path)
    except PermissionError:
        os.chmod(path, stat.S_IWRITE)
        os.remove(path)


def _legacy_replace(src, dst):
    """Move src to dst, clearing read-only on either side if Windows balks.

    os.replace fails if the destination is read-only (Windows) or if the source
    can't be unlinked. Make both writable on PermissionError, then retry once.
    """
    try:
        os.replace(src, dst)
    except PermissionError:
        for p in (src, dst):
            if os.path.isfile(p):
                os.chmod(p, stat.S_IWRITE)
        os.replace(src, dst)


def _process_project_config(project_config_section, plugin_data_dir, plugin_root, action_entries, ok_entries=None, plugin_name="", failures=None):
    """Process the project_config section of a plugin manifest.

    Discovers or reads per-project config (in CWD), syncs values to the data-dir config.

    ``required_fields`` accepts either a flat list of field names (legacy) or a dict
    keyed by field name with values ``{user_msg, agent_msg, default?}``. In dict form:
    - A declared ``default`` is applied when the field is missing from both the file
      and autodetect output (defaults never override already-populated values).
    - Fields that remain missing after autodetect + defaults are emitted as fix-all
      failure entries on the optional ``failures`` list.

    Returns True if a project was detected (config exists or autodetect succeeded),
    False if no project was found (autodetect returned None / no file / no autodetect).
    """
    from .config_check import load_yaml_config, save_yaml_config, run_project_autodetect

    config_file = project_config_section["file"]
    required_fields_spec = _normalize_project_required_fields(
        project_config_section.get("required_fields", [])
    )
    required_field_names = list(required_fields_spec.keys())
    autodetect_spec = project_config_section.get("autodetect")
    legacy_file = project_config_section.get("legacy_file")

    project_config_path = os.path.join(os.getcwd(), config_file)

    # Legacy migration: when the manifest declares a legacy_file, reconcile the
    # old and new paths so downstream logic can run against the new path as if
    # it had always been there. Four cases:
    #   1. only legacy exists           -> move legacy to new path
    #   2. both exist, legacy <= new    -> delete legacy (new is fresher/equal)
    #   3. both exist, legacy >  new    -> move legacy to new (overwrite stale)
    #   4. only new exists, or neither  -> no-op (downstream handles creation)
    # Cases 2/3 cover sessions that ran before legacy_file was honored: the
    # engine had already created a new file from defaults/autodetect, leaving
    # the legacy file orphaned alongside it. mtime decides which copy wins.
    # Wrapped in try/except so a hostile filesystem state (file locked, ACL
    # blocked, etc.) downgrades to a warning instead of killing the whole
    # bootstrap run.
    if legacy_file:
        legacy_path = os.path.join(os.getcwd(), legacy_file)
        try:
            legacy_exists = os.path.isfile(legacy_path)
            new_exists = os.path.isfile(project_config_path)
            if legacy_exists and not new_exists:
                os.makedirs(os.path.dirname(project_config_path), exist_ok=True)
                _legacy_replace(legacy_path, project_config_path)
                action_entries.append(
                    f"project config: migrated {legacy_path} -> {project_config_path}"
                )
            elif legacy_exists and new_exists:
                if os.path.getmtime(legacy_path) <= os.path.getmtime(project_config_path):
                    _legacy_remove(legacy_path)
                    action_entries.append(
                        f"project config: removed stale legacy {legacy_path} (new path {project_config_path} is fresher)"
                    )
                else:
                    _legacy_replace(legacy_path, project_config_path)
                    action_entries.append(
                        f"project config: migrated {legacy_path} -> {project_config_path} (overwrote stale new path)"
                    )
        except OSError as e:
            # Most common cause on Windows: the legacy file is read-only because
            # source control (e.g. Perforce) hasn't checked it out for delete.
            # Surface as a warning and let the user resolve manually rather than
            # dying mid-bootstrap.
            action_entries.append(
                f"project config: WARNING failed to reconcile {legacy_path} -> {project_config_path}: {e}"
            )

    file_changed = False  # Track whether project_data was modified from disk state

    if os.path.isfile(project_config_path):
        # File exists — load it and check required fields
        project_data = load_yaml_config(project_config_path)
        missing_fields = [f for f in required_field_names if not project_data.get(f)]

        if missing_fields and autodetect_spec:
            # Some fields missing — try autodetect to fill gaps
            detected = run_project_autodetect(plugin_root, autodetect_spec)
            if detected:
                for field in missing_fields:
                    if detected.get(field):
                        project_data[field] = detected[field]
                        file_changed = True
                if file_changed:
                    save_yaml_config(project_config_path, project_data)
                    action_entries.append(f"project config: updated {project_config_path}")
                else:
                    if ok_entries is not None:
                        ok_entries.append(f"project config: ok - {project_config_path}")
            else:
                # Autodetect returned None — no active project in CWD
                # Stale config file exists but no project is present
                if ok_entries is not None:
                    ok_entries.append("project config: no project detected (stale config)")
                return False
        else:
            if ok_entries is not None:
                ok_entries.append(f"project config: ok - {project_config_path}")
    else:
        # File doesn't exist — try autodetect
        if autodetect_spec:
            detected = run_project_autodetect(plugin_root, autodetect_spec)
            if detected:
                os.makedirs(os.path.dirname(project_config_path), exist_ok=True)
                project_data = dict(detected)
                # Apply defaults for any declared field still missing from detected
                defaults_applied = _apply_project_defaults(project_data, required_fields_spec)
                save_yaml_config(project_config_path, project_data)
                if defaults_applied:
                    action_entries.append(
                        f"project config: created {project_config_path} (with defaults: {', '.join(defaults_applied)})"
                    )
                else:
                    action_entries.append(f"project config: created {project_config_path}")
                file_changed = True
            else:
                if ok_entries is not None:
                    ok_entries.append("project config: no project detected")
                return False  # Nothing detected — downstream phases should skip project-scoped work
        else:
            if ok_entries is not None:
                ok_entries.append("project config: no project detected")
            return False  # No file, no autodetect — nothing to do

    # Apply declared defaults for any required field still missing after autodetect.
    # Defaults never override already-populated values.
    defaults_applied_now = _apply_project_defaults(project_data, required_fields_spec)
    if defaults_applied_now:
        save_yaml_config(project_config_path, project_data)
        action_entries.append(
            f"project config: applied defaults [{', '.join(defaults_applied_now)}] to {project_config_path}"
        )
        file_changed = True

    # Collect fix-all failures for any field that is still missing and has no default.
    # Only applies in dict form (string-list form defines no user/agent messages).
    if failures is not None:
        for field_name, field_spec in required_fields_spec.items():
            if project_data.get(field_name):
                continue
            if field_spec.get("default") is not None:
                continue  # default already applied above
            if not field_spec:
                # String-list form carries no messages — skip fix-all emission
                continue
            agent_msg = field_spec.get(
                "agent_msg", f"Set {field_name} in {project_config_path}"
            ).replace("{config_path}", project_config_path)
            failures.append({
                "type": "project_config",
                "field": field_name,
                "user_msg": field_spec.get("user_msg", field_name),
                "agent_msg": agent_msg,
                "plugin": plugin_name,
            })

    # Sync discovered values to data-dir config
    data_config_path = os.path.join(plugin_data_dir, "config.yaml")
    if os.path.isfile(data_config_path):
        data_config = load_yaml_config(data_config_path)
    else:
        data_config = {}

    changed = False
    for field in required_field_names:
        val = project_data.get(field, "")
        if val and val != data_config.get(field, ""):
            data_config[field] = val
            changed = True

    if changed:
        save_yaml_config(data_config_path, data_config)

    return True


def _apply_project_defaults(project_data, required_fields_spec):
    """Apply declared defaults for any required field not already set in project_data.

    Mutates ``project_data`` in place. Returns the list of field names that received
    a default (empty if none).
    """
    applied = []
    for field_name, field_spec in required_fields_spec.items():
        if project_data.get(field_name):
            continue
        default = field_spec.get("default")
        if default is None:
            continue
        project_data[field_name] = default
        applied.append(field_name)
    return applied


def _process_manifest(manifest, current_os, data_dir, plugin_root, action_entries, ok_entries, plugin_name="bootstrap", project_dir=None, project_detected=True):
    """Process a single plugin's bootstrap manifest. Returns list of failures.

    Entries are split into two lists:
    - action_entries: actions performed, failures, conditions not met (always displayed)
    - ok_entries: checks that passed (never displayed; written to log file when log_success is true)

    When project_detected is False, project-scoped primitives (ini_settings) are skipped.
    """
    from .tool_check import check_tool
    from .path_check import check_path_entry
    from .venv_check import check_venv, export_venv_env_var
    from .git_dep_check import check_git_dep

    failures = []
    prefix = ""

    # Check tools
    for tool_def in manifest.get("tools", []):
        name = tool_def["name"]
        install_cmds = tool_def.get("install", {})
        tool_install_path = tool_def.get("installPath")
        result = check_tool(name, install_cmds, current_os, install_path=tool_install_path)

        if result.passed:
            ok_entries.append(f"{prefix}{result.name}: ok - {result.message}")
            continue

        # Tool not found — attempt remediation if install command available
        if result.install_cmd:
            action_entries.append(f"{prefix}{result.name}: not found, attempting install")
            from .tool_check import run_install
            ok, _output = run_install(result.install_cmd)
            if ok:
                recheck = check_tool(name, install_cmds, current_os, install_path=tool_install_path)
                if recheck.passed:
                    action_entries.append(f"{prefix}{result.name}: installed - ran `{result.install_cmd}`, now {recheck.message}")
                    continue  # no failure to record
            # Install failed or tool still missing after install
            action_entries.append(f"{prefix}{result.name}: FAILED - install attempted but still not found")
        else:
            action_entries.append(f"{prefix}{result.name}: FAILED - {result.message}")

        failures.append({
            "type": "tool",
            "name": result.name,
            "message": result.message,
            "install_cmd": result.install_cmd,
            "plugin": plugin_name,
        })

    # Check path entries
    for path_entry in manifest.get("path_entries", []):
        expanded = os.path.expanduser(path_entry)
        result = check_path_entry(path_entry)
        if result.passed:
            ok_entries.append(f"{prefix}PATH {result.path}: ok - {result.message}")
        else:
            # Attempt persistent remediation: add to shell RC files
            from .path_check import add_path_to_shell_config
            ok, msg = add_path_to_shell_config(path_entry)
            action_entries.append(f"{prefix}PATH {result.path}: not in PATH, added to shell config - {msg}")
        # Add to current process PATH so subsequent phases can find tools there
        current_path = os.environ.get("PATH", "")
        if os.path.normpath(expanded) not in [os.path.normpath(d) for d in current_path.split(os.pathsep)]:
            os.environ["PATH"] = expanded + os.pathsep + current_path

    # Check venv
    venv_def = manifest.get("venv")
    if venv_def:
        check_imports = venv_def.get("check_imports", [])
        result = check_venv(data_dir, plugin_root, check_imports)

        if not result.passed:
            # Attempt auto-remediation — run uv sync with venv in data dir
            uv_cmd = f"uv sync --project {plugin_root}"
            action_entries.append(f"{prefix}venv: not ready, running `{uv_cmd}`")
            import shutil
            import subprocess as _sp
            venv_path = os.path.join(data_dir, ".venv")

            # Find uv — may have just been installed to ~/.local/bin
            local_bin = os.path.expanduser("~/.local/bin")
            uv_bin = shutil.which("uv")
            if not uv_bin:
                # Check ~/.local/bin directly (not yet in PATH)
                for name in ("uv", "uv.exe", "uv.EXE"):
                    candidate = os.path.join(local_bin, name)
                    if os.path.isfile(candidate):
                        uv_bin = candidate
                        break

            if uv_bin:
                env = dict(os.environ, UV_PROJECT_ENVIRONMENT=venv_path)
                # Ensure ~/.local/bin in PATH for uv's own child processes
                if local_bin not in env.get("PATH", ""):
                    env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")
                try:
                    proc = _sp.run(
                        [uv_bin, "sync", "--project", plugin_root],
                        env=env, capture_output=True, timeout=120,
                    )
                    # Re-check after remediation
                    result = check_venv(data_dir, plugin_root, check_imports)
                    if result.passed:
                        action_entries.append(f"{prefix}venv: created")
                    elif proc.returncode != 0:
                        stderr_text = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
                        action_entries.append(f"{prefix}venv: uv sync failed (exit {proc.returncode}): {stderr_text[:200]}")
                    else:
                        action_entries.append(f"{prefix}venv: uv sync completed but re-check failed: {result.message}")
                except (_sp.SubprocessError, OSError) as exc:
                    action_entries.append(f"{prefix}venv: uv sync error: {exc}")
            else:
                action_entries.append(f"{prefix}venv: uv not found on PATH or in ~/.local/bin")

        if result.passed:
            ok_entries.append(f"{prefix}venv: ok - {result.message}")
            exported = export_venv_env_var(plugin_name, data_dir)
            if exported:
                ok_entries.append(f"{prefix}venv: exported {exported} to CLAUDE_ENV_FILE")
        else:
            action_entries.append(f"{prefix}venv: FAILED - {result.message}")
            failures.append({
                "type": "venv",
                "message": result.message,
                "remediation_cmd": result.remediation_cmd,
                "plugin": plugin_name,
            })

    # Check git deps
    for dep_def in manifest.get("git_deps", []):
        result = check_git_dep(
            data_dir,
            dep_def["url"],
            dep_def["branch"],
            dep_def.get("sparse_paths"),
            dep_def.get("commit"),
        )
        if result.passed:
            ok_entries.append(f"{prefix}git {result.repo_name}: ok - {result.message}")
        else:
            from .git_dep_check import clone_git_dep, pull_git_dep
            import os as _os
            target_path = result.target_path
            pinned_commit = dep_def.get("commit")
            if not _os.path.isdir(target_path):
                # Not cloned — clone it
                action_entries.append(f"{prefix}git {result.repo_name}: not cloned, cloning from {dep_def['url']}")
                ok, msg = clone_git_dep(dep_def["url"], dep_def["branch"], target_path, dep_def.get("sparse_paths"), pinned_commit)
            elif pinned_commit:
                # Exists but wrong commit — fetch and checkout
                action_entries.append(f"{prefix}git {result.repo_name}: {result.message}, checking out {pinned_commit[:7]}")
                try:
                    import subprocess as _sp2
                    from .git_dep_check import _git_exe
                    _git = _git_exe()
                    _sp2.run([_git, "-C", target_path, "fetch"], capture_output=True, timeout=60)
                    r = _sp2.run([_git, "-C", target_path, "checkout", pinned_commit], capture_output=True, text=True, timeout=30)
                    ok = r.returncode == 0
                    msg = f"checked out {pinned_commit[:7]}" if ok else (r.stderr.strip() or "checkout failed")
                except (_sp2.SubprocessError, OSError) as e:
                    ok, msg = False, str(e)
            else:
                # Exists but wrong branch or broken — pull
                action_entries.append(f"{prefix}git {result.repo_name}: {result.message}, pulling")
                ok, msg = pull_git_dep(target_path)

            if ok:
                action_entries.append(f"{prefix}git {result.repo_name}: {msg}")
            else:
                action_entries.append(f"{prefix}git {result.repo_name}: FAILED - {msg}")
                failures.append({
                    "type": "git_dep",
                    "name": result.repo_name,
                    "message": msg,
                    "remediation_cmd": result.remediation_cmd,
                    "plugin": plugin_name,
                })

    # Sync files to data directory
    # Rule: successful outcomes -> ok_entries (verbose-only); failures/actions -> action_entries (always shown)
    for sync_def in manifest.get("sync_to_data", []):
        src_rel = sync_def["src"]
        dst_rel = sync_def["dst"]
        src = os.path.join(plugin_root, src_rel)
        dst = os.path.join(data_dir, dst_rel)
        if not os.path.isdir(src):
            action_entries.append(f"{prefix}sync {src_rel} -> {dst_rel}: FAILED - source not found")
            failures.append({
                "type": "sync_to_data",
                "src": src_rel,
                "dst": dst_rel,
                "message": f"source directory not found: {src}",
                "plugin": plugin_name,
            })
            continue
        import shutil
        os.makedirs(dst, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        ok_entries.append(f"{prefix}sync {src_rel} -> {dst_rel}: ok")

    # Check marketplace entries (before json_entries — marketplaces must be cloned
    # before we merge fields like autoUpdate into known_marketplaces.json)
    for mkt_def in manifest.get("marketplaces", []):
        mkt_name = mkt_def.get("name", "")
        source_url = mkt_def.get("source", "")
        if not mkt_name or not source_url:
            continue

        from .marketplace_lifecycle import check_marketplace_exists, check_marketplace_current, add_marketplace, update_marketplace

        mkt_result = check_marketplace_exists(mkt_name)
        if mkt_result.passed:
            # Check if alwaysUpdate is set — if so, check for updates
            if mkt_def.get("alwaysUpdate"):
                current_result = check_marketplace_current(mkt_name)
                if current_result.passed:
                    ok_entries.append(f"{prefix}marketplace {mkt_name}: up to date")
                else:
                    action_entries.append(f"{prefix}marketplace {mkt_name}: updating (alwaysUpdate)")
                    upd_result = update_marketplace(mkt_name)
                    if upd_result.passed:
                        action_entries.append(f"{prefix}marketplace {mkt_name}: updated")
                    else:
                        action_entries.append(f"{prefix}marketplace {mkt_name}: update failed - {upd_result.message}")
                        failures.append({
                            "type": "marketplace",
                            "name": mkt_name,
                            "message": upd_result.message,
                            "plugin": plugin_name,
                        })
            else:
                ok_entries.append(f"{prefix}marketplace {mkt_name}: ok")
        else:
            # Auto-add marketplace via CLI
            action_entries.append(f"{prefix}marketplace {mkt_name}: not found, adding")
            add_result = add_marketplace(source_url, mkt_name)
            if add_result.passed:
                action_entries.append(f"{prefix}marketplace {mkt_name}: added via `claude plugin marketplace add {source_url}` (modifies known_marketplaces.json)")
            else:
                action_entries.append(f"{prefix}marketplace {mkt_name}: FAILED - {add_result.message}")
                failures.append({
                    "type": "marketplace",
                    "name": mkt_name,
                    "message": add_result.message,
                    "plugin": plugin_name,
                })

    # Check plugin entries
    for plugin_def in manifest.get("plugins", []):
        plugin_ref = plugin_def.get("ref", "")
        enabled = plugin_def.get("enabled", True)
        desired_scope = plugin_def.get("scope", "user")
        min_version = plugin_def.get("min_version", "")
        if not plugin_ref:
            continue

        from .marketplace_lifecycle import check_plugin_installed, install_plugin

        # Compute CLI ref for logging (marketplace:plugin → plugin@marketplace)
        cli_ref = f"{plugin_ref.split(':', 1)[1]}@{plugin_ref.split(':', 1)[0]}" if ":" in plugin_ref else plugin_ref

        # Check if plugin is installed (global registry, handles both ref formats)
        install_result = check_plugin_installed(plugin_ref)
        if not install_result.passed:
            # Auto-install via CLI
            action_entries.append(f"{prefix}plugin {plugin_ref}: not installed, running `claude plugin install {cli_ref} --scope {desired_scope}`")
            inst = install_plugin(plugin_ref, scope=desired_scope)
            if inst.passed:
                action_entries.append(f"{prefix}plugin {plugin_ref}: installed (added '{cli_ref}' to settings.json enabledPlugins)")
            else:
                action_entries.append(f"{prefix}plugin {plugin_ref}: FAILED - {inst.message}")
                failures.append({
                    "type": "plugin",
                    "ref": plugin_ref,
                    "message": inst.message,
                    "plugin": plugin_name,
                })
                continue

        from .marketplace_lifecycle import enable_plugin_in_claude, disable_plugin_in_claude, check_plugin_enabled, check_plugin_enabled_at_scope, check_plugin_version, update_plugin, ensure_registry_scope

        # Ensure plugin is enabled at desired scope (reads settings file directly,
        # not installed_plugins.json which can have stale scope metadata)
        if install_result.passed:
            scope_check = check_plugin_enabled_at_scope(plugin_ref, desired_scope, project_dir)
            if not scope_check.passed:
                action_entries.append(f"{prefix}plugin {plugin_ref}: {scope_check.message}, installing at {desired_scope} scope")
                reinst = install_plugin(plugin_ref, scope=desired_scope)
                if reinst.passed:
                    action_entries.append(f"{prefix}plugin {plugin_ref}: installed at {desired_scope} scope")
                else:
                    action_entries.append(f"{prefix}plugin {plugin_ref}: install at {desired_scope} failed - {reinst.message}")
                    failures.append({
                        "type": "plugin",
                        "ref": plugin_ref,
                        "message": f"scope install failed: {reinst.message}",
                        "plugin": plugin_name,
                    })
                    continue

            # Sync installed_plugins.json scope to match desired scope.
            # CLI commands (update, uninstall) read scope from this file and
            # fail if it's stale. Fix the data before running those commands.
            ensure_registry_scope(plugin_ref, desired_scope)

        if enabled:
            # Check if version is up to date (only for already-installed plugins)
            if install_result.passed:
                ver_result = check_plugin_version(plugin_ref)
                if not ver_result.up_to_date:
                    action_entries.append(f"{prefix}plugin {plugin_ref}: outdated ({ver_result.message}), running `claude plugin update {cli_ref}`")
                    upd_result = update_plugin(plugin_ref, scope=desired_scope)
                    if upd_result.passed:
                        action_entries.append(f"{prefix}plugin {plugin_ref}: updated to {ver_result.latest_version}")
                    else:
                        action_entries.append(f"{prefix}plugin {plugin_ref}: update failed - {upd_result.message}")

            # Check min_version constraint (auto-update, then fail if still unsatisfied)
            if install_result.passed and min_version:
                from .marketplace_lifecycle import check_plugin_min_version
                min_result = check_plugin_min_version(plugin_ref, min_version)
                if not min_result.up_to_date:
                    action_entries.append(f"{prefix}plugin {plugin_ref}: installed {min_result.installed_version} < required {min_version}, running `claude plugin update {cli_ref}`")
                    upd_result = update_plugin(plugin_ref, scope=desired_scope)
                    if upd_result.passed:
                        recheck = check_plugin_min_version(plugin_ref, min_version)
                        if recheck.up_to_date:
                            action_entries.append(f"{prefix}plugin {plugin_ref}: updated to {recheck.installed_version} (satisfies >= {min_version})")
                        else:
                            action_entries.append(f"{prefix}plugin {plugin_ref}: installed {recheck.installed_version} < required {min_version}, update failed to satisfy constraint")
                            failures.append({
                                "type": "plugin",
                                "ref": plugin_ref,
                                "message": f"min_version {min_version} not satisfied (installed {recheck.installed_version})",
                                "plugin": plugin_name,
                            })
                    else:
                        action_entries.append(f"{prefix}plugin {plugin_ref}: installed {min_result.installed_version} < required {min_version}, update failed - {upd_result.message}")
                        failures.append({
                            "type": "plugin",
                            "ref": plugin_ref,
                            "message": f"min_version {min_version} not satisfied: {upd_result.message}",
                            "plugin": plugin_name,
                        })

            # Check enabled state at desired scope
            enabled_result = check_plugin_enabled_at_scope(plugin_ref, desired_scope, project_dir)
            if enabled_result.passed:
                ok_entries.append(f"{prefix}plugin {plugin_ref}: ok")
            else:
                action_entries.append(f"{prefix}plugin {plugin_ref}: installed but not enabled at {desired_scope} scope, running `claude plugin enable {cli_ref}`")
                en_result = enable_plugin_in_claude(plugin_ref)
                if en_result.passed:
                    action_entries.append(f"{prefix}plugin {plugin_ref}: enabled (added '{cli_ref}' to settings.json enabledPlugins)")
                else:
                    action_entries.append(f"{prefix}plugin {plugin_ref}: enable failed - {en_result.message}")
                    failures.append({
                        "type": "plugin",
                        "ref": plugin_ref,
                        "message": en_result.message,
                        "plugin": plugin_name,
                    })
        else:
            # Only disable if currently enabled (check before acting)
            enabled_result = check_plugin_enabled(plugin_ref)
            if not enabled_result.passed:
                ok_entries.append(f"{prefix}plugin {plugin_ref}: already disabled")
            else:
                dis_result = disable_plugin_in_claude(plugin_ref)
                if dis_result.passed:
                    action_entries.append(f"{prefix}plugin {plugin_ref}: disabled via `claude plugin disable {cli_ref}` (removed '{cli_ref}' from settings.json enabledPlugins)")
                else:
                    action_entries.append(f"{prefix}plugin {plugin_ref}: disable failed - {dis_result.message}")
                    failures.append({
                        "type": "plugin",
                        "ref": plugin_ref,
                        "message": dis_result.message,
                        "plugin": plugin_name,
                    })

    # Variable resolution for subsequent phases
    from .var_resolve import build_variables, resolve_vars
    config = _load_plugin_config(data_dir)
    variables = build_variables(plugin_root, data_dir, config)

    # Check INI settings (project-scoped — skip when no project detected)
    if not project_detected and manifest.get("ini_settings"):
        ok_entries.append(f"{prefix}ini_settings: skipped (no project detected)")
    for ini_def in (manifest.get("ini_settings", []) if project_detected else []):
        ini_file = resolve_vars(ini_def["file"], variables)
        if ini_file is None:
            ok_entries.append(f"{prefix}ini {ini_def['file']}: skipped (unresolved vars)")
            continue

        section = ini_def["section"]
        # Ensure section has brackets for check/write
        section_header = section if section.startswith("[") else f"[{section}]"

        from .ini_check import check_ini_setting, write_ini_setting
        for key, expected in ini_def.get("settings", {}).items():
            result = check_ini_setting(ini_file, section_header, key, expected)
            if result.passed:
                ok_entries.append(f"{prefix}ini {key}: ok")
            else:
                try:
                    write_ini_setting(ini_file, section_header, key, expected)
                    action_entries.append(f"{prefix}ini {key}: set to {expected}")
                except OSError as e:
                    action_entries.append(f"{prefix}ini {key}: FAILED - {e}")
                    failures.append({
                        "type": "ini",
                        "file": ini_file,
                        "key": key,
                        "message": str(e),
                        "plugin": plugin_name,
                    })

    # Check JSON entries (after marketplaces — so known_marketplaces.json has valid entries)
    for json_def in manifest.get("json_entries", []):
        ref_path = resolve_vars(json_def.get("reference", ""), variables)
        target_path = resolve_vars(json_def.get("target", ""), variables)
        if ref_path is None or target_path is None:
            ok_entries.append(f"{prefix}json: skipped (unresolved vars)")
            continue

        # Resolve reference relative to plugin root if not absolute
        if not os.path.isabs(ref_path):
            ref_path = os.path.join(plugin_root, ref_path)
        # Expand ~ in target path
        target_path = os.path.expanduser(target_path)

        merge_fields = json_def.get("merge_fields", [])
        preserve_fields = json_def.get("preserve_fields", [])

        from .json_check import check_json_entries, merge_json_entries
        result = check_json_entries(ref_path, target_path, merge_fields, preserve_fields)
        if result.passed:
            ok_entries.append(f"{prefix}json {os.path.basename(target_path)}: ok")
        else:
            result = merge_json_entries(ref_path, target_path, merge_fields, preserve_fields)
            if result.passed:
                action_entries.append(f"{prefix}json {os.path.basename(target_path)}: merged")
            else:
                action_entries.append(f"{prefix}json {os.path.basename(target_path)}: FAILED - {result.message}")
                failures.append({
                    "type": "json",
                    "target": target_path,
                    "message": result.message,
                    "plugin": plugin_name,
                })

    # Check PyPI packages
    for pypi_def in manifest.get("pypi_packages", []):
        extract_to = resolve_vars(pypi_def["extract_to"], variables)
        if extract_to is None:
            ok_entries.append(f"{prefix}pypi {pypi_def['package']}: skipped (unresolved vars)")
            continue

        from .pypi_check import check_pypi_package, download_and_extract
        result = check_pypi_package(pypi_def["package"], extract_to)
        if result.passed:
            ok_entries.append(f"{prefix}pypi {result.package}: ok")
        else:
            extract_pattern = pypi_def.get("extract_pattern")
            result = download_and_extract(pypi_def["package"], extract_to, extract_pattern)
            if result.passed:
                action_entries.append(f"{prefix}pypi {result.package}: {result.message}")
            else:
                action_entries.append(f"{prefix}pypi {result.package}: FAILED - {result.message}")
                failures.append({
                    "type": "pypi",
                    "package": pypi_def["package"],
                    "message": result.message,
                    "plugin": plugin_name,
                })

    # Script phase
    script_def = manifest.get("script")
    if script_def:
        script_failures = _run_script_phase(
            script_def, plugin_root, data_dir, config, action_entries,
            prefix=prefix, plugin_name=plugin_name, project_dir=project_dir,
        )
        failures.extend(script_failures)

    return failures


def _load_plugin_config(data_dir):
    """Load plugin config from data_dir if it exists. Returns dict or empty."""
    try:
        from .config_check import load_yaml_config
        import os
        config_path = os.path.join(data_dir, "config.yaml")
        if os.path.isfile(config_path):
            return load_yaml_config(config_path)
    except Exception:
        pass
    return {}


def _find_plugins_dir(plugin_root):
    """Find the directory containing installed_plugins.json by walking up from plugin_root.

    Works for both layouts:
    - Dev: ~/Dev/<marketplace>/plugins/bootstrap → finds at ../installed_plugins.json
    - Cache: ~/.claude/plugins/cache/<mkt>/bootstrap/<ver> → finds at ~/.claude/plugins/installed_plugins.json

    Falls back to os.path.dirname(plugin_root) if not found (original behavior).
    """
    d = os.path.dirname(plugin_root)
    for _ in range(10):  # safety limit
        candidate = os.path.join(d, "installed_plugins.json")
        if os.path.isfile(candidate):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    # Fallback: immediate parent (original behavior)
    return os.path.dirname(plugin_root)



def _run_script_phase(script_def, plugin_root, data_dir, config, log_entries, prefix="", plugin_name="", project_dir=None):
    """Run a custom bootstrap script. Returns list of failures."""
    import importlib.util

    script_path = os.path.join(plugin_root, script_def["path"])
    entry_point = script_def.get("entry_point", "bootstrap")

    if not os.path.isfile(script_path):
        log_entries.append(f"{prefix}script: skipped ({script_def['path']} not found)")
        return []

    # Build context object for the script
    ctx = _ScriptContext(config, data_dir, plugin_root, log_entries, prefix, plugin_name, project_dir)

    try:
        spec = importlib.util.spec_from_file_location("_bootstrap_script", script_path)
        if spec is None or spec.loader is None:
            log_entries.append(f"{prefix}script: FAILED - could not load {script_def['path']}")
            return []
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        func = getattr(module, entry_point, None)
        if func is None:
            log_entries.append(f"{prefix}script: FAILED - {entry_point}() not found in {script_def['path']}")
            return []

        func(ctx)
        return ctx.failures
    except Exception as e:
        log_entries.append(f"{prefix}script: FAILED - {e}")
        return []


class _ScriptContext:
    """Context object passed to custom bootstrap scripts."""

    def __init__(self, config, data_dir, plugin_root, log_entries, prefix, plugin_name, project_dir=None):
        self.config = dict(config) if config else {}
        self.config_path = os.path.join(data_dir, "config.yaml")
        self.data_dir = data_dir
        self.plugin_root = plugin_root
        # Canonical project root the engine was invoked against (Claude Code's
        # launch CWD). May be None for non-project sessions. Scripts should use
        # this instead of re-deriving from Path.cwd() — never walk up looking
        # for .claude/ since Claude Code itself does not.
        self.project_dir = project_dir
        self.failures = []
        self._log_entries = log_entries
        self._prefix = prefix
        self._plugin_name = plugin_name

    def save_config(self) -> None:
        """Write config back to disk."""
        from .config_check import save_yaml_config
        save_yaml_config(self.config_path, self.config)

    def add_failure(self, failure_type: str, **kwargs) -> None:
        """Register a failure for fix-all aggregation."""
        failure = {"type": failure_type, "plugin": self._plugin_name}
        failure.update(kwargs)
        self.failures.append(failure)

    def log(self, message: str) -> None:
        """Add a log entry."""
        self._log_entries.append(f"{self._prefix}{message}")


def _read_new_log_entries(data_dir, start_time=None):
    """Read log entries since the last time we displayed them.

    Uses a 'last_displayed_at' file to track the timestamp of the last display.
    Does NOT update the marker — call _update_display_marker() after all entries are written.

    A `start_time` floor (default: now - 120s) bounds the lookback window even
    when the marker is missing or stale. This prevents the engine from dumping
    the entire historical log to the user when the marker is reset (e.g. on
    fresh installs, version downgrades, or after a corrupt-marker recovery).
    Without this bound, the user would see months of stale entries — including
    historical failures already resolved — every time the marker disappears.
    """
    from .log import LOG_FILENAME
    log_file = os.path.join(data_dir, LOG_FILENAME)
    marker_file = os.path.join(data_dir, "last_displayed_at")

    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return ""

    # Read last-displayed timestamp
    last_displayed = ""
    try:
        with open(marker_file, "r") as f:
            last_displayed = f.read().strip()
    except FileNotFoundError:
        pass

    # Compute the floor: 120 seconds before start_time covers shell startup
    # plus clock skew without including any pre-session content.
    if start_time is None:
        start_time = datetime.now(timezone.utc)
    floor_dt = start_time - timedelta(seconds=120)
    floor = floor_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Effective marker is the LATER of last_displayed and the floor. This means
    # entries older than `start_time - 120s` are never re-displayed, even if the
    # marker is missing or stale.
    effective_marker = max(last_displayed, floor)

    # Filter to blocks strictly after the effective marker.
    # Timestamps are only on header lines (--- label timestamp ---).
    # Untimestamped headers (or content before any header) start excluded —
    # they only get included if a subsequent timestamped header lets them in.
    new_lines = []
    include_block = False
    for line in lines:
        ts = _extract_timestamp(line)
        if ts:
            # This is a header line — decide whether to include this block
            include_block = ts > effective_marker
        if include_block:
            new_lines.append(line)

    if not new_lines:
        return ""

    return "".join(new_lines).rstrip("\n")


def _update_display_marker(data_dir):
    """Update the display marker to the latest timestamp in the log file."""
    from .log import LOG_FILENAME
    log_file = os.path.join(data_dir, LOG_FILENAME)
    marker_file = os.path.join(data_dir, "last_displayed_at")

    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return

    latest_ts = ""
    for line in reversed(lines):
        ts = _extract_timestamp(line)
        if ts:
            latest_ts = ts
            break
    if latest_ts:
        os.makedirs(data_dir, exist_ok=True)
        with open(marker_file, "w") as f:
            f.write(latest_ts)


def _extract_timestamp(line):
    """Extract ISO timestamp from a log header line.

    Format: --- label YYYY-MM-DDTHH:MM:SSZ ---
    Returns the timestamp string or empty string.
    Rejects footer lines (--- label done in X.Xs ---).
    """
    line = line.strip()
    if line.startswith("---") and line.endswith("---"):
        parts = line.split()
        if len(parts) >= 3:
            candidate = parts[-2]
            # Must look like an ISO timestamp (starts with digit, contains T)
            if candidate and candidate[0].isdigit() and "T" in candidate:
                return candidate
    return ""


def _write_atomic(path, content):
    """Write content to path atomically via tmp+rename."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(content)
    os.replace(tmp, path)


def emit_success_response(log_content, label="bootstrap", output_file=None):
    """Emit hook JSON showing bootstrap log to user and agent."""
    if output_file:
        # Background mode: consumed by UserPromptSubmit hook.
        # `systemMessage` is user-facing, `additionalContext` is Claude-facing.
        response = {
            "continue": True,
            "suppressOutput": False,
            "systemMessage": f"{label} -> bootstrap complete:\n{log_content}",
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"{label} -> bootstrap complete:\n{log_content}",
            },
        }
        _write_atomic(output_file, json.dumps(response))
    else:
        # SessionStart hook: supports hookSpecificOutput with hookEventName
        response = {
            "continue": True,
            "suppressOutput": False,
            "systemMessage": f"{label}:\n{log_content}",
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": f"{label} -> bootstrap complete:\n{log_content}",
            },
        }
        print(json.dumps(response))


def emit_failure_response(failures, current_os, log_content, label="bootstrap", output_file=None, persistent_output_file=None):
    """Emit hook JSON with fix-all directives to stdout or file.

    If persistent_output_file is provided AND any failure is marked
    `persist_across_sessions`, the same JSON is also written to that path so
    subsequent sessions can re-prime bootstrap_display.pending from it.
    """
    agent_lines = [f"{label} -> Setup issues found. Fix in order:\n"]

    for i, f in enumerate(failures, 1):
        plugin_tag = f" [{f['plugin']}]" if f.get("plugin", "bootstrap") != "bootstrap" else ""
        if f["type"] == "tool":
            agent_lines.append(f"{i}. Install {f['name']}{plugin_tag}: `{f['install_cmd'] or 'see documentation'}`")
        elif f["type"] == "path":
            agent_lines.append(f"{i}. Add {f['path']} to PATH{plugin_tag}")
        elif f["type"] == "venv":
            agent_lines.append(f"{i}. Setup venv{plugin_tag}: `{f['remediation_cmd']}`")
        elif f["type"] == "git_dep":
            agent_lines.append(f"{i}. Clone {f['name']}{plugin_tag}: `{f['remediation_cmd']}`")
        elif f["type"] == "config":
            agent_lines.append(f"{i}. {f['agent_msg']}{plugin_tag}")
        elif f["type"] == "project_config":
            agent_lines.append(f"{i}. {f['agent_msg']}{plugin_tag}")
        elif f["type"] == "ini":
            agent_lines.append(f"{i}. Fix INI setting {f['key']} in {f['file']}{plugin_tag}: {f['message']}")
        elif f["type"] == "pypi":
            agent_lines.append(f"{i}. Download {f['package']} from PyPI{plugin_tag}: {f['message']}")
        elif f["type"] == "script":
            agent_lines.append(f"{i}. Script issue{plugin_tag}: {f.get('message', 'see log')}")
        elif f["type"] == "json":
            agent_lines.append(f"{i}. Merge JSON entries into {f['target']}{plugin_tag}: {f['message']}")
        elif f["type"] == "marketplace":
            agent_lines.append(f"{i}. Add marketplace {f['name']}{plugin_tag}: {f['message']}")
        elif f["type"] == "plugin":
            agent_lines.append(f"{i}. Install plugin {f['ref']}{plugin_tag}: {f['message']}")
        elif f["type"] == "sync_to_data":
            agent_lines.append(f"{i}. Sync {f['src']} -> {f['dst']}{plugin_tag}: {f['message']}")
        elif f["type"] == "python_stub":
            agent_lines.append(f"{i}. python stub fix needed{plugin_tag}: {f.get('agent_msg', f.get('message', 'see log'))}")
        elif f["type"] == "manifest_parse":
            agent_lines.append(f"{i}. {f.get('agent_msg', f.get('message', 'manifest parse error'))}{plugin_tag}")

    agent_lines.append("\nAfter fixing, type 'fix-all' or 'fixed' to re-run bootstrap, or restart Claude Code.")
    agent_msg = "\n".join(agent_lines)

    # Special-case: if all failures are python_stub, emit a focused, user-friendly
    # response (no log_content noise, no "fix-all" boilerplate — the user can't
    # tell Claude to fix this since it requires admin elevation on their machine).
    python_stub_failures = [f for f in failures if f["type"] == "python_stub"]
    only_python_stub = bool(python_stub_failures) and len(python_stub_failures) == len(failures)

    if only_python_stub:
        # Use the first python_stub failure's structured messages.
        ps = python_stub_failures[0]
        focused_user_msg = ps.get("user_msg", ps.get("message", ""))
        focused_agent_msg = ps.get("agent_msg", ps.get("message", ""))
        if output_file:
            response = {
                "systemMessage": f"{label}: {focused_user_msg}",
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": f"{label} -> {focused_agent_msg}",
                },
            }
            _write_atomic(output_file, json.dumps(response))
            if persistent_output_file:
                _write_atomic(persistent_output_file, json.dumps(response))
        else:
            response = {
                "continue": True,
                "suppressOutput": False,
                "systemMessage": f"{label}: {focused_user_msg}",
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": f"{label} -> {focused_agent_msg}",
                },
            }
            print(json.dumps(response))
        return

    # General path: mixed or non-python_stub failures.
    if output_file:
        # Background mode: consumed by UserPromptSubmit hook.
        # `additionalContext` gives Claude the full log + fix directives,
        # `systemMessage` is user-facing only.
        user_msg = "Tell Claude 'fix-all' to auto-fix, or 'fixed' after manual fixes."
        response = {
            "systemMessage": f"{label} -> Setup issues found. Fix in order:\n{log_content}\n\n{user_msg}",
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"{label} -> bootstrap complete:\n{log_content}\n\n{agent_msg}",
            },
        }
        _write_atomic(output_file, json.dumps(response))
        if persistent_output_file:
            _write_atomic(persistent_output_file, json.dumps(response))
    else:
        # SessionStart hook: supports hookSpecificOutput with hookEventName
        response = {
            "continue": True,
            "suppressOutput": False,
            "systemMessage": f"{label}:\n{log_content}",
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": agent_msg,
            },
        }
        print(json.dumps(response))


if __name__ == "__main__":
    main()
