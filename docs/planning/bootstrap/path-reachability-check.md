# Design: PATH-reachability is part of "installed"

## Problem (observed)

Adding `draw.io` to `~/.claude/bootstrap.json` produced a **false failure**:
`config: draw.io: FAILED - install attempted but still not found`, even though
`draw.io.exe` was sitting at `/c/Program Files/draw.io/draw.io.exe` the whole
time. Two distinct defects combined:

1. **`shutil.which("draw.io")` returned None** because `C:\Program Files\draw.io`
   was on neither the session PATH nor HKCU/HKLM Path. The binary existed; it was
   just not *reachable by name*. For a tool a skill invokes by bare name
   (`drawio-skill` shells out to `draw.io`), unreachable-by-name **is** broken —
   the user's framing: "it's not really installed if it isn't on PATH."

2. **A manifest `"check"` field was silently ignored.** The author (me) wrote a
   custom `check` shell command into the tool entry assuming the schema supported
   it. `check_tool()` only reads `name` / `install` / `installPath`, so the field
   did nothing — the engine fell straight through to `which` → not found → ran
   `winget` → winget exited **43** ("already installed, no upgrade") → the engine
   read non-zero as failure → logged "install command failed."

So: a tool that is present-on-disk but absent-from-PATH is currently
unresolvable, and there is no manifest hook to teach the engine how to detect
such a tool. `tools[]` and `path_entries[]` are independent sections with **no
linkage** — nothing says "tool X lives in dir D, therefore ensure D is on PATH."

## Constraints from existing design (must not contradict)

From `references/dependency-philosophy.md`:

- **Principle 4 — find-or-download, never find-and-trust.** "Telling a user to
  'restart your IDE so it picks up a new PATH' is contrary to this principle."
  → My earlier idea of a "restart your session" notice is an ANTI-PATTERN. The
  engine must own the chain, not delegate a link to the user.
- **`installed_but_path_stale` already exists** as a failure state with bespoke
  fix-all messaging (engine.py ~2249) and is deliberately **not** auto-fixable
  (`_is_auto_fixable` returns False for it, ~2225) to avoid the winget
  "already installed" reinstall loop.
- The philosophy's own prescription for `installed_but_path_stale` on a
  system-side tool: **"add an `installPath` hint to the tool entry"** — i.e. the
  fix is supposed to be a manifest hint, but today `installPath` only accepts a
  **single directory** and the consumer must know it in advance.

## What's actually wrong vs. what to add

| Defect | Today | Fix |
|---|---|---|
| `installPath` is one dir | `installPath: "X"` only | accept a **list** of candidate dirs (draw.io lives in `Program Files`, *or* `LOCALAPPDATA\Programs`) |
| No "is it really here" hook | only name-on-PATH or installPath file-exists | add optional **`check`** command field (run it; exit 0 = present) — the field I wrongly assumed existed |
| Found-on-disk ≠ on-PATH not reconciled | passes silently OR reinstalls | when resolved via installPath/check but dir not on PATH, **auto-add the dir to PATH** (link tool→dir) |
| winget exit 43 read as failure | `install_failed` | treat "already installed / no upgrade" as **success**, then re-check |
| Post-install PATH staleness | (handled via repair_path) | keep repair_path; never emit a user "restart" instruction (philosophy P4) |

## Design

### 1. `installPath` accepts a list (backward compatible)

`check_tool(install_path=...)` already expands one dir. Accept `str` **or**
`list[str]`; try each in order; first hit wins. Manifest:

```json
{"name": "draw.io",
 "installPath": ["/c/Program Files/draw.io", "$LOCALAPPDATA/Programs/draw.io"]}
```

(`$VAR` and `~` expansion already done by `os.path.expanduser`; add
`os.path.expandvars` for `$LOCALAPPDATA`.)

### 2. Optional `check` command field

A tool entry may carry `"check": "<shell cmd>"`. When present, `check_tool` runs
it (via the same bash-on-Windows shim as `run_install`); **exit 0 ⇒ present**.
This is the general escape hatch for "present" semantics that name-on-PATH can't
express (version probes, app-bundle layouts, `--version` smoke). Resolution
order becomes:

