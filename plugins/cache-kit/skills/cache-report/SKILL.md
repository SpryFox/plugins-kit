---
name: cache-report
description: Show cache hit rate and token usage for the current or a specified session. Use when the user asks about cache usage, cache hit rate, token costs, or prompt caching stats.
---

## Instructions

Display the report output below verbatim. Do not summarize, paraphrase, or omit any lines. Show the complete report exactly as produced by the script.

## Cache Usage Report

!`python3 $(python3 -c "import json;from pathlib import Path;d=json.loads((Path.home()/'.claude/plugins/installed_plugins.json').read_text());print(str(Path(d['plugins']['cache-kit@plugins-kit'][0]['installPath'])/'scripts/cache-report.py'))") $ARGUMENTS`

---

To see all sessions: run `python3 <install-path>/scripts/cache-report.py --all`

To see a specific session: run `python3 <install-path>/scripts/cache-report.py SESSION_ID`

To include per-request breakdown: run `python3 <install-path>/scripts/cache-report.py --detailed`
