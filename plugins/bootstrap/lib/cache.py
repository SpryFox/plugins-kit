"""Content-hash caching for bootstrap manifests."""

import hashlib
import os
from typing import List


CACHE_FILENAME = "bootstrap_cache.sha256"


def _compute_hash(paths: List[str]) -> str:
    """Compute SHA256 hash of file contents."""
    h = hashlib.sha256()
    for path in sorted(paths):
        try:
            with open(path, "rb") as f:
                h.update(f.read())
        except (FileNotFoundError, PermissionError):
            h.update(b"MISSING:" + path.encode())
    return h.hexdigest()


def check_cache(data_dir: str, paths: List[str]) -> bool:
    """Check if cached hash matches current file contents.

    Args:
        data_dir: Directory containing the cache file
        paths: List of file paths to hash

    Returns:
        True if cache is valid (hash matches), False otherwise
    """
    cache_file = os.path.join(data_dir, CACHE_FILENAME)
    try:
        with open(cache_file, "r") as f:
            stored_hash = f.read().strip()
    except (FileNotFoundError, PermissionError):
        return False

    current_hash = _compute_hash(paths)
    return stored_hash == current_hash


def write_cache(data_dir: str, paths: List[str]) -> None:
    """Write content hash to cache file.

    Args:
        data_dir: Directory to write the cache file
        paths: List of file paths that were hashed
    """
    os.makedirs(data_dir, exist_ok=True)
    cache_file = os.path.join(data_dir, CACHE_FILENAME)
    current_hash = _compute_hash(paths)
    with open(cache_file, "w") as f:
        f.write(current_hash + "\n")
