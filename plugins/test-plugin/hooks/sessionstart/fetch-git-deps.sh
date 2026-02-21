#!/usr/bin/env bash
set -euo pipefail

# fetch-git-deps.sh — Step 3 of session bootstrap
#
# Reads git-dependencies.yaml and clones/pulls each declared repository
# into a persistent data directory (outside the plugin cache).
#
# Usage:
#   bash fetch-git-deps.sh <path-to-git-dependencies.yaml> <plugin-data-dir>
#
# Output: JSON to stdout (for additionalContext integration)
# Exit:   0 = all deps fetched (or none declared), 1 = error

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

_emit_gd_success() {
    local count="$1"
    shift
    local repos_json=""
    for repo in "$@"; do
        [ -n "$repos_json" ] && repos_json="$repos_json, "
        repos_json="$repos_json\"$(json_escape "$repo")\""
    done
    cat <<EOF
{"status": "ok", "step": "git_deps", "repos_processed": $count, "repos": [$repos_json]}
EOF
}

_emit_gd_error() {
    local message="$1"
    local remediation="${2:-}"
    local rem_field=""
    if [ -n "$remediation" ]; then
        rem_field=", \"remediation\": \"$(json_escape "$remediation")\""
    fi
    cat <<EOF
{"status": "error", "step": "git_deps", "message": "$(json_escape "$message")"$rem_field}
EOF
}

# --- YAML Parser ---
# Extracts entries from git-dependencies.yaml.
# Output: newline-delimited records, one per entry, as "url\tbranch\tsparse_paths" (tab-delimited)
# sparse_paths is pipe-delimited (e.g., "agents/|docs/") or empty when not specified.

parse_git_deps() {
    local yaml_path="$1"
    local in_list=false
    local url="" branch="" sparse_paths=""
    local in_sparse=false
    local line

    while IFS= read -r line || [ -n "$line" ]; do
        # Skip blank lines and comments
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

        # Top-level key
        if [[ "$line" =~ ^git_dependencies: ]]; then
            in_list=true
            continue
        fi

        $in_list || continue

        # New entry: "  - url: <value>"
        if [[ "$line" =~ ^[[:space:]]+\-[[:space:]]+url:[[:space:]]+(.*) ]]; then
            # Flush previous entry if complete
            if [ -n "$url" ] && [ -n "$branch" ]; then
                printf '%s\t%s\t%s\n' "$url" "$branch" "$sparse_paths"
            fi
            url="${BASH_REMATCH[1]}"
            branch=""
            sparse_paths=""
            in_sparse=false
            # Strip surrounding quotes
            url="${url#\"}" ; url="${url%\"}"
            url="${url#\'}" ; url="${url%\'}"
            continue
        fi

        # Field: "    sparse_paths:" (starts sub-list)
        if [[ "$line" =~ ^[[:space:]]+sparse_paths:[[:space:]]*$ ]]; then
            in_sparse=true
            continue
        fi

        # Sub-list item under sparse_paths: "      - value"
        if $in_sparse && [[ "$line" =~ ^[[:space:]]+-[[:space:]]+(.*) ]]; then
            local path="${BASH_REMATCH[1]}"
            path="${path#\"}" ; path="${path%\"}"
            path="${path#\'}" ; path="${path%\'}"
            if [ -n "$sparse_paths" ]; then
                sparse_paths="${sparse_paths}|${path}"
            else
                sparse_paths="$path"
            fi
            continue
        fi

        # Any other field ends the sparse_paths sub-list
        in_sparse=false

        # Field: "    branch: <value>"
        if [[ "$line" =~ ^[[:space:]]+branch:[[:space:]]+(.*) ]]; then
            branch="${BASH_REMATCH[1]}"
            branch="${branch#\"}" ; branch="${branch%\"}"
            branch="${branch#\'}" ; branch="${branch%\'}"
            continue
        fi
    done < "$yaml_path"

    # Flush last entry
    if [ -n "$url" ] && [ -n "$branch" ]; then
        printf '%s\t%s\t%s\n' "$url" "$branch" "$sparse_paths"
    fi
}

# --- Git Dependency Fetcher ---

