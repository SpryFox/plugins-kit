"""Resolve the OpenRouter API key from the canonical sources.

Precedence (highest to lowest):

1. ``OPENROUTER_API_KEY`` environment variable
2. ``<project_root>/.local-data/openrouter-kit/.env`` (per-project override)
3. ``~/.claude/plugins/data/plugins-kit/openrouter-kit/.env`` (user default)

``get_api_key`` returns a small dataclass that records both the key value
and where it was sourced from, so consumers can log the source path on
startup for debugging credential confusion.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .constants import API_KEY_ENV, USER_ENV_FILE, project_env_file
from .env_file import read_env_file


@dataclass(frozen=True)
class KeyLookupResult:
    """Result of an API key lookup.

    ``source`` is one of ``"env"``, ``"project"``, ``"user"``, or
    ``"missing"``. When ``key`` is ``None``, ``source`` is always
    ``"missing"`` and ``source_path`` is ``None``.
    """

    key: Optional[str]
    source: str
    source_path: Optional[Path]


def get_api_key(project_root: Optional[Path] = None) -> KeyLookupResult:
    """Resolve the OpenRouter API key.

    Args:
        project_root: Directory to check for a per-project ``.env`` override.
            Defaults to the current working directory when not provided.

    Returns:
        KeyLookupResult with the key, source label, and source path.
        ``key`` is ``None`` if no source has the key.
    """
    env_value = os.environ.get(API_KEY_ENV)
    if env_value:
        return KeyLookupResult(key=env_value, source="env", source_path=None)

    root = Path(project_root) if project_root is not None else Path.cwd()
    project_file = project_env_file(root)
    project_values = read_env_file(project_file)
    project_key = project_values.get(API_KEY_ENV)
    if project_key:
        return KeyLookupResult(key=project_key, source="project", source_path=project_file)

    user_values = read_env_file(USER_ENV_FILE)
    user_key = user_values.get(API_KEY_ENV)
    if user_key:
        return KeyLookupResult(key=user_key, source="user", source_path=USER_ENV_FILE)

    return KeyLookupResult(key=None, source="missing", source_path=None)
