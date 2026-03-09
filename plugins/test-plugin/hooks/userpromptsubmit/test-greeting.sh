#!/usr/bin/env bash
# test-greeting.sh — UserPromptSubmit hook that demonstrates both user and Claude messaging.
#
# Displays "UserPromptSubmit - User" to the user via systemMessage
# and "UserPromptSubmit - Claude" to Claude via additionalContext.

cat <<'EOF'
{
  "continue": true,
  "suppressOutput": false,
  "systemMessage": "UserPromptSubmit - User",
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "UserPromptSubmit - Claude"
  }
}
EOF
