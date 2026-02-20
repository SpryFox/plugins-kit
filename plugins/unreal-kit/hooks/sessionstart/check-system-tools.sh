#!/usr/bin/env bash
set -euo pipefail

# check-system-tools.sh — Step 1 of session bootstrap
#
# Reads system-tools.yaml for the detected OS, checks each entry via
# command -v (default) or persistent PATH verification (check_type: persistent_path),
# and collects all independent failures. Consequential failures (e.g., a command
# that lives in a failed persistent_path directory) are skipped since the PATH
# fix will resolve them.
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

# --- Persistent PATH Checkers ---

_check_win_user_path() {
    local target_path="$1"

    # Get Windows user-level PATH via PowerShell
    local user_path
    user_path="$(powershell.exe -NoProfile -Command \
        '[Environment]::GetEnvironmentVariable("Path", "User")' 2>/dev/null)" || return 1

    # Resolve target path: expand $HOME, then convert to Windows path
    local resolved="${target_path/\$HOME/$HOME}"
    resolved="${resolved/#\~/$HOME}"
    # Convert to Windows-style path for comparison
    local win_resolved
    win_resolved="$(cygpath -w "$resolved" 2>/dev/null || echo "$resolved")"
    win_resolved="${win_resolved%\\}"
    win_resolved="${win_resolved%/}"

    # Compare case-insensitively against each PATH entry
    local IFS=';'
    local entry
    for entry in $user_path; do
        entry="${entry%\\}"
        entry="${entry%/}"
        # Remove trailing \r from PowerShell output
        entry="${entry%$'\r'}"
        if [[ "${entry,,}" == "${win_resolved,,}" ]]; then
            return 0
        fi
    done
    return 1
}

_check_shell_rc_path() {
    local target_path="$1"
    local rc_file="$2"

    [ -f "$rc_file" ] || return 1

    # Extract directory suffix (e.g., ".local/bin") by stripping $HOME/~ prefix
    local dir_suffix="$target_path"
    dir_suffix="${dir_suffix/\$HOME/}"
    dir_suffix="${dir_suffix/#\~/}"
    dir_suffix="${dir_suffix#/}"

    # Grep for the directory suffix in the rc file
    grep -q "$dir_suffix" "$rc_file" 2>/dev/null
}

check_persistent_path() {
    local target_path="$1"
    local os_key="$2"

    case "$os_key" in
        windows)
            _check_win_user_path "$target_path"
            ;;
        macos)
            _check_shell_rc_path "$target_path" "$HOME/.zshrc" ||
            _check_shell_rc_path "$target_path" "$HOME/.zprofile"
            ;;
        ubuntu)
            _check_shell_rc_path "$target_path" "$HOME/.bashrc" ||
            _check_shell_rc_path "$target_path" "$HOME/.profile"
            ;;
        *)
            return 1
            ;;
    esac
}

_ensure_session_path() {
    local target_path="$1"
    local os_key="$2"
    local resolved

    # Resolve the path to an absolute directory
    case "$os_key" in
        windows)
            resolved="${target_path/\$HOME/$HOME}"
            resolved="${resolved/#\~/$HOME}"
            # Convert to Unix-style path for Git Bash PATH
            resolved="$(cygpath -u "$(cygpath -w "$resolved")" 2>/dev/null || echo "$resolved")"
            ;;
        *)
            resolved="${target_path/\$HOME/$HOME}"
            resolved="${resolved/#\~/$HOME}"
            ;;
    esac

    # Add to PATH if not already present
    case ":$PATH:" in
        *":$resolved:"*) ;;
        *) export PATH="$resolved:$PATH" ;;
    esac
}

# --- YAML Parser ---
# Extracts entries for a given OS section from system-tools.yaml.
# Output: newline-delimited records, one per tool, as "name\tcheck\tinstall\tcheck_type\tenabled" (tab-delimited)
#
# Parsing approach: line-by-line scan. Detect OS section headers by matching
# "  <key>:" at 2-space indent. Within the target section, accumulate fields
# from "- name:", "check:", "check_type:", "install:" entries. Stop on next section or EOF.

