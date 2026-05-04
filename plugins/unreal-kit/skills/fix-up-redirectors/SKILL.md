---
name: fix-up-redirectors
skill-type: technique-skill
description: Use when cleaning up Unreal ObjectRedirector assets in a P4-backed UE project. Fixes safe redirectors in a fresh CL. Do NOT use for non-P4 projects.
disable-model-invocation: false
argument-hint: "[scope path, e.g. /Game/Art - omit for whole project]"
---

# Fix Up Redirectors

Unreal's editor command `Fix Up Redirectors in Folder` stalls on the first file someone else has checked out. This skill instead classifies every redirector by P4 safety, fixes only the safe ones in a fresh CL, and tells you who to ping for the rest.

## Two redirector categories

Not every redirector needs the same treatment:

- **Fix-up redirectors** (target exists, has referencers): the standard case. Referencers must be re-saved to point at the redirector's target before the redirector .uasset can be deleted.
- **Orphaned redirectors** (target gone, zero referencers): pure dead pointers. No rewriting needed — just `p4 delete` the .uasset (and its `.umap` sibling, for level redirectors). Much faster than the fix-up path because there's no UE referencer load/save work.
- **Referenced-broken** (target gone, has referencers): genuinely broken. Deleting the redirector would leave dangling refs. Manual cleanup required; the skill flags these but does not touch them.

The classifier emits the fix-up safe set and (optionally) the orphaned safe set as separate JSON files. The apply script consumes either shape.

## When to Use

- Periodic content hygiene (every couple of weeks, or before a content freeze)
- After a rename/move pass that left redirectors behind
- When `Fix Up Redirectors in Folder` keeps failing on locked files
- Cleaning up orphaned redirectors left behind by deleted assets (the orphan path is cheap; consider running it routinely)

## Prerequisites

- Perforce CLI on PATH (`p4`)
- The unreal-kit plugin installed; `ue-runner` available
- A working dir for outputs (the skill defaults to `tmp/redirectors/` in cwd)

## Arguments

- No arg: scan all of `/Game`
- One arg: scan a sub-path (e.g. `/Game/Art`, `/Game/UI/Widgets`)

## Step tracking

This skill has six phases. Track progress in a TodoWrite list with one entry per phase so nothing is skipped between Discover, Classify, Report, Code-ref filter, Apply, and Final report.

