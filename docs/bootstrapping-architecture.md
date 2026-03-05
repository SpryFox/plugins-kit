# Bootstrapping Architecture

This document describes how plugins-kit ensures all dependencies are available before any plugin code runs. There are two bootstrapping systems operating at different layers.

## Overview

| Layer | System | When it runs | What it manages |
|-------|--------|-------------|-----------------|
| Plugin | Session Bootstrap | Claude Code SessionStart | System tools, Python venv, git repos |
| Skill | Script Bootstrap | Script execution time | UE-side Python packages, host-side wrappers |

The session bootstrap runs once per session (or skips via cache). The script bootstrap runs inside individual scripts that need runtime dependencies.

## Session Bootstrap

A bash SessionStart hook (`hooks/sessionstart/session-bootstrap.sh`) that validates the entire plugin environment through a 5-step sequence. Steps 1-4 handle environment readiness (tools, venv, git deps, cache). Step 5 handles plugin configuration via the [Claude-Driven Setup Pattern](claude-driven-setup-pattern.md). All platform-specific knowledge lives in manifest files, not in hook logic.

### Manifests

Three manifest files at the plugin root (`plugins/unreal-kit/`) declare what the plugin needs:

| Manifest | Format | Purpose |
|----------|--------|---------|
| `system-tools.yaml` | Per-OS tool entries | CLI tools with check/install methods per platform |
| `pyproject.toml` | PEP 621 | Host-side Python packages (managed by uv) |
| `git-dependencies.yaml` | URL + branch entries | External git repositories to clone |

### Sequence

```
SessionStart fires
    |
    v
Step 0: Check validation flag
    |-- Cache hit (hash matches) --> exit (zero overhead)
    |-- Cache miss --> continue
    v
Step 1: Check system tools (check-system-tools.sh)
    Read system-tools.yaml for detected OS
    Walk entries in declared order
    Collect all independent failures
    |-- Any failures --> emit remediation JSON, exit
    v
Step 2: Create/update venv (create-venv.sh)
    Tier 1: Validate existing venv (no uv needed)
    Tier 2: uv sync from pyproject.toml (if venv missing/broken)
    Venv stored at ~/.claude/plugins/data/unreal-kit/.venv
    |-- Failure --> emit remediation JSON, exit
    v
Step 3: Fetch git dependencies (fetch-git-deps.sh)
    Clone missing repos, pull existing ones
    Enforce branch specification
    Target: ~/.claude/plugins/data/unreal-kit/github/<repo-name>/
    |-- Failure --> emit remediation JSON, exit
    v
Step 4: Write validation flag (validate-cache.sh)
    SHA256 hash of all three manifests
    Stored at ~/.claude/plugins/data/<plugin>/.bootstrap-validated
    Next session: hash matches --> skip Steps 1-3
    |
    v
Step 5: Check plugin config (check-config.sh) [optional]
    Run setup.py --check if setup script exists
    Config is NOT cached — checked every session
    |-- Config valid --> emit success
    |-- Config missing --> emit setup guidance, exit 0
    |-- No setup script --> skip (success)
```

### Design Principles

**Configuration-driven, not logic-driven.** The hook contains no platform-specific conditional branches for individual tools. It detects the OS once, reads the manifest entries for that OS, and executes what's declared. All platform knowledge lives in the manifests.

**Explicit per-OS entries.** Every tool dependency declares its check and install method for each platform it supports. No defaults, no inheritance. If `curl` is needed on all platforms, it appears three times.

**Collect independent failures.** System tool checking collects all independent failures rather than failing on the first one, so the user sees everything they need to fix. Consequential failures (e.g., a command that lives in a failed PATH directory) are detected and skipped.

**Two-tier venv management.** Step 2 first checks if the existing venv is functional (Tier 1: directory exists, Python runs, packages importable) without needing uv. Only falls back to `uv sync` (Tier 2) if the venv is missing or broken. This removes the hard uv dependency for sessions where the venv is already good.

**Persistent storage.** The venv and cloned git repos live in `~/.claude/plugins/data/unreal-kit/` (outside the plugin cache), so they survive cache refreshes when the plugin updates.

**Remediation, not auto-fix.** When something is missing, the hook emits structured JSON with the exact install command into Claude's `additionalContext`. The user can fix it themselves or tell Claude to do it.

### File Layout

```
plugins/unreal-kit/
  system-tools.yaml              # System tool manifest
  pyproject.toml                 # Python package manifest
  git-dependencies.yaml          # Git dependency manifest
  bootstrap-config.yaml          # Bootstrap behavior config (silent_when_valid)
  hooks/sessionstart/
    session-bootstrap.sh         # Orchestrator (sources step scripts)
    check-system-tools.sh        # Step 1: system tool verification
    create-venv.sh               # Step 2: venv creation/validation
    fetch-git-deps.sh            # Step 3: git dependency fetching
    validate-cache.sh            # Step 4: hash-based cache validation
    lib/
      bootstrap-helpers.sh       # Shared functions (json_escape, detect_os, sha256)
    check-config.sh              # Step 5: config setup check (optional)
  scripts/
    setup.py                     # Config management (--check/--describe/--apply/--init-defaults)
  defaults/
    config.yaml                  # Template config with default values
```

### System Tool Manifest Format

