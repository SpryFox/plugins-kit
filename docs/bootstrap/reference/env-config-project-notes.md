# env-config Project Notes

Reference notes from `~/Dev/env-config` — patterns relevant to plugins-kit's SessionStart bootstrap architecture.

## Dependency Declaration

### System Tools (`config/dependencies/os-{platform}.yaml`)

Flat YAML schema per dependency with layered overrides:

```yaml
dependencies:
  jj:
    description: "Fast JSON get/set tool"
    required: true
    check_command: "jj"               # shutil.which() lookup
    version_flag: "-h"
    version_check_contains: "JSON"
    method: "brew"                    # brew | apt | choco | github_release | shell_script | deb_download | skip
    package: "tidwall/jj/jj"
    tap: "tidwall/jj"                 # brew-specific
```

Key fields: `check_command` (PATH lookup), `check_path` (filesystem existence), `check_command_inline` (arbitrary shell test), `method` (install strategy), `required` (boolean).

**Layering**: `os-{platform}.yaml` loaded first, then `host-{hostname}.yaml` overrides. Platform-to-file mapping:
```python
{"macOS": "macos", "Ubuntu-Desktop": "ubuntu", "WSL": "ubuntu", "Windows": "windows"}
```

### Git Repositories (`config/repositories.yaml`)

```yaml
repositories:
  - name: kitaekatt-plugins
    path: ~/Dev/kitaekatt-plugins
    github_url: git@github.com:kitaekatt/kitaekatt-plugins.git
    branch: master
    update_script: bin/update.sh          # optional: run after clone/pull
    update_script_platforms: [macOS, WSL]  # optional: platform filter
    skip_recursive_update: true            # optional: prevent recursion
    checks:
      - repo-exists
      - repo-on-branch
      - repo-up-to-date
```

Behavior: clone if missing, pull if exists. **Never auto-switches branches** — hard error if on wrong branch. Tracks branch name, not commit hash.

### GitHub Release Downloads

```yaml
  jj:
    method: "github_release"
    url: "https://github.com/tidwall/jj/releases/download/v1.9.2/jj-1.9.2-linux-amd64.tar.gz"
    binary_path: "jj-1.9.2-linux-amd64/jj"
    install_path: "/usr/local/bin/jj"
```

Downloads archive, extracts specified file, installs to target path. Supports tar.gz and zip.

### Python Packages

Standard `pyproject.toml` synced via `uv pip sync requirements.lock`.

## Bootstrap Pattern

Three-stage pipeline: bash entry point → bash bootstrap → Python execution.

**Bash bootstrap** (`scripts/update-unified.sh`):
1. Platform detection via `$OSTYPE` (darwin/linux-gnu/msys/cygwin)
2. Check package manager (brew/apt/choco)
3. Install uv if missing (`curl | sh`)
4. Check Python 3.9+
5. Create/verify venv (`uv venv`)
6. Install Python deps (`uv pip sync`)
7. Exec into Python for remaining phases

**Python phases**:
1. **Diagnosis** — run all checks, produce structured results
2. **Planning** — categorize as auto-fixable vs manual
3. **Execution** — apply fixes, re-verify, show manual instructions

## Cross-Platform Detection

**Bash level** (`$OSTYPE`):
```bash
if [[ "$OSTYPE" == "darwin"* ]]; then PLATFORM="macOS"; PKG_MANAGER="brew"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then PLATFORM="Ubuntu/WSL"; PKG_MANAGER="apt"
elif [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]]; then PLATFORM="Windows"; PKG_MANAGER="choco"
fi
```

Key difference: venv Python is `bin/python` on unix, `Scripts/python` on Windows. Linux needs `UV_LINK_MODE=copy`.

**Python level** (`platform_utils.py`):
- `platform.system()` for Darwin/Linux/Windows
- `/proc/version` contains `"microsoft"` → WSL
- `MachineIdentifier` uses hostname to look up machine config

## Git Repository Management

Clone logic:
```python
repo_path.parent.mkdir(parents=True, exist_ok=True)
cmd = ["git", "clone", "--branch", branch, url, str(repo_path)]
result = subprocess.run(cmd, capture_output=True, timeout=300)
```

Sync flow: check status → validate branch → push unpushed commits → fetch + pull → run update script.

Results tracked via `RepositoryUpdateResult` dataclass with: name, path, action (cloned/pulled/skipped/failed), branch, commits_pulled, is_clean, error_message.

## Validation Caching

- `.update-metadata/deps.hash` stores config hash (gitignored, local-only)
- Checks themselves are not cached — re-run every time (fast enough: mostly `which()` and path existence)
- The proposal's hash-based validation flag is a tighter version of this pattern

## Error Handling

**Remediation types**: `auto` (system fixes it), `manual` (provides instructions), `both` (auto with manual fallback).

**Structured results**: `CheckResult` carries status, message, structured data, remediation config, severity.

**Modes**: `--dry-run` (preview), `--interactive` (select fixes), `--yes` (non-interactive), `--force` (override safety), `--diagnosis-only` (check only).

## Patterns to Adopt

| Pattern | Application |
|---------|-------------|
| Flat YAML manifest per dependency type | System tool manifest, data dependency manifest |
| `check_command` / `check_path` / `check_command_inline` | Validate presence before install |
| `method: skip` for platform-irrelevant deps | Same manifest works everywhere |
| Clone-if-missing, pull-if-exists | Git repo data dependencies |
| Branch enforcement (never auto-switch) | Pin data deps to branches |
| `update_script` + `update_script_platforms` | Post-clone/pull setup per repo |
| `$OSTYPE` bash detection | Bash hook platform logic |
| Hash-based skip flag | Avoid re-running when manifests unchanged |
| Diagnosis → Planning → Execution phases | Separate checking from fixing in the hook |
| Structured JSON output | Remediation context into `additionalContext` |

## Patterns to Skip

| Pattern | Reason |
|---------|--------|
| Machine identity (`machines.yaml`, hostname lookup) | Plugins must work on unknown machines |
| Host-level config overrides (`host-{hostname}.yaml`) | No per-machine plugin config |
| Package inventory snapshots | Out of scope for plugin bootstrap |
| Sudoers configuration | Plugins shouldn't need sudo |
| Interactive mode | SessionStart hooks run non-interactively |
