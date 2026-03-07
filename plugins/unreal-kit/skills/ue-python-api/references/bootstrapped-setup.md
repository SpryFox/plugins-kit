# Bootstrapped Setup

The bootstrap plugin automatically handles all setup on session start. This document describes what is configured and how to troubleshoot if something breaks.

## What Bootstrap Configures

| Item | What | Where |
|------|------|-------|
| Project config | `.uproject` path and engine directory | `~/.claude/plugins/data/unreal-kit/config.yaml` |
| Remote execution | `bRemoteExecution=True` | `<Project>/Config/UserEngine.ini` |
| Developer mode | `bIsDeveloperMode=True` | `<Project>/Config/UserEngine.ini` |
| Host Python deps | `upyrc`, `pyyaml` | Plugin venv (managed by bootstrap) |
| API stubs | `unreal.py` stub file | `stubs/unreal.py` (from PyPI; project-specific stubs copied when available) |

## Troubleshooting

These issues should be rare since bootstrap runs automatically. Check if something went wrong during session startup.

### Config not found

If `ue_runner.py` reports "uproject path not configured":
- Bootstrap may have failed to auto-detect the project. Check bootstrap output at session start.
- Manually write `~/.claude/plugins/data/unreal-kit/config.yaml` with `uproject` and `engine_dir` fields.

### Remote execution not working

If remote execution fails with "Editor not responding":
- Verify `bRemoteExecution=True` is set in `<Project>/Config/UserEngine.ini`
- The Editor must be restarted after ini changes take effect
- Commandlet fallback will be used automatically — no action needed

### Stubs missing

If `stubs/unreal.py` doesn't exist:
- Bootstrap downloads from PyPI automatically. Check for network/firewall issues.
- Stubs are optional — scripts still run without them, but API search won't work.
- Project-specific stubs (richer) are copied from `<Project>/Intermediate/PythonStub/unreal.py` when available (requires Developer Mode enabled and Editor restarted at least once).
