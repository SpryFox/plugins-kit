# Third-Party Tools

## unreal-pip (installed)

**Repo:** https://github.com/hannesdelbeke/unreal-pip
**Location:** `lib/unreal_pip.py` (vendored in this skill)
**Status:** Installed and in use

Package manager for installing Python packages into UE's embedded Python environment.
UE's embedded Python has no pip by default — unreal-pip bridges that gap.

### How it works

1. Finds UE's Python interpreter via `unreal.get_interpreter_executable_path()`
2. Determines the correct site-packages directory in the engine installation
3. Runs `pip install --target <site-packages>` using UE's own interpreter
4. Checks `pkg_resources.working_set` to skip already-installed packages

### Key functions

```python
import unreal_pip

# Install packages (skips already-installed)
unreal_pip.install(['pyyaml', 'numpy'])

# Uninstall packages
unreal_pip.uninstall(['numpy'])

# Low-level pip command
unreal_pip._pip_cmd(command='list')
```

### Where packages go

Packages install to:
```
<EngineDir>/Binaries/ThirdParty/Python3/Win64/Lib/site-packages/
```
This is UE's engine-level site-packages, so installed packages persist across projects
and editor restarts.

### Bootstrap pattern

Scripts don't call unreal_pip directly. Instead, they use the bootstrap helper:

```python
import sys
# ${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api = plugin's ue-python-api skill directory
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/lib')
from bootstrap import ensure_dependencies
ensure_dependencies()
```

This reads `requirements.yaml` at the skill root, checks what's installed, and uses
unreal_pip to install anything missing. The bootstrap parser doesn't need pyyaml itself
(handles the chicken-and-egg problem with a simple line parser).

### Platform note

The current implementation uses `subprocess.STARTUPINFO` which is Windows-specific.
This matches our current setup (Windows dev machine with UE Editor).

---

## upyrc — Remote Execution (installed)

**Repo:** https://github.com/cgtoolbox/UnrealRemoteControlWrapper
**PyPI:** https://pypi.org/project/upyrc/
**Location:** Host-side dependency (system Python, not UE's Python)
**Status:** Integrated into `ue_runner.py`

Python wrapper around UE's built-in Python Remote Execution protocol (UDP multicast).
Sends Python code to a running UE Editor for execution — no copy-paste needed.

**Key insight:** This uses UE's **Python Remote Execution** (part of Python Editor Script Plugin),
NOT the Web Remote Control plugin. No additional plugins needed — just enable
"Remote Execution" in Editor Preferences → Plugins → Python.

### How it works

1. Creates a UDP multicast connection (default `239.0.0.1:6766`)
2. Sends Python code to the editor's embedded Python interpreter
3. Editor executes the code and sends results back via the same channel

### Key API

```python
from upyrc import upyre

# Config from .uproject (reads Python plugin settings)
config = upyre.RemoteExecutionConfig.from_uproject_path(r"path/to/project.uproject")

# Or manual config
config = upyre.RemoteExecutionConfig(
    multicast_group=("239.0.0.1", 6766),
    multicast_bind_address="0.0.0.0",
)

# Execute
with upyre.PythonRemoteConnection(config) as conn:
    result = conn.execute_python_command(
        "unreal.log('hello')",
        exec_type=upyre.ExecTypes.EXECUTE_FILE,
        raise_exc=True,
    )
```

### Integration with ue_runner.py

The terminal runner (`bin/ue_runner.py`) uses upyrc as its primary execution path.
If the editor isn't responding, it falls back to the headless commandlet.

Install host-side: `pip install -r host-requirements.txt`
