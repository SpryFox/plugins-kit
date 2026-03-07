"""Unit tests for manifest_merge.merge_manifests()."""

import os
import sys

import pytest

# Add lib/ to path for direct imports
BOOTSTRAP_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "bootstrap")
)
sys.path.insert(0, os.path.join(BOOTSTRAP_ROOT, "lib"))

from manifest_merge import merge_manifests


class TestEmptyInputs:
    def test_both_empty(self):
        assert merge_manifests({}, {}) == {}

    def test_base_empty(self):
        override = {"tools": [{"name": "git"}]}
        assert merge_manifests({}, override) == override

    def test_override_empty(self):
        base = {"tools": [{"name": "git"}]}
        assert merge_manifests(base, {}) == base

    def test_both_none(self):
        assert merge_manifests(None, None) == {}

    def test_base_none(self):
        override = {"tools": [{"name": "uv"}]}
        assert merge_manifests(None, override) == override


class TestPluginsUnion:
    def test_disjoint_plugins(self):
        base = {"plugins": [{"ref": "mk:a", "enabled": True}]}
        override = {"plugins": [{"ref": "mk:b", "enabled": True}]}
        result = merge_manifests(base, override)
        refs = [p["ref"] for p in result["plugins"]]
        assert refs == ["mk:a", "mk:b"]

    def test_same_plugin_override_fields(self):
        base = {"plugins": [{"ref": "mk:a", "enabled": True, "scope": "user"}]}
        override = {"plugins": [{"ref": "mk:a", "enabled": False}]}
        result = merge_manifests(base, override)
        assert len(result["plugins"]) == 1
        assert result["plugins"][0]["ref"] == "mk:a"
        assert result["plugins"][0]["enabled"] is False
        assert result["plugins"][0]["scope"] == "user"  # preserved from base

    def test_order_preserved(self):
        base = {"plugins": [{"ref": "mk:a"}, {"ref": "mk:b"}]}
        override = {"plugins": [{"ref": "mk:c"}, {"ref": "mk:a", "enabled": True}]}
        result = merge_manifests(base, override)
        refs = [p["ref"] for p in result["plugins"]]
        assert refs == ["mk:a", "mk:b", "mk:c"]
        assert result["plugins"][0]["enabled"] is True


class TestMarketplacesUnion:
    def test_disjoint_marketplaces(self):
        base = {"marketplaces": [{"name": "mk1", "source": "url1"}]}
        override = {"marketplaces": [{"name": "mk2", "source": "url2"}]}
        result = merge_manifests(base, override)
        names = [m["name"] for m in result["marketplaces"]]
        assert names == ["mk1", "mk2"]

    def test_same_marketplace_override(self):
        base = {"marketplaces": [{"name": "mk1", "source": "old", "alwaysUpdate": False}]}
        override = {"marketplaces": [{"name": "mk1", "alwaysUpdate": True}]}
        result = merge_manifests(base, override)
        assert len(result["marketplaces"]) == 1
        assert result["marketplaces"][0]["alwaysUpdate"] is True
        assert result["marketplaces"][0]["source"] == "old"


class TestToolsUnion:
    def test_disjoint_tools(self):
        base = {"tools": [{"name": "git"}]}
        override = {"tools": [{"name": "uv", "install": {"linux": "curl ..."}}]}
        result = merge_manifests(base, override)
        names = [t["name"] for t in result["tools"]]
        assert names == ["git", "uv"]

    def test_same_tool_override_install(self):
        base = {"tools": [{"name": "uv", "install": {"linux": "old"}}]}
        override = {"tools": [{"name": "uv", "install": {"linux": "new", "darwin": "brew"}}]}
        result = merge_manifests(base, override)
        assert len(result["tools"]) == 1
        # install is a dict replaced by override (not deep-merged at array-entry level)
        assert result["tools"][0]["install"] == {"linux": "new", "darwin": "brew"}


class TestPathEntriesUnion:
    def test_disjoint_paths(self):
        base = {"path_entries": ["~/.local/bin"]}
        override = {"path_entries": ["/usr/local/bin"]}
        result = merge_manifests(base, override)
        assert result["path_entries"] == ["~/.local/bin", "/usr/local/bin"]

    def test_duplicate_paths(self):
        base = {"path_entries": ["~/.local/bin", "/usr/local/bin"]}
        override = {"path_entries": ["~/.local/bin", "/opt/bin"]}
        result = merge_manifests(base, override)
        assert result["path_entries"] == ["~/.local/bin", "/usr/local/bin", "/opt/bin"]

    def test_empty_base_paths(self):
        override = {"path_entries": ["~/.local/bin"]}
        result = merge_manifests({}, override)
        assert result["path_entries"] == ["~/.local/bin"]


class TestDeepMergeObjects:
    def test_venv_merge(self):
        base = {"venv": {"check_imports": ["yaml"]}}
        override = {"venv": {"check_imports": ["requests"]}}
        result = merge_manifests(base, override)
        # venv is a plain dict — override wins for check_imports
        assert result["venv"]["check_imports"] == ["requests"]

    def test_config_merge(self):
        base = {"config": {"file": "config.yaml", "defaults_source": "defaults/config.yaml"}}
        override = {"config": {"file": "config.yaml", "required_fields": {"key": {"user_msg": "msg"}}}}
        result = merge_manifests(base, override)
        assert result["config"]["file"] == "config.yaml"
        assert result["config"]["defaults_source"] == "defaults/config.yaml"
        assert "key" in result["config"]["required_fields"]


