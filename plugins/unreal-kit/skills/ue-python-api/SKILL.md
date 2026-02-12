---
_schema_version: 1
name: ue-python-api
description: Write and understand Unreal Engine Python editor scripts for asset inspection, reference graph traversal, and data extraction
---

# Unreal Engine Python API

## Purpose

Write Python scripts for UE Editor automation: asset inspection, reference graph traversal,
property reading, and data extraction. Claude writes scripts; user runs them in UE Editor
and shares output for analysis.

## Workflow

1. Claude writes a `.py` script using patterns below
2. User runs it in UE Editor (Output Log → Python, or `py "C:/path/to/script.py"`)
3. User shares the printed output back to Claude
4. Claude analyzes results and writes follow-up scripts as needed

## Key Facts

- **Editor-only**: UE Python is for Editor automation, NOT runtime gameplay
- **Module**: `import unreal` — mirrors C++/Blueprint API
- **Required plugins**: "Python Editor Script Plugin" + "Editor Scripting Utilities"
- **Stubs**: `<Project>/Intermediate/PythonStub/unreal.py` (enable Developer Mode in Editor Preferences → Plugins → Python)
- **Local stubs**: Run `scripts/setup-stubs.py` to download searchable API stubs to `stubs/`
- **Dependencies**: Managed via unreal-pip. See [Dependencies](#dependencies) below

## Running Scripts

### Terminal Runner (recommended)

Run UE Python scripts from the terminal — auto-detects whether UE Editor is running:

| Editor running? | Method | Speed |
|-----------------|--------|-------|
| Yes | Remote execution via `upyrc` (UDP multicast) | ~seconds |
| No | Headless commandlet (`UnrealEditor-Cmd.exe`) | ~30-120s |

```bash
# Windows — use the .cmd wrapper (handles Python + deps via uv):
# ${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api = plugin install path + /skills/ue-python-api
${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue-runner.cmd script.py
${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue-runner.cmd script.py --mode remote
${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue-runner.cmd script.py --mode commandlet
${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue-runner.cmd script.py --copy-output ./results/

# Or with Python directly (if python + deps are on PATH):
python ${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue_runner.py script.py
```

**Setup:**
```bash
${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/bin/ue-runner.cmd --setup
```
Discovers your UE project, configures paths, and enables remote execution (prompts before each change).

**Output detection:** Scripts that write YAML to `<Project>/Saved/PythonOutput/` will have their
output automatically detected and reported. Use `--copy-output` to pull results to a local directory.

### Manual methods

```
# Output Log (switch dropdown to Python)
py "C:/path/to/script.py"

# Startup scripts (auto-run on editor load)
# Place .py files in <Project>/Content/Python/

# Commandline (headless)
UnrealEditor-Cmd.exe project.uproject -ExecutePythonScript="C:/path/to/script.py"
```

## Essential Classes

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

### Load and Inspect Asset
```python
import unreal

asset = unreal.EditorAssetLibrary.load_asset('/Game/Path/To/Asset')
unreal.log(f"Class: {asset.get_class().get_name()}")
# List all readable properties
for prop in dir(asset):
    if not prop.startswith('_'):
        try:
            val = asset.get_editor_property(prop)
            unreal.log(f"  {prop} = {val}")
        except:
            pass
```

### Reference Graph — What Does This Asset Depend On?
```python
registry = unreal.AssetRegistryHelpers.get_asset_registry()
deps = registry.get_dependencies(
    '/Game/Path/To/Asset',
    unreal.AssetRegistryDependencyOptions(
        include_soft_package_references=True,
        include_hard_package_references=True,
        include_searchable_names=False,
        include_soft_management_references=False
    ))
for d in deps:
    unreal.log(f"Depends on: {d}")
```

### Reference Graph — What References This Asset?
```python
registry = unreal.AssetRegistryHelpers.get_asset_registry()
refs = registry.get_referencers(
    '/Game/Path/To/Asset',
    unreal.AssetRegistryDependencyOptions(
        include_soft_package_references=True,
        include_hard_package_references=True,
        include_searchable_names=False,
        include_soft_management_references=False
    ))
for r in refs:
    unreal.log(f"Referenced by: {r}")
```

### List Assets by Path or Class
```python
# All assets under a path
assets = unreal.EditorAssetLibrary.list_assets('/Game/Content/Path', recursive=True)

# Filter by class using asset registry
registry = unreal.AssetRegistryHelpers.get_asset_registry()
ar_filter = unreal.ARFilter(class_names=['DataTable'], package_paths=['/Game/Data'])
found = registry.get_assets(ar_filter)
for asset_data in found:
    unreal.log(f"{asset_data.asset_name} at {asset_data.package_name}")
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
emote_map = asset.get_editor_property('emote_map')
for key, value in emote_map.items():
    unreal.log(f"  {key}: {value}")
```

### Output to File (YAML)
```python
import sys, os
# ${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api resolves to the plugin's ue-python-api skill directory
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/lib')
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
unreal.log(f"Wrote results to {out_path}")
```

## Dependencies

Two separate dependency sets — one for scripts running inside UE, one for the terminal runner:

### UE-side dependencies (`requirements.yaml`)

Managed via **unreal-pip**, installed into UE's embedded Python. Scripts use a bootstrap pattern:

```python
import sys
# ${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api resolves to the plugin's ue-python-api skill directory
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/lib')
from bootstrap import ensure_dependencies
ensure_dependencies()
```

Add packages to `requirements.yaml`:
```yaml
packages:
  - pyyaml
  - some-new-package
```

`ensure_dependencies()` reads the file, checks what's installed, uses unreal-pip for anything missing.
For internals, see `references/third-party-tools.md`.

### Host-side dependencies (`host-requirements.txt`)

For the terminal runner (`ue_runner.py`), installed into your system Python:

```bash
pip install -r ${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/host-requirements.txt
```

Contains: `upyrc` (remote execution), `pyyaml` (config loading).

## Conditional Loading

Read these references when you need deeper patterns:

- **Asset inspection deep dive** → `references/asset-inspection.md`
  Keywords: struct properties, nested objects, class hierarchy, Blueprint inspection, soft references
- **Reference graph traversal** → `references/reference-graph.md`
  Keywords: dependency chain, full graph walk, circular references, asset audit
- **Animation and emote patterns** → `references/animation-patterns.md`
  Keywords: AnimSequence, AnimMontage, AnimBlueprint, NPCEmoteSet, skeleton
- **Script execution modes** → `references/script-execution.md`
  Keywords: startup scripts, commandlet, editor utility widget, slow task progress, batch
- **Third-party tools** → `references/third-party-tools.md`
  Keywords: unreal-pip, upyrc, remote control, package management, external scripting

## Searching Stubs

After running `scripts/setup-stubs.py`, search the stubs file for API methods:
```
# Find methods related to "dependency"
grep -i "def.*depend" stubs/unreal.py
# Find a specific class
grep -i "class EditorAssetLibrary" stubs/unreal.py
```
