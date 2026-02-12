"""
UE Python Script Runner — Execute UE Python scripts from the terminal.

Auto-detects whether UE Editor is running:
  - Editor running + remote execution enabled → fast UDP execution via upyrc
  - Editor not running → headless commandlet (slow, ~30-120s)

Usage:
    python ue_runner.py script.py
    python ue_runner.py script.py --mode commandlet
    python ue_runner.py script.py --mode remote
    python ue_runner.py script.py --copy-output ./results/
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Add lib/ to path (sibling of bin/)
_SKILL_DIR = Path(__file__).resolve().parent.parent
_LIB_DIR = _SKILL_DIR / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from ue_runner_config import RunnerConfig, load_config


@dataclass
class RunResult:
    success: bool
    mode: str  # "remote" or "commandlet"
    stdout: str = ""
    stderr: str = ""
    output_file: str | None = None
    elapsed: float = 0.0
    error: str = ""


def run_ue_script(
    script_path: str,
    force_mode: str | None = None,
    config: RunnerConfig | None = None,
    copy_output_to: str | None = None,
) -> RunResult:
    """
    Execute a UE Python script, auto-selecting the best execution path.

    Args:
        script_path: Path to the .py script to run.
        force_mode: "remote", "commandlet", or None (auto-detect).
        config: RunnerConfig instance, or None to load from default config.
        copy_output_to: If set, copy any output YAML to this directory.

    Returns:
        RunResult with execution details.
    """
    if config is None:
        config = load_config()

    script_path = os.path.abspath(script_path)
    if not os.path.isfile(script_path):
        return RunResult(success=False, mode="none", error=f"Script not found: {script_path}")

    # Validate config (commandlet needs valid paths; remote can work without them)
    errors = config.validate()
    if force_mode == "commandlet" and errors:
        return RunResult(success=False, mode="commandlet", error="\n".join(errors))

    # Try remote execution first (unless forced to commandlet)
    if force_mode != "commandlet":
        result = _try_remote(script_path, config)
        if result is not None:
            if copy_output_to and result.output_file:
                result.output_file = _copy_output(result.output_file, copy_output_to)
            return result
        if force_mode == "remote":
            return RunResult(
                success=False,
                mode="remote",
                error="Remote execution failed. Is UE Editor running with Remote Execution enabled?\n"
                      "  Run: python ue_runner.py --setup",
            )

    # Fall back to commandlet
    if errors:
        return RunResult(success=False, mode="commandlet", error="\n".join(errors))

    result = _run_commandlet(script_path, config)
    if copy_output_to and result.output_file:
        result.output_file = _copy_output(result.output_file, copy_output_to)
    return result


def _try_remote(script_path: str, config: RunnerConfig) -> RunResult | None:
    """
    Attempt remote execution via upyrc. Returns RunResult on success, None if
    the editor isn't reachable (so caller can fall back to commandlet).
    """
    try:
        from upyrc import upyre
    except ImportError:
        _warn(
            "upyrc not installed — skipping remote execution.\n"
            "  Install with: pip install upyrc\n"
            "  Falling back to commandlet..."
        )
        return None

    remote_cfg = upyre.RemoteExecutionConfig(
        multicast_group=(config.remote.multicast_group, config.remote.multicast_port),
        multicast_bind_address=config.remote.multicast_bind_address,
    )

    # Snapshot output dir before execution
    output_dir = _get_output_dir(config)
    pre_snapshot = _snapshot_output_dir(output_dir)

    start = time.time()
    try:
        with upyre.PythonRemoteConnection(remote_cfg) as conn:
            # EXECUTE_FILE tells UE to load and run a .py file by path.
            # EXECUTE_STATEMENT would exec() inline code instead.
            cmd_result = conn.execute_python_command(
                script_path,
                exec_type=upyre.ExecTypes.EXECUTE_FILE,
                raise_exc=False,
            )
    except Exception as e:
        err_str = str(e)
        # Connection refused / timeout / failed = editor not running
        if any(keyword in err_str.lower() for keyword in ("timed out", "timeout", "refused", "unreachable", "connection failed")):
            _warn(f"Editor not responding ({err_str}). Falling back to commandlet...")
            return None
        # Other errors may be script errors — still a valid execution attempt
        elapsed = time.time() - start
        return RunResult(
            success=False, mode="remote", stderr=err_str, elapsed=elapsed,
            error=f"Remote execution error: {err_str}",
        )

    elapsed = time.time() - start
    raw_result = cmd_result.result if hasattr(cmd_result, 'result') else str(cmd_result)
    stdout = raw_result if raw_result and raw_result != "None" else ""
    success = cmd_result.success if hasattr(cmd_result, 'success') else True

    # Check for new output files
    output_file = _find_new_output(output_dir, pre_snapshot)

    error = ""
    if not success:
        error = f"Script error (see editor Output Log): {stdout[:200]}" if stdout else "Script execution failed"

    return RunResult(
        success=success, mode="remote", stdout=stdout,
        output_file=output_file, elapsed=elapsed, error=error,
    )


def _run_commandlet(script_path: str, config: RunnerConfig) -> RunResult:
    """Run script via UnrealEditor-Cmd.exe -run=pythonscript."""
    exe = config.editor_cmd_exe
    uproject = config.uproject

    command = [
        exe,
        uproject,
        "-run=pythonscript",
        f"-script={script_path}",
        "-stdout",
        "-Unattended",
        "-NoLoadStartupPackages",
        "-FullStdOutLogOutput",
    ]

    _info(f"Running commandlet...")
    _info(f"  {' '.join(command)}")

    # Snapshot output dir before execution
    output_dir = _get_output_dir(config)
    pre_snapshot = _snapshot_output_dir(output_dir)

    start = time.time()
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            # No timeout — user can Ctrl-C if needed
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except FileNotFoundError:
        return RunResult(
            success=False, mode="commandlet",
            error=f"Editor executable not found: {exe}",
        )

    elapsed = time.time() - start
    output_file = _find_new_output(output_dir, pre_snapshot)

    # UE commandlets frequently exit non-zero due to asset loading warnings
    # (e.g. Niagara modules) that are unrelated to the Python script.
    # Consider it a success if the output file was produced, or if stdout
    # contains no Python-level error indicators.
    has_script_error = _detect_script_error(proc.stdout, script_path)

    if has_script_error:
        success = False
    elif output_file is not None:
        # Script produced output — success regardless of UE exit code
        success = True
    else:
        success = proc.returncode == 0

    error = ""
    if not success:
        if has_script_error:
            error = "Python script error detected in output (see stdout)"
        else:
            error = proc.stderr

    return RunResult(
        success=success,
        mode="commandlet",
        stdout=proc.stdout,
        stderr=proc.stderr,
        output_file=output_file,
        elapsed=elapsed,
        error=error,
    )


def _get_output_dir(config: RunnerConfig) -> Path | None:
    """Get the PythonOutput directory under the project's Saved folder."""
    if not config.uproject:
        return None
    project_dir = Path(config.uproject).parent
    return project_dir / "Saved" / "PythonOutput"