class TestIniSettingsUnion:
    def test_disjoint_ini(self):
        base = {"ini_settings": [{"file": "a.ini", "section": "S1", "settings": {"k": "v"}}]}
        override = {"ini_settings": [{"file": "b.ini", "section": "S2", "settings": {"k2": "v2"}}]}
        result = merge_manifests(base, override)
        assert len(result["ini_settings"]) == 2

    def test_same_file_section_merge(self):
        base = {"ini_settings": [{"file": "a.ini", "section": "S", "settings": {"k1": "v1"}}]}
        override = {"ini_settings": [{"file": "a.ini", "section": "S", "settings": {"k2": "v2"}}]}
        result = merge_manifests(base, override)
        assert len(result["ini_settings"]) == 1
        # settings dict replaced by override (shallow merge at array-entry level)
        assert result["ini_settings"][0]["settings"] == {"k2": "v2"}


class TestPypiPackagesUnion:
    def test_disjoint_packages(self):
        base = {"pypi_packages": [{"package": "foo", "extract_to": "/a"}]}
        override = {"pypi_packages": [{"package": "bar", "extract_to": "/b"}]}
        result = merge_manifests(base, override)
        pkgs = [p["package"] for p in result["pypi_packages"]]
        assert pkgs == ["foo", "bar"]

    def test_same_package_override(self):
        base = {"pypi_packages": [{"package": "foo", "extract_to": "/old"}]}
        override = {"pypi_packages": [{"package": "foo", "extract_to": "/new"}]}
        result = merge_manifests(base, override)
        assert len(result["pypi_packages"]) == 1
        assert result["pypi_packages"][0]["extract_to"] == "/new"


class TestScalarOverride:
    def test_scalar_override(self):
        base = {"some_flag": True}
        override = {"some_flag": False}
        result = merge_manifests(base, override)
        assert result["some_flag"] is False

    def test_new_keys_added(self):
        base = {"a": 1}
        override = {"b": 2}
        result = merge_manifests(base, override)
        assert result == {"a": 1, "b": 2}


class TestInputsNotMutated:
    def test_base_not_mutated(self):
        base = {"plugins": [{"ref": "mk:a", "enabled": True}]}
        override = {"plugins": [{"ref": "mk:a", "enabled": False}]}
        base_copy = {"plugins": [{"ref": "mk:a", "enabled": True}]}
        merge_manifests(base, override)
        assert base == base_copy

    def test_override_not_mutated(self):
        base = {"plugins": [{"ref": "mk:a"}]}
        override = {"plugins": [{"ref": "mk:b"}]}
        override_copy = {"plugins": [{"ref": "mk:b"}]}
        merge_manifests(base, override)
        assert override == override_copy


class TestProjectVenvMerge:
    def test_project_venv_deep_merge(self):
        """project_venv from two layers is deep-merged (override wins for conflicts)."""
        base = {"project_venv": {"extras": ["dev"], "check_imports": ["pytest"]}}
        override = {"project_venv": {"extras": ["docs"], "check_imports": ["sphinx"]}}
        result = merge_manifests(base, override)
        # Override wins for conflicting keys (both are scalar lists under a dict)
        assert result["project_venv"]["extras"] == ["docs"]
        assert result["project_venv"]["check_imports"] == ["sphinx"]

    def test_project_venv_additive_keys(self):
        """project_venv keys from base are preserved when override adds new keys."""
        base = {"project_venv": {"extras": ["dev"]}}
        override = {"project_venv": {"check_imports": ["pytest"]}}
        result = merge_manifests(base, override)
        assert result["project_venv"]["extras"] == ["dev"]
        assert result["project_venv"]["check_imports"] == ["pytest"]

    def test_project_venv_only_in_one_layer(self):
        """project_venv in only one layer is passed through."""
        base = {"tools": [{"name": "git"}]}
        override = {"project_venv": {"extras": ["dev"]}}
        result = merge_manifests(base, override)
        assert result["project_venv"] == {"extras": ["dev"]}
        assert result["tools"] == [{"name": "git"}]


class TestMultiLayerMerge:
    def test_three_layer_merge(self):
        """Simulates user → user.local → project merge."""
        user = {"tools": [{"name": "git"}], "path_entries": ["~/.local/bin"]}
        user_local = {"tools": [{"name": "uv"}]}
        project = {"tools": [{"name": "git", "install": {"linux": "apt install git"}}],
                   "plugins": [{"ref": "mk:p1"}]}

        merged = merge_manifests(user, user_local)
        merged = merge_manifests(merged, project)

        tool_names = [t["name"] for t in merged["tools"]]
        assert "git" in tool_names
        assert "uv" in tool_names
        # git should have install from project layer
        git_tool = next(t for t in merged["tools"] if t["name"] == "git")
        assert git_tool["install"] == {"linux": "apt install git"}
        assert merged["path_entries"] == ["~/.local/bin"]
        assert merged["plugins"][0]["ref"] == "mk:p1"
