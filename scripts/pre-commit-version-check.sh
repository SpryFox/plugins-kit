#!/usr/bin/env bash
# pre-commit-version-check.sh — Block commits when marketplace.json versions
# don't match plugin.json versions.
#
# Install: ln -sf ../../scripts/pre-commit-version-check.sh .git/hooks/pre-commit

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MARKETPLACE_JSON="$REPO_ROOT/.claude-plugin/marketplace.json"

if [ ! -f "$MARKETPLACE_JSON" ]; then
    exit 0
fi

MISMATCHES=()

while IFS=$'\t' read -r name mkt_version source; do
    # Resolve plugin.json path from marketplace source
    plugin_json="$REPO_ROOT/${source#./}/.claude-plugin/plugin.json"
    if [ ! -f "$plugin_json" ]; then
        continue
    fi

    plugin_version=$(python3 -c "
import json, sys
data = json.load(open(sys.argv[1]))
print(data.get('version', ''))
" "$plugin_json" 2>/dev/null || echo "")

    if [ -n "$plugin_version" ] && [ "$mkt_version" != "$plugin_version" ]; then
        MISMATCHES+=("  $name: marketplace.json=$mkt_version  plugin.json=$plugin_version")
    fi
done < <(python3 -c "
import json, sys
data = json.load(open(sys.argv[1]))
for p in data.get('plugins', []):
    name = p.get('name', '')
    version = p.get('version', '')
    source = p.get('source', '')
    print(f'{name}\t{version}\t{source}')
" "$MARKETPLACE_JSON" 2>/dev/null)

if [ ${#MISMATCHES[@]} -gt 0 ]; then
    echo "VERSION MISMATCH — marketplace.json out of sync with plugin.json:"
    echo ""
    for m in "${MISMATCHES[@]}"; do
        echo "$m"
    done
    echo ""
    echo "Update .claude-plugin/marketplace.json to match, then re-commit."
    exit 1
fi