def _detect_script_error(stdout: str, script_path: str) -> bool:
    """Check UE commandlet stdout for Python errors from our script.

    UE auto-runs startup scripts (Content/Python/) which commonly fail in
    commandlet mode (no UI, missing debug modules). We only flag errors that
    reference the script we actually ran.
    """
    # Normalize path for matching (UE logs use mixed separators)
    script_name = os.path.basename(script_path)

    in_our_traceback = False
    for line in stdout.split("\n"):
        if "Traceback (most recent call last)" in line:
            in_our_traceback = False  # reset — new traceback starting
        if script_name in line and "LogPython: Error:" in line:
            # Error line that references our script
            return True
        if script_name in line and "Traceback" not in line:
            # Our script appeared in a traceback frame
            in_our_traceback = True
        if in_our_traceback and any(err in line for err in (
            "SyntaxError:", "ModuleNotFoundError:", "ImportError:",
            "NameError:", "TypeError:", "AttributeError:", "ValueError:",
        )):
            return True

    return False


def _snapshot_output_dir(output_dir: Path | None) -> dict[str, float]:
    """Return {filename: mtime} for all YAML files in the output directory."""
    if output_dir is None or not output_dir.is_dir():
        return {}
    snapshot = {}
    for f in output_dir.iterdir():
        if f.suffix in (".yaml", ".yml"):
            snapshot[str(f)] = f.stat().st_mtime
    return snapshot


