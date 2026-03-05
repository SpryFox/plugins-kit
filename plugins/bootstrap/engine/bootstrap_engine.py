#!/usr/bin/env python3
"""Bootstrap engine — processes bootstrap manifests and emits hook responses.

Usage:
    python3 bootstrap_engine.py --plugin-root /path/to/bootstrap --data-dir /path/to/data

Exit behavior:
    - Cache hit: bare exit (no stdout, exit 0)
    - All checks pass: write cache, bare exit (no stdout, exit 0)
    - Failures: emit hook JSON to stdout, exit 0
"""

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Bootstrap engine")
    parser.add_argument("--plugin-root", required=True, help="Path to bootstrap plugin root")
    parser.add_argument("--data-dir", required=True, help="Path to bootstrap data directory")
    args = parser.parse_args()

    plugin_root = args.plugin_root
    data_dir = args.data_dir

    # Add lib/ to path for imports
    sys.path.insert(0, os.path.join(plugin_root, "lib"))
    sys.path.insert(0, os.path.join(plugin_root, "engine"))

    from config import load_config
    from cache import check_cache, write_cache, compute_current_hash
    from log import write_log, write_session_header
    from tool_check import check_tool
    from path_check import check_path_entry
    from platform_detect import detect_os
    from plugin_resolve import list_enabled_plugins
    from venv_check import check_venv
    from git_dep_check import check_git_dep

    # Write session separator (one line per engine run, helps reading multi-session logs)
    write_session_header(data_dir)

    # Step 1: Load/migrate config
    defaults_dir = os.path.join(plugin_root, "defaults")
    config = load_config(data_dir, defaults_dir)

    # Step 2: Compute current hash + check cache (self-bootstrap only)
    manifest_path = os.path.join(plugin_root, "bootstrap.json")
    compute_current_hash(data_dir, [manifest_path])
    self_cached = check_cache(data_dir, [manifest_path])
    if self_cached:
        write_log(data_dir, ["bootstrap: cached"])

    current_os = detect_os()
    all_failures = []

    # Step 3: Self-bootstrap (own manifest)
    if not self_cached:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        log_entries = []
        failures = _process_manifest(manifest, current_os, data_dir, plugin_root, log_entries)
        write_log(data_dir, log_entries)

        if failures:
            all_failures.extend(failures)
        else:
            write_cache(data_dir, [manifest_path])

    # Step 4: Process enabled plugins
    # Compute marketplace root: bootstrap is at <marketplace>/plugins/bootstrap
    plugins_dir = os.path.dirname(plugin_root)
    registry_path = os.path.join(plugins_dir, "installed_plugins.json")

    enabled = list_enabled_plugins(config, registry_path, plugins_dir)
    for plugin_info in enabled:
        plugin_manifest_path = os.path.join(plugin_info.install_path, "bootstrap.json")
        if not os.path.isfile(plugin_manifest_path):
            continue

        # Per-plugin data dir and cache
        plugin_data_dir = os.path.join(
            os.path.dirname(data_dir), plugin_info.name
        )
        os.makedirs(plugin_data_dir, exist_ok=True)

        compute_current_hash(plugin_data_dir, [plugin_manifest_path])
        if check_cache(plugin_data_dir, [plugin_manifest_path]):
            write_log(data_dir, [f"{plugin_info.name}: cached"])
            continue

        with open(plugin_manifest_path, "r") as f:
            plugin_manifest = json.load(f)

        log_entries = []
        failures = _process_manifest(
            plugin_manifest, current_os, plugin_data_dir, plugin_info.install_path, log_entries,
            plugin_name=plugin_info.name,
        )
        write_log(data_dir, [f"{plugin_info.name}: {e}" for e in log_entries])

        if failures:
            all_failures.extend(failures)
        else:
            write_cache(plugin_data_dir, [plugin_manifest_path])

    # Step 5: Handle results
    if all_failures:
        emit_failure_response(all_failures, current_os)


