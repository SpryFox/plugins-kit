---
_schema_version: 1
name: ue-python-api
description: Enables reading, writing, and understanding unreal data and communicating with the unreal editor by reading/writing/creating/executing python scripts that use the unreal python api
---

# Unreal Engine Python API

## Purpose

Write and run Python scripts for UE Editor automation: asset inspection, reference graph traversal,
property reading, and data extraction. Scripts work with or without the Editor open.

> **This is a generic, public MIT-licensed plugin.** All patterns, examples, and documentation must be engine-generic. Do not add project-specific asset paths, class names, workflows, or code patterns.

## Workflow

1. Write a `.py` script using patterns below
2. Run it via the terminal runner (see [Running Scripts](#running-scripts))
3. Analyze results and write follow-up scripts as needed

## Key Facts

- **Module**: `import unreal` to access UE classes and functions (e.g. `UEditorAssetLibrary` in C++ becomes `unreal.EditorAssetLibrary` in Python)
- **Stubs**: Searchable API stubs at `stubs/unreal.py`
- **UE-side dependencies**: Managed via unreal-pip. See [Dependencies](#dependencies) below

## Running Scripts

**Important:** Always use the plugin's venv Python to run `ue_runner.py`. This venv has `upyrc` pre-installed for fast remote execution to a running Editor. Using system Python causes `upyrc` to be missing, degrading to slower commandlet-only mode.

```bash
# Windows
~/.claude/plugins/data/plugins-kit/unreal-kit/.venv/Scripts/python.exe ${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue_runner.py script.py

# macOS / Linux
~/.claude/plugins/data/plugins-kit/unreal-kit/.venv/bin/python3 ${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue_runner.py script.py

# With output copy
~/.claude/plugins/data/plugins-kit/unreal-kit/.venv/Scripts/python.exe ${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue_runner.py script.py --copy-output ./results/
```

The runner auto-detects whether the Editor is open and picks the best execution method.

> **Editor is NOT required.** When the Editor is closed, the runner launches a headless commandlet that starts a UE process, loads the project, and runs the script. Asset loading, registry queries, property reading/writing, reference graph traversal, and saving all work in commandlet mode. The only operations that require an open Editor are those needing a live UI context: getting the user's current selection, manipulating actors in an open level viewport, showing progress dialogs, and PIE (Play in Editor).

**Output detection:** Scripts that write YAML to `<Project>/Saved/PythonOutput/` will have their
output automatically detected and reported. Use `--copy-output` to pull results to a local directory.

## Essential Classes

> **Naming note:** The `Editor` prefix in class names like `EditorAssetLibrary` is a UE C++ naming convention — it does NOT mean these classes require the Editor to be running. They work in commandlet (headless) mode too. The exception is `EditorUtilityLibrary`, which queries the user's active selection and therefore requires a running Editor with a UI.

| Class | Purpose |
|-------|---------|
| `unreal.EditorAssetLibrary` | Load, save, rename, delete, list, find assets |
| `unreal.EditorUtilityLibrary` | Get selected assets/actors in editor |
| `unreal.AssetRegistryHelpers` | Fast asset metadata queries, dependency graph |
| `unreal.EditorLevelLibrary` | Actor operations in open levels |
| `unreal.DataTableFunctionLibrary` | Read DataTable row names/data |
| `unreal.AnimationLibrary` | Animation sequence/montage queries |
| `unreal.BlueprintEditorLibrary` | Inspect Blueprint graphs and nodes |

## Core Patterns

**Output**: `unreal.log()` writes to the Editor's Output Log but is NOT captured by the terminal runner.
To get results back, write to a YAML file in `<Project>/Saved/PythonOutput/` — the runner auto-detects these.
All patterns below use the YAML output approach.

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

# get_editor_property reads UPROPERTY fields by name.
# Use the stubs or UE docs to find property names for a given class.
results['some_property'] = str(asset.get_editor_property('some_property_name'))
```

### Reference Graph — Dependencies and Referencers
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
# All assets under a path
assets = unreal.EditorAssetLibrary.list_assets('/Game/Path', recursive=True)
results['assets'] = [str(a) for a in assets]

# Filter by class using asset registry
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

## Dependencies

### Host-side dependencies (plugin venv)

The runner (`ue_runner.py`) needs `upyrc` and `pyyaml` on the host. These are pre-installed in the plugin venv at `~/.claude/plugins/data/plugins-kit/unreal-kit/.venv/` by the bootstrap system. Always invoke the runner with this venv's Python (see [Running Scripts](#running-scripts)).

### UE-side dependencies (`requirements.yaml`)

Scripts running inside UE may need third-party packages. Use the bootstrap pattern:

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

`ensure_dependencies()` reads the file, checks what's installed, uses unreal-pip for anything missing.
For bootstrapping internals, see `references/script-bootstrap.md`. For the unreal-pip API, see `references/unreal-pip.md`.

## Conditional Loading

Read these references when you need deeper patterns:

- **Architecture** → `references/architecture.md`
  Keywords: required plugins, execution modes, remote vs commandlet, stubs, how it works
- **Bootstrapped setup** → `references/bootstrapped-setup.md`
  Keywords: setup, config, ini settings, venv, host deps, stubs, troubleshooting
- **Asset inspection deep dive** → `references/asset-inspection.md`
  Keywords: struct properties, nested objects, class hierarchy, Blueprint inspection, soft references
- **Reference graph traversal** → `references/reference-graph.md`
  Keywords: dependency chain, full graph walk, circular references, asset audit
- **Animation and emote patterns** → `references/animation-patterns.md`
  Keywords: AnimSequence, AnimMontage, AnimBlueprint, emote set, skeleton
- **Script execution modes** → `references/script-execution.md`
  Keywords: startup scripts, commandlet, editor utility widget, slow task progress, batch
- **unreal-pip** → `references/unreal-pip.md`
  Keywords: unreal-pip, package manager, UE packages, site-packages, pip install, bootstrap pattern
- **upyrc** → `references/upyrc.md`
  Keywords: upyrc, remote execution, UDP multicast, remote control, send script to editor
- **Script bootstrap internals** → `references/script-bootstrap.md`
  Keywords: two dependency sets, UE-side packages, host-side venv, stdlib constraint, ensure_dependencies internals, interaction flow

## Searching Stubs

Search the stubs file for API methods:
```
# Find methods related to "dependency"
grep -i "def.*depend" stubs/unreal.py
# Find a specific class
grep -i "class EditorAssetLibrary" stubs/unreal.py
```
