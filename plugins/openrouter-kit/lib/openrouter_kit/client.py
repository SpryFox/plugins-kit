"""Lazy-imported OpenAI SDK client pointed at OpenRouter.

The SDK is an optional dependency. Consumers that only need ``get_api_key``
or ``check_account`` do not pay the import cost; consumers that want a
ready-made Chat Completions client call ``make_openai_client``.
"""

from pathlib import Path
from typing import Any, Optional

from .api_key import get_api_key
from .constants import BASE_URL


def make_openai_client(
    api_key: Optional[str] = None,
    *,
    project_root: Optional[Path] = None,
) -> Any:
    """Return an ``openai.OpenAI`` client configured for OpenRouter.

    Args:
        api_key: Explicit key. When None, ``get_api_key`` is invoked to
            resolve from environment or .env files.
        project_root: Forwarded to ``get_api_key`` when ``api_key`` is None.

    Returns:
        An ``openai.OpenAI`` instance with ``base_url`` set to OpenRouter's
        Chat Completions endpoint.

    Raises:
        ImportError: If the ``openai`` package is not installed.
        RuntimeError: If no API key can be resolved from any source.
    """
    if api_key is None:
        result = get_api_key(project_root)
        if result.key is None:
            raise RuntimeError(
                "No OpenRouter API key found. Set OPENROUTER_API_KEY or run "
                "`openrouter-kit set-key`."
            )
        api_key = result.key

    try:
        from openai import OpenAI  # noqa: PLC0415
    except ImportError as e:
        raise ImportError(
            "The 'openai' package is required for make_openai_client. "
            "Install it via `pip install openai` (or pull it as an extra "
            "via `openrouter-kit[sdk]`)."
        ) from e

    return OpenAI(api_key=api_key, base_url=BASE_URL)