def _find_new_output(output_dir: Path | None, pre_snapshot: dict[str, float]) -> str | None:
    """Poll for new/modified YAML files after script execution."""
    if output_dir is None or not output_dir.is_dir():
        return None

    # Poll a few times to handle slight delay in file writes
    for _ in range(5):
        for f in output_dir.iterdir():
            if f.suffix not in (".yaml", ".yml"):
                continue
            fpath = str(f)
            mtime = f.stat().st_mtime
            if fpath not in pre_snapshot or mtime > pre_snapshot[fpath]:
                return fpath
        time.sleep(1)

    return None


def _copy_output(output_file: str, dest_dir: str) -> str:
    """Copy output file to destination directory, return new path."""
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(output_file))
    shutil.copy2(output_file, dest)
    _info(f"Copied output to {dest}")
    return dest


def _info(msg: str):
    print(f"[ue_runner] {msg}", file=sys.stderr)


def _warn(msg: str):
    print(f"[ue_runner] WARNING: {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Setup — check project settings (delegates to shared libs)
# ---------------------------------------------------------------------------

from ue_discovery import find_engine_dir, find_uproject_files, is_game_project
from ue_ini import read_ini_bool, write_ini_setting

_INI_SECTION = "[/Script/PythonScriptPlugin.PythonScriptPluginSettings]"


def run_setup(config: RunnerConfig) -> bool:
    """Interactive setup: discover UE project, check settings, prompt before fixes.

    For non-interactive setup, use bin/setup.cmd instead.
    """
    from ue_runner_config import _find_local_config, LOCAL_CONFIG_RELATIVE

    all_ok = True

    # 1. Check if we have a configured project
    local_config_path = _find_local_config()
    if config.uproject and config.engine_dir and not config.validate():
        print(f"  OK    uproject: {config.uproject}")
        print(f"  OK    engine:   {config.engine_dir}")
        if local_config_path:
            print(f"        (from {local_config_path})")
    else:
        # Ask user for .uproject path
        uproject = _ask_uproject_path()
        if not uproject:
            return False

        engine_dir = find_engine_dir(uproject)
        if not engine_dir:
            print(f"  ERROR: Could not find Engine/ directory relative to {uproject}")
            print(f"  (Walked up looking for Engine/Binaries/Win64/UnrealEditor-Cmd.exe)")
            return False

        # Write project.yaml — prompt first
        project_yaml_path = Path.cwd().resolve() / LOCAL_CONFIG_RELATIVE
        print(f"\n  Project:")
        print(f"    uproject:   {uproject}")
        print(f"    engine_dir: {engine_dir}")
        print(f"\n  Write project config?")
        print(f"    File: {project_yaml_path}")
        if not _confirm("  Create this file?"):
            print("  Skipped.")
            return False

        project_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        # Write YAML without pyyaml dependency
        with open(project_yaml_path, "w") as f:
            f.write(f'engine_dir: "{engine_dir}"\n')
            f.write(f'uproject: "{uproject}"\n')
        print(f"  WROTE {project_yaml_path}")

        # Reload config with the new file
        from ue_runner_config import load_config as _reload
        config = _reload()
        print(f"\n  OK    uproject: {config.uproject}")
        print(f"  OK    engine:   {config.engine_dir}")

    # 2. Check editor settings (bRemoteExecution + bIsDeveloperMode)
    project_dir = Path(config.uproject).parent
    default_ini = project_dir / "Config" / "DefaultEngine.ini"
    user_ini = project_dir / "Config" / "UserEngine.ini"

    settings_to_check = [
        ("bRemoteExecution", "Enables remote script execution from terminal"),
        ("bIsDeveloperMode", "Enables Python API stub generation"),
    ]

    for key, description in settings_to_check:
        default_value = read_ini_bool(default_ini, _INI_SECTION, key)
        user_value = read_ini_bool(user_ini, _INI_SECTION, key)
        effective = user_value if user_value is not None else default_value

        if effective is True:
            source = "UserEngine.ini" if user_value is True else "DefaultEngine.ini"
            print(f"  OK    {key}=True (from {source})")
        else:
            print(f"\n  {key} is not enabled ({description}).")
            print(f"    File: {user_ini}")
            print(f"    Setting: {key}=True")
            if _confirm(f"  Write this setting?"):
                write_ini_setting(user_ini, _INI_SECTION, key, "True")
                print(f"  WROTE {user_ini}")
                print(f"  NOTE: Restart the editor for this to take effect.")
            else:
                print(f"  Skipped.")
                all_ok = False

    # 3. Check host deps
    print()
    for pkg_name, import_name, install_name in [
        ("upyrc", "upyrc", "upyrc"),
        ("pyyaml", "yaml", "pyyaml"),
    ]:
        try:
            __import__(import_name)
            print(f"  OK    Python package: {pkg_name}")
        except ImportError:
            print(f"  MISS  Python package: {pkg_name} — install with: pip install {install_name}")
            all_ok = False

    return all_ok


def _confirm(prompt: str) -> bool:
    """Ask user yes/no. Returns True for yes."""
    try:
        answer = input(f"{prompt} [y/N] ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def _ask_uproject_path() -> Path | None:
    """Ask user for a .uproject file or directory containing one."""
    print("\n  Enter path to your .uproject file (or a directory to search):")
    try:
        raw = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    if not raw:
        return None

    # Expand ~ and resolve
    p = Path(os.path.expanduser(raw)).resolve()

    # Direct .uproject file
    if p.is_file() and p.suffix == ".uproject":
        return p

    # Directory — search it for .uproject files
    if p.is_dir():
        found = find_uproject_files(p, max_depth=4)
        if not found:
            print(f"  No .uproject files found under {p}")
            return None
        if len(found) == 1:
            print(f"  Found: {found[0]}")
            return found[0]
        # Multiple — let user pick
        print(f"  Found {len(found)} .uproject files:\n")
        for i, f in enumerate(found, 1):
            print(f"    [{i}] {f}")
        print()
        try:
            choice = input("  Enter number (or 'q' to quit): ").strip()
            if choice.lower() == 'q' or not choice:
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(found):
                return found[idx]
        except (ValueError, EOFError, KeyboardInterrupt):
            print()
        return None

    print(f"  Path not found: {p}")
    return None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run UE Python scripts from the terminal.",
        epilog="Examples:\n"
               "  python ue_runner.py --setup                # check/fix project settings\n"
               "  python ue_runner.py script.py              # auto-detect mode\n"
               "  python ue_runner.py script.py --mode remote # force remote only\n"
               "  python ue_runner.py script.py --mode commandlet\n"
               "  python ue_runner.py script.py --copy-output ./results/\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("script", nargs="?", help="Path to the .py script to execute")
    parser.add_argument(
        "--setup", action="store_true",
        help="Check and fix UE project settings for remote execution",
    )
    parser.add_argument(
        "--mode", choices=["remote", "commandlet"],
        help="Force execution mode (default: auto-detect)",
    )
    parser.add_argument(
        "--config", help="Path to config YAML",
    )
    parser.add_argument(
        "--copy-output", metavar="DIR",
        help="Copy output YAML to this directory",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if args.setup:
        print("[ue_runner] Setup check:")
        ok = run_setup(config)
        sys.exit(0 if ok else 1)

    if not args.script:
        parser.error("script is required (or use --setup)")

    result = run_ue_script(
        script_path=args.script,
        force_mode=args.mode,
        config=config,
        copy_output_to=getattr(args, "copy_output", None),
    )

    # Print results
    if result.stdout:
        print(result.stdout)

    if result.error:
        print(f"\nERROR: {result.error}", file=sys.stderr)

    # Summary line
    status = "OK" if result.success else "FAILED"
    summary = f"[{status}] mode={result.mode} elapsed={result.elapsed:.1f}s"
    if result.output_file:
        summary += f" output={result.output_file}"
    print(f"\n{summary}", file=sys.stderr)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
