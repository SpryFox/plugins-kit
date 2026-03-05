"""JSON entry merging for bootstrap manifests.

Ensures a target JSON file contains expected entries from a reference file,
merging specified fields while preserving others.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional


class JsonCheckResult(NamedTuple):
    passed: bool
    target: str
    message: str


def check_json_entries(
    reference_path: str,
    target_path: str,
    merge_fields: List[str],
    preserve_fields: Optional[List[str]] = None,
) -> JsonCheckResult:
    """Check if target JSON has all entries from reference with matching merge fields.

    Args:
        reference_path: Path to reference JSON file (source of truth)
        target_path: Path to target JSON file to check
        merge_fields: Fields to compare for equality
        preserve_fields: Fields to keep from target (not overwritten)

    Returns:
        JsonCheckResult with pass/fail
    """
    ref_data = _load_json(reference_path)
    if ref_data is None:
        return JsonCheckResult(
            passed=False, target=target_path,
            message=f"reference file not found: {reference_path}",
        )

    target_data = _load_json(target_path)
    if target_data is None:
        return JsonCheckResult(
            passed=False, target=target_path,
            message="target file does not exist",
        )

    # Compare merge fields
    for field in merge_fields:
        ref_val = ref_data.get(field)
        target_val = target_data.get(field)
        if ref_val != target_val:
            return JsonCheckResult(
                passed=False, target=target_path,
                message=f"field '{field}' differs",
            )

    return JsonCheckResult(
        passed=True, target=target_path,
        message="all merge fields match",
    )


def merge_json_entries(
    reference_path: str,
    target_path: str,
    merge_fields: List[str],
    preserve_fields: Optional[List[str]] = None,
) -> JsonCheckResult:
    """Merge entries from reference into target JSON.

    Copies merge_fields from reference to target. If target exists,
    preserves preserve_fields from the existing target.

    Args:
        reference_path: Path to reference JSON file
        target_path: Path to target JSON file
        merge_fields: Fields to copy from reference
        preserve_fields: Fields to keep from existing target

    Returns:
        JsonCheckResult with pass/fail
    """
    ref_data = _load_json(reference_path)
    if ref_data is None:
        return JsonCheckResult(
            passed=False, target=target_path,
            message=f"reference file not found: {reference_path}",
        )

    target_data = _load_json(target_path) or {}
    preserve_fields = preserve_fields or []

    # Preserve existing fields that shouldn't be overwritten
    preserved: Dict[str, Any] = {}
    for field in preserve_fields:
        if field in target_data:
            preserved[field] = target_data[field]

    # Merge: copy merge_fields from reference
    for field in merge_fields:
        if field in ref_data:
            if isinstance(ref_data[field], dict) and isinstance(target_data.get(field), dict):
                # Deep merge for dicts: reference entries override, target extras kept
                merged = dict(target_data[field])
                merged.update(ref_data[field])
                target_data[field] = merged
            else:
                target_data[field] = ref_data[field]

    # Restore preserved fields
    target_data.update(preserved)

    # Write target
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w") as f:
        json.dump(target_data, f, indent=2)
        f.write("\n")

    return JsonCheckResult(
        passed=True, target=target_path,
        message="merged successfully",
    )


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    """Load a JSON file. Returns None if not found or invalid."""
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
