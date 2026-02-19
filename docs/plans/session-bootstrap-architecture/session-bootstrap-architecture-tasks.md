# Session-Bootstrap Architecture: Implementation Tasks

Source: Session `f67430da-686a-432a-9e2f-7660d0cca6a1` (2026-02-17)

## Dependency Graph

```
Task #1: Design manifest schemas ✅ DONE
    ↓
    ├── Task #2: Create manifest files for unreal-kit ✅ DONE
    ├── Task #3: Implement system tool checking (Step 1) ✅ DONE
    ├── Task #4: Implement venv creation via uv sync (Step 2) ✅ DONE
    └── Task #5: Implement data dependency fetching (Step 3) ✅ DONE
         ↓ (all three #3, #4, #5 must complete)
         Task #6: Implement validation flag and hash caching (Step 4)
              ↓
              Task #7: Assemble SessionStart hook and wire into hooks.json
                   ↓
                   Task #8: Test bootstrap on macOS
```

**Parallelization**: Tasks #2–#5 can be worked in parallel once #1 is done. Everything converges at #7 (assembly), then #8 (testing).

---

## Task #1: Design Manifest Schemas

**Status**: Done
**Blocks**: #2, #3, #4, #5
**Blocked By**: None

Define YAML schemas for the system tool manifest (per-OS entries with explicit check/install methods) and data dependency manifest. pyproject.toml uses its standard format.

**Key design principles**:
- No defaults, no inheritance — explicit per-OS entries for every dependency
- Fail-fast — first missing tool stops the hook; manifest author responsible for ordering
- Ad-hoc analysis — no automatic dependency resolution; authors discover gaps by running the hook

**Deliverables**: `session-bootstrap` skill with `references/manifest-schemas.md`

**Detailed plan**: `plan-task-1-manifest-schemas.md` (in this directory)

---

## Task #2: Create Manifest Files for unreal-kit

**Status**: Done
**Blocks**: #7
**Blocked By**: #1

Create the three manifest files for unreal-kit — the first consumer of the bootstrap system.

**Scope**:
- `system-tools.yaml` — per-OS entries (macOS, Windows, Ubuntu) declaring uv and any other CLI deps (git, curl, etc.) with explicit install commands per platform
- `pyproject.toml` — Python package dependencies (standard PEP 621 format)
- `data-dependencies.yaml` — git repos to clone (UE Python stubs, references) and any file downloads

**File location**: `plugins/unreal-kit/` (alongside `.claude-plugin/plugin.json`)

**Acceptance criteria**:
- All three manifests conform to Task #1 schemas
- System tool manifest includes uv with platform-specific install instructions
- Data manifest lists stubs repo and documentation references
- Valid YAML, no schema violations

---

## Task #3: Implement System Tool Checking (Step 1)

**Status**: Done
**Blocks**: #6, #7
**Blocked By**: #1

Bash functions that detect OS, read the system tool manifest for that OS, walk entries in order, check each via `command -v`, and fail fast on the first missing tool — emitting the install command from the manifest.

**Implementation details**:
- OS detection via `$OSTYPE` or `uname -s` — maps: `darwin*` → `macos`, `linux-gnu*` → `ubuntu`, `msys*`/`cygwin*` → `windows`
- Parse YAML manifest for current OS section
- Loop tools in declared order; `command -v` each
- On first missing tool: emit structured error with tool name + install command from manifest
- No platform conditionals in hook logic — all platform knowledge lives in the manifest

**Deliverables**:
- Bash function: `check_system_tools()`
- Structured error output (tool name, install command, OS)
- Integration point: only proceeds to Step 2 if all tools pass

**Acceptance criteria**:
- Correctly detects macOS, Windows (Git Bash), Ubuntu
- Reads correct OS section from manifest
- Checks tools in declared order
- Fails fast with actionable remediation
- Zero platform conditionals in bash logic

---

## Task #4: Implement venv Creation via uv sync (Step 2)

**Status**: Done
**Blocks**: #6, #7
**Blocked By**: #1

Bash logic that creates or updates the plugin's `.venv` from `pyproject.toml` using `uv sync`. Only runs if Step 1 passes.

**Implementation details**:
- Venv location: persistent, outside plugin cache (e.g. `${PLUGIN_DATA}/.venv`) so it survives cache refreshes
- Run `uv sync` against the plugin's `pyproject.toml`
- Handle cross-platform Python path: `bin/python` (macOS/Linux) vs `Scripts/python` (Windows)
- Export Python executable path for use in subsequent steps

**Deliverables**:
- Bash function: `create_venv()`
- Cross-platform Python executable detection
- Integration point: only proceeds to Step 3 if venv ready

**Acceptance criteria**:
- Creates or updates venv via `uv sync`
- Venv persists across plugin cache refreshes
- Correctly resolves Python executable on all platforms
- Only runs after Step 1 passes

---

## Task #5: Implement Data Dependency Fetching (Step 3)

**Status**: Done
**Blocks**: #6, #7
**Blocked By**: #1

