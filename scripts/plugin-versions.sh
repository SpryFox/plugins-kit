#!/usr/bin/env bash
# plugin-versions.sh — Dump version info for plugins-kit marketplace and all plugins
# Compares: local repo, marketplace clone, installed_plugins.json, and cache

set -euo pipefail

CLAUDE_DIR="$HOME/.claude/plugins"
MARKETPLACE_NAME="plugins-kit"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

MARKETPLACE_CLONE="$CLAUDE_DIR/marketplaces/$MARKETPLACE_NAME"
INSTALLED_JSON="$CLAUDE_DIR/installed_plugins.json"
KNOWN_JSON="$CLAUDE_DIR/known_marketplaces.json"
CACHE_DIR="$CLAUDE_DIR/cache/$MARKETPLACE_NAME"

# All plugin dirs in the local repo
PLUGIN_DIRS=("$REPO_ROOT"/plugins/*/.)

sep() { echo "────────────────────────────────────────────────────"; }

json_field() {
    # Simple JSON string field extractor (no jq dependency)
    # Uses uv run python to avoid Windows Store python stub issue
    uv run python -c "
import json, sys
data = json.load(open(sys.argv[1]))
keys = sys.argv[2].split('.')
for k in keys:
    if isinstance(data, dict):
        data = data.get(k)
    else:
        data = None
        break
print(data if data is not None else '')
" "$1" "$2" 2>/dev/null || echo ""
}

installed_field() {
    # Extract field from installed_plugins.json for a given plugin key
    local plugin_key="$1" field="$2"
    uv run python -c "
import json, sys
data = json.load(open(sys.argv[1]))
plugins = data.get('plugins', data) if isinstance(data, dict) else {}
entries = plugins.get(sys.argv[2], [])
if entries:
    print(entries[0].get(sys.argv[3], ''))
else:
    print('')
" "$INSTALLED_JSON" "$plugin_key" "$field" 2>/dev/null || echo ""
}

marketplace_plugin_version() {
    # Extract version for a named plugin from marketplace.json
    local manifest="$1" plugin_name="$2"
    uv run python -c "
import json, sys
data = json.load(open(sys.argv[1]))
for p in data.get('plugins', []):
    if p.get('name') == sys.argv[2]:
        print(p.get('version', ''))
        sys.exit(0)
print('')
" "$manifest" "$plugin_name" 2>/dev/null || echo ""
}

# ── Header ──
echo ""
echo "PLUGINS-KIT VERSION REPORT"
echo "Generated: $(date '+%Y-%m-%d %H:%M:%S')"
sep

# ── Marketplace-level info ──
echo ""
echo "MARKETPLACE: $MARKETPLACE_NAME"
sep

# Local repo
local_sha=$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo "")
local_sha_short=$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo "")
if [[ -n "$local_sha" ]]; then
    echo "  Local repo:        $REPO_ROOT"
    echo "    commit:          $local_sha_short ($local_sha)"
else
    echo "  Local repo:        NOT A GIT REPO"
fi

# Marketplace clone
if [[ -d "$MARKETPLACE_CLONE" ]]; then
    clone_sha=$(git -C "$MARKETPLACE_CLONE" rev-parse HEAD 2>/dev/null || echo "")
    clone_sha_short=$(git -C "$MARKETPLACE_CLONE" rev-parse --short HEAD 2>/dev/null || echo "")
    clone_updated=$(json_field "$KNOWN_JSON" "$MARKETPLACE_NAME.lastUpdated")
    clone_auto=$(json_field "$KNOWN_JSON" "$MARKETPLACE_NAME.autoUpdate")
    echo "  Marketplace clone: $MARKETPLACE_CLONE"
    echo "    commit:          $clone_sha_short ($clone_sha)"
    echo "    lastUpdated:     ${clone_updated:-unknown}"
    echo "    autoUpdate:      ${clone_auto:-unknown}"
    if [[ "$local_sha" == "$clone_sha" ]]; then
        echo "    sync status:     IN SYNC with local"
    else
        echo "    sync status:     OUT OF SYNC with local"
    fi
else
    echo "  Marketplace clone: NOT INSTALLED"
fi

echo ""

# ── Per-plugin info ──
echo "PLUGINS"
sep

for plugin_dir in "${PLUGIN_DIRS[@]}"; do
    plugin_dir="${plugin_dir%/.}"
    plugin_name=$(basename "$plugin_dir")
    plugin_json="$plugin_dir/.claude-plugin/plugin.json"

    echo ""
    echo "  $plugin_name"
    echo "  $(printf '%.0s─' {1..40})"

    # Local plugin.json version
    if [[ -f "$plugin_json" ]]; then
        local_ver=$(json_field "$plugin_json" "version")
        echo "    local plugin.json:     v${local_ver:-?}"
    else
        echo "    local plugin.json:     NOT FOUND"
    fi

    # Marketplace manifest version (from local repo marketplace.json)
    local_manifest="$REPO_ROOT/.claude-plugin/marketplace.json"
    if [[ -f "$local_manifest" ]]; then
        mkt_ver=$(marketplace_plugin_version "$local_manifest" "$plugin_name")
        if [[ -n "$mkt_ver" ]]; then
            echo "    marketplace.json:      v${mkt_ver}"
            # Check version match
            if [[ -n "${local_ver:-}" && "$local_ver" != "$mkt_ver" ]]; then
                echo "      ** MISMATCH: plugin.json=$local_ver vs marketplace.json=$mkt_ver"
            fi
        else
            echo "    marketplace.json:      NOT LISTED"
        fi
    fi

    # Installed plugins registry
    plugin_key="${plugin_name}@${MARKETPLACE_NAME}"
    if [[ -f "$INSTALLED_JSON" ]]; then
        inst_ver=$(installed_field "$plugin_key" "version")
        inst_sha=$(installed_field "$plugin_key" "gitCommitSha")
        inst_sha_short="${inst_sha:0:7}"
        inst_path=$(installed_field "$plugin_key" "installPath")
        inst_updated=$(installed_field "$plugin_key" "lastUpdated")

        if [[ -n "$inst_ver" ]]; then
            echo "    installed_plugins:     v${inst_ver} @ ${inst_sha_short:-?} (${inst_updated:-?})"
            echo "      installPath:         ${inst_path:-?}"
            # Check if installed version matches local
            if [[ -n "${local_ver:-}" && "$local_ver" != "$inst_ver" ]]; then
                echo "      ** VERSION DRIFT: local=$local_ver vs installed=$inst_ver"
            fi
            if [[ -n "$inst_sha" && -n "$local_sha" && "$inst_sha" != "$local_sha" ]]; then
                echo "      ** COMMIT DRIFT: local=$local_sha_short vs installed=$inst_sha_short"
            fi
        else
            echo "    installed_plugins:     NOT INSTALLED"
        fi
    else
        echo "    installed_plugins:     $INSTALLED_JSON NOT FOUND"
    fi

    # Cache
    cache_plugin_dir="$CACHE_DIR/$plugin_name"
    if [[ -d "$cache_plugin_dir" ]]; then
        cached_versions=$(ls "$cache_plugin_dir" 2>/dev/null | tr '\n' ', ' | sed 's/,$//')
        echo "    cache:                 ${cached_versions:-empty}"
        # Check cached plugin.json version
        for cv in "$cache_plugin_dir"/*/; do
            cv_name=$(basename "$cv")
            cv_json="$cv/.claude-plugin/plugin.json"
            if [[ -f "$cv_json" ]]; then
                cv_ver=$(json_field "$cv_json" "version")
                echo "      $cv_name/plugin.json: v${cv_ver:-?}"
            fi
        done
    else
        echo "    cache:                 NOT CACHED"
    fi
done

echo ""
sep
echo "Done."
