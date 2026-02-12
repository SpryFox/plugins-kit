"""
UE Python dependency bootstrap.

Call ensure_dependencies() at the top of any script that needs external packages.
Reads requirements from the skill's requirements.yaml and uses unreal_pip to install
any missing packages into UE's site-packages.

Usage in scripts:
    import sys
    sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/skills/ue-python-api/lib')  # SKILL_DIR = plugin's ue-python-api skill path
    from bootstrap import ensure_dependencies
    ensure_dependencies()

    import yaml  # now available
"""

import sys
from pathlib import Path

# Skill root (parent of lib/)
SKILL_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = SKILL_DIR / 'lib'
REQUIREMENTS_FILE = SKILL_DIR / 'requirements.yaml'


def ensure_dependencies():
    """Install any missing packages listed in requirements.yaml."""
    import unreal

    # Ensure lib/ is on path so unreal_pip is importable
    lib_str = str(LIB_DIR)
    if lib_str not in sys.path:
        sys.path.insert(0, lib_str)

    # Read requirements (use a simple parser to avoid needing yaml before it's installed)
    packages = _read_requirements()
    if not packages:
        return

    # Check what's already installed
    try:
        import pkg_resources
        installed = {pkg.key for pkg in pkg_resources.working_set}
    except ImportError:
        installed = set()

    missing = [p for p in packages if p.lower() not in installed]
    if not missing:
        unreal.log("All UE Python dependencies satisfied.")
        return

    unreal.log(f"Installing missing UE Python packages: {missing}")
    import unreal_pip
    unreal_pip.install(missing)

    # Refresh pkg_resources so newly installed packages are importable
    try:
        import importlib
        importlib.invalidate_caches()
        pkg_resources._initialize_master_working_set()
    except:
        pass

    unreal.log("Dependencies installed. You may need to restart the script if imports still fail.")


def _read_requirements():
    """Parse requirements.yaml without needing pyyaml (chicken-and-egg)."""
    if not REQUIREMENTS_FILE.exists():
        return []

    packages = []
    in_packages = False
    with open(REQUIREMENTS_FILE, 'r') as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith('#') or not stripped:
                continue
            if stripped == 'packages:':
                in_packages = True
                continue
            if in_packages and stripped.startswith('- '):
                packages.append(stripped[2:].strip())
            elif not stripped.startswith('-'):
                in_packages = False
    return packages
