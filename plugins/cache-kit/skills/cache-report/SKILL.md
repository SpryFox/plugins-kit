---
name: cache-report
author: christina
skill-type: technique-skill
description: Use when the user asks about cache hit rate, token usage, or prompt-caching stats. Do NOT use for runtime cache configuration.
disable-model-invocation: true
---

# Cache Report

Display the prompt-cache hit-rate and token-usage report for the current
or a specified session. The slash-command body is the technique; the
contract data below routes user phrasing to it.

```yaml
technique_skill:
  _schema_version: "1"
  trigger_model: user-only
  identity: Display the prompt-cache hit-rate report for the current or a specified session.
  scope:
    covers:
      - cache hit rate questions
      - token usage questions
      - prompt-caching stats requests
      - per-request cost breakdown requests
    excludes:
      - runtime cache configuration changes
      - cache invalidation policy decisions
  techniques:
    - id: show_cache_report
      name: Show cache report
      keywords: [cache hit rate, cache report, token usage, prompt caching stats, session cache, cache breakdown, cache costs, /cache-report]
      goal: Render the cache_report.py output verbatim, in the user's chat.
      arguments:
        - name: SESSION_ID
          required: false
          description: Specific session to report on; omit for current.
        - name: "--all"
          required: false
          description: Report across all sessions.
        - name: "--detailed"
          required: false
          description: Include per-request breakdown.
      steps:
        - n: 1
          action: Resolve the cache_report.py path from installed_plugins.json under the plugins-kit:cache-kit entry, then invoke it with $ARGUMENTS.
          tool: python3
          expected: stdout containing the cache hit-rate, token usage, and (if --detailed) per-request breakdown.
          on_failure: If installed_plugins.json is missing or the plugin id is not present, surface the error to the user verbatim. Do not improvise the script path.
        - n: 2
          action: Display the script's stdout verbatim in the user's chat. Do not summarize, paraphrase, or omit any lines.
      output_template: |
        Display the script's stdout verbatim. Do not summarize, paraphrase, or omit any lines.
      gotchas:
        - The slash command resolves the script path via installed_plugins.json. If installed_plugins.json is missing or the plugin id changes, the invocation fails -- surface the error to the user, do not improvise the path.
```

## Instructions

Display the report output below verbatim. Do not summarize, paraphrase, or omit any lines. Show the complete report exactly as produced by the script.

## Cache Usage Report

!`python3 $(python3 -c "import json;from pathlib import Path;d=json.loads((Path.home()/'.claude/plugins/installed_plugins.json').read_text());print(str(Path(d['plugins']['plugins-kit:cache-kit'][0]['installPath'])/'scripts/cache_report.py'))") $ARGUMENTS`

---

To see all sessions: run `python3 <install-path>/scripts/cache_report.py --all`

To see a specific session: run `python3 <install-path>/scripts/cache_report.py SESSION_ID`

To include per-request breakdown: run `python3 <install-path>/scripts/cache_report.py --detailed`
