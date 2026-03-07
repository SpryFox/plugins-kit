# Add Claude-driven bootstrap setup pattern

---
priority: P1
agent_hint: backend-developer
status: archived
---

## Objective

Enhance the plugins-kit bootstrap system to support interactive config setup. When a plugin needs configuration (API keys, user preferences, connection strings), the bootstrap detects the missing config and emits context that guides Claude through asking the user questions and calling a setup script with the answers. This gives every plugin a consistent, guided first-run experience.

## Problem

The current bootstrap handles environment readiness (system tools, venv, git deps) but has no concept of **plugin configuration**. Plugins that need user-specific config (credentials, preferences, paths) have no standard way to:

1. Detect that config is missing or incomplete
2. Describe what config is needed (in a way Claude can act on)
3. Accept config values and write them to the plugin's data directory
4. Provide a CLI fallback for headless / non-Claude environments

Each plugin would have to invent its own setup mechanism. This pattern standardizes it.

## Design

### New Bootstrap Step: Config Setup Check

After the existing 4-step bootstrap (tools, venv, git deps, cache validation), add Step 5:

```
SessionStart hook
  |
  Steps 1-4: existing bootstrap (unchanged)
  |
  Step 5: Config setup check
    |-- setup script not present --> skip (plugin has no config needs)
    |-- setup script --check exits 0 --> configured, silent pass
    |-- setup script --check exits 1 --> emit "needs-setup" in additionalContext
        |
        Claude reads additionalContext, invokes the plugin's setup skill
        |
        Skill calls --describe to learn what fields are needed
        |
        Claude asks the user for each value
        |
        Claude calls --apply with gathered values
        |
        Config files written to ~/.claude/plugins/data/{plugin-name}/
```

### Setup Script Interface Contract

Each plugin that needs config provides a setup script with a standard CLI interface:

```bash
# Check if setup is complete (exit 0 = configured, exit 1 = needs setup)
# Stdout: JSON describing what's missing (for additionalContext)
python3 <PLUGIN_ROOT>/scripts/setup.py --check --data-dir <path>

# Describe required config fields (machine-readable for Claude)
# Stdout: YAML describing each field (name, type, description, required, default)
python3 <PLUGIN_ROOT>/scripts/setup.py --describe --data-dir <path>

# Apply config values
python3 <PLUGIN_ROOT>/scripts/setup.py --apply --data-dir <path> \
    --set KEY=VALUE [--set KEY=VALUE ...]

# Copy default files from source (e.g., templates from a git dependency)
python3 <PLUGIN_ROOT>/scripts/setup.py --init-defaults --data-dir <path> \
    --source <path-to-defaults>
```

**Exit codes**: 0 = success, 1 = needs setup / validation failure, 2 = error.

**--describe output format** (YAML, consumed by the setup skill):

```yaml
fields:
  - name: API_KEY
    type: secret
    description: "API key for the LLM provider"
    required: true
  - name: USERNAME
    type: string
    description: "Your display name"
    required: false
    default: "User"
config_files:
  - name: config.yaml
    description: "Plugin configuration"
    init_from: defaults/config.yaml  # optional: copy from source
```

### Setup Skill Pattern

A plugin provides a setup skill that:

1. Is referenced in the bootstrap's "needs-setup" additionalContext
2. Calls `--describe` to learn what's needed
3. Guides Claude through asking the user for each field (respecting types — secrets get masked, booleans become yes/no, etc.)
4. Calls `--apply` with the gathered values
5. Optionally calls `--init-defaults` to copy template files
6. Confirms success to the user

### Bootstrap Hook Enhancement

In `session-bootstrap.sh`, after Step 4 (validate-cache):

```bash
# Step 5: Config setup check
run_config_check() {
    local setup_script="${PLUGIN_ROOT}/scripts/setup.py"
    [[ ! -f "$setup_script" ]] && return 0

    local data_dir="${PLUGINS_DATA_DIR}/${PLUGIN_NAME}"
    mkdir -p "$data_dir"

    local check_output
    check_output=$("$VENV_PYTHON" "$setup_script" --check --data-dir "$data_dir" 2>&1)
    local rc=$?

    if [[ $rc -eq 0 ]]; then
        return 0  # Configured
    fi

    # Emit needs-setup context
    local context="Plugin requires configuration. Run the plugin's setup skill to configure."
    context="$context\n\nMissing config:\n$check_output"
    emit_hook_response "needs-setup" "$context"
}
```

