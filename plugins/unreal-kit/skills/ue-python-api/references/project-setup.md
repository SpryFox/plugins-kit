# Project Setup

## Automatic Setup (Bootstrap)

Setup happens automatically on every Claude Code session start via the bootstrap engine. No manual steps required.

The bootstrap engine (`bootstrap.json`) handles:

1. **Discovers `.uproject` and engine directory** — via `project_config` autodetect (walks up from CWD)
2. **Writes per-project config** — to `<project_root>/.local-data/unreal-kit/config.yaml` (gitignored; legacy `<project_root>/.claude/unreal-kit.yaml` is auto-migrated to the new path on session start)
3. **Syncs config to data dir** — so `ue_runner.py` can resolve paths at runtime
4. **Enables `bRemoteExecution`** — in `Config/UserEngine.ini` (per-user, not checked in). Allows running scripts from terminal via UDP
5. **Enables `bIsDeveloperMode`** — in `Config/UserEngine.ini`. Enables UE to generate Python API stubs
6. **Downloads API stubs** — from PyPI (`unreal-stub` package). Used by the AI to search the UE Python API
7. **Upgrades to project stubs** — if project-generated stubs exist (`Intermediate/PythonStub/unreal.py`), copies them over PyPI stubs since they include project-specific types

## After First Session

**Restart UE Editor** — the `bRemoteExecution` and `bIsDeveloperMode` settings only take effect on editor startup. After restarting, the next session's bootstrap will automatically pick up project-generated stubs if Developer Mode produced them.

## Interactive Setup

If bootstrap can't auto-discover your project (e.g., CWD is not inside a UE project tree), use the interactive setup:

```bash
<skill-dir>/scripts/ue-runner.cmd --setup
```

This prompts for the `.uproject` path and configures everything interactively.

## How to Tell If Setup Is Needed

**Default assumption: setup is complete.** Only investigate if you encounter:

- Config validation errors from `ue_runner.py` (e.g., "uproject path not configured")
- `stubs/unreal.py` not found when searching the API
- Remote execution fails with "Editor not responding" and settings haven't been configured

## Troubleshooting

### `.uproject` Not Found

The autodetect walks up from CWD looking for `.uproject` files. If Claude Code was not launched from inside a UE project tree, autodetect can't discover the project. Use `scripts/ue-runner.cmd --setup` to configure manually.

### Stubs Download Failed

If PyPI is unreachable (firewall, no internet):

- Stubs are optional — scripts will still run, the AI just can't search the API
- After getting editor running with Developer Mode, the next bootstrap session will automatically copy project-generated stubs
