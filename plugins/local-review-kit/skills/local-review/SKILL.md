---
_schema_version: 1
name: local-review
description: Run AI code reviews of Perforce changelists in conversation — list CLs, pick agent, review, display results
---

# Local Review

## Purpose

Run an AI code review of a Perforce changelist directly in conversation. Results are displayed inline — no persistence to disk.

## Prerequisites

Check config is complete before proceeding:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/setup.py --check --data-dir ~/.claude/plugins/data/local-review-kit
```

If exit code is non-zero, suggest invoking the **local-review-setup** skill first.

## Review Flow

### 1. List pending changelists

Show the user's pending CLs so they can pick one:

```bash
p4 -ztag changes -s pending -u <P4USER> -m 20
```

Read `P4USER` from `~/.claude/plugins/data/local-review-kit/config.yaml`.

### 2. Pick CL and agent

Ask the user which CL to review and which agent to use. List available agents:

```bash
ls ~/.claude/plugins/data/local-review-kit/github/code-review-research/agents/*.yaml | grep -v _base | grep -v agents.yaml | sed 's/.*\///' | sed 's/\.yaml$//'
```

Or read `DEFAULT_AGENT` from config as the default choice.

### 3. Run the review

Invoke the review script using the plugin venv Python:

```bash
~/.claude/plugins/data/local-review-kit/.venv/bin/python ${CLAUDE_PLUGIN_ROOT}/scripts/run-review.py <CL> --agent <AGENT> --json
```

Options:
- `--diff-file <path>` — use a local diff file instead of `p4 describe` (useful for testing)
- `--dry-run` — print assembled prompts without calling the LLM (no cost)
- `--json` — output as JSON (default is YAML)

### 4. Format output for conversation

Parse the JSON/YAML stdout and present as markdown:

**Summary section:**
- Agent name and model
- CL number and description
- Overall verdict / severity summary
- Token usage and estimated cost

**Findings grouped by file:**
For each finding, show:
- File path and line number
- Severity badge: `[critical]` `[major]` `[minor]` `[suggestion]`
- The finding text
- Code snippet if available

Example format:

```
## Review: CL 131250 — claude-haiku

**Verdict**: Needs revision (2 major, 1 minor)
**Cost**: ~$0.003 (1.2k input / 0.4k output tokens)

### src/inventory/overflow.cpp

**[major]** Line 42: Buffer overflow risk — `items` array accessed without bounds check.

**[minor]** Line 78: Unused variable `temp_count`.

### src/inventory/quest_items.h

**[suggestion]** Line 15: Consider using `constexpr` for `MAX_QUEST_ITEMS`.
```

## Dry Run

To preview what the LLM will receive without spending tokens:

```bash
~/.claude/plugins/data/local-review-kit/.venv/bin/python ${CLAUDE_PLUGIN_ROOT}/scripts/run-review.py <CL> --agent <AGENT> --dry-run
```

Prompts are printed to stderr. Useful for verifying agent config and diff parsing.

## Testing with a diff file

To review without a live Perforce connection:

```bash
~/.claude/plugins/data/local-review-kit/.venv/bin/python ${CLAUDE_PLUGIN_ROOT}/scripts/run-review.py 99999 --agent claude-haiku --diff-file /path/to/test.diff --json
```
