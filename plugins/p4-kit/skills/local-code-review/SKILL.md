---
_schema_version: 1
name: local-code-review
skill-type: technique-skill
description: Use when the user requests a code review of a pending Perforce changelist. Do NOT use for git diffs or non-Perforce review workflows.
disable-model-invocation: true
---

# Local Code Review

Run a multi-agent code review of a Perforce changelist directly in conversation. Three Claude subagents review the diff in parallel; each flagged issue is then validated by an independent subagent to suppress false positives. Results are rendered as markdown — no persistence to disk.

## Agent assumptions (apply to all subagents you launch)

- All tools are functional. Do not test tools or make exploratory calls.
- Only call a tool if it is required to complete the task.

## Narration (user-facing) — REQUIRED, use the exact templates below

Reviews involve long silent stretches (batched file reads, parallel subagents that take 30s+). The user must be able to follow along. Post one short status line per step using these templates verbatim, filling in the bracketed counts. Do not paraphrase, omit, or add extras.

| When | Template |
|------|----------|
| Before step 1 (only if no CL arg was passed) | `Listing your pending changelists.` |
| Before step 2 | `Gathering context for CL <CL>: fetching diff and mapping CLAUDE.md scopes.` |
| After step 2, before step 3 (M ≥ 1) | `Got <N> changed file(s) and <M> unique CLAUDE.md scope(s). Reading them now.` |
| After step 2, before step 4 (M = 0) | `Got <N> changed file(s); no CLAUDE.md scopes apply. Skipping to reviewers.` |
| Before step 4 | `Launching 3 reviewers in parallel: sonnet CLAUDE.md compliance, opus diff-only bugs, opus introduced-code.` |
| After step 4, before step 5 (X ≥ 1) | `Reviewers returned <X> candidate issue(s) (<B> bug, <C> CLAUDE.md). Launching <X> validator(s) in parallel.` |
| After step 4 (X = 0) | `Reviewers found no issues. Skipping validation.` Then go straight to step 7. |
| After step 5, before step 7 | `Validators confirmed <Y> of <X>. Rendering review.` |

Variables:
- `<CL>` — the changelist number
- `<N>` — `len(bundle.changed_files)`
- `<M>` — `len(bundle.unique_claude_mds)`
- `<X>` — total candidate issues from all three reviewers combined
- `<B>` — count where `reason == "bug"`
- `<C>` — count where `reason == "claude_md"`
- `<Y>` — count of validators returning `CONFIRMED`

No additional narration between sub-steps. The final markdown review (step 7) is the user-facing output and stands on its own.

## Pipeline

Follow these steps precisely.

### 1. Resolve the changelist

If the user invoked the skill with a CL number argument, use it. Otherwise, list the user's pending CLs and ask them to pick one:

```bash
p4 -ztag changes -s pending -u "$(p4 set -q P4USER | cut -d= -f2)" -m 20
```

Render the list as a small table (CL, description). Wait for the user's choice.

### 2. Gather context (deterministic, scripted)

Run the bundling script — it fetches the diff (with shelved fallback), parses the changed files, resolves them to local workspace paths, and walks each file's parent directories collecting any ancestor `CLAUDE.md` files:

```bash
uv run --no-project python "${CLAUDE_PLUGIN_ROOT}/scripts/prepare_review.py" <CL>
```

The script outputs JSON with this shape:

```json
{
  "cl": "143376",
  "description": "Fix inventory overflow",
  "diff": "==== //depot/.../foo.cpp#3 ...\n@@ -10,5 +10,6 @@ ...",
  "changed_files": [
    {"depot": "//depot/.../foo.cpp", "local": "C:\\ws\\foo.cpp",
     "claude_mds": ["C:\\ws\\src\\CLAUDE.md", "C:\\ws\\CLAUDE.md"]}
  ],
  "unique_claude_mds": ["C:\\ws\\src\\CLAUDE.md", "C:\\ws\\CLAUDE.md"]
}
```

If the script exits non-zero, surface the stderr message to the user and stop.

### 3. Read CLAUDE.md files

Use the `Read` tool on each path in `unique_claude_mds`. You will pass their full contents to the CLAUDE.md compliance reviewer in step 4. Do this once — subagents do not need to re-read.

### 4. Launch reviewer subagents (3 in parallel)

