#!/usr/bin/env bash
# test-delay.sh — Test hook to find SessionStart output suppression threshold.
#
# Set BOOTSTRAP_TEST_DELAY env var to control delay (default: 0).
# Output will show as "SessionStart:startup says: ..." if not suppressed.
#
# Usage:
#   BOOTSTRAP_TEST_DELAY=3 claude    # test with 3s delay
#
# Remove this hook after testing by deleting the SessionStart entry
# from settings that references this script.

set -euo pipefail

# Consume stdin (required — hook hangs if stdin isn't read)
cat > /dev/null

DELAY="${BOOTSTRAP_TEST_DELAY:-0}"

if [ "$DELAY" -gt 0 ] 2>/dev/null; then
    sleep "$DELAY"
fi

cat <<EOF
{"continue": true, "suppressOutput": false, "systemMessage": "delay-test: slept ${DELAY}s", "hookSpecificOutput": {"hookEventName": "SessionStart"}}
EOF
