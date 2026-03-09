"""Tests for plugins/bootstrap/lib/var_resolve.py."""

from pathlib import Path

import pytest

from bootstrap_lib.var_resolve import resolve_vars, build_variables


class TestResolveVars:
    def test_simple_expansion(self):
        result = resolve_vars("${plugin_root}/stubs", {"plugin_root": "/opt/plugin"})
        assert result == "/opt/plugin/stubs"

    def test_multiple_vars(self):
        variables = {"plugin_root": "/opt/plugin", "data_dir": "/data"}
        result = resolve_vars("${plugin_root}/config in ${data_dir}", variables)
        assert result == "/opt/plugin/config in /data"

    def test_no_vars(self):
        result = resolve_vars("plain string", {"foo": "bar"})
        assert result == "plain string"

    def test_unresolved_returns_none(self):
        result = resolve_vars("${missing_var}/path", {"other": "val"})
        assert result is None

    def test_partial_unresolved_returns_none(self):
        result = resolve_vars("${known}/${unknown}", {"known": "ok"})
        assert result is None

    def test_empty_string(self):
        result = resolve_vars("", {"foo": "bar"})
        assert result == ""


class TestBuildVariables:
    def test_static_vars(self):
        variables = build_variables("/opt/plugin", "/data")
        assert variables["plugin_root"] == "/opt/plugin"
        assert variables["data_dir"] == "/data"

    def test_config_values_added(self):
        config = {"uproject": "/projects/MyGame/MyGame.uproject"}
        variables = build_variables("/opt/plugin", "/data", config)
        assert variables["uproject"] == "/projects/MyGame/MyGame.uproject"

    def test_dir_derived_from_file_path(self):
        config = {"uproject": "/projects/MyGame/MyGame.uproject"}
        variables = build_variables("/opt/plugin", "/data", config)
        # Path.parent uses OS-native separators, so compare with Path
        assert variables["uproject_dir"] == str(Path("/projects/MyGame"))

    def test_no_dir_for_simple_values(self):
        config = {"mode": "remote"}
        variables = build_variables("/opt/plugin", "/data", config)
        assert "mode_dir" not in variables

    def test_empty_config_values_skipped(self):
        config = {"uproject": "", "engine_dir": ""}
        variables = build_variables("/opt/plugin", "/data", config)
        assert "uproject" not in variables
        assert "engine_dir" not in variables

    def test_non_string_config_skipped(self):
        config = {"count": 42, "flag": True}
        variables = build_variables("/opt/plugin", "/data", config)
        assert "count" not in variables
        assert "flag" not in variables

    def test_none_config(self):
        variables = build_variables("/opt/plugin", "/data", None)
        assert len(variables) == 2
