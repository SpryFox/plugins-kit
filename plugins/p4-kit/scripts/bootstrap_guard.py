"""bootstrap_guard.py -- detect whether the bootstrap plugin has provisioned a
plugin, and fail gracefully (with an actionable message) when it has not.

CANONICAL SOURCE. This module is **vendored** (copied byte-for-byte) into each
plugin that needs a runtime bootstrap-presence guard, the same way path_repair.py
is vendored. A drift test asserts the copies match this canonical.

CRITICAL CONSTRAINT: this module must be **stdlib-only** and must **never import
bootstrap_lib** -- the whole point is to run when bootstrap (and therefore
bootstrap_lib) may be absent. The vendored copies live next to the script that
imports them (e.g. `<plugin>/scripts/bootstrap_guard.py`) and are imported as a
plain top-level module (`from bootstrap_guard import require_bootstrap`), NOT via
the bootstrap_lib package.

Detection signal: bootstrap writes a per-plugin log at
`~/.claude/plugins/data/<marketplace>/<plugin>/bootstrap.log` the first time its
engine processes that plugin (see root CLAUDE.md: "if the log doesn't exist,
bootstrap never reached that plugin"). Its absence is the cheap, reliable proxy
for "the bootstrap plugin has not run for this plugin" -- whether because the
bootstrap plugin is not installed at all, or is installed but never provisioned
this plugin.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

EXIT_BOOTSTRAP_MISSING = 3


def data_dir(plugin: str, marketplace: str = "plugins-kit") -> Path:
    """The per-plugin bootstrap data directory."""
    return Path(os.path.expanduser("~")) / ".claude" / "plugins" / "data" / marketplace / plugin


def is_provisioned(plugin: str, marketplace: str = "plugins-kit") -> bool:
    """True if bootstrap appears to have run for this plugin at least once."""
    return (data_dir(plugin, marketplace) / "bootstrap.log").exists()


def message(plugin: str, marketplace: str = "plugins-kit", feature: str | None = None,
            missing: str | None = None) -> str:
    """The canonical, actionable bootstrap-absence message."""
    what = f"{plugin}'s setup" if not feature else f"{plugin}'s {feature}"
    miss = f" (missing: {missing})" if missing else ""
    return (
        f"[{plugin}] the '{marketplace}:bootstrap' plugin has not provisioned "
        f"{what}{miss}. Install/enable the bootstrap plugin and start a new "
        f"session so it can build this plugin's dependencies, then retry."
    )


def require_bootstrap(plugin: str, marketplace: str = "plugins-kit",
                      feature: str | None = None, missing: str | None = None,
                      force: bool = False) -> None:
    """Exit with the canonical message if bootstrap has not provisioned this plugin.

    Pass force=True to emit the message unconditionally -- use this in an
    `except ImportError` handler around a bootstrap_lib import, where the failed
    import is itself proof bootstrap did not provision the venv.
    """
    if force or not is_provisioned(plugin, marketplace):
        print(message(plugin, marketplace, feature, missing), file=sys.stderr)
        sys.exit(EXIT_BOOTSTRAP_MISSING)
