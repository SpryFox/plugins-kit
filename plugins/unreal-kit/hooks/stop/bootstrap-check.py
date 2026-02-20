#!/usr/bin/env python3
"""Stop hook: Re-run bootstrap checks so VS Code users see failures.

The SessionStart hook runs before the VS Code conversation window opens,
making its output invisible. This Stop hook re-runs the read-only subset
(cache validation + system tool checks) at turn end, when the message
is visible to both the user and Claude.

Decision logic:
  stop_hook_active == true  -> exit 0 (avoid conflicts)
  cache valid               -> exit 0 (everything fine)
  system tools failing      -> block with remediation message
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
    # hooks/stop/bootstrap-check.py -> hooks -> plugin root
    hooks_dir = os.path.dirname(script_dir)
    plugin_root = os.path.dirname(hooks_dir)
    plugin_data = os.path.join(
        os.path.expanduser("~"), ".claude", "plugins", "data", "unreal-kit"
    )
    return plugin_root, plugin_data


def _find_git_bash():
    """Find Git Bash on Windows (avoid WSL bash).

    On Windows, plain 'bash' in subprocess often resolves to WSL's
    C:\\Windows\\System32\\bash.exe. We need Git Bash instead.
    Returns the path to use as the bash executable.
    """
    if sys.platform != "win32":
        return "bash"

    # Try Git Bash at standard install locations
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Git", "usr", "bin", "bash.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Git", "bin", "bash.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Git", "usr", "bin", "bash.exe"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    # Fallback: search PATH but skip known WSL locations
    bash_path = shutil.which("bash")
    if bash_path:
        normalized = os.path.normpath(bash_path).lower()
        if "system32" not in normalized and "windowsapps" not in normalized:
            return bash_path

    # Last resort — hope 'bash' works
    return "bash"


def _run_bash_step(bash_exe, script_path, args):
    """Run a bash step script and return (success, stdout).

    Returns the subprocess stdout regardless of exit code so the caller
    can parse JSON output from both success and failure cases.
    """
    result = subprocess.run(
        [bash_exe, script_path] + args,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stdout.strip()


def _format_system_tools_block(step_json):
    """Build a markdown remediation message from check-system-tools.sh JSON.

    Replicates the logic of format_bootstrap_error_context() and
    format_bootstrap_error_user() from session-bootstrap.sh, but in
    Python using json.loads() instead of sed.
    """
    try:
        data = json.loads(step_json)
    except (json.JSONDecodeError, TypeError):
        return "Bootstrap check failed (could not parse tool check output)."

    context_msg = data.get("context_message", "")
    if context_msg:
        # context_message is already escaped for JSON embedding by the bash
        # script (literal \n instead of real newlines). Decode those escapes.
        decoded = context_msg.replace("\\n", "\n").replace("\\t", "\t")
        return (
            "## Bootstrap: System Tool Failures\n\n"
            "Fix these in order:\n\n"
            f"{decoded}\n\n"
            "'fix-all' means fix each failure in the order listed above. "
            "After all fixes succeed, restart Claude Code so bootstrap can "
            "verify the changes."
        )

    # Fallback: no context_message, use plain message
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

    # Guard: avoid conflicts with other Stop hooks
    if input_data.get("stop_hook_active"):
        sys.exit(0)

    plugin_root, plugin_data = _resolve_paths()
    sessionstart_dir = os.path.join(plugin_root, "hooks", "sessionstart")
    bash_exe = _find_git_bash()

    # Step 1: Check validation cache — if valid, everything is fine
    cache_script = os.path.join(sessionstart_dir, "validate-cache.sh")
    cache_ok, _cache_out = _run_bash_step(bash_exe, cache_script, [plugin_root, plugin_data])
    if cache_ok:
        # Cache hit: bootstrap already validated — allow stop silently
        sys.exit(0)

    # Step 2: Cache miss — run system tool checks (read-only)
    tools_script = os.path.join(sessionstart_dir, "check-system-tools.sh")
    tools_yaml = os.path.join(plugin_root, "system-tools.yaml")
    tools_ok, tools_out = _run_bash_step(bash_exe, tools_script, [tools_yaml])

    if not tools_ok:
        # System tools have failures — block with remediation
        reason = _format_system_tools_block(tools_out)
        print(json.dumps({"decision": "block", "reason": reason}))
        return

    # Step 3: Tools are fine but cache is stale (venv or git deps may need sync)
    reason = (
        "## Bootstrap: Setup Incomplete\n\n"
        "System tools are present, but the bootstrap cache is stale "
        "(venv or git dependencies may need syncing).\n\n"
        "**Restart Claude Code** to complete setup."
    )
    print(json.dumps({"decision": "block", "reason": reason}))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({
            "decision": "block",
            "reason": f"Bootstrap check hook error: {e}",
        }))
        sys.exit(1)
