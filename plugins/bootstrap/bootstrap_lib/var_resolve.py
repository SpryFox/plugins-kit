"""Variable resolution for bootstrap manifest string values.

Expands ${var} references using a variables dict. Unresolved variables
cause the value to be marked as unresolvable (returns None).
"""

import re
from pathlib import Path
from typing import Any, Dict, Optional

VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def resolve_vars(value: str, variables: Dict[str, str]) -> Optional[str]:
    """Expand ${var} references in a string value.

    Args:
        value: String potentially containing ${var} references
        variables: Dict of variable name -> value

    Returns:
        Expanded string, or None if any variable is unresolved
    """
    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in variables:
            return variables[var_name]
        raise _UnresolvedVar(var_name)

    try:
        return VAR_PATTERN.sub(replacer, value)
    except _UnresolvedVar:
        return None


def build_variables(
    plugin_root: str,
    data_dir: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Build the variables dict from static sources and config.

    Static variables:
        plugin_root: Plugin install path
        data_dir: Plugin data directory

    Config-derived variables:
        For each config key whose value looks like a file path,
        adds <key>_dir with the dirname. E.g. uproject=/foo/bar.uproject
        -> uproject_dir=/foo
    """
    variables: Dict[str, str] = {
        "plugin_root": plugin_root,
        "data_dir": data_dir,
    }

    if config:
        for key, val in config.items():
            if not isinstance(val, str) or not val:
                continue
            variables[key] = val
            # Derive _dir for values that look like file paths
            p = Path(val)
            if p.suffix and len(p.parts) > 1:
                variables[f"{key}_dir"] = str(p.parent)

    return variables


class _UnresolvedVar(Exception):
    """Internal sentinel for unresolved variables."""
