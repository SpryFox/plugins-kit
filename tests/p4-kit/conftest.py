"""Fixtures for p4-kit tests."""

import os
import sys

import pytest

PLUGIN_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "p4-kit")
)

scripts_path = os.path.join(PLUGIN_ROOT, "scripts")
for p in (scripts_path, PLUGIN_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture
def plugin_root():
    """Path to the p4-kit plugin."""
    return PLUGIN_ROOT