Bash logic that reads the data dependency manifest and processes git repos (clone-if-missing, pull-if-stale, branch enforcement) and file downloads (curl with optional sha256 verification). Only runs if Steps 1–2 pass.

**Implementation details**:
- Parse data dependency manifest YAML
- Git repositories: check if `target/.git` exists → clone if missing, pull if stale, fail on wrong branch (never auto-switch)
- File downloads: `curl` to target path, verify sha256 hash if declared in manifest
- All data goes to `${PLUGIN_DATA}` (persistent, outside plugin cache)
- Handle network errors, auth failures, disk space issues — emit structured remediation

**Deliverables**:
- Bash function: `fetch_data_dependencies()`
- Git repo handling: clone / pull / branch enforcement
- File download with optional sha256 verification
- Integration point: only proceeds to Step 4 if all deps resolved

**Acceptance criteria**:
- Clones missing repos, pulls existing ones
- Enforces branch specification (fails on mismatch, never auto-switches)
- Downloads files, verifies sha256 when declared
- Data stored in `${PLUGIN_DATA}`
- Only runs after Steps 1–2 pass

---

## Task #6: Implement Validation Flag and Hash Caching (Step 4)

**Status**: Pending
**Blocks**: #7
**Blocked By**: #3, #4, #5

Write a validation flag keyed to a combined hash of all three manifests. On subsequent sessions, check the flag first — exit immediately if current. Any manifest change invalidates the flag and triggers a full re-run.

**Implementation details**:
- Hash: SHA256 of concatenated manifest file contents
- Flag file location: `${PLUGIN_DATA}/.bootstrap-validated`
- Flag format: contains manifest hash (and optionally a timestamp)
- On session start: compute current hash → compare to stored hash → skip if match, re-run if mismatch
- Only write the flag after Steps 1–3 all pass successfully

**Deliverables**:
- Bash functions: `check_validation_flag()` and `write_validation_flag()`
- Hash computation across all three manifests
- Flag file read/write logic

**Acceptance criteria**:
- Flag correctly caches combined manifest hash
- Unchanged manifests → skip Steps 1–3 (zero overhead on normal sessions)
- Any manifest change → flag invalidated → full re-run
- Flag only written after all steps succeed (never caches a partial/failed state)

---

## Task #7: Assemble SessionStart Hook and Wire into hooks.json

**Status**: Pending
**Blocks**: #8
**Blocked By**: #2, #3, #4, #5, #6

Combine Steps 1–4 into a single bash SessionStart hook script. Wire it into the plugin's hooks configuration. Ensure structured JSON output lands in `additionalContext`.

**Implementation details**:
- Hook script flow:
  1. Check validation flag (Task #6) → if valid, exit with success JSON
  2. Detect OS, run system tool check (Task #3)
  3. Create/update venv (Task #4)
  4. Fetch data dependencies (Task #5)
  5. Write validation flag (Task #6)
- Structured JSON output to stdout → lands in `additionalContext`:
  - Overall status (success / failure)
  - Per-step status and results
  - Error messages with remediation commands
- Wire into plugin's `hooks.json`: event `SessionStart`, matcher `"*"`

**Deliverables**:
- Single bash SessionStart hook script (composing all functions from Tasks #3–#6)
- `hooks.json` entry for the plugin
- Structured JSON output format documentation

**Acceptance criteria**:
- All four steps execute in correct order
- Flag check optimization works (skips when current)
- JSON output includes status, per-step results, and errors with remediation
- Hook properly registered in hooks.json
- Errors propagate with actionable guidance in `additionalContext`

---

## Task #8: Test Bootstrap on macOS

**Status**: Pending
**Blocks**: None
**Blocked By**: #7

End-to-end testing on macOS (primary development platform).

**Test plan**:

1. **Initial run** (no validation flag):
   - Remove `${PLUGIN_DATA}/.bootstrap-validated`
   - Start Claude Code with `--plugin-dir plugins/unreal-kit`
   - Verify all four steps execute
   - Verify JSON output appears in `additionalContext`
   - Verify validation flag is written

2. **Cached run** (flag present, manifests unchanged):
   - Restart Claude Code (same command)
   - Verify flag check skips Steps 1–3
   - Verify JSON confirms "already validated"

3. **Failure path** (tool missing):
   - Temporarily hide a system tool (e.g., rename `uv`)
   - Restart Claude Code
   - Verify error message lists missing tool + install command
   - Verify flag is NOT written
   - Restore tool, verify next run succeeds

4. **Manifest change**:
   - Modify one manifest file
   - Restart Claude Code
   - Verify hash mismatch triggers full re-run
   - Verify new flag written with updated hash

**Acceptance criteria**:
- All four sub-tests pass
- JSON output properly formatted
- Flag caching works (skip on unchanged, re-run on change)
- Failure path produces actionable remediation
- No unexpected errors or warnings

**Future**: Windows/WSL and Ubuntu testing in subsequent phases.
