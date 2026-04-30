---
_schema_version: 1
name: ue-python-api
skill-type: capability-skill
description: Use when reading, writing, or extracting Unreal Editor data via Python. Do NOT use for blueprint edits or non-Python Editor work.
---

# Unreal Engine Python API

Wraps Unreal Engine's public Python scripting interface so a Claude agent can read, write, and extract Editor data via Python scripts that work with or without the Editor open.

> **This is a generic, public MIT-licensed plugin.** All patterns, examples, and documentation must be engine-generic. Do not add project-specific asset paths, class names, workflows, or code patterns.

The fenced YAML block below is the load-bearing contract: external_capability declaration, layering manifest, capability surface, gotchas, and references index. Markdown sections after the YAML carry orientation prose, code recipes, and the essential-classes table -- consult them after the YAML.

```yaml
capability_skill:
  _schema_version: "1"
  identity: Unreal Engine Python API automation for reading, writing, and extracting Unreal Editor data via Python scripts that work with or without the Editor open.
  scope:
    covers:
      - asset inspection, reference graph traversal, property reading and writing
      - scripts that work with the Editor open or closed (commandlet)
      - host-side venv management and UE-side dependency setup via unreal-pip
      - searching the bundled stubs/unreal.py API surface
    excludes:
      - blueprint edits requiring graph manipulation (use a blueprint-details skill)
      - non-Python Editor UI work
      - project-specific asset paths or class names (this plugin must stay engine-generic)
  external_capability:
    kind: framework
    name: Unreal Engine Python API
    description: Unreal Engine's public Python scripting interface for asset inspection, property reading and writing, reference-graph traversal, batch operations via EditorAssetLibrary and AssetRegistryHelpers, and animation/datatable/level queries. Includes the ue_runner.py host-side runner that auto-detects whether the Editor is open and chooses remote (UDP multicast via upyrc) or commandlet (headless) execution.
  layering:
    claude_md: []
    skill_md:
      - orientation prose -- what the skill is and how scripts get run
      - vocabulary glossary -- ue_runner, commandlet mode, remote mode, stubs, unreal-pip, upyrc
      - capability surface -- run_script, search_stubs
      - capability-skill-level gotchas -- provider quirks that fire regardless of capability
      - essential-classes table and Core Patterns code recipes
    references:
      - architecture.md -- runner architecture and execution-mode selection
      - bootstrapped-setup.md -- first-run setup, ini, venv, troubleshooting
      - asset-inspection.md -- asset inspection patterns
      - reference-graph.md -- dependency-chain and full-graph walks
      - animation-patterns.md -- AnimSequence/AnimMontage/AnimBlueprint/emote patterns
      - script-execution.md -- execution-mode-specific patterns
      - project-setup.md -- project-side setup and config keys
      - unreal-pip.md -- UE-side dependency manager
      - upyrc.md -- remote-execution wire protocol
      - script-bootstrap.md -- ensure_dependencies internals
  capabilities:
    - id: run_script
      keywords: [run script, execute, commandlet, remote, ue_runner, run python, send to editor]
      user_objective: Execute a Python script against the Unreal Editor, with the Editor either open (remote mode) or closed (commandlet mode).
      operation: python ${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue_runner.py <script>.py [--copy-output <dir>]
      tool: bin/ue_runner.py
      scope_axes: [editor-open, editor-closed]
      reference_section: architecture.md (execution modes)
      gotchas:
        - Output via unreal.log() is NOT captured by the terminal runner -- write YAML to <Project>/Saved/PythonOutput/ to return results to the agent.
        - Invoke the runner with the plugin venv Python so upyrc is available; system Python misses upyrc and falls back to commandlet-only mode.
    - id: search_stubs
      keywords: [search stubs, find class, find method, API lookup, autocomplete equivalent]
      user_objective: Look up class names, method signatures, or property names in the bundled unreal.py stub file before authoring a script.
      operation: grep -i "<pattern>" ${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/stubs/unreal.py
      tool: grep
      scope_axes: [classes, methods]
      reference_section: architecture.md (stubs)
  gotchas:
    - Always invoke ue_runner.py with the plugin venv Python (~/.claude/plugins/data/plugins-kit/unreal-kit/.venv/) so upyrc is available; system Python misses upyrc and degrades to slower commandlet-only mode.
    - The Editor prefix in class names like EditorAssetLibrary is a UE C++ naming convention -- it does NOT mean those classes need the Editor running. They work in commandlet mode. Exception EditorUtilityLibrary, which queries the user's active selection and does require a running Editor.
    - Output via unreal.log() is NOT captured by the terminal runner. To get results back, write YAML to <Project>/Saved/PythonOutput/ -- the runner auto-detects these.
    - Never add project-specific asset paths, class names, workflows, or code patterns. This plugin is engine-generic and MIT-licensed; project-specific content goes in a project-side skill.
  references:
    - id: architecture
      path: references/architecture.md
      keywords: [required plugins, execution modes, remote vs commandlet, stubs, how it works, runner architecture]
      summary: How the runner picks execution modes; what each mode supports.
    - id: bootstrapped_setup
      path: references/bootstrapped-setup.md
      keywords: [setup, config, ini settings, venv, host deps, stubs, troubleshooting, first-run]
      summary: First-run setup, ini settings, venv, host-side dependencies, common troubleshooting.
    - id: asset_inspection
      path: references/asset-inspection.md
      keywords: [struct properties, nested objects, class hierarchy, blueprint inspection, soft references, asset deep dive]
      summary: Asset inspection deep-dive patterns.
    - id: reference_graph
      path: references/reference-graph.md
      keywords: [dependency chain, full graph walk, circular references, asset audit, dependency graph]
      summary: Reference graph traversal patterns.
    - id: animation_patterns
      path: references/animation-patterns.md
      keywords: [AnimSequence, AnimMontage, AnimBlueprint, emote set, skeleton, animation patterns]
      summary: Animation and emote patterns.
    - id: script_execution
      path: references/script-execution.md
      keywords: [startup scripts, commandlet, editor utility widget, slow task progress, batch, execution modes]
      summary: Execution-mode-specific patterns.
    - id: project_setup
      path: references/project-setup.md
      keywords: [project setup, .uproject, engine_dir, config keys, autodetect]
      summary: Project-side setup steps and config.
    - id: unreal_pip
      path: references/unreal-pip.md
      keywords: [unreal-pip, package manager, UE packages, site-packages, pip install, bootstrap pattern]
      summary: UE-side dependency management via unreal-pip.
    - id: upyrc
      path: references/upyrc.md
      keywords: [upyrc, remote execution, UDP multicast, remote control, send script to editor]
      summary: Remote execution wire protocol.
    - id: script_bootstrap
      path: references/script-bootstrap.md
      keywords: [two dependency sets, UE-side packages, host-side venv, stdlib constraint, ensure_dependencies internals, interaction flow]
      summary: How ensure_dependencies bootstraps UE-side packages from inside a script.
  companion:
    skill: unreal-kit-a
    description: Sub-agent companion that pairs with this skill for UE Python automation tasks; auto-loaded for unreal-kit work.
```