Send a single message with **three** `Agent` tool calls, all `subagent_type: general-purpose`, with the model overrides below. Each agent's prompt must be self-contained — include the diff, the CL description, and the relevant context. Each agent must return a JSON array of issues with this shape:

```json
[{"file": "<depot or local path>", "lines": "<line range, e.g. 42 or 42-48>",
  "reason": "bug" | "claude_md", "description": "<one-sentence explanation>",
  "citation": "<exact rule quote, only for claude_md issues>"}]
```

#### Reviewer A — CLAUDE.md compliance (`model: sonnet`)

Pass the full diff plus the per-file CLAUDE.md mapping with full text of each CLAUDE.md (you have these from step 3). Tell the agent: only consider CLAUDE.md files that share a path with the file being reviewed (use the per-file mapping, do not cross-apply).

#### Reviewer B — Diff-only bug audit (`model: opus`)

Pass only the diff and CL description. The agent must NOT use `Read` or any other tool to look beyond the diff. Scope: obvious bugs visible in the diff alone — won't-compile, syntax/type errors, missing imports, unresolved references, definitely-wrong logic regardless of inputs.

#### Reviewer C — Introduced-code audit (`model: opus`)

Pass the diff and CL description, plus the list of local file paths. The agent MAY use `Read` to look at surrounding context in the changed files when needed. Scope: bugs/security/logic problems in the introduced code that need broader context to identify (e.g. concurrency issues, lifetime bugs, security holes).

#### False-positive guardrails (include in every reviewer prompt)

Only flag issues where:
- The code will fail to compile or parse (syntax errors, type errors, missing imports, unresolved references).
- The code will definitely produce wrong results regardless of inputs (clear logic errors).
- A CLAUDE.md rule is clearly and unambiguously violated, and you can quote the exact rule.

Do NOT flag:
- Code style or quality concerns.
- Potential issues that depend on specific inputs or state.
- Subjective suggestions or improvements.
- Pre-existing issues (only review the diff).
- Anything a linter would catch (do not run a linter).
- Issues that appear in CLAUDE.md but are explicitly silenced in the code (e.g. lint-ignore comments).

If you are not certain an issue is real, do not flag it. False positives erode trust.

### 5. Validate every flagged issue (parallel subagents)

Collect the issues returned by reviewers A, B, and C into one combined list. For each issue, launch one validator subagent in parallel.

- **Bug issues** (`reason: "bug"`) → `model: opus`
- **CLAUDE.md issues** (`reason: "claude_md"`) → `model: sonnet`

Each validator's prompt:

> A reviewer flagged the following issue on Perforce CL `<CL>` (`<description>`). Validate whether this is a real issue with high confidence. For bugs: examine the cited diff lines (and surrounding code via `Read` if needed). For CLAUDE.md issues: confirm the cited rule is in scope for the file and is actually violated by the change. Reply with exactly one line: `CONFIRMED: <one-sentence reason>` or `REJECTED: <one-sentence reason>`.
>
> Issue: `<JSON of the issue>`
> Diff: `<full diff>`
> [If CLAUDE.md issue: include relevant CLAUDE.md contents]

The validator does not see who flagged the issue — independence is the value.

### 6. Filter

Keep only issues whose validator returned `CONFIRMED`. Drop the rest silently (do not report rejected issues to the user — that erodes signal).

### 7. Render the review

Output one markdown summary in chat. Group issues by file. Use this format:

```
## Review: CL <CL> — <description>

Found N issues (M filtered as false positives).

### path/to/file.cpp
- **[bug]** L42: Buffer overflow risk — `items[i]` accessed without bounds check.
- **[claude_md]** L78: Violates `src/CLAUDE.md` rule "Use absl::Status not bool returns".
```

If 0 issues survive validation:

```
## Review: CL <CL> — <description>

No issues found. Reviewed for bugs and CLAUDE.md compliance.
```

## Notes

- **Render only.** This skill outputs results in chat — there is no Swarm comment, PR comment, or disk write step.
- **No retries.** If `prepare_review.py` fails, report the error and stop.
- **Parallelism matters.** Reviewer agents (step 4) run in one message with three concurrent `Agent` calls. Validators (step 5) run in one message with N concurrent `Agent` calls. Sequential calls waste time.
- **Quoting.** Always quote the exact CLAUDE.md rule text when flagging a `claude_md` issue. If you cannot quote it verbatim, do not flag it.
