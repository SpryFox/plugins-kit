---
name: cache-report
skill-type: technique-skill
description: Use when the user asks about cache hit rate, token usage, or prompt-caching stats. Do NOT use for runtime cache configuration.
disable-model-invocation: true
---

## Instructions

Display the report output below verbatim. Do not summarize, paraphrase, or omit any lines. Show the complete report exactly as produced by the script.

## Cache Usage Report

!`python3 $(python3 -c "import json;from pathlib import Path;d=json.loads((Path.home()/'.claude/plugins/installed_plugins.json').read_text());print(str(Path(d['plugins']['plugins-kit:cache-kit'][0]['installPath'])/'scripts/cache_report.py'))") $ARGUMENTS`

---

To see all sessions: run `python3 <install-path>/scripts/cache_report.py --all`

To see a specific session: run `python3 <install-path>/scripts/cache_report.py SESSION_ID`

To include per-request breakdown: run `python3 <install-path>/scripts/cache_report.py --detailed`
