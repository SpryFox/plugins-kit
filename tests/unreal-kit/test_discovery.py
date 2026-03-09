"""Tests for ue_discovery — project discovery and engine resolution."""

import json
import sys
from pathlib import Path

import pytest

# Add lib/ to path so we can import ue_discovery directly
_LIB_DIR = Path(__file__).resolve().parent.parent.parent / "plugins" / "unreal-kit" / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from ue_discovery import (
    find_engine_dir,
    find_uproject_files,
    find_uproject_from_cwd,
    find_uproject_from_path,
    is_game_project,
)


def _make_uproject(path: Path, modules: bool = True):
    """Create a minimal .uproject file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"Modules": [{"Name": "TestGame"}]} if modules else {}
    path.write_text(json.dumps(data), encoding="utf-8")


def _make_engine(engine_dir: Path):
    """Create the minimal engine marker (UnrealEditor-Cmd.exe)."""
    exe = engine_dir / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text("fake", encoding="utf-8")


class TestFindUprojectFromPath:
    """find_uproject_from_path should walk up from any file/dir to find .uproject."""

    def test_from_script_inside_project(self, tmp_path):
        proj = tmp_path / "MyGame"
        _make_uproject(proj / "MyGame.uproject")
        script = proj / "tmp" / "test_api.py"
        script.parent.mkdir(parents=True)
        script.write_text("pass")

        result = find_uproject_from_path(script)
        assert result is not None
        assert result.name == "MyGame.uproject"

    def test_from_subdirectory(self, tmp_path):
        proj = tmp_path / "MyGame"
        _make_uproject(proj / "MyGame.uproject")
        deep = proj / "Content" / "Python" / "scripts"
        deep.mkdir(parents=True)

        result = find_uproject_from_path(deep)
        assert result is not None
        assert result.name == "MyGame.uproject"

    def test_no_uproject_returns_none(self, tmp_path, monkeypatch):
        # Use a deep isolated path so walking up 6 levels stays inside tmp_path
        deep = tmp_path / "a" / "b" / "c" / "d" / "e" / "f" / "g" / "random"
        deep.mkdir(parents=True)
        script = deep / "script.py"
        script.write_text("pass")

        result = find_uproject_from_path(script)
        assert result is None

    def test_skips_non_game_uproject(self, tmp_path):
        # Create a non-game .uproject deep enough that walking up won't escape
        deep = tmp_path / "a" / "b" / "c" / "d" / "e" / "f" / "g" / "NotAGame"
        _make_uproject(deep / "NotAGame.uproject", modules=False)
        script = deep / "script.py"
        script.write_text("pass")

        result = find_uproject_from_path(script)
        assert result is None


class TestFindEngineDir:
    """find_engine_dir should walk up from .uproject to find Engine/."""

    def test_source_build_layout(self, tmp_path):
        """Source build: Engine/ is a sibling or ancestor of the project dir."""
        # Layout: root/Engine/Binaries/Win64/UnrealEditor-Cmd.exe
        #         root/MyGame/MyGame.uproject
        root = tmp_path / "depot"
        _make_engine(root / "Engine")
        uproject = root / "MyGame" / "MyGame.uproject"
        _make_uproject(uproject)

        result = find_engine_dir(uproject)
        assert result is not None
        assert result.name == "Engine"

    def test_no_engine_returns_none(self, tmp_path):
        uproject = tmp_path / "MyGame" / "MyGame.uproject"
        _make_uproject(uproject)

        result = find_engine_dir(uproject)
        assert result is None


class TestFindUprojectFromCwd:
    """find_uproject_from_cwd should find project from working directory."""

    def test_cwd_is_project_root(self, tmp_path, monkeypatch):
        _make_uproject(tmp_path / "MyGame.uproject")
        monkeypatch.chdir(tmp_path)

        result = find_uproject_from_cwd()
        assert result is not None
        assert result.name == "MyGame.uproject"

    def test_cwd_is_subdirectory(self, tmp_path, monkeypatch):
        _make_uproject(tmp_path / "MyGame.uproject")
        sub = tmp_path / "Content" / "Python"
        sub.mkdir(parents=True)
        monkeypatch.chdir(sub)

        result = find_uproject_from_cwd()
        assert result is not None
        assert result.name == "MyGame.uproject"
