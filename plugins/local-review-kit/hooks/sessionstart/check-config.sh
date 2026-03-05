#!/usr/bin/env bash
set -euo pipefail

# check-config.sh — Step 5 of session bootstrap
#
# Checks whether plugin configuration exists and is complete by running
# the plugin's setup.py --check. If config is missing, emits context
# directing Claude to guide the user through an interactive setup flow.
#
# Usage:
#   bash check-config.sh <plugin-root> <plugin-data-dir>
#
# Output: JSON to stdout (for additionalContext integration)
# Exit:   0 = config valid (or no setup script), 1 = needs setup

# --- JSON Output Helpers ---
# Guarded: skip if already provided by bootstrap-helpers.sh

if ! declare -f json_escape >/dev/null 2>&1; then
json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}
fi

# --- OS Detection ---
# Guarded: skip if already provided by bootstrap-helpers.sh

if ! declare -f detect_os >/dev/null 2>&1; then
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
fi

# --- Venv Python Resolver ---
# Guarded: skip if already provided by create-venv.sh

if ! declare -f _resolve_python_exe >/dev/null 2>&1; then
_resolve_python_exe() {
    local venv_dir="$1"
    local os_key
    os_key="$(detect_os 2>/dev/null || true)"

    if [ "$os_key" = "windows" ] && [ -f "${venv_dir}/Scripts/python.exe" ]; then
        printf '%s' "${venv_dir}/Scripts/python.exe"
    elif [ -f "${venv_dir}/bin/python" ]; then
        printf '%s' "${venv_dir}/bin/python"
    fi
}
fi

_emit_cc_success() {
    cat <<EOF
{"status": "ok", "step": "config_check"}
EOF
}

_emit_cc_error() {
    local message="$1"
    cat <<EOF
{"status": "error", "step": "config_check", "message": "$(json_escape "$message")"}
EOF
}

_emit_cc_needs_setup() {
    local context_message="$1"
    local user_message="$2"
    cat <<EOF
{"status": "needs_setup", "step": "config_check", "context_message": "$(json_escape "$context_message")", "user_message": "$(json_escape "$user_message")"}
EOF
}

# --- Config Checker ---

check_config() {
    local plugin_root="$1"
    local plugin_data="$2"
    local setup_script="${plugin_root}/scripts/setup.py"

    # No setup script = no config to check
    if [ ! -f "$setup_script" ]; then
        _emit_cc_success
        return 0
    fi

    # Resolve Python: prefer venv Python, fall back to system
    local python_exe=""
    local venv_dir="${plugin_data}/.venv"
    if [ -d "$venv_dir" ]; then
        python_exe="$(_resolve_python_exe "$venv_dir")"
    fi
    if [ -z "$python_exe" ]; then
        # Fall back to system Python — verify it actually runs
        # (Windows App Execution Aliases pass command -v but don't work)
        local candidate
        for candidate in python3 python; do
            if command -v "$candidate" >/dev/null 2>&1 && \
               "$candidate" -c "print('ok')" >/dev/null 2>&1; then
                python_exe="$candidate"
                break
            fi
        done
        if [ -z "$python_exe" ]; then
            _emit_cc_error "No Python executable found for config check"
            return 1
        fi
    fi

    # Run setup.py --check
    local check_output
    local check_exit
    check_output=$("$python_exe" "$setup_script" --check --data-dir "$plugin_data" 2>&1) || check_exit=$?
    check_exit="${check_exit:-0}"

    if [ "$check_exit" -eq 0 ]; then
        _emit_cc_success
        return 0
    elif [ "$check_exit" -eq 1 ]; then
        # Needs setup — build context message directing Claude to the setup skill
        local context_msg="Plugin configuration is incomplete. Missing fields detected.
To set up configuration, invoke the local-review-setup skill which will guide you through an interactive setup flow.
The setup script is at: ${setup_script}
Data directory: ${plugin_data}
Run '${python_exe} ${setup_script} --describe --data-dir ${plugin_data}' to see field descriptions."

        local user_msg="local-review-kit configuration is incomplete. Say 'setup local-review-kit' to configure."

        _emit_cc_needs_setup "$context_msg" "$user_msg"
        return 1
    else
        _emit_cc_error "setup.py --check failed with exit code ${check_exit}: ${check_output}"
        return 1
    fi
}

# --- Main ---
# When run directly (not sourced), execute check_config with $1 and $2

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ $# -lt 2 ]; then
        _emit_cc_error "Usage: check-config.sh <plugin-root> <plugin-data-dir>"
        exit 1
    fi
    check_config "$1" "$2"
fi
