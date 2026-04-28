---
_schema_version: 1
name: ue-python-api
skill-type: domain-skill
description: Use when reading, writing, or extracting Unreal Editor data via Python. Do NOT use for blueprint edits or non-Python Editor work.
---

# Unreal Engine Python API

Unreal Engine Python API automation is the discipline of reading, writing, and extracting Unreal Editor data via Python scripts that work with or without the Editor open. This domain owns the runner, stubs, patterns, and reference set for that work.

> **This is a generic, public MIT-licensed plugin.** All patterns, examples, and documentation must be engine-generic. Do not add project-specific asset paths, class names, workflows, or code patterns.

```yaml
domain_skill:
  _schema_version: "1"
  identity: Unreal Engine Python API automation for reading, writing, and extracting Unreal Editor data via Python scripts that work with or without the Editor open.
  companions:
    siblings: []
    note: No siblings within plugins-kit.
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
  orientation:
    summary: |
      Write a .py script using the Core Patterns recipes in the markdown body, run it via
      bin/ue_runner.py (which auto-detects whether the Editor is open and picks remote vs.
      commandlet mode), analyze results, iterate. Output goes to YAML in
      <Project>/Saved/PythonOutput/.
    vocabulary:
      - term: ue_runner.py
        definition: The host-side runner shipped at bin/ue_runner.py. Auto-detects Editor presence; falls back to commandlet when the Editor is closed.
      - term: commandlet mode
        definition: Headless UE process that loads the project and runs the script without opening the Editor UI. Asset loading, registry queries, property R/W, reference graph walks, and saves all work in commandlet mode.
      - term: remote mode
        definition: Sends the script over UDP multicast to a running Editor's upyrc listener.
      - term: stubs
        definition: Searchable API stubs at stubs/unreal.py for grep/IDE introspection.
      - term: unreal-pip
        definition: UE-side package manager. Bridges PyPI packages into UE's Python via the bootstrap pattern (sys.path injection + ensure_dependencies()).
      - term: upyrc
        definition: Host-side library used by ue_runner.py to send scripts over UDP multicast to a running Editor.
    behavioral_guardrails:
      - Always invoke ue_runner.py with the plugin venv Python (~/.claude/plugins/data/plugins-kit/unreal-kit/.venv/) so upyrc is available; system Python misses upyrc and degrades to slower commandlet-only mode.
      - The Editor prefix in class names like EditorAssetLibrary is a UE C++ naming convention -- it does NOT mean those classes need the Editor running. They work in commandlet mode. Exception EditorUtilityLibrary, which queries the user's active selection and does require a running Editor.
      - Output via unreal.log() is NOT captured by the terminal runner. To get results back, write YAML to <Project>/Saved/PythonOutput/ -- the runner auto-detects these.
      - Never add project-specific asset paths, class names, workflows, or code patterns. This plugin is engine-generic and MIT-licensed; project-specific content goes in a project-side skill.
  index:
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
  capabilities:
    - id: run_script
      keywords: [run script, execute, commandlet, remote, ue_runner, run python, send to editor]
      description: Run a Python script against the Unreal Editor (open or closed); auto-detects mode.
      operation: python ${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue_runner.py <script>.py [--copy-output <dir>]
      tool: bin/ue_runner.py
      scope_axes: [editor-open, editor-closed]
      reference_section: architecture.md (execution modes)
    - id: search_stubs
      keywords: [search stubs, find class, find method, API lookup, autocomplete equivalent]
      description: Search the bundled stubs/unreal.py for class names or method signatures.
      operation: grep -i "<pattern>" ${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/stubs/unreal.py
      tool: grep
      scope_axes: [classes, methods]
      reference_section: architecture.md (stubs)
  tools:
    - name: ue_runner
      command: bin/ue_runner.py
      description: Auto-detecting runner for Editor or commandlet execution.
  agent_binding:
    agent_name: unreal-kit-a
    auto_load: true
```

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
