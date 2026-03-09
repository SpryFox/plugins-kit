"""Content-hash and time-based caching for bootstrap manifests."""

import hashlib
import os
import time
from typing import List, Optional


CACHE_FILENAME = "bootstrap_cache.sha256"
CURRENT_HASH_FILENAME = "bootstrap_current.sha256"
TIME_CACHE_FILENAME = "bootstrap_time_cache.txt"


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


def compute_current_hash(data_dir: str, paths: List[str]) -> str:
    """Compute hash of file contents and write to current-hash file.

    Called by SessionStart to pre-compute the hash once per session.
    The Stop hook then uses check_cache_fast() for cheap comparisons.

    Args:
        data_dir: Directory to write the current hash file
        paths: List of file paths to hash

    Returns:
        The computed hash string
    """
    current_hash = _compute_hash(paths)
    os.makedirs(data_dir, exist_ok=True)
    current_file = os.path.join(data_dir, CURRENT_HASH_FILENAME)
    with open(current_file, "w") as f:
        f.write(current_hash + "\n")
    return current_hash


def check_cache_fast(data_dir: str) -> Optional[bool]:
    """Compare stored cache hash vs pre-computed current hash.

    Uses the current-hash file written by compute_current_hash() to avoid
    recomputing the hash on every turn.

    Args:
        data_dir: Directory containing both hash files

    Returns:
        True if cache is valid (hashes match), False if cache miss,
        None if current hash file doesn't exist (caller should compute)
    """
    cache_file = os.path.join(data_dir, CACHE_FILENAME)
    current_file = os.path.join(data_dir, CURRENT_HASH_FILENAME)

    try:
        with open(current_file, "r") as f:
            current_hash = f.read().strip()
    except (FileNotFoundError, PermissionError):
        return None

    try:
        with open(cache_file, "r") as f:
            stored_hash = f.read().strip()
    except (FileNotFoundError, PermissionError):
        return False

    return stored_hash == current_hash


def check_time_cache(data_dir: str, key: str, cooldown_seconds: int) -> bool:
    """Check if a time-based cache is still valid.

    Args:
        data_dir: Directory containing the time cache file
        key: Cache key (e.g. "git_remote_check")
        cooldown_seconds: Seconds before the cache expires

    Returns:
        True if cache is valid (within cooldown window), False otherwise
    """
    cache_file = os.path.join(data_dir, TIME_CACHE_FILENAME)
    try:
        with open(cache_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t", 1)
                if len(parts) == 2 and parts[0] == key:
                    timestamp = float(parts[1])
                    return (time.time() - timestamp) < cooldown_seconds
    except (FileNotFoundError, PermissionError, ValueError):
        pass
    return False


def write_time_cache(data_dir: str, key: str) -> None:
    """Write a time-based cache entry.

    Args:
        data_dir: Directory to write the time cache file
        key: Cache key to record
    """
    cache_file = os.path.join(data_dir, TIME_CACHE_FILENAME)
    os.makedirs(data_dir, exist_ok=True)

    # Read existing entries (excluding this key)
    lines: list[str] = []
    try:
        with open(cache_file, "r") as f:
            for line in f:
                if line.strip() and not line.startswith(f"{key}\t"):
                    lines.append(line.rstrip("\n"))
    except FileNotFoundError:
        pass

    # Add new entry
    lines.append(f"{key}\t{time.time()}")

    with open(cache_file, "w") as f:
        f.write("\n".join(lines) + "\n")
