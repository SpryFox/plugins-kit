#!/usr/bin/env bash
set -euo pipefail

# validate-cache.sh — Step 4 of session bootstrap
#
# Computes a SHA256 hash of all three manifest files and compares it
# to a stored validation flag. If the hash matches, Steps 1–3 can be
# skipped. If not, the caller should run all steps then call
# write_validation_flag to update the cache.
#
# Usage:
#   bash validate-cache.sh <plugin-root> <plugin-data-dir>
#   (check only — exits 0 if cache valid, 1 if invalid)
#
# Output: JSON to stdout (for additionalContext integration)

# --- JSON Output Helpers ---
# Duplicated from sibling scripts for standalone operation.
# Task #7 (assembly) will factor these into a shared file.

json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

emit_error() {
    local message="$1"
    local step="${2:-validate_cache}"
    cat <<EOF
{"status": "error", "step": "$(json_escape "$step")", "message": "$(json_escape "$message")"}
EOF
}

# --- Cross-Platform SHA256 ---

compute_sha256() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 | awk '{print $1}'
    elif command -v sha256sum >/dev/null 2>&1; then
        sha256sum | awk '{print $1}'
    else
        return 1
    fi
}

# --- Hash Computation ---

compute_manifest_hash() {
    local plugin_root="$1"
    local manifests=(
        "${plugin_root}/system-tools.yaml"
        "${plugin_root}/pyproject.toml"
        "${plugin_root}/git-dependencies.yaml"
    )

    # Verify all manifests exist
    for f in "${manifests[@]}"; do
        if [ ! -f "$f" ]; then
            return 1
        fi
    done

    # Concatenate all manifest contents and hash
    cat "${manifests[@]}" | compute_sha256
}

# --- Validation Flag Functions ---

check_validation_flag() {
    local plugin_root="$1"
    local plugin_data="$2"
    local flag_file="${plugin_data}/.bootstrap-validated"

    # Compute current hash
    local current_hash
    if ! current_hash=$(compute_manifest_hash "$plugin_root"); then
        cat <<EOF
{"status": "ok", "step": "validate_cache", "cached": false, "reason": "hash computation failed"}
EOF
        return 1
    fi

    # Check flag file exists
    if [ ! -f "$flag_file" ]; then
        cat <<EOF
{"status": "ok", "step": "validate_cache", "cached": false, "reason": "no flag file"}
EOF
        return 1
    fi

    # Compare hashes
    local stored_hash
    stored_hash="$(cat "$flag_file" 2>/dev/null || true)"

    if [ "$stored_hash" = "$current_hash" ]; then
        cat <<EOF
{"status": "ok", "step": "validate_cache", "cached": true, "hash": "$(json_escape "$current_hash")"}
EOF
        return 0
    else
        cat <<EOF
{"status": "ok", "step": "validate_cache", "cached": false, "reason": "hash mismatch"}
EOF
        return 1
    fi
}

write_validation_flag() {
    local plugin_root="$1"
    local plugin_data="$2"
    local flag_file="${plugin_data}/.bootstrap-validated"

    # Ensure data directory exists
    mkdir -p "$plugin_data"

    # Compute current hash
    local current_hash
    if ! current_hash=$(compute_manifest_hash "$plugin_root"); then
        emit_error "Failed to compute manifest hash" "write_cache"
        return 1
    fi

    # Write flag
    if ! printf '%s' "$current_hash" > "$flag_file"; then
        emit_error "Failed to write flag file: $flag_file" "write_cache"
        return 1
    fi

    cat <<EOF
{"status": "ok", "step": "write_cache", "hash": "$(json_escape "$current_hash")"}
EOF
    return 0
}

# --- Main ---
# When run directly (not sourced), check the validation flag

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ $# -lt 2 ]; then
        emit_error "Usage: validate-cache.sh <plugin-root> <plugin-data-dir>"
        exit 1
    fi
    check_validation_flag "$1" "$2"
fi
