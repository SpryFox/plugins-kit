#!/usr/bin/env bash
set -euo pipefail

DATA=$(cat)

# Extract fields via single jq call
IFS=$'\t' read -r MODEL MODEL_ID DIR PCT SESS WEEK < <(
    echo "$DATA" | jq -r '[
        (.model.display_name // "Claude"),
        (try (.model.id // "unknown") catch "unknown"),
        (.cwd // "~" | split("/") | last),
        (try (
    if (.context_window.remaining_percentage // null) != null then
      100 - (.context_window.remaining_percentage | floor)
    elif (.context_window.context_window_size // 0) > 0 then
      (((.context_window.current_usage.input_tokens // 0) +
        (.context_window.current_usage.cache_creation_input_tokens // 0) +
        (.context_window.current_usage.cache_read_input_tokens // 0)) * 100 /
       .context_window.context_window_size) | floor
    else 0 end
  ) catch 0),
        (.rate_limits.five_hour.used_percentage // "" | tostring | split(".")[0]),
        (.rate_limits.seven_day.used_percentage // "" | tostring | split(".")[0])
    ] | @tsv'
)

# Threshold colors (256-color: 196 = red, 208 = orange, 250 = default gray)
# Override defaults via env vars in settings.json:
#   STATUSLINE_CTX_ORANGE_AT, STATUSLINE_CTX_RED_AT,
#   STATUSLINE_SESS_ORANGE_AT, STATUSLINE_SESS_RED_AT
CTX_ORANGE_AT="${STATUSLINE_CTX_ORANGE_AT:-30}"
CTX_RED_AT="${STATUSLINE_CTX_RED_AT:-70}"
SESS_ORANGE_AT="${STATUSLINE_SESS_ORANGE_AT:-70}"
SESS_RED_AT="${STATUSLINE_SESS_RED_AT:-90}"

if   [ "$PCT" -ge "$CTX_RED_AT" ];    then CTX_CLR="\033[38;5;196m"
elif [ "$PCT" -ge "$CTX_ORANGE_AT" ]; then CTX_CLR="\033[38;5;208m"
else                                       CTX_CLR="\033[38;5;250m"
fi

SESS_CLR="\033[38;5;250m"
if [ -n "$SESS" ] && [ "$SESS" -eq "$SESS" ] 2>/dev/null; then
    if   [ "$SESS" -ge "$SESS_RED_AT" ];    then SESS_CLR="\033[38;5;196m"
    elif [ "$SESS" -ge "$SESS_ORANGE_AT" ]; then SESS_CLR="\033[38;5;208m"
    fi
fi

OUT="\033[38;5;250m📁 $DIR\033[0m\033[2m\033[38;5;238m │ \033[0m${CTX_CLR}🧠 $PCT%\033[0m"
if [ -n "$SESS" ]; then
    OUT="$OUT\033[2m\033[38;5;238m │ \033[0m${SESS_CLR}⏳ $SESS%\033[0m"
fi
if [ -n "$WEEK" ]; then
    OUT="$OUT\033[2m\033[38;5;238m │ \033[0m\033[38;5;250m📅 $WEEK%\033[0m"
fi
echo -e "$OUT"
