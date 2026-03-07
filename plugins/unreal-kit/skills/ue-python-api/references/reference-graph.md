# Reference Graph Patterns

## Concepts

- **Dependencies**: Assets that a given asset references (what it needs to load)
- **Referencers**: Assets that reference a given asset (what uses it)
- **Hard refs**: Direct references — loading the parent loads the dependency
- **Soft refs**: Indirect references — resolved at runtime, not auto-loaded
- **Package name**: The `/Game/...` path identifying an asset package

## Dependency Options

Always create options explicitly to control what you're querying:

```python
def make_dep_options(hard=True, soft=True):
    return unreal.AssetRegistryDependencyOptions(
        include_hard_package_references=hard,
        include_soft_package_references=soft,
        include_searchable_names=False,
        include_soft_management_references=False
    )
```

## Walk Full Dependency Tree

```python
import json, os

def walk_dependencies(root_path, max_depth=5):
    """Recursively walk the dependency tree of an asset."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    opts = make_dep_options()

    visited = set()
    tree = {}

    def _walk(path, depth):
        if depth > max_depth or path in visited:
            return
        visited.add(path)
        deps = registry.get_dependencies(path, opts)
        tree[path] = [str(d) for d in deps]
        for d in deps:
            _walk(str(d), depth + 1)

    _walk(root_path, 0)

    out_path = os.path.join(unreal.Paths.project_dir(), 'Saved', 'PythonOutput', 'dep_tree.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(tree, f, indent=2)
    unreal.log(f"Dependency tree ({len(visited)} nodes) written to {out_path}")
    return tree
```

## Walk Full Referencers Tree (Reverse)

```python
def walk_referencers(root_path, max_depth=3):
    """Find everything that references this asset, recursively."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    opts = make_dep_options()

    visited = set()
    tree = {}

    def _walk(path, depth):
        if depth > max_depth or path in visited:
            return
        visited.add(path)
        refs = registry.get_referencers(path, opts)
        tree[path] = [str(r) for r in refs]
        for r in refs:
            _walk(str(r), depth + 1)

    _walk(root_path, 0)

    out_path = os.path.join(unreal.Paths.project_dir(), 'Saved', 'PythonOutput', 'ref_tree.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(tree, f, indent=2)
    unreal.log(f"Referencers tree ({len(visited)} nodes) written to {out_path}")
    return tree
```

## Find All Assets of a Class and Their Dependencies

```python
def map_class_dependencies(class_name, search_path='/Game'):
    """For every asset of a given class, list its dependencies."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    opts = make_dep_options()

    ar_filter = unreal.ARFilter(
        class_names=[class_name],
        package_paths=[search_path],
        recursive_paths=True
    )
    assets = registry.get_assets(ar_filter)

    result = {}
    for asset_data in assets:
        pkg = str(asset_data.package_name)
        deps = registry.get_dependencies(pkg, opts)
        result[pkg] = [str(d) for d in deps]
        unreal.log(f"{pkg}: {len(deps)} dependencies")

    return result
```

## Cross-Reference Two Asset Sets

```python
def find_connections(set_a_paths, set_b_paths):
    """Find which assets in set A reference assets in set B and vice versa."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    opts = make_dep_options()
    set_b = set(set_b_paths)

    connections = []
    for path_a in set_a_paths:
        deps = registry.get_dependencies(path_a, opts)
        for d in deps:
            if str(d) in set_b:
                connections.append({'from': path_a, 'to': str(d), 'direction': 'A_depends_on_B'})
        refs = registry.get_referencers(path_a, opts)
        for r in refs:
            if str(r) in set_b:
                connections.append({'from': str(r), 'to': path_a, 'direction': 'B_depends_on_A'})

    for c in connections:
        unreal.log(f"{c['from']} → {c['to']} ({c['direction']})")
    return connections
```

## Detect Circular References

```python
def find_circular_deps(root_path, max_depth=10):
    """Detect circular dependency chains starting from root."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    opts = make_dep_options()
    cycles = []

    def _walk(path, chain):
        if len(chain) > max_depth:
            return
        deps = registry.get_dependencies(path, opts)
        for d in deps:
            d_str = str(d)
            if d_str in chain:
                cycle = chain[chain.index(d_str):] + [d_str]
                cycles.append(cycle)
                continue
            _walk(d_str, chain + [d_str])

    _walk(root_path, [root_path])
    for cycle in cycles:
        unreal.log(f"CYCLE: {' → '.join(cycle)}")
    return cycles
```

## Practical: Audit Unused Assets

```python
def find_unreferenced_assets(search_path='/Game/Content'):
    """Find assets that nothing references (potential orphans)."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    opts = make_dep_options()

    ar_filter = unreal.ARFilter(package_paths=[search_path], recursive_paths=True)
    all_assets = registry.get_assets(ar_filter)

    orphans = []
    for asset_data in all_assets:
        pkg = str(asset_data.package_name)
        refs = registry.get_referencers(pkg, opts)
        if len(refs) == 0:
            orphans.append(pkg)
            unreal.log(f"ORPHAN: {pkg}")

    unreal.log(f"Found {len(orphans)} unreferenced assets in {search_path}")
    return orphans
```
