#!/usr/bin/env bash
set -euo pipefail

# create-venv.sh — Step 2 of session bootstrap
#
# Creates a persistent Python virtual environment from pyproject.toml
# using uv sync. The venv is stored in plugin data (outside the cache)
# so it survives cache refreshes.
#
# Usage:
#   bash create-venv.sh <plugin-root> <plugin-data-dir>
#
# Output: JSON to stdout (for additionalContext integration)
# Exit:   0 = venv ready, 1 = error

# --- JSON Output Helpers ---
# Duplicated from check-system-tools.sh for standalone operation.
# Task #7 (assembly) will factor these into a shared file.

json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

emit_success() {
    local venv_path="$1"
    local python_exe="$2"
    cat <<EOF
{"status": "ok", "step": "venv", "venv_path": "$(json_escape "$venv_path")", "python_executable": "$(json_escape "$python_exe")"}
EOF
}

emit_error() {
    local message="$1"
    local remediation="${2:-}"
    local rem_field=""
    if [ -n "$remediation" ]; then
        rem_field=", \"remediation\": \"$(json_escape "$remediation")\""
    fi
    cat <<EOF
{"status": "error", "step": "venv", "message": "$(json_escape "$message")"$rem_field}
EOF
}

# --- OS Detection ---
# Duplicated from check-system-tools.sh for standalone operation.

detect_os() {
    local ostype="${OSTYPE:-}"
    if [ -n "$ostype" ]; then
        case "$ostype" in
            darwin*)    printf 'macos'   ; return ;;
            linux-gnu*) printf 'ubuntu'  ; return ;;
            msys*|cygwin*) printf 'windows'; return ;;
        esac
    fi

    local uname_s
    uname_s="$(uname -s 2>/dev/null || true)"
    case "$uname_s" in
        Darwin)  printf 'macos'   ; return ;;
        Linux)   printf 'ubuntu'  ; return ;;
        MINGW*|MSYS*|CYGWIN*) printf 'windows'; return ;;
    esac

    return 1
}

# --- Venv Creator ---

create_venv() {
    local plugin_root="$1"
    local plugin_data="$2"
    local pyproject="${plugin_root}/pyproject.toml"
    local venv_dir="${plugin_data}/.venv"

    # Validate pyproject.toml exists
    if [ ! -f "$pyproject" ]; then
        emit_error "pyproject.toml not found: $pyproject"
        return 1
    fi

    # Ensure plugin data directory exists
    mkdir -p "$plugin_data"

    # Run uv sync with redirected venv location
    # UV_PROJECT_ENVIRONMENT tells uv where to place the venv
    # instead of adjacent to pyproject.toml
    local uv_output
    if ! uv_output=$(UV_PROJECT_ENVIRONMENT="$venv_dir" uv sync \
        --project "$plugin_root" 2>&1); then
        emit_error "uv sync failed: $uv_output" \
            "Run manually: UV_PROJECT_ENVIRONMENT=\"$venv_dir\" uv sync --project \"$plugin_root\""
        return 1
    fi

    # Determine Python executable path (cross-platform)
    local python_exe
    local os_key
    os_key="$(detect_os 2>/dev/null || true)"

    if [ "$os_key" = "windows" ] && [ -f "${venv_dir}/Scripts/python.exe" ]; then
        python_exe="${venv_dir}/Scripts/python.exe"
    elif [ -f "${venv_dir}/bin/python" ]; then
        python_exe="${venv_dir}/bin/python"
    else
        emit_error "Python executable not found in venv at $venv_dir"
        return 1
    fi

    # Verify Python works
    if ! "$python_exe" -c "print('ok')" >/dev/null 2>&1; then
        emit_error "Python executable exists but failed to run: $python_exe"
        return 1
    fi

    emit_success "$venv_dir" "$python_exe"
    return 0
}

# --- Main ---
# When run directly (not sourced), execute create_venv with $1 and $2

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ $# -lt 2 ]; then
        emit_error "Usage: create-venv.sh <plugin-root> <plugin-data-dir>"
        exit 1
    fi
    create_venv "$1" "$2"
fi