def _process_manifest(manifest, current_os, data_dir, plugin_root, log_entries, plugin_name="bootstrap"):
    """Process a single plugin's bootstrap manifest. Returns list of failures."""
    from tool_check import check_tool
    from path_check import check_path_entry
    from venv_check import check_venv
    from git_dep_check import check_git_dep

    failures = []
    prefix = f"{plugin_name}: " if plugin_name != "bootstrap" else ""

    # Check tools
    for tool_def in manifest.get("tools", []):
        name = tool_def["name"]
        install_cmds = tool_def.get("install", {})
        result = check_tool(name, install_cmds, current_os)

        if not result.passed and result.install_cmd:
            # Attempt silent remediation
            from tool_check import run_install
            ok, _output = run_install(result.install_cmd)
            if ok:
                result = check_tool(name, install_cmds, current_os)  # re-check
                if result.passed:
                    log_entries.append(f"{prefix}{result.name}: installed - {result.message}")
                    continue  # no failure to record
            # Install failed or tool still missing after install
            log_entries.append(f"{prefix}{result.name}: FAILED - install attempted but {result.message}")
        else:
            log_entries.append(f"{prefix}{result.name}: {'passed' if result.passed else 'FAILED'} - {result.message}")

        if not result.passed:
            failures.append({
                "type": "tool",
                "name": result.name,
                "message": result.message,
                "install_cmd": result.install_cmd,
                "plugin": plugin_name,
            })

    # Check path entries
    for path_entry in manifest.get("path_entries", []):
        result = check_path_entry(path_entry)
        log_entries.append(f"{prefix}PATH {result.path}: {'passed' if result.passed else 'FAILED'} - {result.message}")
        if not result.passed:
            failures.append({
                "type": "path",
                "path": result.path,
                "message": result.message,
                "plugin": plugin_name,
            })

    # Check venv
    venv_def = manifest.get("venv")
    if venv_def:
        check_imports = venv_def.get("check_imports", [])
        result = check_venv(data_dir, plugin_root, check_imports)
        log_entries.append(f"{prefix}venv: {'passed' if result.passed else 'FAILED'} - {result.message}")
        if not result.passed:
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
        )
        log_entries.append(f"{prefix}git {result.repo_name}: {'passed' if result.passed else 'FAILED'} - {result.message}")
        if not result.passed:
            failures.append({
                "type": "git_dep",
                "name": result.repo_name,
                "message": result.message,
                "remediation_cmd": result.remediation_cmd,
                "plugin": plugin_name,
            })

    return failures


def emit_failure_response(failures, current_os):
    """Emit hook JSON with fix-all directives to stdout."""
    agent_lines = ["bootstrap -> Setup issues found. Fix in order:\n"]
    user_lines = ["bootstrap -> Setup issues:\n"]

    for i, f in enumerate(failures, 1):
        plugin_tag = f" [{f['plugin']}]" if f.get("plugin", "bootstrap") != "bootstrap" else ""
        if f["type"] == "tool":
            agent_lines.append(f"{i}. Install {f['name']}{plugin_tag}: `{f['install_cmd'] or 'see documentation'}`")
            user_lines.append(f"{i}. {f['name']} not installed{plugin_tag}")
        elif f["type"] == "path":
            agent_lines.append(f"{i}. Add {f['path']} to PATH{plugin_tag}")
            user_lines.append(f"{i}. {f['path']} not in PATH{plugin_tag}")
        elif f["type"] == "venv":
            agent_lines.append(f"{i}. Setup venv{plugin_tag}: `{f['remediation_cmd']}`")
            user_lines.append(f"{i}. Python venv needs setup{plugin_tag}")
        elif f["type"] == "git_dep":
            agent_lines.append(f"{i}. Clone {f['name']}{plugin_tag}: `{f['remediation_cmd']}`")
            user_lines.append(f"{i}. Git dependency {f['name']} missing{plugin_tag}")

    agent_lines.append("\nAfter fixing, type 'fix-all' or restart Claude Code.")
    user_lines.append("\nType 'fix-all' to remediate.")

    agent_msg = "\n".join(agent_lines)
    user_msg = "\n".join(user_lines)

    response = {
        "continue": True,
        "suppressOutput": False,
        "systemMessage": user_msg,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": agent_msg,
        },
    }

    print(json.dumps(response))


if __name__ == "__main__":
    main()
