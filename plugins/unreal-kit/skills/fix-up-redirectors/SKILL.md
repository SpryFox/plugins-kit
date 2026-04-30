---
name: fix-up-redirectors
skill-type: technique-skill
description: Use when cleaning up Unreal ObjectRedirector assets in a P4-backed UE project. Fixes safe redirectors in a fresh CL. Do NOT use for non-P4 projects.
disable-model-invocation: false
argument-hint: "[scope path, e.g. /Game/Art - omit for whole project]"
---

# Fix Up Redirectors

Unreal's editor command `Fix Up Redirectors in Folder` stalls on the first file someone else has checked out. This skill instead classifies every redirector by P4 safety, fixes only the safe ones in a fresh CL, and tells you who to ping for the rest.

## When to Use

- Periodic content hygiene (every couple of weeks, or before a content freeze)
- After a rename/move pass that left redirectors behind
- When `Fix Up Redirectors in Folder` keeps failing on locked files

## Prerequisites

- Perforce CLI on PATH (`p4`)
- The unreal-kit plugin installed; `ue-runner` available
- A working dir for outputs (the skill defaults to `tmp/redirectors/` in cwd)

## Arguments

- No arg: scan all of `/Game`
- One arg: scan a sub-path (e.g. `/Game/Art`, `/Game/UI/Widgets`)

## Step tracking

This skill has six phases. Track progress in a TodoWrite list with one entry per phase so nothing is skipped between Discover, Classify, Report, Code-ref filter, Apply, and Final report.

## Phase 1 - Discover redirectors (UE Python)

Run discovery via the plugin's `ue-runner`. Pass scope via `SCOPE` env var.

```bash
mkdir -p tmp/redirectors
MSYS_NO_PATHCONV=1 SCOPE="${1:-/Game}" \
  "${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue-runner.cmd" \
  "${CLAUDE_PLUGIN_ROOT}/skills/fix-up-redirectors/bin/discover_redirectors.py" \
  --copy-output tmp/redirectors/
```

> `MSYS_NO_PATHCONV=1` is required on Windows Git Bash so it doesn't translate `/Game/...` into a Windows path before Python sees it.

The discovery YAML lands at `tmp/redirectors/redirectors_discovery.yaml`. It contains, per redirector: package name, on-disk file, target package, target-exists flag, all referencer files (hard + soft), and a flag for level referencers.

## Phase 2 - Classify safety (host Python)

The classifier is a host-side script (no Unreal needed). Run it from the project root so `p4` picks up the right `P4USER`/`P4CLIENT` from `.p4config.txt`:

```bash
uv run python \
  "${CLAUDE_PLUGIN_ROOT}/skills/fix-up-redirectors/bin/classify_safety.py" \
  --discovery tmp/redirectors/redirectors_discovery.yaml \
  --out-safe tmp/redirectors/safe.json \
  --out-report tmp/redirectors/report.json
```

`uv run python` is the standard way to invoke Python from any plugins-kit script — it activates the right venv and works on Windows where bare `python` resolves to a Microsoft Store stub. Requires `pyyaml` in the venv (declared in the skill's host-side requirements).

The classifier runs `p4 opened -a` once for the workspace, then buckets each redirector:

- `safe` — neither the redirector nor any of its referencers is opened by anyone (levels are included)
- `blocked` — at least one file is opened by a teammate (or you, in another CL); records the user(s)
- `broken` — the redirector's target asset is missing
- `non_writable` — at least one referencer file isn't in the local workspace mapping (plugin content we can't edit)

The report also tracks how many `safe` redirectors touch a `.umap` referencer, just for visibility.

> Phase 2 does NOT consult the code-references cache. That happens lazily in Phase 4 prep below, so we don't pay for a full source scan unless the user actually decides to apply.

## Phase 3 - Present the report

Read `tmp/redirectors/report.json` and print this exact summary:

```
Scanning <scope>... <total> redirectors found.

  <N>  safe to fix    (<M> touch levels)
  <N>  blocked by P4 checkouts:
       @<user1>  <count>  (CL <#>, CL <#>)
       @<user2>  <count>  (default CL)
       ...
  <N>  broken (target missing - manual cleanup needed)
  <N>  in non-writable mounts (plugin content; skipped)
```

Then ask: **"Want me to fix the N safe ones in a new CL? [y/N]"**

Do NOT proceed without explicit yes.

## Phase 3.5 - Filter against code references (host Python, only at apply time)

A redirector that's still referenced from C++/C#/Python source must NOT be fixed - the code would silently start pointing at a missing asset. We treat code references the same way we treat P4 checkouts: a hard block.

The cache lives at `./.local-data/code_references.yaml` (per-project, not checked in). It's only required when applying. The filter script regenerates it transparently if it's missing or older than 24 hours; otherwise it reuses the cached scan:

