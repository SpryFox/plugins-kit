#!/usr/bin/env bash
# check-editor-build-fresh.sh -- PreToolUse hook for mcp__unreal-engine__*
#
# Detects when the running Unreal Editor was launched against a stale
# UnrealEditor-BuildSettings.dll (compiled with CURRENT_CHANGELIST=0, before
# the latest sync). In that state UPackage::SavePackage stamps
# Summary.SavedByEngineVersion with Changelist=0, which the cooker treats as
# "empty engine version" and rejects.
#
# Detection: BuildSettings.dll mtime vs Build.version mtime. If Build.version
# is newer than the DLL, the running editor doesn't reflect the latest sync.
#
# Defensive: silently exits if the project config, the engine_dir field, or
# the referenced files are missing. Only emits the advisory when all
# preconditions are met and staleness is detected. Non-blocking -- the tool
# call always proceeds.

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null) || exit 0
[[ "$TOOL_NAME" == mcp__unreal-engine__* ]] || exit 0

CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null) || exit 0
PROJECT_CFG="${CWD:-.}/.claude/unreal-kit.yaml"
[ -f "$PROJECT_CFG" ] || exit 0

ENGINE_DIR=$(grep -E '^engine_dir:' "$PROJECT_CFG" 2>/dev/null \
    | sed -E 's/^engine_dir:[[:space:]]*//; s/^"//; s/"$//' \
    | head -1)
[ -n "$ENGINE_DIR" ] || exit 0

if command -v cygpath >/dev/null 2>&1; then
    ENGINE_DIR=$(cygpath -u "$ENGINE_DIR" 2>/dev/null || echo "$ENGINE_DIR")
fi

DLL="$ENGINE_DIR/Binaries/Win64/UnrealEditor-BuildSettings.dll"
VERSION_FILE="$ENGINE_DIR/Build/Build.version"

[ -f "$DLL" ] && [ -f "$VERSION_FILE" ] || exit 0

DLL_MTIME=$(stat -c %Y "$DLL" 2>/dev/null || echo 0)
VER_MTIME=$(stat -c %Y "$VERSION_FILE" 2>/dev/null || echo 0)

if [ "$DLL_MTIME" -lt "$VER_MTIME" ]; then
    REASON="Editor requires rebuild before assets can be safely saved. UnrealEditor-BuildSettings.dll mtime is older than Engine/Build/Build.version, which means the running editor was launched without rebuilding after the latest sync. Asset saves through MCP will stamp Summary.SavedByEngineVersion with Changelist=0 and be rejected by the cooker as 'empty engine version'. Run a build before any save tool call."
    cat <<HOOKEOF
{"systemMessage":"Unreal editor build is stale -- rebuild before saving assets","hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"$REASON"}}
HOOKEOF
fi

exit 0
