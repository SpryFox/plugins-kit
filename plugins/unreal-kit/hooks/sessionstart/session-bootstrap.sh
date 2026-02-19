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

# --- Output Helpers ---

emit_cached_success() {
    local hash="$1"
    cat <<EOF
{"status": "ok", "plugin": "unreal-kit", "message": "✓ unreal-kit dependencies validated (cached)", "cached": true, "hash": "$(json_escape "$hash")"}
EOF
}

emit_full_success() {
    local step_system_tools="$1"
    local step_venv="$2"
    local step_git_deps="$3"
    local step_cache="$4"
    cat <<EOF
{"status": "ok", "plugin": "unreal-kit", "message": "✓ unreal-kit dependencies validated", "cached": false, "steps": {"system_tools": $step_system_tools, "venv": $step_venv, "git_deps": $step_git_deps, "cache": $step_cache}}
EOF
}

emit_bootstrap_error() {
    local step_json="$1"
    # Pass through the step's error JSON, wrapped with plugin context
    cat <<EOF
{"status": "error", "plugin": "unreal-kit", "message": "✗ unreal-kit bootstrap failed", "failed_step": $step_json}
EOF
}

# --- Main Bootstrap Flow ---

main() {
    local silent_mode
    silent_mode="$(read_silent_config)"

    # Step 0: Check validation flag
    local cache_json
    if cache_json=$(check_validation_flag "$PLUGIN_ROOT" "$PLUGIN_DATA" 2>/dev/null); then
        # Cache hit — extract hash from JSON
        local hash
        hash="$(printf '%s' "$cache_json" | sed -n 's/.*"hash":[[:space:]]*"\([^"]*\)".*/\1/p')"
        if [ "$silent_mode" = "true" ]; then
            exit 0
        fi
        emit_cached_success "$hash"
        exit 0
    fi

    # Cache miss — run full bootstrap

    # Step 1: Check system tools
    local step1_json
    if ! step1_json=$(check_system_tools "${PLUGIN_ROOT}/system-tools.yaml"); then
        emit_bootstrap_error "$step1_json"
        exit 1
    fi

    # Step 2: Create/update venv
    local step2_json
    if ! step2_json=$(create_venv "$PLUGIN_ROOT" "$PLUGIN_DATA"); then
        emit_bootstrap_error "$step2_json"
        exit 1
    fi

    # Step 3: Fetch git dependencies
    local step3_json
    if ! step3_json=$(fetch_git_deps "${PLUGIN_ROOT}/git-dependencies.yaml" "$PLUGIN_DATA"); then
        emit_bootstrap_error "$step3_json"
        exit 1
    fi

    # Step 4: Write validation flag
    local step4_json
    if ! step4_json=$(write_validation_flag "$PLUGIN_ROOT" "$PLUGIN_DATA"); then
        emit_bootstrap_error "$step4_json"
        exit 1
    fi

    # All steps passed
    if [ "$silent_mode" = "true" ]; then
        exit 0
    fi
    emit_full_success "$step1_json" "$step2_json" "$step3_json" "$step4_json"
}

main
