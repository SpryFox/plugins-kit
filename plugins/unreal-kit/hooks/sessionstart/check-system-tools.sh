#!/usr/bin/env bash
set -euo pipefail

# check-system-tools.sh — Step 1 of session bootstrap
#
# Reads system-tools.yaml for the detected OS, checks each tool via
# command -v, and fails fast on the first missing tool.
#
# Usage:
#   bash check-system-tools.sh <path-to-system-tools.yaml>
#
# Output: JSON to stdout (for additionalContext integration)
# Exit:   0 = all tools present, 1 = missing tool / error

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

_emit_st_success() {
    local os_key="$1"
    shift
    local tools_json=""
    for tool in "$@"; do
        [ -n "$tools_json" ] && tools_json="$tools_json, "
        tools_json="$tools_json\"$(json_escape "$tool")\""
    done
    cat <<EOF
{"status": "ok", "step": "system_tools", "os": "$os_key", "tools_checked": [$tools_json]}
EOF
}

_emit_st_failure() {
    local tool_name="$1"
    local os_key="$2"
    local install_cmd="$3"
    local escaped_cmd
    escaped_cmd="$(json_escape "$install_cmd")"
    cat <<EOF
{"status": "error", "step": "system_tools", "os": "$os_key", "missing_tool": "$(json_escape "$tool_name")", "install_command": "$escaped_cmd", "message": "Required tool '$(json_escape "$tool_name")' not found. Install with: $escaped_cmd"}
EOF
}

_emit_st_error() {
    local message="$1"
    cat <<EOF
{"status": "error", "step": "system_tools", "message": "$(json_escape "$message")"}
EOF
}

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

    # Fallback to uname
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

# --- YAML Parser ---
# Extracts entries for a given OS section from system-tools.yaml.
# Output: newline-delimited records, one per tool, as "name\tcheck\tinstall" (tab-delimited)
#
# Parsing approach: line-by-line scan. Detect OS section headers by matching
# "  <key>:" at 2-space indent. Within the target section, accumulate fields
# from "- name:", "check:", "install:" entries. Stop on next section or EOF.

parse_system_tools() {
    local yaml_path="$1"
    local target_os="$2"
    local in_section=false
    local name="" check="" install=""
    local line

    while IFS= read -r line || [ -n "$line" ]; do
        # Skip blank lines and comments
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

        # Top-level key (system_tools:) — skip
        if [[ "$line" =~ ^system_tools: ]]; then
            continue
        fi

        # OS section header: exactly 2-space indent followed by word and colon
        if [[ "$line" =~ ^[[:space:]]{2}[a-z]+:$ ]]; then
            # Flush any pending entry from previous section
            if $in_section && [ -n "$name" ] && [ -n "$check" ] && [ -n "$install" ]; then
                printf '%s\t%s\t%s\n' "$name" "$check" "$install"
            fi

            # Check if this is our target section
            local section_name="${line#"${line%%[! ]*}"}"  # strip leading spaces
            section_name="${section_name%:}"                # strip trailing colon
            if [ "$section_name" = "$target_os" ]; then
                in_section=true
            else
                # If we were in the target section and hit a new one, we're done
                if $in_section; then
                    name="" ; check="" ; install=""
                    break
                fi
                in_section=false
            fi
            name="" ; check="" ; install=""
            continue
        fi

        # Only parse lines if we're in the target section
        $in_section || continue

        # New entry: "    - name: <value>"
        if [[ "$line" =~ ^[[:space:]]+\-[[:space:]]+name:[[:space:]]+(.*) ]]; then
            # Flush previous entry if complete
            if [ -n "$name" ] && [ -n "$check" ] && [ -n "$install" ]; then
                printf '%s\t%s\t%s\n' "$name" "$check" "$install"
            fi
            name="${BASH_REMATCH[1]}"
            check="" ; install=""
            # Strip surrounding quotes
            name="${name#\"}" ; name="${name%\"}"
            name="${name#\'}" ; name="${name%\'}"
            continue
        fi

        # Field: "      check: <value>"
        if [[ "$line" =~ ^[[:space:]]+check:[[:space:]]+(.*) ]]; then
            check="${BASH_REMATCH[1]}"
            check="${check#\"}" ; check="${check%\"}"
            check="${check#\'}" ; check="${check%\'}"
            continue
        fi

        # Field: "      install: <value>"
        if [[ "$line" =~ ^[[:space:]]+install:[[:space:]]+(.*) ]]; then
            install="${BASH_REMATCH[1]}"
            install="${install#\"}" ; install="${install%\"}"
            install="${install#\'}" ; install="${install%\'}"
            continue
        fi
    done < "$yaml_path"

    # Flush last entry
    if $in_section && [ -n "$name" ] && [ -n "$check" ] && [ -n "$install" ]; then
        printf '%s\t%s\t%s\n' "$name" "$check" "$install"
    fi
}

# --- Tool Checker ---

check_system_tools() {
    local yaml_path="$1"

    # Validate input
    if [ ! -f "$yaml_path" ]; then
        _emit_st_error "Manifest not found: $yaml_path"
        return 1
    fi

    # Detect OS
    local os_key
    os_key="$(detect_os)" || {
        _emit_st_error "Unable to detect operating system (OSTYPE=${OSTYPE:-unset}, uname=$(uname -s 2>/dev/null || echo unknown))"
        return 1
    }

    # Parse manifest for this OS
    local entries
    entries="$(parse_system_tools "$yaml_path" "$os_key")"

    if [ -z "$entries" ]; then
        _emit_st_error "No system tool entries found for OS '$os_key' in $yaml_path"
        return 1
    fi

    # Check each tool in order
    local checked_tools=()
    while IFS=$'\t' read -r name check install; do
        if ! command -v "$check" >/dev/null 2>&1; then
            _emit_st_failure "$name" "$os_key" "$install"
            return 1
        fi
        checked_tools+=("$name")
    done <<< "$entries"

    _emit_st_success "$os_key" "${checked_tools[@]}"
    return 0
}

# --- Main ---
# When run directly (not sourced), execute check_system_tools with $1

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ $# -lt 1 ]; then
        _emit_st_error "Usage: check-system-tools.sh <path-to-system-tools.yaml>"
        exit 1
    fi
    check_system_tools "$1"
fi
