"""OpenRouter endpoint and canonical credential file locations."""

from pathlib import Path

BASE_URL = "https://openrouter.ai/api/v1"
API_KEY_ENV = "OPENROUTER_API_KEY"

# User-scoped credential file. Bootstrap-engine plugin data dirs follow the
# layout ``~/.claude/plugins/data/<marketplace>/<plugin>/``. openrouter-kit
# ships in the plugins-kit marketplace, so the canonical .env path is fixed
# at this location regardless of which CWD a session is launched from.
#
# A developer who needs a different key per project can drop a file at
# ``<project_root>/.local-data/openrouter-kit/.env``; ``get_api_key`` checks
# the project file first and only falls back to USER_ENV_FILE.
USER_ENV_FILE = (
    Path.home() / ".claude" / "plugins" / "data" / "plugins-kit" / "openrouter-kit" / ".env"
)


def project_env_file(project_root: Path) -> Path:
    """Per-project override location.

    Layered after env vars and before the user-scoped file in
    ``get_api_key`` precedence.
    """
    return Path(project_root) / ".local-data" / "openrouter-kit" / ".env"
