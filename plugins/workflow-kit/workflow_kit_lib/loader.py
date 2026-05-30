"""Load a .workflow.yaml file into a validated WorkflowDoc."""

from __future__ import annotations

from pathlib import Path

import yaml

from .errors import WorkflowError
from .model import WorkflowDoc


def load_workflow(path) -> WorkflowDoc:
    """Read, parse, and validate a workflow YAML file. Raises WorkflowError on any problem."""
    p = Path(path)
    if not p.is_file():
        raise WorkflowError(f"workflow file not found: {p}")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise WorkflowError(f"{p}: invalid YAML: {exc}") from exc
    if raw is None:
        raise WorkflowError(f"{p}: file is empty")
    return WorkflowDoc.parse(raw)
