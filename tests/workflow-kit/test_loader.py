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


# --------------------------------------------------------------------------- #
# node strategies: script + openrouter steps
# --------------------------------------------------------------------------- #
def _load_text(text, write_workflow):
    return load_workflow(write_workflow(text))


def test_script_step_parses(write_workflow):
    doc = _load_text(
        """
name: s
description: a script node
steps:
  - id: stats
    script:
      command: "wc -w {{ inputs.source }}"
      label: wordcount
""",
        write_workflow,
    )
    step = doc.steps[0]
    assert step.kind == "script"
    assert step.script.command == "wc -w {{ inputs.source }}"
    assert step.script.label == "wordcount"
    assert step.script.out is None  # default derived at compile time


def test_openrouter_step_parses(write_workflow):
    doc = _load_text(
        """
name: o
description: an openrouter node
steps:
  - id: classify
    openrouter:
      prompt_file: "{{ inputs.source }}"
      cheap: true
      system: "Classify in one word."
""",
        write_workflow,
    )
    step = doc.steps[0]
    assert step.kind == "openrouter"
    assert step.openrouter.prompt_file == "{{ inputs.source }}"
    assert step.openrouter.cheap is True
    assert step.openrouter.model is None  # omitted -> configured default(Cheap)


def test_script_missing_command_raises(write_workflow):
    with pytest.raises(WorkflowError, match="missing required field 'command'"):
        _load_text(
            "name: b\ndescription: x\nsteps:\n  - id: s\n    script: { label: oops }\n",
            write_workflow,
        )


def test_openrouter_missing_prompt_file_raises(write_workflow):
    with pytest.raises(WorkflowError, match="missing required field 'prompt_file'"):
        _load_text(
            "name: b\ndescription: x\nsteps:\n  - id: s\n    openrouter: { cheap: true }\n",
            write_workflow,
        )


def test_openrouter_cheap_must_be_bool(write_workflow):
    with pytest.raises(WorkflowError, match="'cheap' must be a boolean"):
        _load_text(
            "name: b\ndescription: x\nsteps:\n"
            "  - id: s\n    openrouter: { prompt_file: f.txt, cheap: 3 }\n",
            write_workflow,
        )


def test_node_unknown_field_raises(write_workflow):
    with pytest.raises(WorkflowError, match="unknown field"):
        _load_text(
            "name: b\ndescription: x\nsteps:\n"
            "  - id: s\n    script: { command: ls, bogus: 1 }\n",
            write_workflow,
        )


def test_two_kinds_on_one_step_raises(write_workflow):
    with pytest.raises(WorkflowError, match="exactly one of"):
        _load_text(
            "name: b\ndescription: x\nsteps:\n"
            "  - id: s\n    agent: { prompt: hi }\n    script: { command: ls }\n",
            write_workflow,
        )
