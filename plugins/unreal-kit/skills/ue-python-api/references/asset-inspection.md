# Asset Inspection Deep Dive

## Struct Properties

UE structs exposed to Python are accessed via `get_editor_property`. Nested structs chain:

```python
asset = unreal.EditorAssetLibrary.load_asset('/Game/Path/To/Asset')

# Simple property
name = asset.get_editor_property('display_name')

# Nested struct: access outer, then inner
transform = asset.get_editor_property('relative_transform')
location = transform.get_editor_property('translation')  # FVector
unreal.log(f"X={location.x}, Y={location.y}, Z={location.z}")
```

## Discovering Properties

```python
def inspect_asset(asset_path):
    """Print all readable properties of an asset."""
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not asset:
        unreal.log_error(f"Failed to load: {asset_path}")
        return

    cls = asset.get_class()
    unreal.log(f"=== {asset_path} ===")
    unreal.log(f"Class: {cls.get_name()}")
    unreal.log(f"Parent: {cls.get_super_class().get_name() if cls.get_super_class() else 'None'}")

    # get_editor_property works for UPROPERTY fields exposed to editor
    for prop_name in sorted(dir(asset)):
        if prop_name.startswith('_'):
            continue
        try:
            val = asset.get_editor_property(prop_name)
            val_str = str(val)
            if len(val_str) > 200:
                val_str = val_str[:200] + '...'
            unreal.log(f"  {prop_name} = {val_str}")
        except Exception:
            pass  # Not all dir() entries are properties
```

## Class Hierarchy Inspection

```python
def print_class_hierarchy(asset_path):
    """Walk the class hierarchy of an asset."""
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    cls = asset.get_class()
    chain = []
    while cls:
        chain.append(cls.get_name())
        cls = cls.get_super_class()
    unreal.log(" → ".join(chain))
```

## Blueprint Asset Inspection

Blueprint assets need special handling — they are `UBlueprint` wrapping a generated class:

```python
bp = unreal.EditorAssetLibrary.load_asset('/Game/Blueprints/BP_MyActor')
# bp is the UBlueprint object
generated_class = bp.get_editor_property('generated_class')
unreal.log(f"Generated class: {generated_class.get_name()}")

# To get the CDO (Class Default Object) and read defaults:
cdo = unreal.get_default_object(generated_class)
# Now read properties from the CDO
```

## Soft Object References

```python
# Soft references are stored as FSoftObjectPath
soft_ref = asset.get_editor_property('some_soft_reference')
# Resolve to load the actual asset
resolved = soft_ref.resolve_object()
if resolved:
    unreal.log(f"Resolved: {resolved.get_name()}")
else:
    # May need to load it
    resolved = unreal.EditorAssetLibrary.load_asset(str(soft_ref))
```

## Enumerating Subobjects

Some assets contain nested UObjects (components, sub-assets):

```python
import unreal

def list_subobjects(asset_path):
    """List immediate subobjects of an asset."""
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    # For actors in a level, get components:
    if hasattr(asset, 'get_components_by_class'):
        components = asset.get_components_by_class(unreal.ActorComponent)
        for comp in components:
            unreal.log(f"  Component: {comp.get_name()} ({comp.get_class().get_name()})")
```

## Asset Metadata (Fast — No Full Load)

```python
registry = unreal.AssetRegistryHelpers.get_asset_registry()
ar_filter = unreal.ARFilter(package_paths=['/Game/Data'])
assets = registry.get_assets(ar_filter)

for asset_data in assets:
    unreal.log(f"Name: {asset_data.asset_name}")
    unreal.log(f"Class: {asset_data.asset_class_path}")
    unreal.log(f"Package: {asset_data.package_name}")
    # Tags are key-value metadata set in asset editors
    # Access via asset_data.get_tag_value('TagName')
```

## Exporting Asset Data as JSON

```python
import json, os

def export_asset_properties(asset_path, output_dir=None):
    """Export all readable properties to JSON."""
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not asset:
        return

    data = {'path': asset_path, 'class': asset.get_class().get_name(), 'properties': {}}

    for prop_name in sorted(dir(asset)):
        if prop_name.startswith('_'):
            continue
        try:
            val = asset.get_editor_property(prop_name)
            # Convert UE types to JSON-serializable
            data['properties'][prop_name] = str(val)
        except Exception:
            pass

    if output_dir is None:
        output_dir = os.path.join(unreal.Paths.project_dir(), 'Saved', 'PythonOutput')
    os.makedirs(output_dir, exist_ok=True)

    safe_name = asset_path.replace('/', '_').strip('_') + '.json'
    out_path = os.path.join(output_dir, safe_name)
    with open(out_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    unreal.log(f"Exported to {out_path}")
```
