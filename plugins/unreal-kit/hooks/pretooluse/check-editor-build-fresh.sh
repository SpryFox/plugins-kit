#!/usr/bin/env bash
# check-editor-build-fresh.sh -- PreToolUse hook for mcp__unreal-engine__*
#
# Two-stage architecture for low foreground latency:
#   - Foreground: substring check on tool_name, file-existence check on a
#     marker, emit warning if marker is present, spawn detector in
#     background, exit. Target: <30ms.
#   - Background: detect-editor-stale.py compares
#     UnrealEditor-BuildSettings.dll mtime vs Engine/Build/Build.version
#     mtime and writes/removes the marker. Latency does not matter -- the
#     foreground exits before the detector finishes.
#
# Marker semantics: file exists -> stale -> emit warning. The first MCP call
# after install runs against an absent marker (no warning emitted) but kicks
# off detection; subsequent calls reflect the latest detection. Self-corrects
# in one call after rebuild.

set -uo pipefail

INPUT=$(< /dev/stdin)

# Cheap regex check on the raw JSON -- no jq subprocess. Tolerates both
# compact ("tool_name":"...") and pretty-printed ("tool_name": "...").
[[ "$INPUT" =~ \"tool_name\"[[:space:]]*:[[:space:]]*\"mcp__unreal-engine__ ]] || exit 0

MARKER="${HOME}/.claude/plugins/data/plugins-kit/unreal-kit/editor-stale.flag"

if [[ -f "$MARKER" ]]; then
    cat <<'HOOKEOF'
{"systemMessage":"Unreal editor build is stale -- rebuild before saving assets","hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"Editor requires rebuild before assets can be safely saved. UnrealEditor-BuildSettings.dll mtime is older than Engine/Build/Build.version, which means the running editor was launched without rebuilding after the latest sync. Asset saves through MCP will stamp Summary.SavedByEngineVersion with Changelist=0 and be rejected by the cooker as 'empty engine version'. Run a build before any save tool call."}}
HOOKEOF
fi

# Spawn the detector fully detached so the foreground returns immediately.
# The subshell-and-background trick orphans the child to init/system.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DETECTOR="$SCRIPT_DIR/detect-editor-stale.py"

if [[ -f "$DETECTOR" ]]; then
    (
        printf '%s' "$INPUT" \
        | uv run --no-project python "$DETECTOR" "$MARKER" \
            >/dev/null 2>&1 &
    ) &
fi

exit 0
