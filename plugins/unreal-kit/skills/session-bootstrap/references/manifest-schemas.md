# Manifest Schemas

Schema reference for the two custom manifests used by the session bootstrap hook. The third manifest (`pyproject.toml`) uses the standard PEP 621 format and is not documented here.

## System Tool Manifest (`system-tools.yaml`)

Declares per-OS CLI tool dependencies. The hook processes entries sequentially and fails on the first missing tool.

### Schema

```yaml
system_tools:
  macos:                             # OS key: macos | windows | ubuntu
    - name: <string>                 # Human-readable name (for error messages)
      check: <string>               # Argument to `command -v` (or path for persistent_path)
      check_type: <string>          # Optional: "command" (default) or "persistent_path"
      install: <string>             # Exact shell command to install
  windows:
    - name: <string>
      check: <string>
      check_type: <string>
      install: <string>
  ubuntu:
    - name: <string>
      check: <string>
      check_type: <string>
      install: <string>
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `system_tools` | mapping | Yes | Top-level key |
| `macos` / `windows` / `ubuntu` | list | At least one | OS section containing tool entries |
| `name` | string | Yes | Human-readable tool name for error messages |
| `check` | string | Yes | For `command` type: argument to `command -v`. For `persistent_path`: directory path to verify in PATH config |
| `check_type` | string | No | Check method: `command` (default, uses `command -v`) or `persistent_path` (verifies directory in persistent PATH config) |
| `install` | string | Yes | Exact shell command to install the tool or configure the path |

### Rules

- **Top-level key**: `system_tools` (exactly one)
- **OS keys**: `macos`, `windows`, `ubuntu` — maps from `$OSTYPE`: `darwin*` -> macos, `linux-gnu*` -> ubuntu, `msys*`/`cygwin*` -> windows
- **Each OS section**: Ordered list of tool entries. Only the section for the detected OS is read
- **Each entry**: 3 required fields (`name`, `check`, `install`) + 1 optional field (`check_type`, defaults to `command`)
- **No defaults**: Each OS section is self-contained. No inheritance between OS sections
- **Order is the dependency chain**: If tool B installs via tool A (e.g., jq installs via brew), tool A must appear earlier in the list. The manifest author discovers missing chain links by running the hook and fixing errors
- **Omission = not needed**: If a tool isn't needed on an OS, don't list it in that OS section

### Excluded from v1

These features are intentionally deferred:

| Feature | Reason |
|---------|--------|
| `version` / `version_check` | Version validation adds complexity; presence check is sufficient for v1 |
| `required: true/false` | Everything declared is required — if optional, don't list it |
| `method: skip` | Omit the tool from the OS section instead |
| `check_path` / `check_command_inline` | Superseded by `check_type` field |
| Platform inheritance | Explicit duplication is clearer than implicit inheritance |

### Check Types

#### `command` (default)

Verifies a tool is available via `command -v <check>`. Used for CLI tools like `uv`, `git`, `jq`.

#### `persistent_path`

Verifies a directory is configured in the user's persistent PATH. Used for directories like `~/.local/bin` where tools install to but which may not be in PATH by default.

**Per-OS verification**:

| OS | Where it checks | Install method |
|----|----------------|----------------|
| macOS | `~/.zshrc` or `~/.zprofile` (grep for directory suffix) | Append `export PATH=...` to `~/.zshrc` |
| Windows | Windows user-level PATH via `[Environment]::GetEnvironmentVariable('Path', 'User')` | PowerShell `[Environment]::SetEnvironmentVariable` |
| Ubuntu | `~/.bashrc` or `~/.profile` (grep for directory suffix) | Append `export PATH=...` to `~/.bashrc` |

**Session PATH injection**: When a `persistent_path` check passes, the directory is also added to the current process `$PATH` so that subsequent `command -v` checks (e.g., for `uv` installed in `~/.local/bin`) work within the same bootstrap run.

### Example

```yaml
system_tools:
  macos:
    - name: brew
      check: "brew"
      install: 'bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    - name: uv
      check: "uv"
      install: "curl -LsSf https://astral.sh/uv/install.sh | sh"
    - name: jq
      check: "jq"
      install: "brew install jq"

  windows:
    - name: uv
      check: "uv"
      install: 'powershell.exe -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    - name: jq
      check: "jq"
      install: "choco install jq"

  ubuntu:
    - name: curl
      check: "curl"
      install: "sudo apt install -y curl"
    - name: uv
      check: "uv"
      install: "curl -LsSf https://astral.sh/uv/install.sh | sh"
    - name: jq
      check: "jq"
      install: "sudo apt install -y jq"
```

Note: `brew` appears before `jq` on macOS because `jq` installs via `brew`. On Ubuntu, `curl` appears before `uv` because `uv` installs via `curl`. The manifest author is responsible for declaring the full dependency chain.

---

## Git Dependencies Manifest (`git-dependencies.yaml`)

Declares external git repositories to clone. Not per-OS — git dependencies are platform-independent.

### Schema

```yaml
git_dependencies:
  - url: <string>                    # GitHub HTTPS clone URL
    branch: <string>                 # Branch, tag, or commit to track
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `git_dependencies` | list | Yes | Top-level key; list of repository entries |
| `url` | string | Yes | HTTPS clone URL (e.g., `https://github.com/user/repo.git`) |
| `branch` | string | Yes | Branch name, tag, or commit hash to track |

### Rules

- **Top-level key**: `git_dependencies` (exactly one)
- **Each entry**: Exactly 2 required fields — `url` and `branch`. No optional fields
- **Target directory**: Always `${PLUGIN_ROOT}/github/<repository-name>/` — derived from the URL by extracting the repository name (last path segment, minus `.git` suffix). No custom paths
- **Full project syncs only**: No sparse checkout, no individual files
- **Not per-OS**: Git dependencies are platform-independent
- **No post-clone hooks or build steps**: The bootstrap ensures the raw data is available — nothing more

### Clone/Pull Logic

| State | Action |
|-------|--------|
| Directory missing | `git clone --branch <branch> <url> <target>` |
| Directory exists, correct branch, behind upstream | `git pull` |
| Directory exists, wrong branch | Fail — report expected vs actual branch in remediation |

### Directory Derivation

The target directory is deterministic — derived from the URL, not declared in the manifest:

| URL | Derived directory |
|-----|-------------------|
| `https://github.com/user/ue-python-stubs.git` | `${PLUGIN_ROOT}/github/ue-python-stubs/` |
| `https://github.com/org/lint-config.git` | `${PLUGIN_ROOT}/github/lint-config/` |

`${PLUGIN_ROOT}` is the plugin's install directory (e.g., `plugins/unreal-kit/`). The `github/` subdirectory should be gitignored.

### Example

```yaml
git_dependencies:
  - url: https://github.com/user/ue-python-stubs.git
    branch: main
  - url: https://github.com/EpicGames/UnrealEngine-Python-Examples.git
    branch: main
```

This clones to:
- `${PLUGIN_ROOT}/github/ue-python-stubs/`
- `${PLUGIN_ROOT}/github/UnrealEngine-Python-Examples/`

---

## File Locations

All manifest files live at the plugin root, alongside `.claude-plugin/`:

```
plugins/<plugin-name>/
  .claude-plugin/plugin.json       # Plugin manifest (existing)
  system-tools.yaml                # System tool dependencies
  git-dependencies.yaml            # Git repository dependencies
  pyproject.toml                   # Python package dependencies (PEP 621)
  github/                          # Gitignored — cloned repos land here
```
