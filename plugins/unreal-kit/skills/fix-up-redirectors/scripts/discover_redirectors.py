"""Phase 1 facade: discover redirectors and emit the phase-1 YAML.

Runs inside Unreal as a commandlet. Scope is read from env var SCOPE
(default: /Game). Output goes to <project>/Saved/PythonOutput/redirectors_discovery.yaml.
"""
import os, sys

# unreal-kit bootstrap (UE-side dependency manager).
sys.path.insert(0, os.path.expanduser('~/.claude/plugins/data/plugins-kit/unreal-kit/lib'))
sys.path.insert(0, os.path.expanduser('~/.claude/plugins/data/plugins-kit/unreal-kit/github/unreal-pip'))
# Restore registry-canonical PATH before any subprocess fan-out.
from path_repair import repair_path
repair_path()
from bootstrap import ensure_dependencies
ensure_dependencies()

# Skill-local lib.
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'lib')))
import unreal
from package_paths import build_mount_map, package_extension, package_to_filename
from redirector_record import save_discovery

SCOPE = os.environ.get('SCOPE', '/Game').rstrip('/')

registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.scan_paths_synchronous([SCOPE], force_rescan=False)

mount_map = build_mount_map()

dep_options = unreal.AssetRegistryDependencyOptions(
    include_soft_package_references=True,
    include_hard_package_references=True,
    include_searchable_names=False,
    include_soft_management_references=False,
)


def get_target_package(redirector_pkg):
    """A redirector's outgoing package dep is its target."""
    deps = registry.get_dependencies(redirector_pkg, dep_options)
    pkg_deps = [str(d) for d in deps if str(d).startswith('/')]
    return pkg_deps[0] if pkg_deps else None


def package_exists(pkg):
    if not pkg:
        return False
    return len(registry.get_assets(unreal.ARFilter(package_names=[pkg]))) > 0


redirector_assets = registry.get_assets(unreal.ARFilter(
    class_names=['ObjectRedirector'],
    package_paths=[SCOPE],
    recursive_paths=True,
))

ext_cache = {}
records = []
seen = set()
for ad in redirector_assets:
    pkg = str(ad.package_name)
    if pkg in seen:
        continue
    seen.add(pkg)

    target_pkg = get_target_package(pkg)
    refs = [str(r) for r in registry.get_referencers(pkg, dep_options)]

    referencer_files = []
    has_level = False
    has_unresolvable = False
    for ref_pkg in refs:
        if ref_pkg not in ext_cache:
            ext_cache[ref_pkg] = package_extension(registry, ref_pkg)
        ext = ext_cache[ref_pkg]
        if ext == '.umap':
            has_level = True
        path = package_to_filename(ref_pkg, ext, mount_map) if ext else None
        if path:
            referencer_files.append(path)
        else:
            has_unresolvable = True

    records.append({
        'pkg': pkg,
        'file': package_to_filename(pkg, '.uasset', mount_map),
        'target_pkg': target_pkg,
        'target_exists': package_exists(target_pkg),
        'referencer_pkgs': refs,
        'referencer_files': referencer_files,
        'has_level_referencer': has_level,
        'has_unresolvable_referencer': has_unresolvable,
    })

out_path = os.path.join(str(unreal.Paths.project_dir()), 'Saved', 'PythonOutput', 'redirectors_discovery.yaml')
save_discovery(out_path, SCOPE, records)
print(f"Wrote {out_path}")
print(f"Discovered {len(records)} redirectors under {SCOPE}")
