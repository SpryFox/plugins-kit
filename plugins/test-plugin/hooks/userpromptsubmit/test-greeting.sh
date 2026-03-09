#!/usr/bin/env bash
# test-greeting.sh — Stop hook that demonstrates both user and Claude messaging.
#
# Displays "Stop - User" to the user via systemMessage
# and "Stop - Claude" to Claude via decision/reason.

cat <<'EOF'
{
  "continue": true,
  "suppressOutput": false,
  "systemMessage": "Stop - User"
}
EOF
