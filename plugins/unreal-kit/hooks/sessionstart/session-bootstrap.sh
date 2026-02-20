#!/usr/bin/env bash
set -euo pipefail

# session-bootstrap.sh — SessionStart hook for unreal-kit plugin
#
# Orchestrates the full bootstrap sequence:
#   1. Check validation flag (skip if cached)
#   2. Verify system tools
#   3. Create/update Python venv
#   4. Fetch git dependencies
#   5. Write validation flag
#
# Output: Single JSON object to stdout (lands in additionalContext)
# Exit:   0 = bootstrap complete (or cached), 1 = error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLUGIN_DATA="${HOME}/.claude/plugins/data/unreal-kit"

# --- Source shared helpers and step functions ---

source "$SCRIPT_DIR/lib/bootstrap-helpers.sh"
source "$SCRIPT_DIR/check-system-tools.sh"
source "$SCRIPT_DIR/create-venv.sh"
source "$SCRIPT_DIR/fetch-git-deps.sh"
source "$SCRIPT_DIR/validate-cache.sh"

# --- Config Reader ---

read_silent_config() {
    local config_file="${PLUGIN_ROOT}/bootstrap-config.yaml"
    [ -f "$config_file" ] || { printf 'false'; return; }

    local line
    while IFS= read -r line || [ -n "$line" ]; do
        if [[ "$line" =~ silent_when_valid:[[:space:]]+(.*) ]]; then
            local val="${BASH_REMATCH[1]}"
            val="${val#\"}" ; val="${val%\"}"
            val="${val#\'}" ; val="${val%\'}"
            printf '%s' "$val"
            return
        fi
    done < "$config_file"
    printf 'false'
}

# --- Hook Response Wrapper ---
# Claude Code SessionStart hooks must output JSON in this format for
# additionalContext to appear in the session.

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

emit_hook_silent() {
    cat <<EOF
{"continue": true, "suppressOutput": true}
EOF
}

# --- JSON Field Extractors ---

_extract_json_field() {
    local json="$1" field="$2"
    printf '%s' "$json" | sed -n 's/.*"'"$field"'":[[:space:]]*"\([^"]*\)".*/\1/p'
}

_extract_json_array() {
    # Extract array values: ["a", "b"] -> "a, b"
    local json="$1" field="$2"
    printf '%s' "$json" | sed -n 's/.*"'"$field"'":[[:space:]]*\[\([^]]*\)\].*/\1/p' | sed 's/"//g; s/,[[:space:]]*/,/g' | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | paste -sd ', ' -
}

# --- Output Helpers ---

format_cached_success() {
    local hash="$1"
    printf '%s' "unreal-kit -> ok (cached)"
}

format_full_success_user() {
    local steps=()
    # Extract venv path
    local venv_path
    venv_path="$(_extract_json_field "$1" "venv_path")"
    [ -n "$venv_path" ] && steps+=("synced venv at ${venv_path}")

    # Extract git repos
    local repos
    repos="$(_extract_json_array "$2" "repos")"
    [ -n "$repos" ] && steps+=("fetched git deps: ${repos}")

    # If no details extracted, fall back
    if [ ${#steps[@]} -eq 0 ]; then
        printf '%s' "unreal-kit -> bootstrapped (system tools, venv, git deps)"
        return
    fi

    local detail
    detail="$(IFS='; '; printf '%s' "${steps[*]}")"
    printf '%s' "unreal-kit -> bootstrapped: ${detail}"
}

format_full_success_agent() {
    printf '%s' "unreal-kit -> ok (validated: system tools, venv, git deps)"
}

format_bootstrap_error_context() {
    local step_json="$1"
    local msg tool install_cmd
    msg="$(_extract_json_field "$step_json" "message")"
    tool="$(_extract_json_field "$step_json" "missing_tool")"
    install_cmd="$(_extract_json_field "$step_json" "install_command")"
    if [ -n "$tool" ] && [ -n "$install_cmd" ]; then
        printf '%s' "unreal-kit -> ERROR: $msg. The user can say 'fix-$tool' to ask you to resolve this. To fix it, run: $install_cmd"
    else
        printf '%s' "unreal-kit -> ERROR: $msg"
    fi
}

format_bootstrap_error_user() {
    local step_json="$1"
    local msg tool
    msg="$(_extract_json_field "$step_json" "message")"
    tool="$(_extract_json_field "$step_json" "missing_tool")"
    if [ -n "$tool" ]; then
        printf '%s' "unreal-kit -> $msg. Say 'fix-$tool' to resolve this."
    else
        printf '%s' "unreal-kit -> ERROR: $msg"
    fi
}

# --- Main Bootstrap Flow ---

main() {
    local silent_mode
    silent_mode="$(read_silent_config)"

    # Step 0: Check validation flag
    local cache_json
    if cache_json=$(check_validation_flag "$PLUGIN_ROOT" "$PLUGIN_DATA" 2>/dev/null); then
        # Cache hit
        if [ "$silent_mode" = "true" ]; then
            emit_hook_silent
            exit 0
        fi
        local hash
        hash="$(printf '%s' "$cache_json" | sed -n 's/.*"hash":[[:space:]]*"\([^"]*\)".*/\1/p')"
        emit_hook_response "$(format_cached_success "$hash")"
        exit 0
    fi

    # Cache miss — run full bootstrap

    # Step 1: Check system tools
    local step1_json
    if ! step1_json=$(check_system_tools "${PLUGIN_ROOT}/system-tools.yaml"); then
        emit_hook_response "$(format_bootstrap_error_context "$step1_json")" "$(format_bootstrap_error_user "$step1_json")"
        exit 0
    fi

    # Step 2: Create/update venv
    local step2_json
    if ! step2_json=$(create_venv "$PLUGIN_ROOT" "$PLUGIN_DATA"); then
        emit_hook_response "$(format_bootstrap_error_context "$step2_json")"
        exit 1
    fi

    # Step 3: Fetch git dependencies
    local step3_json
    if ! step3_json=$(fetch_git_deps "${PLUGIN_ROOT}/git-dependencies.yaml" "$PLUGIN_DATA"); then
        emit_hook_response "$(format_bootstrap_error_context "$step3_json")"
        exit 1
    fi

    # Step 4: Write validation flag
    local step4_json
    if ! step4_json=$(write_validation_flag "$PLUGIN_ROOT" "$PLUGIN_DATA"); then
        emit_hook_response "$(format_bootstrap_error_context "$step4_json")"
        exit 1
    fi

    # All steps passed
    if [ "$silent_mode" = "true" ]; then
        emit_hook_silent
        exit 0
    fi
    emit_hook_response "$(format_full_success_agent)" "$(format_full_success_user "$step2_json" "$step3_json")"
}

main