parse_system_tools() {
    local yaml_path="$1"
    local target_os="$2"
    local in_section=false
    local name="" check="" install="" check_type="" enabled=""
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
                printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$check" "$install" "${check_type:-command}" "${enabled:-true}"
            fi

            # Check if this is our target section
            local section_name="${line#"${line%%[! ]*}"}"  # strip leading spaces
            section_name="${section_name%:}"                # strip trailing colon
            if [ "$section_name" = "$target_os" ]; then
                in_section=true
            else
                # If we were in the target section and hit a new one, we're done
                if $in_section; then
                    name="" ; check="" ; install="" ; check_type="" ; enabled=""
                    break
                fi
                in_section=false
            fi
            name="" ; check="" ; install="" ; check_type="" ; enabled=""
            continue
        fi

        # Only parse lines if we're in the target section
        $in_section || continue

        # New entry: "    - name: <value>"
        if [[ "$line" =~ ^[[:space:]]+\-[[:space:]]+name:[[:space:]]+(.*) ]]; then
            # Flush previous entry if complete
            if [ -n "$name" ] && [ -n "$check" ] && [ -n "$install" ]; then
                printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$check" "$install" "${check_type:-command}" "${enabled:-true}"
            fi
            name="${BASH_REMATCH[1]}"
            check="" ; install="" ; check_type="" ; enabled=""
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

        # Field: "      enabled: <value>"
        if [[ "$line" =~ ^[[:space:]]+enabled:[[:space:]]+(.*) ]]; then
            enabled="${BASH_REMATCH[1]}"
            enabled="${enabled#\"}" ; enabled="${enabled%\"}"
            enabled="${enabled#\'}" ; enabled="${enabled%\'}"
            continue
        fi

        # Field: "      check_type: <value>"
        if [[ "$line" =~ ^[[:space:]]+check_type:[[:space:]]+(.*) ]]; then
            check_type="${BASH_REMATCH[1]}"
            check_type="${check_type#\"}" ; check_type="${check_type%\"}"
            check_type="${check_type#\'}" ; check_type="${check_type%\'}"
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
        printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$check" "$install" "${check_type:-command}" "${enabled:-true}"
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

    # Derive plugin root from manifest path for variable expansion
    local plugin_root
    plugin_root="$(cd "$(dirname "$yaml_path")" && pwd)"

    # Parse manifest for this OS
    local entries
    entries="$(parse_system_tools "$yaml_path" "$os_key")"

    if [ -z "$entries" ]; then
        _emit_st_error "No system tool entries found for OS '$os_key' in $yaml_path"
        return 1
    fi

    # Check each tool, collecting all independent failures
    local checked_tools=()
    local failed_paths=()
    local user_lines=()
    local context_lines=()
    local failure_count=0

    while IFS=$'\t' read -r name check install check_type enabled; do
        # Skip disabled entries
        [ "${enabled:-true}" = "false" ] && continue
        # Expand ${PLUGIN_ROOT} in install commands
        install="${install//\$\{PLUGIN_ROOT\}/$plugin_root}"
        local check_passed=false
        case "${check_type:-command}" in
            persistent_path)
                if check_persistent_path "$check" "$os_key"; then
                    _ensure_session_path "$check" "$os_key"
                    check_passed=true
                else
                    # Track the resolved path so we can skip dependent command checks
                    local resolved="${check/\$HOME/$HOME}"
                    resolved="${resolved/#\~/$HOME}"
                    failed_paths+=("$resolved")
                fi
                ;;
            command)
                if command -v "$check" >/dev/null 2>&1; then
                    check_passed=true
                elif [ ${#failed_paths[@]} -gt 0 ]; then
                    # If command not found, check if it exists in a failed path
                    # (consequence of PATH issue, not an independent failure)
                    for fp in "${failed_paths[@]}"; do
                        if [ -f "$fp/$check" ] || [ -f "$fp/$check.exe" ]; then
                            check_passed=true  # skip — will be resolved by PATH fix
                            break
                        fi
                    done
                fi
                ;;
            *)
                _emit_st_error "Unknown check_type '$check_type' for tool '$name'"
                return 1
                ;;
        esac
        if $check_passed; then
            checked_tools+=("$name")
        else
            failure_count=$((failure_count+1))
            # Build user-facing and context messages per failure
            case "${check_type:-command}" in
                persistent_path)
                    user_lines+=("- $check is not in PATH")
                    context_lines+=("$failure_count. Required path '$check' not found in persistent PATH configuration. Add with: $install (fix-$name)")
                    ;;
                *)
                    user_lines+=("- $name is not installed")
                    context_lines+=("$failure_count. Required tool '$name' not found. Install with: $install (fix-$name)")
                    ;;
            esac
        fi
    done <<< "$entries"

    if [ $failure_count -gt 0 ]; then
        # Join arrays with real newlines, then json_escape once for the JSON output
        local user_msg context_msg
        user_msg="$(printf '%s\n' "${user_lines[@]}")"
        user_msg+=$'\n'"Say 'fix-all' to fix all issues."
        context_msg="$(printf '%s\n' "${context_lines[@]}")"

        local escaped_user escaped_context
        escaped_user="$(json_escape "$user_msg")"
        escaped_context="$(json_escape "$context_msg")"
        cat <<EOF
{"status": "error", "step": "system_tools", "os": "$os_key", "user_message": "$escaped_user", "context_message": "$escaped_context"}
EOF
        return 1
    fi

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
