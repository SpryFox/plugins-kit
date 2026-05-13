"""
UE Python Script Runner — Configuration loading.

Resolution order: CLI args → per-project config → global config → skill config → defaults.

Per-project config lives at:
    <project_root>/.local-data/unreal-kit/config.yaml
Written by bootstrap's project_config primitive during session start.

Legacy path (read-only fallback during migration):
    <project_root>/.claude/unreal-kit.yaml
The bootstrap engine moves the file to the new path automatically; this fallback
is here for sessions that read config before bootstrap has run, or for projects
that haven't seen a session start since the path changed.

Global config (legacy, migration fallback) lives at:
    ~/.claude/plugins/data/plugins-kit/unreal-kit/config.yaml
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
SKILL_CONFIG_PATH = _PLUGIN_DIR / "skills" / "ue-python-api" / "ue_runner_config.yaml"

PROJECT_CONFIG_NAME = ".local-data/unreal-kit/config.yaml"
LEGACY_PROJECT_CONFIG_NAME = ".claude/unreal-kit.yaml"

_GLOBAL_CONFIG_PATH = Path.home() / ".claude" / "plugins" / "data" / "plugins-kit" / "unreal-kit" / "config.yaml"

# Hardcoded defaults for global settings (last resort)
_DEFAULTS = {
    "remote_execution": {
        "timeout_seconds": 5,
        "multicast_group": "239.0.0.1",
        "multicast_port": 6766,
        "multicast_bind_address": "127.0.0.1",
    },
}


@dataclass
class RemoteConfig:
    timeout_seconds: int = 5
    multicast_group: str = "239.0.0.1"
    multicast_port: int = 6766
    multicast_bind_address: str = "127.0.0.1"


@dataclass
class RunnerConfig:
    engine_dir: str = ""
    uproject: str = ""
    remote: RemoteConfig = field(default_factory=RemoteConfig)

    @property
    def editor_cmd_exe(self) -> str:
        if not self.engine_dir:
            return ""
        return os.path.join(self.engine_dir, "Binaries", "Win64", "UnrealEditor-Cmd.exe")

    @property
    def editor_exe(self) -> str:
        if not self.engine_dir:
            return ""
        return os.path.join(self.engine_dir, "Binaries", "Win64", "UnrealEditor.exe")

    def validate(self) -> list[str]:
        """Return list of validation errors (empty = valid)."""
        errors = []
        if not self.uproject:
            errors.append("uproject path not configured. Run: python ue_runner.py --setup")
        elif not os.path.isfile(self.uproject):
            errors.append(f"uproject not found: {self.uproject}")

        if not self.engine_dir:
            errors.append("engine_dir not configured. Run: python ue_runner.py --setup")
        elif not os.path.isdir(self.engine_dir):
            errors.append(f"engine_dir not found: {self.engine_dir}")

        exe = self.editor_cmd_exe
        if exe and not os.path.isfile(exe):
            errors.append(f"UnrealEditor-Cmd.exe not found: {exe}")

        return errors


def find_project_config(start: Path | None = None) -> Path | None:
    """Walk up from start (default CWD) looking for the per-project config.

    Prefers the current path (.local-data/unreal-kit/config.yaml). Falls back
    to the legacy path (.claude/unreal-kit.yaml) for projects mid-migration —
    bootstrap will move it on the next session start.
    """
    current = (start or Path.cwd()).resolve()
    if not current.is_dir():
        current = current.parent
    for _ in range(10):
        candidate = current / PROJECT_CONFIG_NAME
        if candidate.is_file():
            return candidate
        legacy = current / LEGACY_PROJECT_CONFIG_NAME
        if legacy.is_file():
            return legacy
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def write_project_config(project_root: Path, data: dict) -> Path:
    """Write config to <project_root>/.local-data/unreal-kit/config.yaml.

    Creates the parent directory if needed. Returns the config path.
    Uses forward slashes for Windows compatibility in YAML.
    """
    config_path = project_root / PROJECT_CONFIG_NAME
    config_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key, value in data.items():
        safe_value = str(value).replace("\\", "/")
        lines.append(f'{key}: "{safe_value}"')
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config_path


def load_config(config_path: str | Path | None = None) -> RunnerConfig:
    """Load config: defaults → skill config → per-project config → CLI.

    If config_path is given, use it directly. Otherwise, search for
    per-project config (.local-data/unreal-kit/config.yaml, with legacy
    .claude/unreal-kit.yaml fallback) by walking up from CWD, falling back
    to the global config for migration.
    """
    # Start with defaults, layer skill-level config
    skill_data = _load_yaml(SKILL_CONFIG_PATH)
    merged = _deep_merge(_DEFAULTS, skill_data)

    # Layer project config: explicit path > per-project > global fallback
    if config_path:
        local_data = _load_yaml(config_path)
    else:
        project_config = find_project_config()
        if project_config:
            local_data = _load_yaml(project_config)
        else:
            local_data = _load_yaml(_GLOBAL_CONFIG_PATH)
    merged = _deep_merge(merged, local_data)

    remote_data = merged.get("remote_execution", {})

    return RunnerConfig(
        engine_dir=merged.get("engine_dir", ""),
        uproject=merged.get("uproject", ""),
        remote=RemoteConfig(
            timeout_seconds=int(remote_data.get("timeout_seconds", 5)),
            multicast_group=str(remote_data.get("multicast_group", "239.0.0.1")),
            multicast_port=int(remote_data.get("multicast_port", 6766)),
            multicast_bind_address=str(remote_data.get("multicast_bind_address", "127.0.0.1")),
        ),
    )


def _load_yaml(path: str | Path) -> dict:
    """Load YAML file, returning empty dict if not found or on error."""
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        import yaml
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except ImportError:
        # Fall back to simple line parser if pyyaml not installed
        return _parse_yaml_simple(path)
    except Exception:
        return {}


def _parse_yaml_simple(path: Path) -> dict:
    """Minimal YAML parser for flat key: value and one level of nesting."""
    result = {}
    current_section = None
    with open(path, "r") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Check for section header (key with no value, next lines indented)
            if ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if not value:
                    # Could be a section header
                    if not line.startswith(" ") and not line.startswith("\t"):
                        current_section = key
                        result[current_section] = {}
                        continue
                if current_section and (line.startswith(" ") or line.startswith("\t")):
                    result[current_section][key] = _coerce_value(value)
                else:
                    current_section = None
                    result[key] = _coerce_value(value)
    return result


def _coerce_value(val: str):
    """Coerce string to int/float/bool if possible."""
    if val.lower() in ("true", "yes"):
        return True
    if val.lower() in ("false", "no"):
        return False
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base, returning new dict. Override wins for leaf values."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        elif val is not None and val != "":
            result[key] = val
    return result
