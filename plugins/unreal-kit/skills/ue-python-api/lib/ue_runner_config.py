"""
UE Python Script Runner — Configuration loading.

Resolution order: CLI args → local project config → skill config → defaults.

Local project config lives at:
    ~/.claude/plugins/data/unreal-kit/config.yaml
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_CONFIG_PATH = SKILL_DIR / "ue_runner_config.yaml"
LOCAL_CONFIG_PATH = Path.home() / ".claude" / "plugins" / "data" / "unreal-kit" / "config.yaml"

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


def load_config(config_path: str | Path | None = None) -> RunnerConfig:
    """Load config: defaults → skill config → local project config → CLI."""
    # Start with defaults, layer skill-level config
    skill_data = _load_yaml(SKILL_CONFIG_PATH)
    merged = _deep_merge(_DEFAULTS, skill_data)

    # Layer local project config (~/.claude/.local-data/...)
    if config_path:
        local_data = _load_yaml(config_path)
    else:
        local_data = _load_yaml(LOCAL_CONFIG_PATH)
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
