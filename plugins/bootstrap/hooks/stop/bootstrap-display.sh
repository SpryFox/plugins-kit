#!/usr/bin/env bash
# bootstrap-display.sh — Stop hook that surfaces bootstrap results once.
#
# The SessionStart hook fires the engine in the background. The engine writes
# its display JSON to bootstrap_display.json when done. This hook checks for
# that file on every turn (~0ms when idle) and emits it once, then removes it.

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MARKETPLACE_NAME="$(basename "$(cd "$PLUGIN_ROOT/../.." && pwd)")"
DISPLAY_FILE="${HOME}/.claude/plugins/data/${MARKETPLACE_NAME}/bootstrap/bootstrap_display.json"

[ -f "$DISPLAY_FILE" ] || exit 0
cat "$DISPLAY_FILE"
rm -f "$DISPLAY_FILE"
