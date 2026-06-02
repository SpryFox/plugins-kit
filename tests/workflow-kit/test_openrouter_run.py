"""Unit tests for the workflow-kit openrouter runner's pure helpers.

The runner lazy-imports openrouter_kit / openai inside main(), so importing the
module here needs no network and no SDK.
"""

import importlib.util
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins" / "workflow-kit" / "scripts" / "openrouter_run.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("workflow_kit_openrouter_run", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


orr = _load()


def test_build_messages_user_only():
    assert orr.build_messages("hi") == [{"role": "user", "content": "hi"}]


def test_build_messages_with_system():
    assert orr.build_messages("hi", "sys") == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
