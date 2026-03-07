# Animation and Emote Patterns

## Animation Asset Types

| UE Type | Python Class | Description |
|---------|-------------|-------------|
| AnimSequence | `unreal.AnimSequence` | Single animation clip |
| AnimMontage | `unreal.AnimMontage` | Composite with sections/notifies |
| AnimBlueprint | `unreal.AnimBlueprint` | State machine / blend logic |
| BlendSpace | `unreal.BlendSpace` | Multi-axis animation blend |
| Skeleton | `unreal.Skeleton` | Bone hierarchy definition |

## List All AnimSequences Under a Path

```python
def list_anim_sequences(search_path='/Game/Art/Characters'):
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    ar_filter = unreal.ARFilter(
        class_names=['AnimSequence'],
        package_paths=[search_path],
        recursive_paths=True
    )
    results = registry.get_assets(ar_filter)
    for r in results:
        unreal.log(f"{r.asset_name} @ {r.package_name}")
    unreal.log(f"Total: {len(results)} AnimSequences")
    return results
```

## Inspect AnimSequence Properties

```python
def inspect_anim_sequence(asset_path):
    anim = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not anim or not isinstance(anim, unreal.AnimSequence):
        unreal.log_error(f"Not an AnimSequence: {asset_path}")
        return

    unreal.log(f"=== {asset_path} ===")
    unreal.log(f"Length: {anim.get_editor_property('sequence_length')}s")
    unreal.log(f"Rate: {anim.get_editor_property('rate_scale')}")

    # Skeleton reference
    skeleton = anim.get_editor_property('skeleton')
    if skeleton:
        unreal.log(f"Skeleton: {skeleton.get_path_name()}")

    # Notify tracks (animation events)
    notifies = anim.get_editor_property('notifies')
    if notifies:
        for n in notifies:
            unreal.log(f"  Notify: {n.get_editor_property('notify_name')}")
```

## Inspect AnimMontage Sections

```python
def inspect_montage(asset_path):
    montage = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not montage:
        return

    # Montage sections
    sections = montage.get_editor_property('composite_sections')
    if sections:
        for section in sections:
            name = section.get_editor_property('section_name')
            unreal.log(f"  Section: {name}")

    # Slot tracks
    slot_tracks = montage.get_editor_property('slot_anim_tracks')
    if slot_tracks:
        for track in slot_tracks:
            slot_name = track.get_editor_property('slot_name')
            unreal.log(f"  Slot: {slot_name}")
```

## Inspect AnimBlueprint

```python
def inspect_anim_blueprint(asset_path):
    abp = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not abp:
        return

    unreal.log(f"=== AnimBlueprint: {asset_path} ===")

    # Target skeleton
    skeleton = abp.get_editor_property('target_skeleton')
    if skeleton:
        unreal.log(f"Target Skeleton: {skeleton.get_path_name()}")

    # Parent class
    parent = abp.get_editor_property('parent_class')
    if parent:
        unreal.log(f"Parent Class: {parent.get_name()}")

    # What animations does this ABP reference?
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    opts = unreal.AssetRegistryDependencyOptions(
        include_hard_package_references=True,
        include_soft_package_references=True,
        include_searchable_names=False,
        include_soft_management_references=False
    )
    deps = registry.get_dependencies(asset_path, opts)
    anim_deps = []
    for d in deps:
        d_str = str(d)
        # Check if dependency is an animation asset
        dep_assets = registry.get_assets_by_package_name(d_str)
        for da in dep_assets:
            class_name = str(da.asset_class_path)
            if 'AnimSequence' in class_name or 'AnimMontage' in class_name or 'BlendSpace' in class_name:
                anim_deps.append(d_str)
                unreal.log(f"  Anim dep: {d_str} ({class_name})")
    unreal.log(f"Total animation dependencies: {len(anim_deps)}")
```

## Inspect TMap-Based Animation Sets

Many projects use TMap<FName, UAnimSequence*> or similar for animation/emote sets.
This pattern reads any DataAsset with TMap properties:

```python
def inspect_animation_set(asset_path):
    """Inspect a DataAsset with TMap animation properties."""
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not asset:
        unreal.log_error(f"Failed to load: {asset_path}")
        return

    unreal.log(f"=== {asset.get_class().get_name()}: {asset_path} ===")

    # Iterate all properties looking for maps/arrays of anim references
    for prop_name in sorted(dir(asset)):
        if prop_name.startswith('_'):
            continue
        try:
            val = asset.get_editor_property(prop_name)
            if isinstance(val, dict):
                unreal.log(f"  MAP {prop_name} ({len(val)} entries):")
                for k, v in val.items():
                    anim_path = v.get_path_name() if hasattr(v, 'get_path_name') else str(v)
                    unreal.log(f"    {k} → {anim_path}")
            elif isinstance(val, (list, unreal.Array)):
                unreal.log(f"  ARRAY {prop_name} ({len(val)} entries):")
                for i, item in enumerate(val):
                    unreal.log(f"    [{i}] {item}")
        except Exception:
            pass
```

## Map Skeleton → AnimBlueprints → Animations

```python
import json, os

def map_skeleton_animations(skeleton_path):
    """Starting from a skeleton, find all ABPs and their animation references."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    opts = unreal.AssetRegistryDependencyOptions(
        include_hard_package_references=True,
        include_soft_package_references=True,
        include_searchable_names=False,
        include_soft_management_references=False
    )

    # Find everything referencing this skeleton
    refs = registry.get_referencers(skeleton_path, opts)

    result = {'skeleton': skeleton_path, 'anim_blueprints': {}, 'direct_anims': []}

    for ref in refs:
        ref_str = str(ref)
        ref_assets = registry.get_assets_by_package_name(ref_str)
        for ra in ref_assets:
            class_name = str(ra.asset_class_path)
            if 'AnimBlueprint' in class_name:
                # Found an ABP — now find its animation deps
                abp_deps = registry.get_dependencies(ref_str, opts)
                anim_refs = []
                for dep in abp_deps:
                    dep_assets = registry.get_assets_by_package_name(str(dep))
                    for da in dep_assets:
                        if 'AnimSequence' in str(da.asset_class_path):
                            anim_refs.append(str(dep))
                result['anim_blueprints'][ref_str] = anim_refs
            elif 'AnimSequence' in class_name:
                result['direct_anims'].append(ref_str)

    out = os.path.join(unreal.Paths.project_dir(), 'Saved', 'PythonOutput', 'skeleton_map.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2)
    unreal.log(f"Skeleton map written to {out}")
    return result
```

## Find All Animations for a Character

Useful when a character's animations span multiple directories:

```python
def find_character_animations(character_name, search_paths=None):
    """Find all animations mentioning a character name."""
    if search_paths is None:
        search_paths = ['/Game']

    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    results = []

    for path in search_paths:
        ar_filter = unreal.ARFilter(
            class_names=['AnimSequence', 'AnimMontage'],
            package_paths=[path],
            recursive_paths=True
        )
        assets = registry.get_assets(ar_filter)
        for a in assets:
            if character_name.lower() in str(a.asset_name).lower():
                results.append(str(a.package_name))
                unreal.log(f"  {a.asset_name} @ {a.package_name}")

    unreal.log(f"Found {len(results)} animations for '{character_name}'")
    return results
```
