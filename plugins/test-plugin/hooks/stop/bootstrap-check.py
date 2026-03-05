#!/usr/bin/env python3
"""Stop hook: Re-run bootstrap checks so VS Code users see failures.

The SessionStart hook runs before the VS Code conversation window opens,
making its output invisible. This Stop hook re-runs the read-only subset
(cache validation + system tool checks + config check) at turn end, when
the message is visible to both the user and Claude.

Decision logic:
  stop_hook_active == true  -> exit 0 (avoid conflicts)
  cache valid + config ok   -> exit 0 (everything fine)
  system tools failing      -> block with remediation message
  config missing            -> block with setup guidance
  tools ok but cache stale  -> block with "restart to complete setup"
"""

import json
import os
import shutil
import subprocess
import sys


def _resolve_paths():
    """Derive plugin root, data dir, and bootstrap plugin root."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    hooks_dir = os.path.dirname(script_dir)
    plugin_root = os.path.dirname(hooks_dir)
    plugin_data = os.path.join(
        os.path.expanduser("~"), ".claude", "plugins", "data", "test-plugin"
    )
    # Bootstrap plugin is a sibling: marketplace/plugins/bootstrap
    marketplace_root = os.path.dirname(os.path.dirname(plugin_root))
    bootstrap_root = os.path.join(marketplace_root, "plugins", "bootstrap")
    return plugin_root, plugin_data, bootstrap_root


def _python_works(exe):
    """Check if a Python executable actually runs."""
    try:
        result = subprocess.run(
            [exe, "-c", "print('ok')"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _find_python():
    """Find a working Python executable for running setup.py."""
    _, plugin_data, _ = _resolve_paths()
    venv_dir = os.path.join(plugin_data, ".venv")

    # Prefer venv Python (but verify it works)
    if sys.platform == "win32":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")

    if os.path.isfile(venv_python) and _python_works(venv_python):
        return venv_python

    # Fall back to system Python (verify each candidate works)
    for name in ("python3", "python"):
        path = shutil.which(name)
        if path and _python_works(path):
            return path

    return sys.executable


def _run_config_check(python_exe, setup_script, data_dir):
    """Run setup.py --check and return (success, stdout)."""
    result = subprocess.run(
        [python_exe, setup_script, "--check", "--data-dir", data_dir],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stdout.strip()


def _check_tools(manifest, current_os):
    """Check tools from bootstrap.json, return list of failures."""
    from tool_check import check_tool

    failures = []
    for tool_def in manifest.get("tools", []):
        name = tool_def["name"]
        install_cmds = tool_def.get("install", {})
        result = check_tool(name, install_cmds, current_os)
        if not result.passed:
            failures.append({
                "name": result.name,
                "message": result.message,
                "install_cmd": result.install_cmd,
            })
    return failures


def _format_tool_failures(failures, current_os):
    """Build a markdown remediation message from tool check failures."""
    lines = ["## Bootstrap: System Tool Failures\n", "Fix these in order:\n"]
    for i, f in enumerate(failures, 1):
        cmd = f["install_cmd"] or "see documentation"
        lines.append(f"{i}. **{f['name']}** — not found. Install: `{cmd}`")
    lines.append(
        "\nAfter all fixes succeed, restart Claude Code so bootstrap can "
        "verify the changes."
    )
    return "\n".join(lines)


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError) as e:
        print(json.dumps({
            "decision": "block",
            "reason": f"Bootstrap check hook error: invalid JSON input: {e}",
        }))
        sys.exit(1)

    if input_data.get("stop_hook_active"):
        sys.exit(0)

    plugin_root, plugin_data, bootstrap_root = _resolve_paths()

    # Add bootstrap engine libs to path
    sys.path.insert(0, os.path.join(bootstrap_root, "lib"))

    from cache import check_cache
    from platform_detect import detect_os

    manifest_path = os.path.join(plugin_root, "bootstrap.json")

    # Step 1: Check validation cache
    cache_ok = check_cache(plugin_data, [manifest_path])

    if not cache_ok:
        # Cache miss — run system tool checks from bootstrap.json
        current_os = detect_os()

        if os.path.isfile(manifest_path):
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        else:
            manifest = {}

        failures = _check_tools(manifest, current_os)

        if failures:
            reason = _format_tool_failures(failures, current_os)
            print(json.dumps({"decision": "block", "reason": reason}))
            return

        # Tools fine but cache stale
        reason = (
            "## Bootstrap: Setup Incomplete\n\n"
            "System tools are present, but the bootstrap cache is stale "
            "(venv or git dependencies may need syncing).\n\n"
            "**Restart Claude Code** to complete setup."
        )
        print(json.dumps({"decision": "block", "reason": reason}))
        return

    # Step 2: Cache valid — check config
    setup_script = os.path.join(plugin_root, "scripts", "setup.py")
    if os.path.isfile(setup_script):
        python_exe = _find_python()
        config_ok, config_out = _run_config_check(python_exe, setup_script, plugin_data)

        if not config_ok:
            reason = (
                "## Bootstrap: Configuration Incomplete\n\n"
                "test-plugin configuration is missing or incomplete.\n\n"
                "Say **'setup test-plugin'** to run the interactive setup, "
                "or invoke the `test-setup` skill."
            )
            print(json.dumps({"decision": "block", "reason": reason}))
            return

    # Everything is fine
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({
            "decision": "block",
            "reason": f"Bootstrap check hook error: {e}",
        }))
        sys.exit(1)
