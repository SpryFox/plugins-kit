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
    """Derive plugin root and data dir from this script's location."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    hooks_dir = os.path.dirname(script_dir)
    plugin_root = os.path.dirname(hooks_dir)
    plugin_data = os.path.join(
        os.path.expanduser("~"), ".claude", "plugins", "data", "test-plugin"
    )
    return plugin_root, plugin_data


def _find_git_bash():
    """Find Git Bash on Windows (avoid WSL bash)."""
    if sys.platform != "win32":
        return "bash"

    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Git", "usr", "bin", "bash.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Git", "bin", "bash.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Git", "usr", "bin", "bash.exe"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    bash_path = shutil.which("bash")
    if bash_path:
        normalized = os.path.normpath(bash_path).lower()
        if "system32" not in normalized and "windowsapps" not in normalized:
            return bash_path

    return "bash"


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
    _, plugin_data = _resolve_paths()
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


def _run_bash_step(bash_exe, script_path, args):
    """Run a bash step script and return (success, stdout)."""
    result = subprocess.run(
        [bash_exe, script_path] + args,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stdout.strip()


def _run_config_check(python_exe, setup_script, data_dir):
    """Run setup.py --check and return (success, stdout)."""
    result = subprocess.run(
        [python_exe, setup_script, "--check", "--data-dir", data_dir],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stdout.strip()


def _format_system_tools_block(step_json):
    """Build a markdown remediation message from check-system-tools.sh JSON."""
    try:
        data = json.loads(step_json)
    except (json.JSONDecodeError, TypeError):
        return "Bootstrap check failed (could not parse tool check output)."

    context_msg = data.get("context_message", "")
    if context_msg:
        decoded = context_msg.replace("\\n", "\n").replace("\\t", "\t")
        return (
            "## Bootstrap: System Tool Failures\n\n"
            "Fix these in order:\n\n"
            f"{decoded}\n\n"
            "'fix-all' means fix each failure in the order listed above. "
            "After all fixes succeed, restart Claude Code so bootstrap can "
            "verify the changes."
        )

    msg = data.get("message", "unknown error")
    return f"## Bootstrap: System Tool Error\n\n{msg}"


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

    plugin_root, plugin_data = _resolve_paths()
    sessionstart_dir = os.path.join(plugin_root, "hooks", "sessionstart")
    bash_exe = _find_git_bash()

    # Step 1: Check validation cache
    cache_script = os.path.join(sessionstart_dir, "validate-cache.sh")
    cache_ok, _cache_out = _run_bash_step(bash_exe, cache_script, [plugin_root, plugin_data])

    if not cache_ok:
        # Cache miss — run system tool checks
        tools_script = os.path.join(sessionstart_dir, "check-system-tools.sh")
        tools_yaml = os.path.join(plugin_root, "system-tools.yaml")
        tools_ok, tools_out = _run_bash_step(bash_exe, tools_script, [tools_yaml])

        if not tools_ok:
            reason = _format_system_tools_block(tools_out)
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
