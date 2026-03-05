#!/usr/bin/env python3
"""Stop hook: Fallback bootstrap for late plugin installs.

When a plugin is installed during startup, SessionStart has already fired.
This Stop hook catches that case by checking the bootstrap cache on every turn.

Fast path (cache hit): only loads cache module, exits immediately.
Slow path (cache miss): runs the full bootstrap engine as a subprocess.

If SessionStart ran, check_cache_fast() uses a pre-computed hash file.
If SessionStart was missed, falls back to computing the hash itself.
"""

import json
import os
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

    # Fast path — only cache module loaded
    sys.path.insert(0, os.path.join(bootstrap_root, "lib"))
    from cache import check_cache_fast, compute_current_hash

    manifest_path = os.path.join(plugin_root, "bootstrap.json")

    result = check_cache_fast(plugin_data)
    if result is None:
        # SessionStart didn't run — compute the hash ourselves
        compute_current_hash(plugin_data, [manifest_path])
        result = check_cache_fast(plugin_data)

    if result:
        # Cache hit — everything is fine
        sys.exit(0)

    # Slow path — cache miss, load logging and run full bootstrap
    from log import write_log

    write_log(plugin_data, ["stop: cache miss, running bootstrap"])

    # Run the full bootstrap engine as a subprocess
    import shutil
    import subprocess

    engine_script = os.path.join(bootstrap_root, "engine", "bootstrap_engine.py")
    bootstrap_data = os.path.join(
        os.path.expanduser("~"), ".claude", "plugins", "data", "bootstrap"
    )

    python_exe = _find_python(plugin_data)
    engine_result = subprocess.run(
        [python_exe, engine_script, "--plugin-root", bootstrap_root, "--data-dir", bootstrap_data],
        capture_output=True,
        text=True,
    )

    if engine_result.stdout.strip():
        # Engine emitted a failure response — forward it
        write_log(plugin_data, ["stop: bootstrap failed"])
        print(engine_result.stdout.strip())
        return

    write_log(plugin_data, ["stop: bootstrap complete"])

    # After engine success, also check config
    setup_script = os.path.join(plugin_root, "scripts", "setup.py")
    if os.path.isfile(setup_script):
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

    sys.exit(0)


def _find_python(plugin_data):
    """Find a working Python executable."""
    import shutil
    import subprocess as sp

    venv_dir = os.path.join(plugin_data, ".venv")
    if sys.platform == "win32":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")

    if os.path.isfile(venv_python) and _python_works(venv_python):
        return venv_python

    for name in ("python3", "python"):
        path = shutil.which(name)
        if path and _python_works(path):
            return path

    return sys.executable


def _python_works(exe):
    """Check if a Python executable actually runs."""
    import subprocess as sp
    try:
        result = sp.run(
            [exe, "-c", "print('ok')"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (OSError, sp.TimeoutExpired):
        return False


def _run_config_check(python_exe, setup_script, data_dir):
    """Run setup.py --check and return (success, stdout)."""
    import subprocess as sp
    result = sp.run(
        [python_exe, setup_script, "--check", "--data-dir", data_dir],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stdout.strip()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({
            "decision": "block",
            "reason": f"Bootstrap check hook error: {e}",
        }))
        sys.exit(1)