fetch_git_deps() {
    local yaml_path="$1"
    local plugin_data="$2"
    local github_dir="${plugin_data}/github"

    # Validate manifest exists
    if [ ! -f "$yaml_path" ]; then
        _emit_gd_error "Manifest not found: $yaml_path"
        return 1
    fi

    # Parse manifest
    local entries
    entries="$(parse_git_deps "$yaml_path")"

    # Handle empty list
    if [ -z "$entries" ]; then
        _emit_gd_success 0
        return 0
    fi

    mkdir -p "$github_dir"

    local processed_repos=()
    while IFS=$'\t' read -r url branch sparse_paths; do
        # Derive repo name from URL
        local repo_name="${url##*/}"
        repo_name="${repo_name%.git}"
        local target="${github_dir}/${repo_name}"

        # Split pipe-delimited sparse_paths into an array
        local sparse_arr=()
        if [ -n "$sparse_paths" ]; then
            IFS='|' read -ra sparse_arr <<< "$sparse_paths"
        fi

        if [ ! -d "${target}/.git" ]; then
            # Clone
            local git_output
            if [ ${#sparse_arr[@]} -gt 0 ]; then
                # Sparse clone: partial clone + sparse-checkout
                if ! git_output=$(git clone --branch "$branch" --no-checkout --filter=blob:none "$url" "$target" 2>&1); then
                    _emit_gd_error "git clone failed for ${repo_name}: ${git_output}" \
                        "Run manually: git clone --branch ${branch} --no-checkout --filter=blob:none ${url} ${target}"
                    return 1
                fi
                if ! git_output=$(git -C "$target" sparse-checkout set --no-cone "${sparse_arr[@]}" 2>&1); then
                    _emit_gd_error "sparse-checkout set failed for ${repo_name}: ${git_output}"
                    return 1
                fi
                if ! git_output=$(git -C "$target" checkout "$branch" 2>&1); then
                    _emit_gd_error "checkout failed for ${repo_name}: ${git_output}"
                    return 1
                fi
            else
                # Full clone
                if ! git_output=$(git clone --branch "$branch" "$url" "$target" 2>&1); then
                    _emit_gd_error "git clone failed for ${repo_name}: ${git_output}" \
                        "Run manually: git clone --branch ${branch} ${url} ${target}"
                    return 1
                fi
            fi
        else
            # Check branch
            local current_branch
            current_branch="$(git -C "$target" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"

            if [ "$current_branch" != "$branch" ]; then
                _emit_gd_error "Branch mismatch for ${repo_name}: expected '${branch}', found '${current_branch}'" \
                    "Manually switch branch: cd ${target} && git checkout ${branch}"
                return 1
            fi

            # Update sparse-checkout configuration
            local git_output
            if [ ${#sparse_arr[@]} -gt 0 ]; then
                # Ensure sparse-checkout is set (idempotent)
                if ! git_output=$(git -C "$target" sparse-checkout set --no-cone "${sparse_arr[@]}" 2>&1); then
                    _emit_gd_error "sparse-checkout set failed for ${repo_name}: ${git_output}"
                    return 1
                fi
            else
                # Disable sparse-checkout if it was previously active
                local sparse_active
                sparse_active="$(git -C "$target" config --get core.sparseCheckout 2>/dev/null || true)"
                if [ "$sparse_active" = "true" ]; then
                    if ! git_output=$(git -C "$target" sparse-checkout disable 2>&1); then
                        _emit_gd_error "sparse-checkout disable failed for ${repo_name}: ${git_output}"
                        return 1
                    fi
                fi
            fi

            # Pull
            if ! git_output=$(git -C "$target" pull 2>&1); then
                _emit_gd_error "git pull failed for ${repo_name}: ${git_output}" \
                    "Run manually: cd ${target} && git pull"
                return 1
            fi
        fi

        processed_repos+=("$repo_name")
    done <<< "$entries"

    _emit_gd_success "${#processed_repos[@]}" "${processed_repos[@]}"
    return 0
}

# --- Main ---
# When run directly (not sourced), execute fetch_git_deps with $1 and $2

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ $# -lt 2 ]; then
        _emit_gd_error "Usage: fetch-git-deps.sh <path-to-git-dependencies.yaml> <plugin-data-dir>"
        exit 1
    fi
    fetch_git_deps "$1" "$2"
fi