### CLI Fallback

The same setup script works outside Claude Code. A wrapper script or the plugin's own CLI can call `--describe` to print prompts, read stdin, and call `--apply`. This ensures plugins are configurable in headless/CI environments without Claude.

## Test Plugin

Create `plugins/test-plugin/` to develop and validate the full pattern. It should exercise **all** bootstrap patterns (not just the new one):

### What test-plugin exercises

| Bootstrap step | What test-plugin declares |
|---------------|--------------------------|
| System tools | One command-check entry (e.g., `git`) in `system-tools.yaml` |
| Venv | A `pyproject.toml` with one dependency (e.g., `pyyaml`) |
| Git deps | One repo in `git-dependencies.yaml` (can be a small public repo) |
| Cache validation | Standard hash-based validation (inherited from bootstrap) |
| **Config setup (new)** | Setup script requiring `GREETING_NAME` and `FAVORITE_COLOR` |

### Test plugin structure

```
plugins/test-plugin/
  .claude-plugin/plugin.json
  pyproject.toml                    # one dep: pyyaml
  bootstrap-config.yaml             # silent_when_valid: false (for testing)
  system-tools.yaml                 # one tool: git
  git-dependencies.yaml             # one small repo
  scripts/
    setup.py                        # --check, --describe, --apply
  defaults/
    config.yaml                     # template config with placeholder values
  hooks/
    hooks.json
    sessionstart/
      session-bootstrap.sh          # standard 4-step + new step 5
      check-system-tools.sh
      create-venv.sh
      fetch-git-deps.sh
      validate-cache.sh
      check-config.sh               # new: calls setup.py --check
      lib/
        bootstrap-helpers.sh
    stop/
      bootstrap-check.py
  skills/
    test-setup/
      SKILL.md                      # setup skill: guides config collection
    test-greeting/
      SKILL.md                      # uses config: reads GREETING_NAME, outputs greeting
```

### Test plugin config fields

```yaml
fields:
  - name: GREETING_NAME
    type: string
    description: "Name to use in greetings"
    required: true
    default: "World"
  - name: FAVORITE_COLOR
    type: string
    description: "Your favorite color"
    required: false
    default: "blue"
```

### End-to-end test flow

1. Install test-plugin (fresh, no data dir)
2. SessionStart fires → Steps 1-4 pass → Step 5 detects missing config
3. additionalContext says "Plugin requires configuration. Invoke test-setup skill."
4. Claude invokes test-setup skill → calls `--describe` → asks user for GREETING_NAME and FAVORITE_COLOR
5. Claude calls `--apply --set GREETING_NAME=Alice --set FAVORITE_COLOR=green`
6. Setup script writes `~/.claude/plugins/data/test-plugin/config.yaml`
7. Next SessionStart → Step 5 passes silently
8. User invokes test-greeting skill → reads config → "Hello, Alice! Your favorite color is green."

## Approach

- [ ] Define the setup script interface contract (--check, --describe, --apply, --init-defaults)
- [ ] Create test-plugin directory structure with all bootstrap manifests
- [ ] Implement test-plugin setup script (scripts/setup.py)
- [ ] Implement test-plugin default config template (defaults/config.yaml)
- [ ] Add Step 5 (check-config.sh) to the bootstrap orchestrator
- [ ] Update bootstrap-helpers.sh with config setup helper functions
- [ ] Create test-setup skill (guides Claude through config collection)
- [ ] Create test-greeting skill (consumes config to demonstrate usage)
- [ ] Register test-plugin in marketplace.json
- [ ] Test full flow: fresh install → bootstrap → setup → usage
- [ ] Document the Claude-driven setup pattern in docs/

## Success Criteria

- [ ] test-plugin exercises all 5 bootstrap steps (tools, venv, git deps, cache, config setup)
- [ ] SessionStart detects missing config and emits needs-setup context
- [ ] Setup skill guides Claude through collecting config values from the user
- [ ] Setup script writes config to `~/.claude/plugins/data/test-plugin/`
- [ ] Subsequent sessions detect valid config and pass silently
- [ ] test-greeting skill reads and uses the config values
- [ ] Existing plugins (unreal-kit, cache-kit) are unaffected
- [ ] Pattern is documented for other plugins to adopt
- [ ] Setup script works standalone (CLI fallback without Claude)
