"""
UE Editor launcher -- spawn the GUI editor and probe the MCP Automation Bridge.

Pure functions. The CLI entry point lives at
``plugins/unreal-kit/scripts/ue_launcher.py`` -- this module contains the
process-spawn, process-scan, and readiness-probe helpers used both by that
CLI and by other consumers (hooks, project-side facades).

Three operations:

- ``is_mcp_ready(host, port)`` -- best-effort handshake against the bridge.
  Uses ``ue_mcp_client.McpClient`` when the host venv has it installed;
  otherwise falls back to a bare TCP probe (proves a socket is listening
  but not that the bridge is functional).

- ``find_editor_processes(editor_exe=None)`` -- enumerate running
  UnrealEditor.exe processes via ``tasklist``. Windows-only; returns ``[]``
  on other platforms.

- ``launch_editor(editor_exe, uproject, map_arg, extra_args)`` -- Popen the
  editor fully detached (no inherited stdio, new process group) and return
  the child PID.

``wait_for_mcp_ready`` is a thin polling wrapper around ``is_mcp_ready``
for callers that want to block until the bridge comes up after a launch.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional


DEFAULT_MCP_HOST = "127.0.0.1"
DEFAULT_MCP_PORT = 8090
DEFAULT_READINESS_TIMEOUT_S = 180.0
DEFAULT_POLL_INTERVAL_S = 2.0
DEFAULT_PROBE_TIMEOUT_S = 1.0


def is_mcp_ready(
    host: str = DEFAULT_MCP_HOST,
    port: int = DEFAULT_MCP_PORT,
    probe_timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
) -> bool:
    """Return True if the MCP Automation Bridge accepts a handshake.

    Tries a full bridge_hello/bridge_ack roundtrip via ue_mcp_client.
    If the websocket dependency isn't available, falls back to a bare TCP
    connect on (host, port) -- a weaker signal that only proves something
    is listening on the port.
    """
    try:
        from ue_mcp_client import McpClient
        from ue_mcp_client import ConnectionError as McpConnectionError
        from ue_mcp_client import HandshakeError
    except ImportError:
        return _tcp_probe(host, port, probe_timeout_s)

    try:
        client = McpClient(host=host, port=port, timeout_s=probe_timeout_s)
        client.connect()
        client.close()
        return True
    except (McpConnectionError, HandshakeError, OSError):
        return False


def _tcp_probe(host: str, port: int, timeout_s: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def wait_for_mcp_ready(
    host: str = DEFAULT_MCP_HOST,
    port: int = DEFAULT_MCP_PORT,
    total_timeout_s: float = DEFAULT_READINESS_TIMEOUT_S,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    on_attempt: Optional[Callable[[int, float], None]] = None,
) -> bool:
    """Poll is_mcp_ready until success or total_timeout_s elapses.

    ``on_attempt(attempt_number, seconds_remaining)`` is called once per
    failed probe so callers can surface progress without re-implementing
    the loop.
    """
    deadline = time.monotonic() + total_timeout_s
    attempt = 0
    while True:
        attempt += 1
        if is_mcp_ready(host, port):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        if on_attempt is not None:
            on_attempt(attempt, remaining)
        time.sleep(min(poll_interval_s, remaining))


def find_editor_processes(editor_exe: Optional[str] = None) -> list[int]:
    """Return PIDs of running UnrealEditor.exe processes (Windows-only).

    On non-Windows or if tasklist is unavailable, returns []. The optional
    ``editor_exe`` argument is currently advisory -- tasklist surfaces the
    image name only, so this function returns every UnrealEditor.exe match.
    Callers that need exact-exe matching should resolve PIDs to image paths
    via a separate query (out of scope here).
    """
    if sys.platform != "win32":
        return []
    try:
        proc = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq UnrealEditor.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    pids: list[int] = []
    for line in proc.stdout.splitlines():
        parts = [p.strip().strip('"') for p in line.split(",")]
        if len(parts) >= 2 and parts[0].lower() == "unrealeditor.exe":
            try:
                pids.append(int(parts[1]))
            except ValueError:
                pass
    return pids


def launch_editor(
    editor_exe: str,
    uproject: str,
    map_arg: Optional[str] = None,
    extra_args: Optional[list[str]] = None,
) -> int:
    """Spawn the GUI editor fully detached and return the child PID.

    Args:
        editor_exe: Absolute path to UnrealEditor.exe.
        uproject: Absolute path to the .uproject. Empty/None opens the
            last-used project.
        map_arg: Optional map asset path or .umap to load on startup.
            Passed positionally after the .uproject (UE's CLI convention).
        extra_args: Additional command-line tokens appended verbatim.

    Returns:
        PID of the spawned editor process.

    Raises:
        FileNotFoundError: editor_exe does not exist.
        OSError: spawn failure.
    """
    if not Path(editor_exe).is_file():
        raise FileNotFoundError(f"Editor binary not found: {editor_exe}")

    cmd: list[str] = [str(editor_exe)]
    if uproject:
        cmd.append(str(uproject))
    if map_arg:
        cmd.append(str(map_arg))
    if extra_args:
        cmd.extend(extra_args)

    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        kwargs["close_fds"] = True
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **kwargs)
    return proc.pid