```
installPath candidates (file exists)  →  check cmd (exit 0)  →  shutil.which(name)
```

`check`-resolved tools won't have a single binary `path`; that's fine —
`tool_paths.record` is skipped when no concrete path is known (it already
guards on falsy path).

### 3. Link tool → PATH (the heart of the user's point)

`CheckResult` gains `on_path: bool`. After a tool resolves:

- resolved **and** its dir is on PATH → ok (today's happy path).
- resolved via installPath/check but dir **not** on PATH → **auto-remediate**:
  call `add_path_to_shell_config(dir)` (persists to RC + HKCU registry,
  idempotent) AND prepend to `os.environ["PATH"]` for this run. Log an action
  line: `draw.io: on disk but not on PATH — added /c/Program Files/draw.io`.
  This is "owning the chain" per P4 — no user instruction, no restart.
- not resolved at all → existing install / download / fix-all flow.

This makes "installed" mean **reachable**, and it's the missing linkage between
`tools[]` and `path_entries[]`: a tool now pulls its own dir onto PATH.

### 4. winget "already installed" is success

`run_install` returns `(ok, output)` on exit code. Add a post-install
reconciliation: if `ok` is False BUT the tool now resolves on re-check (or the
output matches a known "already installed / no available upgrade" signature),
treat as resolved, not `install_failed`. The cleaner, install-tool-agnostic
version: **always re-check after an install attempt regardless of exit code** —
if the re-check passes, it's installed; the installer's exit code is advisory.
(winget 43, brew "already installed", apt "newest version" all collapse to "the
tool is there now.")

### 5. Never tell the user to restart (P4)

Audit the `installed_but_path_stale` messaging. With #3 in place, the common
case (binary exists, dir off PATH) is now **auto-fixed**, so it should rarely
fire. When it genuinely can't resolve, keep the existing "bootstrap bug /
download to ~/.local/bin" guidance — but ensure no code path emits a
"restart your IDE/session" instruction.

## Touch points

- `bootstrap_lib/tool_check.py`: `CheckResult.on_path`; `installPath` list +
  `expandvars`; `check` command execution; return whether resolved-dir is on PATH.
- `bootstrap_lib/engine.py`: both tool loops (`_process_self_setup` ~607,
  `_process_manifest` ~1266) — identical edits: after resolve, if not on_path,
  auto-add dir; after install attempt, re-check regardless of exit code.
  Factor the shared loop body to avoid divergence (they're already near-identical).
- `bootstrap_lib/path_check.py`: reuse `add_path_to_shell_config` (no change).
- `references/manifest-reference.md` + `dependency-philosophy.md`: document
  `check`, list-form `installPath`, and the tool→PATH auto-link.

## Tests (tests/bootstrap/)

- `test_tool_check.py`: list `installPath` (first/second/none hit); `$VAR`
  expansion; `check` cmd exit 0 vs nonzero; `on_path` true/false.
- new `test_tool_path_linkage.py`: tool resolved off-PATH → `add_path_to_shell_config`
  invoked with the right dir (monkeypatch; `BOOTSTRAP_SKIP_REGISTRY=1`),
  PATH mutated in-process, action line emitted, no failure recorded.
- engine: install attempt that exits nonzero but re-check passes → recorded as
  installed, not `install_failed` (covers winget 43).
- regression: a normal on-PATH tool still logs plain `ok` with no PATH churn.

## Rollout

Engine + manifest-schema change → **version bump** required (bootstrap is the
foundation; consumers read the cached manifest). Smoke-test via `claude-dev`
(dev-tree mode) because it touches manifest-content semantics, per CLAUDE.md.
Then fix `~/.claude/bootstrap.json`'s draw.io entry to the new list-`installPath`
+ `check` form (drop the currently-dead `check` once it's actually supported).

## Out of scope

- Migrating system tools to download-under-~/.local (separate, larger
  redesign already tracked in `tool-resolution-redesign.md`).
- Changing `tool_paths.json` schema.
```