```bash
uv run python \
  "${CLAUDE_PLUGIN_ROOT}/skills/fix-up-redirectors/bin/filter_safe_by_code_refs.py" \
  --safe-in tmp/redirectors/safe.json \
  --safe-out tmp/redirectors/safe_filtered.json \
  --report-out tmp/redirectors/code_refs_report.json \
  --max-age-hours 24
```

The scan walks the cwd by default. Override with `--root <path>` if your code lives elsewhere. Default extensions cover C/C++/C#/Python/INI plus `.uproject`/`.uplugin`; override with `--extensions` (comma-separated) to include configs (`.yaml`, `.json`) if your project encodes asset paths in data.

If any redirectors get dropped here, re-print an updated count to the user before proceeding:

```
Code-ref filter: <kept>/<total> remain after dropping <dropped> referenced from source.
```

To force a fresh scan ahead of time (e.g. you just renamed a bunch of assets in source):

```bash
uv run python \
  "${CLAUDE_PLUGIN_ROOT}/skills/fix-up-redirectors/bin/scan_code_references.py"
```

## Phase 4 - Apply fixups (UE Python, after approval)

Use `safe_filtered.json` from Phase 3.5, NOT the raw `safe.json`:

```bash
SAFE_JSON=tmp/redirectors/safe_filtered.json \
  "${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue-runner.cmd" \
  "${CLAUDE_PLUGIN_ROOT}/skills/fix-up-redirectors/bin/apply_fixups.py"
```

To prepend a project-specific CL tag (e.g. for naming conventions like `[Mix, Tool]`), pass it via env:

```bash
CL_DESC_SUFFIX="[Mix, Tool]" SAFE_JSON=tmp/redirectors/safe_filtered.json \
  "${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue-runner.cmd" \
  "${CLAUDE_PLUGIN_ROOT}/skills/fix-up-redirectors/bin/apply_fixups.py"
```

The apply script:

1. Creates a new pending CL with description `Fix up redirectors: <N> assets in <scope>` (plus `CL_DESC_SUFFIX` if set).
2. `p4 edit -c <CL>` every referencer + every redirector file.
3. `p4 opened -c <CL>` and validates that the opened set equals the expected set. Bails on any mismatch.
4. Loads the redirector assets in UE and runs `unreal.AssetToolsHelpers.get_asset_tools().fixup_referencers(redirectors, checkout_dialog_prompt=False)`.
5. `p4 reconcile -c <CL>` over the affected paths to convert local deletes into P4 deletes.
6. Saves a manifest at `<project>/Saved/PythonOutput/redirectors_apply_<CL>.yaml`.

## Phase 5 - Final report

After phase 4, print:

```
Fixed N redirectors in CL <#>.
Skipped M (blocked by checkouts) - re-run later or ping the users above.
```

If there are blocked redirectors, suggest: **"Tell the blocked users to run `/fix-up-redirectors` themselves to handle their slice."**

## Edge Cases

- **No redirectors found:** print "Clean - no redirectors in <scope>." and stop.
- **All redirectors blocked:** still print the report; nothing to apply. Suggest re-running later.
- **Phase-4 validation mismatch:** if `p4 opened -c <CL>` doesn't match the expected set, abort and tell the user. Do NOT call `fixup_referencers` against an unverified CL.
- **fixup_referencers reports failures:** UE returns a failure list; note them in the manifest. The CL still contains the partial fixup. The user can decide whether to submit or revert.
- **Re-running mid-fix:** if there's already a pending CL with description starting `Fix up redirectors:`, refuse phase 4 and ask the user to either submit/revert that one first, or pass `--force-new-cl`.

## Common Mistakes

- **Skipping validation in phase 4.** Never call `fixup_referencers` without first verifying the CL's opened set matches what discovery promised. A surprise file in the CL means the world moved between discovery and apply.
- **Treating "checked out by me in another CL" as safe.** It's not. Other-CL checkouts are still blocked - the file would land in the wrong CL otherwise.
- **Skipping the code-references filter.** Phase 3.5 isn't optional. A redirector that compiles into a string literal in C++/C#/Python source will silently break that code if you fix the redirector and the target asset later moves or is renamed. Always run the filter; never feed `safe.json` directly into Phase 4.

## Architecture

The skill follows a facade-over-libs structure:

- `bin/` are thin facades that orchestrate one phase each
- `lib/p4cli.py` — host-side P4 CLI (find, run, parse opened, where mapping)
- `lib/package_paths.py` — UE-side mount-point map and package -> on-disk path
- `lib/redirector_record.py` — YAML/JSON I/O for the discovery and safe-set files
- `lib/code_refs.py` — host-side source scanner + cache I/O for `./.local-data/code_references.yaml` (24h freshness)

The libs are also useful for one-off redirector-related scripts. Import them directly:

```python
import sys, os
sys.path.insert(0, os.path.join(os.environ['CLAUDE_PLUGIN_ROOT'], 'skills', 'fix-up-redirectors', 'lib'))
from p4cli import get_opened_map, run_p4
```
