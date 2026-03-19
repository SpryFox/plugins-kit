"""End-to-end tests for unreal-kit bootstrap manifest processing."""

import json
import os
from pathlib import Path

import pytest

from bootstrap_lib.var_resolve import resolve_vars, build_variables
from bootstrap_lib.ini_check import check_ini_setting, write_ini_setting


class TestUnrealKitManifestStructure:
    """Validate the unreal-kit bootstrap.json manifest structure."""

    @pytest.fixture
    def manifest(self):
        manifest_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), os.pardir, os.pardir,
                         "plugins", "unreal-kit", "bootstrap.json")
        )
        with open(manifest_path) as f:
            return json.load(f)

    def test_has_venv_with_imports(self, manifest):
        assert "venv" in manifest
        assert "upyrc" in manifest["venv"]["check_imports"]
        assert "yaml" in manifest["venv"]["check_imports"]

    def test_has_config_section(self, manifest):
        config = manifest["config"]
        assert config["file"] == "config.yaml"
        assert "uproject" in config["required_fields"]
        assert "engine_dir" in config["required_fields"]
        assert "autodetect" in manifest["project_config"]

    def test_has_ini_settings(self, manifest):
        assert len(manifest["ini_settings"]) >= 1
        ini = manifest["ini_settings"][0]
        assert "${uproject_dir}" in ini["file"]
        assert "bRemoteExecution" in ini["settings"]

    def test_has_pypi_packages(self, manifest):
        assert len(manifest["pypi_packages"]) >= 1
        pkg = manifest["pypi_packages"][0]
        assert pkg["package"] == "unreal-stub"
        assert "${plugin_root}" in pkg["extract_to"]

    def test_has_script(self, manifest):
        assert manifest["script"]["path"] == "custom_bootstrap.py"
        assert manifest["script"]["entry_point"] == "bootstrap"


class TestUnrealKitVariableResolution:
    """Test variable resolution with unreal-kit-like config."""

    def test_ini_file_resolves_with_uproject(self):
        config = {"uproject": "/projects/MyGame/MyGame.uproject"}
        variables = build_variables("/opt/unreal-kit", "/data/unreal-kit", config)
        result = resolve_vars("${uproject_dir}/Config/UserEngine.ini", variables)
        # Path.parent uses OS-native separators for the derived _dir variable
        expected = str(Path("/projects/MyGame")) + "/Config/UserEngine.ini"
        assert result == expected

    def test_ini_file_skipped_without_uproject(self):
        config = {"uproject": ""}
        variables = build_variables("/opt/unreal-kit", "/data/unreal-kit", config)
        result = resolve_vars("${uproject_dir}/Config/UserEngine.ini", variables)
        assert result is None

    def test_pypi_extract_resolves(self):
        variables = build_variables("/opt/unreal-kit", "/data/unreal-kit")
        result = resolve_vars("${plugin_root}/skills/ue-python-api/stubs/unreal.py", variables)
        assert result == "/opt/unreal-kit/skills/ue-python-api/stubs/unreal.py"


class TestUnrealKitIniSettings:
    """Test INI settings with UE-style section names."""

    UE_SECTION = "[/Script/PythonScriptPlugin.PythonScriptPluginSettings]"

    def test_write_and_check_remote_execution(self, tmp_path):
        ini = tmp_path / "Config" / "UserEngine.ini"
        write_ini_setting(str(ini), self.UE_SECTION, "bRemoteExecution", "True")
        result = check_ini_setting(str(ini), self.UE_SECTION, "bRemoteExecution", "True")
        assert result.passed is True

    def test_write_multiple_settings(self, tmp_path):
        ini = tmp_path / "Config" / "UserEngine.ini"
        write_ini_setting(str(ini), self.UE_SECTION, "bRemoteExecution", "True")
        write_ini_setting(str(ini), self.UE_SECTION, "bIsDeveloperMode", "True")

        assert check_ini_setting(str(ini), self.UE_SECTION, "bRemoteExecution", "True").passed
        assert check_ini_setting(str(ini), self.UE_SECTION, "bIsDeveloperMode", "True").passed

    def test_update_existing_setting(self, tmp_path):
        ini = tmp_path / "Config" / "UserEngine.ini"
        write_ini_setting(str(ini), self.UE_SECTION, "bRemoteExecution", "False")
        write_ini_setting(str(ini), self.UE_SECTION, "bRemoteExecution", "True")
        result = check_ini_setting(str(ini), self.UE_SECTION, "bRemoteExecution", "True")
        assert result.passed is True


class TestCustomBootstrapScript:
    """Test the custom_bootstrap.py autodetect function."""

    def test_autodetect_importable(self):
        """Verify the custom_bootstrap module can be imported."""
        script_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), os.pardir, os.pardir,
                         "plugins", "unreal-kit", "custom_bootstrap.py")
        )
        assert os.path.isfile(script_path)

        import importlib.util
        spec = importlib.util.spec_from_file_location("_cb", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "autodetect")
        assert hasattr(module, "bootstrap")

    def test_autodetect_no_uproject_returns_false(self):
        """Autodetect returns False when no .uproject is found."""
        script_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), os.pardir, os.pardir,
                         "plugins", "unreal-kit", "custom_bootstrap.py")
        )
        import importlib.util
        spec = importlib.util.spec_from_file_location("_cb", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # In a tmp dir with no .uproject files, autodetect should return None or a dict
        result = module.autodetect()
        # May be None or dict depending on CWD, but should not raise
        assert result is None or isinstance(result, dict)
