#!/usr/bin/env bash
set -euo pipefail

# session-bootstrap.sh — SessionStart hook for test-plugin
#
# Post-M2: Tool checks, venv setup, git deps, and caching are handled by
# the bootstrap engine via bootstrap.json. This hook only runs the config
# check (Step 5) which requires user interaction.
#
# Output: Single JSON object to stdout (lands in additionalContext)
# Exit:   0 = config valid, 1 = error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLUGIN_DATA="${HOME}/.claude/plugins/data/test-plugin"

# --- Source helpers ---
source "$SCRIPT_DIR/check-config.sh"

# --- JSON Field Extraction ---
# Lightweight JSON field extractor (no jq dependency)
_extract_json_field() {
    local json="$1" field="$2"
    printf '%s' "$json" | sed -n 's/.*"'"$field"'":[[:space:]]*"\([^"]*\)".*/\1/p'
}

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

# --- Output Helpers ---

format_config_error_context() {
    local step_json="$1"
    local context_msg
    context_msg="$(_extract_json_field "$step_json" "context_message")"
    if [ -n "$context_msg" ]; then
        local decoded
        decoded="$(printf '%b' "$context_msg")"
        printf '%s' "test-plugin -> Config setup needed:
${decoded}"
    else
        local msg
        msg="$(_extract_json_field "$step_json" "message")"
        printf '%s' "test-plugin -> Config ERROR: $msg"
    fi
}

format_config_error_user() {
    local step_json="$1"
    local user_msg
    user_msg="$(_extract_json_field "$step_json" "user_message")"
    if [ -n "$user_msg" ]; then
        local decoded
        decoded="$(printf '%b' "$user_msg")"
        printf '%s' "test-plugin -> ${decoded}"
    else
        local msg
        msg="$(_extract_json_field "$step_json" "message")"
        printf '%s' "test-plugin -> Config ERROR: $msg"
    fi
}

# --- Main ---

main() {
    local step5_json
    if ! step5_json=$(check_config "$PLUGIN_ROOT" "$PLUGIN_DATA"); then
        emit_hook_response "$(format_config_error_context "$step5_json")" "$(format_config_error_user "$step5_json")"
        exit 0
    fi

    # Config OK — bare exit (no stdout)
    exit 0
}

main