```yaml
system_tools:
  windows:
    - name: local-bin
      check_type: persistent_path    # Verifies PATH entry persists across sessions
      check: "$HOME/.local/bin"
      install: "powershell.exe ... add-to-win-path.ps1"
    - name: uv
      enabled: false                 # Skip this entry (soft dependency)
      check: "uv"
      install: "curl -LsSf https://astral.sh/uv/install.sh | sh"
    - name: git
      check: "git"                   # Default check_type: command (command -v)
      install: "winget install --id Git.Git"
```

Key fields: `name` (display), `check` (what to verify), `install` (exact command), `check_type` (default `command`, or `persistent_path`), `enabled` (default `true`, set `false` to skip).

## Config Setup (Step 5)

Step 5 is an optional config check that runs after the environment bootstrap (Steps 1-4). Plugins that need user-specific configuration (API keys, preferences, paths) provide a `scripts/setup.py` implementing a standard interface contract. The bootstrap step runs `setup.py --check` and, if config is incomplete, emits context directing Claude to guide the user through interactive setup via a setup skill.

Key properties:
- **Not cached**: Config is user data, checked every session regardless of cache state
- **Same severity as Step 1**: Missing config emits remediation context and exits 0 (session starts with guidance)
- **Stdlib-only**: `setup.py` uses no third-party packages — works even if the venv is broken
- **Optional**: Plugins without a setup script skip Step 5 silently

For the full pattern specification, see [Claude-Driven Setup Pattern](claude-driven-setup-pattern.md). For a reference implementation, see `plugins/test-plugin/`.

## Script Bootstrap

The ue-python-api skill has its own bootstrapping for scripts that run inside Unreal Engine's embedded Python, where the session bootstrap's venv isn't available.

### The Problem

Scripts running inside UE Editor need packages like `pyyaml`, but UE's embedded Python doesn't share the host's venv. Meanwhile, the host-side runner needs `upyrc` and `pyyaml` to function. These are two separate Python environments with different dependency management.

### Two Dependency Sets

| Set | Manifest | Runtime | Manager | Install target |
|-----|----------|---------|---------|----------------|
| UE-side | `requirements.yaml` | UE's embedded Python | `bootstrap.py` + `unreal_pip.py` | Engine site-packages |
| Host-side | `pyproject.toml` | System Python | Session bootstrap (uv sync) | Plugin data venv |

### UE-Side Bootstrap (`lib/bootstrap.py`)

Scripts call `ensure_dependencies()` at the top:

```python
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/lib')
from bootstrap import ensure_dependencies
ensure_dependencies()

import yaml  # now available
```

The function:
1. Reads `requirements.yaml` using a **hand-rolled YAML parser** (not pyyaml — since pyyaml is itself a dependency being installed)
2. Checks installed packages via `pkg_resources.working_set`
3. Installs missing packages via `unreal_pip.install()`, which shells out to pip using UE's embedded Python interpreter
4. Targets UE's own site-packages: `Engine/Binaries/ThirdParty/Python3/Win64/Lib/site-packages`
5. Invalidates import caches so new packages are immediately importable

### Host-Side Wrappers

The `.cmd` entry points handle host-side dependencies:

- **`ue-runner.cmd`**: Uses `uv run --with upyrc --with pyyaml` for an ephemeral environment (legacy path, before session bootstrap existed)
- **`setup.cmd`**: Requires only Python on PATH — `setup.py` is stdlib-only by design

### Stdlib-Only Constraint

Three modules include hand-rolled minimal YAML parsers to avoid needing pyyaml before it's installed:

| Module | Where it runs | Why it can't use pyyaml |
|--------|--------------|------------------------|
| `lib/bootstrap.py` | UE Editor | pyyaml is the dependency being installed |
| `lib/ue_runner_config.py` | Host Python | May run before venv exists |
| `bin/setup.py` | Host Python | Runs before any dependencies are installed |

This duplication is intentional — each module must function independently during the bootstrapping phase when no external packages are guaranteed to exist.

### Config Resolution

The runner loads configuration through a layered system:

```
CLI args  >  project config  >  skill config  >  hardcoded defaults
              (~/.claude/.local-data/skills/     (ue_runner_config.yaml)
               ue-python-api/project.yaml)
```

`setup.py` writes the project config during initial setup. The config includes `engine_dir` and `uproject` paths needed by both the remote executor and the commandlet fallback.

## How the Two Systems Interact

The session bootstrap ensures system tools and the host-side venv are ready. The script bootstrap handles UE-side dependencies that can only be resolved inside the editor.

```
Session Start
    |
    v
Session Bootstrap (bash hook)
    Verifies: git, uv, PATH entries
    Creates: host-side venv (upyrc, pyyaml)
    Clones: git dependencies
    |
    v
Claude Code session active
    |
    v
User runs a UE Python script (via ue-runner)
    |
    v
ue_runner.py loads config (fallback YAML parser if needed)
    |
    v
Script sent to UE Editor (remote or commandlet)
    |
    v
Script Bootstrap (inside UE Python)
    ensure_dependencies() installs to Engine site-packages
    |
    v
Script executes with all dependencies available
```

## Related Documentation

- [plugins/bootstrap/ARCHITECTURE.md](../plugins/bootstrap/ARCHITECTURE.md) — Bootstrap engine internals: manifest processing, remediation loop, caching, messaging protocol

## Historical Context

The session bootstrap architecture was designed and implemented in February 2026. The original proposal and implementation task breakdown are preserved in `docs/historical/session-bootstrap-architecture/`.
