"""Compiler tests: structural assertions on the emitted Workflow JS."""

from conftest import EXAMPLES, FIXTURES

from workflow_kit_lib import compile_doc, load_workflow


def _compile(path):
    return compile_doc(load_workflow(path))


def test_example_compiles_to_pipeline_with_nested_parallel():
    js = _compile(EXAMPLES / "review-changes.workflow.yaml")

    # meta
    assert 'export const meta = {' in js
    assert 'name: "review-changes"' in js
    assert '{ title: "Review" }' in js and '{ title: "Verify" }' in js

    # schema consts emitted and referenced
    assert "const schema_findings = {" in js
    assert "const schema_verdict = {" in js
    assert "schema: schema_findings" in js

    # no-barrier pipeline with stage callbacks
    assert "await pipeline(" in js
    assert '["bugs", "perf", "style"]' in js
    assert "(prev, dim, i) =>" in js

    # stage 2 fans out over the previous stage's findings
    assert "parallel(prev.findings.map((finding) => () => agent(" in js

    # interpolation
    assert "${dim}" in js
    assert "${args.diff}" in js
    assert "${finding.title}" in js

    # per-step model override
    assert 'model: "sonnet"' in js

    # output
    assert "return step_dimensions;" in js


def test_flat_step_compiles_to_parallel_map():
    js = _compile(FIXTURES / "good" / "flat.workflow.yaml")

    # fan-out over a string expression
    assert "await parallel(args.paths.map((item) => () => agent(" in js
    assert "agentType: \"Explore\"" in js

    # single agent step (no fan-out)
    assert "const step_summarize = await agent(" in js

    # [*] flatten in the summarize prompt
    assert "step_scan.flatMap((r) => r.note)" in js

    # default output (no `output:` key) returns an object of all steps
    assert 'return { "scan": step_scan, "summarize": step_summarize };' in js
