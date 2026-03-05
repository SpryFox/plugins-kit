#!/usr/bin/env bash
set -euo pipefail

# session-bootstrap.sh — Thin bash wrapper for the Python bootstrap engine.
#
# Resolves paths, guards for python3, then delegates to the engine.
# Engine's stdout becomes the hook response (or no stdout = bare exit = success/cached).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLUGIN_DATA="${HOME}/.claude/plugins/data/bootstrap"

# --- Find Python 3 ---

PYTHON=""
if command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    # Verify it's Python 3
    if python -c "import sys; sys.exit(0 if sys.version_info[0] >= 3 else 1)" 2>/dev/null; then
        PYTHON="python"
    fi
fi

if [ -z "$PYTHON" ]; then
    # No Python 3 — emit error JSON directly from bash
    cat <<'EOF'
{"continue": true, "suppressOutput": false, "systemMessage": "bootstrap -> python3 not found. Install Python 3 to enable bootstrapping.", "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "bootstrap -> CRITICAL: python3 not found in PATH. Cannot run bootstrap engine. Install Python 3.x."}}
EOF
    exit 0
fi

# --- Invoke Engine ---

exec "$PYTHON" "${PLUGIN_ROOT}/engine/bootstrap_engine.py" \
    --plugin-root "$PLUGIN_ROOT" \
    --data-dir "$PLUGIN_DATA"
