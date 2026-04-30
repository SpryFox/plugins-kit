"""Host-side code-reference scanner and cache I/O.

Scans project source for hardcoded UE content paths (e.g. `/Game/Foo/Bar`)
so the redirector pipeline can refuse to fix any redirector whose package
is referenced from code.

CCP: anything that touches the on-disk shape or freshness contract of the
code-references YAML lives here. Stdlib + pyyaml only.
"""
import datetime as _dt
import os
import re

import yaml


# Match `/MountPoint/Path/...` style UE package paths. MountPoint must start
# with an uppercase letter (UE convention: /Game, /Engine, /MyPlugin) so we
# don't slurp every Unix-style path on the planet.
#
# The trailing charset allows `.AssetName` and `_C` suffixes; we normalize
# those off later.
_PATH_RE = re.compile(r'/[A-Z][A-Za-z0-9_]*(?:/[A-Za-z0-9_.\-]+)+')

DEFAULT_EXTENSIONS = (
    '.cpp', '.h', '.hpp', '.c', '.cc', '.cxx', '.inl',
    '.cs', '.py', '.ini',
    '.uplugin', '.uproject',
)

DEFAULT_EXCLUDE_DIRS = frozenset({
    '.git', '.svn', '.hg',
    'Intermediate', 'Binaries', 'Saved', 'DerivedDataCache', 'Build',
    'node_modules', '.venv', 'venv', '__pycache__',
    'tmp', '.local-data', '.pytest_cache',
    '.vs', '.vscode', '.idea',
})

# Skip very large files - generated dumps, lockfiles, blobs. 5 MB is plenty
# for any real source file.
_MAX_FILE_BYTES = 5 * 1024 * 1024


def _normalize(path):
    """Strip `.AssetName` / `.AssetName_C` suffix so `/Game/Foo/Bar.Bar`
    collapses to the package path `/Game/Foo/Bar`."""
    last_slash = path.rfind('/')
    if last_slash < 0:
        return path
    asset = path[last_slash + 1:]
    if '.' in asset:
        asset = asset.split('.', 1)[0]
    # Trim trailing punctuation that the charset accidentally swept in.
    asset = asset.rstrip('-_.')
    if not asset:
        return path[:last_slash]
    return path[:last_slash + 1] + asset


def _is_binaryish(sample):
    return b'\x00' in sample


def _iter_source_files(root, extensions, exclude_dirs):
    ext_set = {e.lower() for e in extensions}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in ext_set:
                yield os.path.join(dirpath, name)


def scan(root, extensions=DEFAULT_EXTENSIONS, exclude_dirs=DEFAULT_EXCLUDE_DIRS):
    """Walk `root` and return (refs_set, file_count, scanned_count).

    refs_set: normalized package paths found anywhere in scanned source.
    file_count: number of files we actually read.
    scanned_count: number of files matched by extension (includes ones we
    skipped for size/binary reasons - useful for sanity-checking coverage).
    """
    refs = set()
    scanned_count = 0
    file_count = 0
    for path in _iter_source_files(root, extensions, exclude_dirs):
        scanned_count += 1
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if size > _MAX_FILE_BYTES:
            continue
        try:
            with open(path, 'rb') as f:
                head = f.read(8192)
                if _is_binaryish(head):
                    continue
                rest = f.read()
        except OSError:
            continue
        try:
            text = (head + rest).decode('utf-8', errors='ignore')
        except Exception:
            continue
        file_count += 1
        for match in _PATH_RE.findall(text):
            refs.add(_normalize(match))
    return refs, file_count, scanned_count


def save(path, refs, root, file_count, scanned_count, extensions):
    """Write the cache YAML."""
    out = {
        'generated_at': _dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'root': os.path.abspath(root).replace('\\', '/'),
        'extensions': list(extensions),
        'file_count': file_count,
        'scanned_count': scanned_count,
        'reference_count': len(refs),
        'references': sorted(refs),
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w') as f:
        yaml.dump(out, f, default_flow_style=False, sort_keys=False)


def load(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def get_age_hours(path):
    """Return age of the cache in hours based on its `generated_at` field.
    Falls back to filesystem mtime if the field is missing/unparseable.
    Returns None if the file doesn't exist."""
    if not os.path.isfile(path):
        return None
    try:
        data = load(path)
        ts = data.get('generated_at') if isinstance(data, dict) else None
        if ts:
            ts = ts.rstrip('Z')
            generated = _dt.datetime.fromisoformat(ts)
            delta = _dt.datetime.utcnow() - generated
            return delta.total_seconds() / 3600.0
    except Exception:
        pass
    try:
        mtime = os.path.getmtime(path)
        delta = _dt.datetime.utcnow().timestamp() - mtime
        return delta / 3600.0
    except OSError:
        return None


def is_stale(path, max_age_hours):
    age = get_age_hours(path)
    return age is None or age > max_age_hours