## Vocabulary

- **ue_runner.py** -- The host-side runner shipped at `bin/ue_runner.py`. Auto-detects Editor presence; falls back to commandlet when the Editor is closed.
- **commandlet mode** -- Headless UE process that loads the project and runs the script without opening the Editor UI. Asset loading, registry queries, property R/W, reference graph walks, and saves all work in commandlet mode.
- **remote mode** -- Sends the script over UDP multicast to a running Editor's upyrc listener.
- **stubs** -- Searchable API stubs at `stubs/unreal.py` for grep/IDE introspection.
- **unreal-pip** -- UE-side package manager. Bridges PyPI packages into UE's Python via the bootstrap pattern (sys.path injection + ensure_dependencies()).
- **upyrc** -- Host-side library used by ue_runner.py to send scripts over UDP multicast to a running Editor.

## Essential Classes

| Class | Purpose |
|-------|---------|
| `unreal.EditorAssetLibrary` | Load, save, rename, delete, list, find assets |
| `unreal.EditorUtilityLibrary` | Get selected assets/actors in editor (requires running Editor) |
| `unreal.AssetRegistryHelpers` | Fast asset metadata queries, dependency graph |
| `unreal.EditorLevelLibrary` | Actor operations in open levels |
| `unreal.DataTableFunctionLibrary` | Read DataTable row names/data |
| `unreal.AnimationLibrary` | Animation sequence/montage queries |
| `unreal.BlueprintEditorLibrary` | Inspect Blueprint graphs and nodes |

