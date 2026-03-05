"""Tests for local-review-kit hooks/stop/bootstrap-check.py."""

import json
import os
import sys
from importlib import import_module
from unittest.mock import patch, MagicMock

import pytest

# The module has a hyphen in its filename, so use importlib
bootstrap_check = import_module("bootstrap-check")
_format_system_tools_block = bootstrap_check._format_system_tools_block
_resolve_paths = bootstrap_check._resolve_paths
main = bootstrap_check.main


# ---------------------------------------------------------------------------
# _format_system_tools_block
# ---------------------------------------------------------------------------


class TestFormatSystemToolsBlock:
    def test_valid_json_with_context_message(self):
        data = json.dumps({
            "context_message": "- uv: not found\\n- p4: not found",
        })
        result = _format_system_tools_block(data)
        assert "System Tool Failures" in result
        assert "- uv: not found" in result
        assert "- p4: not found" in result
        assert "fix-all" in result.lower() or "Fix" in result

    def test_valid_json_with_message_only(self):
        data = json.dumps({"message": "check-system-tools.sh failed"})
        result = _format_system_tools_block(data)
        assert "System Tool Error" in result
        assert "check-system-tools.sh failed" in result

    def test_invalid_json(self):
        result = _format_system_tools_block("not json {{{")
        assert "could not parse" in result.lower()

    def test_none_input(self):
        result = _format_system_tools_block(None)
        assert "could not parse" in result.lower()

    def test_context_message_with_tabs(self):
        data = json.dumps({"context_message": "tool:\\tok"})
        result = _format_system_tools_block(data)
        assert "tool:\tok" in result

    def test_empty_context_message_falls_to_message(self):
        data = json.dumps({"context_message": "", "message": "fallback msg"})
        result = _format_system_tools_block(data)
        assert "fallback msg" in result


# ---------------------------------------------------------------------------
# _resolve_paths
# ---------------------------------------------------------------------------


class TestResolvePaths:
    def test_derives_plugin_root_from_script(self):
        plugin_root, plugin_data = _resolve_paths()
        # Script is at hooks/stop/bootstrap-check.py
        # So plugin_root should be 2 levels up from hooks/stop/
        assert plugin_root.endswith("local-review-kit")
        assert os.path.isdir(plugin_root)

    def test_plugin_data_in_home(self):
        _, plugin_data = _resolve_paths()
        home = os.path.expanduser("~")
        assert plugin_data.startswith(home)
        assert "local-review-kit" in plugin_data


# ---------------------------------------------------------------------------
# main decision logic (mocked subprocess)
# ---------------------------------------------------------------------------


class TestMainDecisionLogic:
    """Test main() by mocking subprocess calls and stdin."""

    def _make_stdin(self, data):
        """Create a mock stdin with JSON data."""
        mock = MagicMock()
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        return data

    def _run_main(self, input_data, subprocess_side_effects=None):
        """Run main() with mocked stdin and subprocess.

        Returns (exit_code, stdout).
        exit_code is captured via SystemExit or 0 if main returns normally.
        """
        import io

        stdin_buf = io.StringIO(json.dumps(input_data))
        captured_out = io.StringIO()

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            if subprocess_side_effects:
                effect = subprocess_side_effects.pop(0)
                result.returncode = effect.get("returncode", 0)
                result.stdout = effect.get("stdout", "")
                result.stderr = effect.get("stderr", "")
            else:
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            return result

        with patch.object(sys, "stdin", stdin_buf), \
             patch.object(sys, "stdout", captured_out), \
             patch("subprocess.run", side_effect=mock_run), \
             patch.object(bootstrap_check, "_find_python", return_value=sys.executable):
            try:
                main()
                exit_code = 0
            except SystemExit as e:
                exit_code = e.code if e.code is not None else 0

        return exit_code, captured_out.getvalue()

    def test_stop_hook_active_exits_0(self):
        exit_code, _ = self._run_main({"stop_hook_active": True})
        assert exit_code == 0

    def test_cache_valid_config_ok_exits_0(self):
        effects = [
            {"returncode": 0, "stdout": ""},  # validate-cache.sh succeeds
            {"returncode": 0, "stdout": ""},  # setup.py --check succeeds
        ]
        exit_code, _ = self._run_main({}, effects)
        assert exit_code == 0

    def test_system_tools_missing_blocks(self):
        tools_output = json.dumps({
            "context_message": "- uv: not found\\n- p4: not found",
        })
        effects = [
            {"returncode": 1, "stdout": ""},     # cache miss
            {"returncode": 1, "stdout": tools_output},  # tools check fails
        ]
        exit_code, stdout = self._run_main({}, effects)
        output = json.loads(stdout)
        assert output["decision"] == "block"
        assert "System Tool Failures" in output["reason"]

    def test_config_missing_blocks(self):
        config_output = json.dumps({
            "status": "needs_setup",
            "missing_fields": ["P4PORT"],
        })
        effects = [
            {"returncode": 0, "stdout": ""},            # cache valid
            {"returncode": 1, "stdout": config_output},  # config check fails
        ]
        exit_code, stdout = self._run_main({}, effects)
        output = json.loads(stdout)
        assert output["decision"] == "block"
        assert "Configuration Incomplete" in output["reason"]

    def test_cache_stale_tools_ok_blocks_with_restart(self):
        effects = [
            {"returncode": 1, "stdout": ""},   # cache stale
            {"returncode": 0, "stdout": ""},   # tools ok
        ]
        exit_code, stdout = self._run_main({}, effects)
        output = json.loads(stdout)
        assert output["decision"] == "block"
        assert "Restart" in output["reason"]

    def test_invalid_stdin_blocks(self):
        """Non-JSON stdin should produce a block decision."""
        import io
        stdin_buf = io.StringIO("not json")
        captured_out = io.StringIO()

        with patch.object(sys, "stdin", stdin_buf), \
             patch.object(sys, "stdout", captured_out):
            try:
                main()
                exit_code = 0
            except SystemExit as e:
                exit_code = e.code if e.code is not None else 0

        assert exit_code == 1
        output = json.loads(captured_out.getvalue())
        assert output["decision"] == "block"
