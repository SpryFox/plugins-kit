"""Shared fixtures for plugins-kit test suite."""

import json
import os

import pytest

BOOTSTRAP_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), os.pardir, "plugins", "bootstrap")
)


@pytest.fixture
def bootstrap_root():
    """Path to the bootstrap plugin root."""
    return BOOTSTRAP_ROOT


@pytest.fixture
def data_dir(tmp_path):
    """Temporary data directory for bootstrap operations."""
    d = tmp_path / "data"
    d.mkdir()
    return str(d)


@pytest.fixture
def defaults_dir():
    """Path to bootstrap defaults directory."""
    return os.path.join(BOOTSTRAP_ROOT, "defaults")


@pytest.fixture
def manifest_file(tmp_path):
    """Write a bootstrap.json manifest to a temp dir and return its path."""

    def _write(manifest: dict) -> str:
        path = tmp_path / "bootstrap.json"
        path.write_text(json.dumps(manifest))
        return str(path)

    return _write
