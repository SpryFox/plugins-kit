#!/usr/bin/env bash
set -euo pipefail

# session-bootstrap.sh — SessionStart hook for update01 plugin
#
# Always-run bootstrap — no cache check, no validation flag.
# Runs step scripts unconditionally every session.
#
#   1. Verify system tools (currently no-op)
#   2. Create/update Python venv (currently no-op)
#
# Output: Single JSON object to stdout (lands in additionalContext)
# Exit:   0 = bootstrap complete, 1 = error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Source shared helpers and step functions ---

source "$SCRIPT_DIR/lib/bootstrap-helpers.sh"
source "$SCRIPT_DIR/check-system-tools.sh"
source "$SCRIPT_DIR/create-venv.sh"
source "$SCRIPT_DIR/ensure-known-marketplaces.sh"

# --- Hook Response Wrapper ---

emit_hook_response() {
    local context_message="$1"
    local user_message="${2:-$1}"
    local escaped_context escaped_user
    escaped_context="$(json_escape "$context_message")"
    escaped_user="$(json_escape "$user_message")"
    cat <<EOF
{"continue": true, "suppressOutput": false, "systemMessage": "$escaped_user", "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "$escaped_context"}}
EOF
}

# --- JSON Field Extractors ---

_extract_json_field() {
    local json="$1" field="$2"
    printf '%s' "$json" | sed -n 's/.*"'"$field"'":[[:space:]]*"\([^"]*\)".*/\1/p'
}

# --- Output Helpers ---

format_bootstrap_error_context() {
    local step_json="$1"
    local context_msg
    context_msg="$(_extract_json_field "$step_json" "context_message")"
    if [ -n "$context_msg" ]; then
        local decoded
        decoded="$(printf '%b' "$context_msg")"
        printf '%s' "update01 -> Bootstrap failed:
${decoded}"
    else
        local msg
        msg="$(_extract_json_field "$step_json" "message")"
        printf '%s' "update01 -> ERROR: $msg"
    fi
}

format_bootstrap_error_user() {
    local step_json="$1"
    local user_msg
    user_msg="$(_extract_json_field "$step_json" "user_message")"
    if [ -n "$user_msg" ]; then
        local decoded
        decoded="$(printf '%b' "$user_msg")"
        printf '%s' "update01 -> Setup issues found:
${decoded}"
    else
        local msg
        msg="$(_extract_json_field "$step_json" "message")"
        printf '%s' "update01 -> ERROR: $msg"
    fi
}

# --- Main Bootstrap Flow ---

main() {
    # Step 1: Check system tools (no-op — always succeeds)
    local step1_json
    if ! step1_json=$(check_system_tools); then
        emit_hook_response "$(format_bootstrap_error_context "$step1_json")" "$(format_bootstrap_error_user "$step1_json")"
        exit 0
    fi

    # Step 2: Create/update venv (no-op — always succeeds)
    local step2_json
    if ! step2_json=$(create_venv); then
        emit_hook_response "$(format_bootstrap_error_context "$step2_json")"
        exit 1
    fi

    # Step 3: Ensure known_marketplaces.json has plugins-kit entry
    local step3_json
    if ! step3_json=$(ensure_known_marketplaces "$PLUGIN_ROOT"); then
        emit_hook_response "$(format_bootstrap_error_context "$step3_json")"
        exit 1
    fi

    # All steps passed
    emit_hook_response "update01 -> ok"
}

main
