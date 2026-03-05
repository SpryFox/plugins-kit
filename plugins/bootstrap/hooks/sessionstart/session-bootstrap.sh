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
# Validate each candidate by execution, not just PATH presence.
# This handles Windows Store stubs (python3 in PATH but exits 126).

PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        if "$candidate" -c "import sys; sys.exit(0 if sys.version_info[0] >= 3 else 1)" 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done

# --- Self-bootstrap Python via python-build-standalone ---
# If no valid Python 3 is found, download a standalone build and install it
# to the plugin data directory with a symlink in ~/.local/bin.

if [ -z "$PYTHON" ]; then
    PY_VERSION="3.12.9"
    RELEASE_TAG="20250317"
    INSTALL_DIR="${PLUGIN_DATA}/python"

    # Detect platform
    OS="$(uname -s)"
    ARCH="$(uname -m)"

    # Map to python-build-standalone target triple
    if [[ "$OS" == "Darwin" ]]; then
        if [[ "$ARCH" == "arm64" ]]; then
            TRIPLE="aarch64-apple-darwin"
        else
            TRIPLE="x86_64-apple-darwin"
        fi
    elif [[ "$OS" == "Linux" ]]; then
        if [[ "$ARCH" == "aarch64" ]]; then
            TRIPLE="aarch64-unknown-linux-gnu"
        else
            TRIPLE="x86_64-unknown-linux-gnu"
        fi
    elif [[ "$OS" == MINGW* ]] || [[ "$OS" == MSYS* ]]; then
        TRIPLE="x86_64-pc-windows-msvc"
    else
        cat <<'EOF'
{"continue": true, "suppressOutput": false, "systemMessage": "bootstrap -> python3 not found and platform not supported for auto-install. Install Python 3 manually.", "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "bootstrap -> CRITICAL: python3 not found. Unsupported platform for auto-install. Install Python 3.x manually."}}
EOF
        exit 0
    fi

    ARCHIVE="cpython-${PY_VERSION}+${RELEASE_TAG}-${TRIPLE}-install_only_stripped.tar.gz"
    URL="https://github.com/indygreg/python-build-standalone/releases/download/${RELEASE_TAG}/${ARCHIVE}"

    # Download and extract
    mkdir -p "$INSTALL_DIR"
    if ! curl -LsSf "$URL" | tar xz -C "$INSTALL_DIR" 2>/dev/null; then
        cat <<'EOF'
{"continue": true, "suppressOutput": false, "systemMessage": "bootstrap -> python3 not found and auto-install failed (download error). Install Python 3 manually.", "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "bootstrap -> CRITICAL: python3 not found. Auto-install download failed. Install Python 3.x manually."}}
EOF
        exit 0
    fi

    # Set binary path and create symlink in ~/.local/bin
    mkdir -p "${HOME}/.local/bin"
    if [[ "$OS" == MINGW* ]] || [[ "$OS" == MSYS* ]]; then
        PYTHON="${INSTALL_DIR}/python/install/python.exe"
        ln -sf "$PYTHON" "${HOME}/.local/bin/python3"
    else
        PYTHON="${INSTALL_DIR}/python/install/bin/python3"
        ln -sf "$PYTHON" "${HOME}/.local/bin/python3"
    fi
fi

# --- Invoke Engine ---

exec "$PYTHON" "${PLUGIN_ROOT}/engine/bootstrap_engine.py" \
    --plugin-root "$PLUGIN_ROOT" \
    --data-dir "$PLUGIN_DATA"
