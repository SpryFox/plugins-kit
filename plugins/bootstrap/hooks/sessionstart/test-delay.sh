#!/usr/bin/env bash
# test-delay.sh — Test hook to find SessionStart output suppression threshold.
#
# Set BOOTSTRAP_TEST_DELAY env var to control delay (default: 0).
# Output will show as "SessionStart:startup says: ..." if not suppressed.
#
# Usage:
#   BOOTSTRAP_TEST_DELAY=3 claude    # test with 3s delay
#
# As a plugin hook, this runs automatically when the bootstrap plugin is enabled.
# Set BOOTSTRAP_TEST_DELAY=0 (or unset) to skip the delay and still emit output.
# The hook always emits output — if you don't see it, suppression is the cause.

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
