"""Fixtures for local-review-kit tests."""

import os
import sys

import pytest

PLUGIN_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "local-review-kit")
)

# Add module paths so tests can import setup and bootstrap-check
scripts_path = os.path.join(PLUGIN_ROOT, "scripts")
hooks_stop_path = os.path.join(PLUGIN_ROOT, "hooks", "stop")
for p in (scripts_path, hooks_stop_path):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture
def plugin_root():
    """Path to the local-review-kit plugin."""
    return PLUGIN_ROOT


@pytest.fixture
def data_dir(tmp_path):
    """Temporary data directory with config.yaml location."""
    d = tmp_path / "data"
    d.mkdir()
    return str(d)


@pytest.fixture
def defaults_dir():
    """Path to plugin's defaults/ directory."""
    return os.path.join(PLUGIN_ROOT, "defaults")


@pytest.fixture
def sample_config(tmp_path):
    """Factory for writing config files with known content."""

    def _write(content: str, filename: str = "config.yaml") -> str:
        path = tmp_path / filename
        path.write_text(content)
        return str(path)

    return _write


@pytest.fixture
def full_config_data():
    """A complete valid config dict."""
    return {
        "OPENAI_API_KEY": "sk-test123",
        "OPENROUTER_API_KEY": "sk-or-test456",
        "P4PORT": "ssl:perforce.example.com:1666",
        "P4USER": "testuser",
        "DEFAULT_AGENT": "claude-haiku",
    }
