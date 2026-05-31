"""Validation tests: good fixtures load; broken fixtures raise WorkflowError."""

import pytest

from conftest import EXAMPLES, FIXTURES

from workflow_kit_lib import load_workflow
from workflow_kit_lib.errors import WorkflowError


def test_example_loads():
    doc = load_workflow(EXAMPLES / "review-changes.workflow.yaml")
    assert doc.name == "review-changes"
    assert len(doc.steps) == 1
    assert doc.steps[0].is_pipeline
    assert set(doc.schemas) == {"findings", "verdict"}


def test_good_flat_loads():
    doc = load_workflow(FIXTURES / "good" / "flat.workflow.yaml")
    assert [s.id for s in doc.steps] == ["scan", "summarize"]
    assert doc.steps[0].for_each == "{{ inputs.paths }}"
    # `paths: list` shorthand coerces to an InputSpec
    assert doc.inputs["paths"].type == "list"


def test_missing_file_raises():
    with pytest.raises(WorkflowError, match="not found"):
        load_workflow(FIXTURES / "good" / "does-not-exist.yaml")


@pytest.mark.parametrize(
    "name, match",
    [
        ("both.workflow.yaml", "exactly one of"),
        ("unknown_schema.workflow.yaml", "unknown schema"),
        ("bad_model.workflow.yaml", "model"),
        ("dup_steps.workflow.yaml", "duplicate step"),
        ("unknown_field.workflow.yaml", "unknown field"),
    ],
)
def test_broken_fixtures_raise(name, match):
    with pytest.raises(WorkflowError, match=match):
        load_workflow(FIXTURES / "broken" / name)