## Core Patterns

> **Output**: write to a YAML file in `<Project>/Saved/PythonOutput/` -- the runner auto-detects these. All patterns below use the YAML output approach.

### Script Template
```python
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/plugins/data/plugins-kit/unreal-kit/lib'))
sys.path.insert(0, os.path.expanduser('~/.claude/plugins/data/plugins-kit/unreal-kit/github/unreal-pip'))
from bootstrap import ensure_dependencies
ensure_dependencies()

import yaml
import unreal

results = {}
# ... collect data ...

out_path = os.path.join(str(unreal.Paths.project_dir()), 'Saved', 'PythonOutput', 'results.yaml')
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w') as f:
    yaml.dump(results, f, default_flow_style=False, sort_keys=False)
```

### Load and Inspect Asset
```python
asset = unreal.EditorAssetLibrary.load_asset('/Game/Path/To/Asset')
results['class'] = asset.get_class().get_name()
results['some_property'] = str(asset.get_editor_property('some_property_name'))
```

### Reference Graph -- Dependencies and Referencers
```python
registry = unreal.AssetRegistryHelpers.get_asset_registry()
dep_options = unreal.AssetRegistryDependencyOptions(
    include_soft_package_references=True,
    include_hard_package_references=True,
    include_searchable_names=False,
    include_soft_management_references=False
)
deps = registry.get_dependencies('/Game/Path/To/Asset', dep_options)
results['dependencies'] = [str(d) for d in deps]
refs = registry.get_referencers('/Game/Path/To/Asset', dep_options)
results['referencers'] = [str(r) for r in refs]
```

### List Assets by Path or Class
```python
assets = unreal.EditorAssetLibrary.list_assets('/Game/Path', recursive=True)
results['assets'] = [str(a) for a in assets]

registry = unreal.AssetRegistryHelpers.get_asset_registry()
ar_filter = unreal.ARFilter(class_names=['DataTable'], package_paths=['/Game'])
found = registry.get_assets(ar_filter)
results['datatables'] = [str(ad.package_name) for ad in found]
```

### Read/Write Properties
```python
asset = unreal.EditorAssetLibrary.load_asset('/Game/Path/To/Asset')
value = asset.get_editor_property('property_name')
asset.set_editor_property('property_name', new_value)
unreal.EditorAssetLibrary.save_loaded_asset(asset)
```

### TMap / TArray Properties
```python
# TMap properties return as dict, TArray as list
map_prop = asset.get_editor_property('some_map_property')
results['map_data'] = {str(k): str(v) for k, v in map_prop.items()}
```

## UE-side Dependencies

To pull packages from PyPI into the UE Python environment, prepend the bootstrap import:

```python
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/plugins/data/plugins-kit/unreal-kit/lib'))
sys.path.insert(0, os.path.expanduser('~/.claude/plugins/data/plugins-kit/unreal-kit/github/unreal-pip'))
from bootstrap import ensure_dependencies
ensure_dependencies()
```

Add packages to `lib/requirements.yaml` (synced to data dir by bootstrap):
```yaml
packages:
  - pyyaml
  - some-new-package
```

`ensure_dependencies()` reads the file, checks what is installed, uses unreal-pip for anything missing. See `references/script-bootstrap.md` for internals; `references/unreal-pip.md` for the unreal-pip API.
