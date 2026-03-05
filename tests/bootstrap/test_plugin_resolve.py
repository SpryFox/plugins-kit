"""Tests for plugin_resolve.py — plugin path resolution from registry."""

import json
import os

import pytest

from plugin_resolve import PluginInfo, list_enabled_plugins, resolve_plugin


class TestResolvePlugin:
    def test_resolves_relative_path(self, tmp_path):
        """Relative installPath is resolved against base_dir."""
        registry = {"plugins": {"kit:test-plugin": [{"installPath": "./test-plugin", "version": "1.0.0"}]}}
        reg_path = str(tmp_path / "installed_plugins.json")
        with open(reg_path, "w") as f:
            json.dump(registry, f)

        base_dir = str(tmp_path / "plugins")
        result = resolve_plugin(reg_path, "kit:test-plugin", base_dir)

        assert result is not None
        assert result.name == "test-plugin"
        assert result.version == "1.0.0"
        assert os.path.isabs(result.install_path)
        assert result.install_path == os.path.normpath(os.path.join(base_dir, "test-plugin"))

    def test_resolves_absolute_path(self, tmp_path):
        """Absolute installPath is used as-is."""
        abs_path = str(tmp_path / "somewhere" / "plugin")
        registry = {"plugins": {"src:my-plugin": [{"installPath": abs_path, "version": "2.0.0"}]}}
        reg_path = str(tmp_path / "installed_plugins.json")
        with open(reg_path, "w") as f:
            json.dump(registry, f)

        result = resolve_plugin(reg_path, "src:my-plugin", str(tmp_path))

        assert result is not None
        assert result.install_path == os.path.normpath(abs_path)

    def test_returns_none_for_missing_ref(self, tmp_path):
        """Unknown plugin ref returns None."""
        registry = {"plugins": {}}
        reg_path = str(tmp_path / "installed_plugins.json")
        with open(reg_path, "w") as f:
            json.dump(registry, f)

        result = resolve_plugin(reg_path, "kit:nonexistent", str(tmp_path))
        assert result is None

    def test_returns_none_for_missing_file(self, tmp_path):
        """Missing registry file returns None."""
        result = resolve_plugin(str(tmp_path / "nope.json"), "y:x", str(tmp_path))
        assert result is None

    def test_returns_none_for_invalid_json(self, tmp_path):
        """Malformed JSON returns None."""
        reg_path = str(tmp_path / "installed_plugins.json")
        with open(reg_path, "w") as f:
            f.write("not json")

        result = resolve_plugin(reg_path, "y:x", str(tmp_path))
        assert result is None

    def test_extracts_name_from_ref(self, tmp_path):
        """Plugin name is the part after : in the ref."""
        registry = {"plugins": {"baz:foo-bar": [{"installPath": "./foo", "version": "1.0.0"}]}}
        reg_path = str(tmp_path / "installed_plugins.json")
        with open(reg_path, "w") as f:
            json.dump(registry, f)

        result = resolve_plugin(reg_path, "baz:foo-bar", str(tmp_path))
        assert result.name == "foo-bar"


class TestListEnabledPlugins:
    def test_returns_resolved_plugins(self, tmp_path):
        """Resolves all enabled plugins from config."""
        registry = {
            "plugins": {
                "kit:a": [{"installPath": "./a", "version": "1.0.0"}],
                "kit:b": [{"installPath": "./b", "version": "2.0.0"}],
            }
        }
        reg_path = str(tmp_path / "installed_plugins.json")
        with open(reg_path, "w") as f:
            json.dump(registry, f)

        config = {"enabled_plugins": ["kit:a", "kit:b"]}
        results = list_enabled_plugins(config, reg_path, str(tmp_path))

        assert len(results) == 2
        assert results[0].name == "a"
        assert results[1].name == "b"

    def test_skips_unresolvable(self, tmp_path):
        """Unresolvable refs are silently skipped."""
        registry = {"plugins": {"kit:a": [{"installPath": "./a", "version": "1.0.0"}]}}
        reg_path = str(tmp_path / "installed_plugins.json")
        with open(reg_path, "w") as f:
            json.dump(registry, f)

        config = {"enabled_plugins": ["kit:a", "kit:missing"]}
        results = list_enabled_plugins(config, reg_path, str(tmp_path))

        assert len(results) == 1
        assert results[0].name == "a"

    def test_empty_enabled_list(self, tmp_path):
        """Empty enabled_plugins returns empty list."""
        reg_path = str(tmp_path / "installed_plugins.json")
        with open(reg_path, "w") as f:
            json.dump({"plugins": {}}, f)

        config = {"enabled_plugins": []}
        results = list_enabled_plugins(config, reg_path, str(tmp_path))
        assert results == []

    def test_missing_enabled_key(self, tmp_path):
        """Config without enabled_plugins key returns empty list."""
        reg_path = str(tmp_path / "installed_plugins.json")
        with open(reg_path, "w") as f:
            json.dump({"plugins": {}}, f)

        results = list_enabled_plugins({}, reg_path, str(tmp_path))
        assert results == []
