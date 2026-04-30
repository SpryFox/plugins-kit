"""UE-side package-path helpers. Imports `unreal`, so only callable inside UE.

CCP: changes to the project's mount-point layout or asset extension rules
change here. Used together: callers that need one usually need the others.
"""
import unreal


def build_mount_map():
    """Return dict {pkg_prefix: content_dir} for /Game/ and all enabled plugins.

    pkg_prefix is the package-name prefix without trailing slash, e.g. '/Game'.
    content_dir is the on-disk content directory, forward-slashed, no trailing slash.
    """
    mount_map = {}

    project_content = unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_content_dir()
    ).replace('\\', '/').rstrip('/')
    mount_map['/Game'] = project_content

    try:
        for plugin_name in unreal.PluginBlueprintLibrary.get_enabled_plugin_names():
            try:
                base = unreal.PluginBlueprintLibrary.get_plugin_base_dir(plugin_name)
                if base:
                    base_full = unreal.Paths.convert_relative_path_to_full(base).replace('\\', '/').rstrip('/')
                    mount_map['/' + plugin_name] = base_full + '/Content'
            except Exception:
                continue
    except Exception:
        pass

    return mount_map


def package_to_filename(pkg, ext, mount_map):
    """Convert a long package name to its on-disk file path.

    Returns forward-slashed absolute path or None if the mount isn't recognized.
    """
    if not pkg or not ext:
        return None
    for prefix in sorted(mount_map.keys(), key=len, reverse=True):
        if pkg == prefix or pkg.startswith(prefix + '/'):
            rel = pkg[len(prefix):].lstrip('/')
            return f"{mount_map[prefix]}/{rel}{ext}" if rel else f"{mount_map[prefix]}{ext}"
    return None


def asset_class_extension(asset_data):
    """Return '.umap' for World assets, '.uasset' for everything else."""
    cls = str(asset_data.asset_class_path.asset_name) if asset_data.asset_class_path else ''
    return '.umap' if cls == 'World' else '.uasset'


def package_extension(registry, pkg):
    """Look up the on-disk extension for a package by querying its asset class.
    Returns None if the package isn't in the registry."""
    f = unreal.ARFilter(package_names=[pkg])
    found = registry.get_assets(f)
    if not found:
        return None
    return asset_class_extension(found[0])
