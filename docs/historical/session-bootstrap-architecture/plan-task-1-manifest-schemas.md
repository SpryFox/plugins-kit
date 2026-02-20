# Plan: Task #1 — Design Manifest Schemas

## Goal

Define the YAML schemas for the two new manifests: **system tool manifest** and **data dependency manifest**. pyproject.toml uses its standard format and needs no custom schema.

## File Locations

All three manifests live at the plugin root (`plugins/unreal-kit/`), alongside `.claude-plugin/`:

```
plugins/unreal-kit/
  .claude-plugin/plugin.json     # existing
  system-tools.yaml              # NEW — system tool manifest
  data-dependencies.yaml         # NEW — data dependency manifest
  pyproject.toml                 # NEW — Python packages (standard format)
```

**Rationale**: These are plugin-level concerns (not skill-level), and co-locating them with the plugin manifest makes them discoverable. The SessionStart hook reads from the plugin root.

## System Tool Manifest Schema (`system-tools.yaml`)

```yaml
# Per-OS system tool dependencies.
# Processed sequentially — order is the dependency chain.
# Fail-fast: first missing tool stops the hook.
system_tools:
  macos:                         # OS key: macos | windows | ubuntu
    - name: <string>             # Human-readable name (for error messages)
      check: <string>            # Argument to `command -v` (required)
      install: <string>          # Exact shell command to install (required)
  windows:
    - ...
  ubuntu:
    - ...
```

**Schema rules**:
- Top-level key: `system_tools`
- Second-level keys: OS identifiers — `macos`, `windows`, `ubuntu`
- Each OS contains an ordered list of tool entries
- Each entry has exactly 3 fields: `name`, `check`, `install`
- No defaults, no inheritance between OS sections
- Order matters: if tool B installs via tool A, tool A must appear first
- OS detection maps: `darwin*` → `macos`, `linux-gnu*` → `ubuntu`, `msys*`/`cygwin*` → `windows`

**Intentionally excluded** (keep it simple for v1):
- `version` / `version_check` — defer version validation
- `required: true/false` — everything declared is required
- `method: skip` — if a tool isn't needed on an OS, don't list it
- `check_path` / `check_command_inline` — `command -v` covers the common case

## Data Dependency Manifest Schema (`data-dependencies.yaml`)

```yaml
# External data: git repos and file downloads.
# Processed after system tools and .venv are ready.
data_dependencies:
  repositories:
    - name: <string>             # Human-readable name
      url: <string>              # Git clone URL (HTTPS or SSH)
      path: <string>             # Target path (supports ${PLUGIN_DATA})
      branch: <string>           # Branch, tag, or commit to track
  files:
    - name: <string>             # Human-readable name
      url: <string>              # Direct download URL
      path: <string>             # Target file path (supports ${PLUGIN_DATA})
      sha256: <string>           # Optional integrity hash
```

**Schema rules**:
- Top-level key: `data_dependencies`
- Two sections: `repositories` (list) and `files` (list), both optional
- `${PLUGIN_DATA}` expands to `~/.claude/plugins/data/<plugin-name>/`
- Repos: clone-if-missing, pull-if-stale, fail on wrong branch
- Files: download-if-missing, re-download if sha256 doesn't match
- No per-OS sections — data dependencies are platform-independent
- No post-fetch hooks or build steps

## Deliverables

1. Document the two schemas above in `docs/reference/manifest-schemas.md` — the canonical schema reference
2. Update the proposal's Appendix C to reference the schema doc (avoid duplication)

## Not in Scope

- Creating the actual manifest files for unreal-kit (that's Task #2)
- pyproject.toml schema (it's a standard)
- Hook implementation (Tasks #3-7)