The orphan path uses the same phases but skips the code-ref filter (orphans have no referencers, so source-code references aren't relevant) and uses `--mode=delete-only` in Phase 4.

## Recommended: per-directory subset for broad purges

For any safe set with more than ~100 redirectors, run the per-directory subset reducer first and apply that smaller set as a test pass. The reducer picks exactly one redirector per unique package directory, deterministically.

Why this works: most "this might break something" scenarios are directory-shaped (a particular folder has unusual referencers, soft refs, or naming quirks). A one-per-directory slice exercises every directory shape without committing to a multi-thousand-file edit. In a reference run, 2839 safe redirectors collapsed to a 241-redirector subset that ran in ~19 minutes vs. multi-hour for the full purge — and surfaced any breakage early, when it could still be reverted cheaply.

Use the reducer on either the fix-up safe set or the orphaned safe set; the input/output JSON shape is the same.

```bash
uv run python \
  "${CLAUDE_PLUGIN_ROOT}/skills/fix-up-redirectors/bin/pick_one_per_dir.py" \
  --in tmp/redirectors/safe_filtered.json \
  --out tmp/redirectors/safe_per_dir.json
```

Then point Phase 4 at `safe_per_dir.json` instead. After the test CL submits cleanly, run Phase 4 again on the original safe set (with the per-dir entries removed if you want a strict residual, or just re-run the whole thing — already-fixed redirectors are no-ops in the second pass).

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
  --out-orphaned tmp/redirectors/orphaned.json \
  --out-report tmp/redirectors/report.json
```

`uv run python` is the standard way to invoke Python from any plugins-kit script — it activates the right venv and works on Windows where bare `python` resolves to a Microsoft Store stub. Requires `pyyaml` in the venv (declared in the skill's host-side requirements).

The classifier runs `p4 opened -a` once for the workspace, then buckets each redirector:

- `safe` — fix-up safe set: target exists, neither the redirector nor any of its referencers is opened by anyone (levels are included)
- `blocked` — at least one file is opened by a teammate (or you, in another CL); records the user(s)
- `broken` — the redirector's target asset is missing. Sub-buckets:
  - `orphaned_safe` — target gone AND zero referencers AND the redirector .uasset itself is unlocked. Safe to `p4 delete` directly. Emitted to `--out-orphaned` if provided.
  - `orphaned_blocked` — orphaned but the redirector itself is checked out by someone. Re-run later.
  - `referenced_broken` — target gone but referencers exist. Manual cleanup needed; the skill never touches these.
- `non_writable` — at least one referencer file isn't in the local workspace mapping (plugin content we can't edit)

The report also tracks how many `safe` redirectors touch a `.umap` referencer, just for visibility.

`--out-orphaned` is optional. Skip it if you only care about fix-up redirectors; pass it whenever you want to also clean up orphans (recommended for routine hygiene runs).

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
  <N>  broken (target missing):
       <N>  orphaned (zero referencers, safe to delete)
       <N>  orphaned but checked out (re-run later)
       <N>  referenced-broken (manual cleanup needed)
  <N>  in non-writable mounts (plugin content; skipped)
```

Then ask: **"Want me to fix the N safe ones in a new CL? [y/N]"**

If there are orphaned redirectors, also ask whether to delete them in a separate CL (delete-only mode is independent of the fix-up path; it can run before, after, or instead).

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

**Important: SAFE_JSON must be an absolute path.** UE commandlets run from a different cwd than the user's shell (typically `<project>/Binaries/Win64`), and a relative SAFE_JSON path silently misses the file. The apply script normalizes whatever it gets to absolute via `os.path.abspath`, so passing a relative path *usually* works — but pass an absolute path explicitly when scripting from CI or any setting where the cwd is unclear.

For the fix-up safe set, use `safe_filtered.json` from Phase 3.5, NOT the raw `safe.json`:

```bash
SAFE_JSON="$PWD/tmp/redirectors/safe_filtered.json" \
  "${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue-runner.cmd" \
  "${CLAUDE_PLUGIN_ROOT}/skills/fix-up-redirectors/bin/apply_fixups.py"
```

For the orphaned safe set (delete-only), point `SAFE_JSON` at `orphaned.json` from Phase 2. The script auto-detects the input shape and switches to delete-only mode (no referencer load/save, no code-ref filter required because orphans have no referencers). To force it explicitly, pass `--mode=delete-only`:

```bash
SAFE_JSON="$PWD/tmp/redirectors/orphaned.json" \
  "${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue-runner.cmd" \
  "${CLAUDE_PLUGIN_ROOT}/skills/fix-up-redirectors/bin/apply_fixups.py" \
  --mode=delete-only
```

To prepend a project-specific CL tag (e.g. for naming conventions like `[Mix, Tool]`), pass it via env:

```bash
CL_DESC_SUFFIX="[Mix, Tool]" SAFE_JSON="$PWD/tmp/redirectors/safe_filtered.json" \
  "${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue-runner.cmd" \
  "${CLAUDE_PLUGIN_ROOT}/skills/fix-up-redirectors/bin/apply_fixups.py"
```

The apply script does (fix-up mode):

1. Creates a new pending CL with description `Fix up redirectors: <N> assets in <scope>` (plus `CL_DESC_SUFFIX` if set).
2. `p4 edit -c <CL>` every non-redirector referencer file.
3. UE: load each referencer (resolves redirectors at link time), rewrite soft refs via `rename_referencing_soft_object_paths`, force-save each package.
4. `EditorAssetLibrary.delete_asset` on each redirector to release UE's file handle, then GC, then `p4 reopen -c <CL>` to herd UE-auto-opened deletes into our pending CL (with `p4 delete -c <CL>` as fallback for any not auto-opened).
5. Saves a manifest at `<project>/Saved/PythonOutput/redirectors_apply_<CL>.yaml`.

In delete-only mode: skips steps 2-4 (no referencer load/save needed), opens redirector .uasset files for delete in the new CL, and **automatically includes the `.umap` sibling of every redirector that has one** — level redirectors come in `.uasset`+`.umap` pairs and both files must land in the CL together.

### Phase 4 tail - lock-failure retry

If the apply script reports lock failures (UE held Windows handles even after `delete_asset` returned), it writes a retry list to `<project>/Saved/PythonOutput/redirectors_lock_retry_<CL>.txt`. After the commandlet exits (UE's process is gone, file handles released), run:

```bash
p4 -x - reconcile -c <CL> < <project>/Saved/PythonOutput/redirectors_lock_retry_<CL>.txt
```

`reconcile` notices the locally-deleted files and opens them for delete in the same CL. The script prints the exact command at the end of its run.

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
- **Referenced-broken bucket non-empty:** these are redirectors with no target AND with referencers. The skill never touches them — surface them in the report (sample list comes through as `orphaned_samples` / `broken_samples` in `report.json`) and let the user investigate.
- **Phase-4 validation mismatch:** if `p4 opened -c <CL>` doesn't match the expected set, abort and tell the user. Do NOT call `fixup_referencers` against an unverified CL.
- **fixup_referencers reports failures:** UE returns a failure list; note them in the manifest. The CL still contains the partial fixup. The user can decide whether to submit or revert.
- **Re-running mid-fix:** if there's already a pending CL with description starting `Fix up redirectors:`, refuse phase 4 and ask the user to either submit/revert that one first, or pass `--force-new-cl`.
- **UE file-lock errors during `p4 delete`:** UE has been observed to keep Windows file handles open on referencer packages even after `delete_asset` and a GC pass. The apply script catches "in use by another process" / "access is denied" errors per file, writes the affected paths to `redirectors_lock_retry_<CL>.txt`, and prints the exact `p4 -x - reconcile` command to run after the commandlet exits. The retry pass uses `reconcile` (not `delete`) because by the time we get there UE has already removed the files from disk — reconcile picks up the local-deletes-without-p4-deletes and opens them for delete in the same CL.
- **Level redirectors (`.umap`):** in delete-only mode the script automatically includes the `.umap` sibling of every `.uasset` it deletes. Without this, a level redirector deletion leaves a dangling `.umap` in the depot pointing at a deleted `.uasset`. The fix-up path handles `.umap` referencers naturally because they show up in `referencer_files` from discovery.

## Common Mistakes

- **Skipping validation in phase 4.** Never call `fixup_referencers` without first verifying the CL's opened set matches what discovery promised. A surprise file in the CL means the world moved between discovery and apply.
- **Treating "checked out by me in another CL" as safe.** It's not. Other-CL checkouts are still blocked - the file would land in the wrong CL otherwise.
- **Skipping the code-references filter for fix-up runs.** Phase 3.5 isn't optional for the fix-up path. A redirector that compiles into a string literal in C++/C#/Python source will silently break that code if you fix the redirector and the target asset later moves or is renamed. Always run the filter; never feed `safe.json` directly into Phase 4. (Orphan runs skip the filter — orphans have no referencers, including no source-code referencers.)
- **Running a multi-thousand-file purge as the first apply.** For broad scopes use the per-directory subset reducer (`pick_one_per_dir.py`) for the test pass — it cuts apply time by 10x+ and surfaces breakage early when revert is still cheap.
- **Passing a relative `SAFE_JSON` path from CI.** The apply script normalizes to absolute via `os.path.abspath`, but normalization happens in the commandlet's cwd (typically `<project>/Binaries/Win64`), not yours. Always pass an absolute path explicitly when scripting.
- **Conflating orphaned redirectors with truly broken ones.** "target_exists: false" means two very different things depending on whether anyone references the redirector. The classifier splits these for you; don't lump them back together in tooling that consumes the report.

## Architecture

The skill follows a facade-over-libs structure:

- `bin/` are thin facades that orchestrate one phase each
  - `discover_redirectors.py` — Phase 1
  - `classify_safety.py` — Phase 2 (emits fix-up safe set + optional orphaned safe set + report)
  - `filter_safe_by_code_refs.py` / `scan_code_references.py` — Phase 3.5
  - `pick_one_per_dir.py` — per-directory subset reducer (works on either safe-set shape)
  - `apply_fixups.py` — Phase 4 (fix-up mode and delete-only mode; auto-detected or `--mode=delete-only`)
- `lib/p4cli.py` — host-side P4 CLI (find, run, parse opened, where mapping)
- `lib/package_paths.py` — UE-side mount-point map and package -> on-disk path
- `lib/redirector_record.py` — YAML/JSON I/O for the discovery and safe-set files (`load_safe_set` / `save_safe_set` are reused by `pick_one_per_dir.py`)
- `lib/code_refs.py` — host-side source scanner + cache I/O for `./.local-data/code_references.yaml` (24h freshness)

The libs are also useful for one-off redirector-related scripts. Import them directly:

```python
import sys, os
sys.path.insert(0, os.path.join(os.environ['CLAUDE_PLUGIN_ROOT'], 'skills', 'fix-up-redirectors', 'lib'))
from p4cli import get_opened_map, run_p4
```
