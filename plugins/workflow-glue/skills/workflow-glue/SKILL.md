---
_schema_version: 1
name: workflow-glue
author: christina
skill-type: technique-skill
description: Use when a human wants to author, validate, or run a declarative .workflow.yaml via the native Workflow tool. Do NOT use when Claude is writing a one-off Workflow script directly (call the Workflow tool itself for that).
---

# workflow-glue

A declarative front-end to the native **Workflow tool**. A human authors a workflow
once as `*.workflow.yaml`; this skill validates it, compiles it to a native Workflow
script, and runs it. The tagline: *workflows is for Claude to make workflows;
workflow-glue is for humans to make workflows with Claude.*

**Invoking this skill to run a workflow IS the user's opt-in to the native Workflow
tool.** The compile step is deterministic Python (no model); only the final run hands
the compiled script to the Workflow tool.

Workflows live at `<project>/.claude/workflows/<name>.workflow.yaml`. Compiled scripts
are derived artifacts written to `<project>/.claude/workflows/.compiled/<name>.js`
(gitignored). The plugin ships an example at `${CLAUDE_PLUGIN_ROOT}/examples/`.

The compiler is invoked through the plugin's own venv interpreter (NOT `uv run python`,
which resolves the venv from the cwd and breaks when run from a foreign project root):

- Windows: `~/.claude/plugins/data/plugins-kit/workflow-glue/.venv/Scripts/python.exe`
- macOS/Linux: `~/.claude/plugins/data/plugins-kit/workflow-glue/.venv/bin/python`

```yaml
technique_skill:
  _schema_version: "1"
  trigger_model: auto
  identity: Validate, compile, and run human-authored .workflow.yaml files via the native Workflow tool.
  scope:
    covers:
      - running a declarative .workflow.yaml through the native Workflow tool
      - validating a .workflow.yaml without running it
      - scaffolding a new .workflow.yaml from the format
    excludes:
      - one-off Workflow scripts Claude writes directly (call the Workflow tool itself)
      - executing workflows without the native Workflow tool (there is no other runtime)
      - multi-model / openrouter workers (Claude-only by design)
  techniques:
    - id: run_workflow
      name: Compile and run a workflow
      keywords: [run workflow, execute workflow, workflow-glue run, run my workflow, run the pipeline]
      goal: Compile a .workflow.yaml and execute it via the native Workflow tool, then relay results.
      preconditions:
        - A .workflow.yaml exists (in <project>/.claude/workflows/, or a path/example the user names).
      steps:
        - n: 1
          action: |
            Resolve the workflow file. If the user named a path, use it. Otherwise look in
            <project>/.claude/workflows/<name>.workflow.yaml, then ${CLAUDE_PLUGIN_ROOT}/examples/.
            If none found, list available *.workflow.yaml files and ask which.
          tool: Glob
          expected: An absolute path to one .workflow.yaml.
        - n: 2
          action: |
            Compile it. Run the compiler via the plugin-venv interpreter (see paths above),
            writing the script next to the source under .compiled/.
          tool: Bash
          input: "<plugin-venv-python> ${CLAUDE_PLUGIN_ROOT}/scripts/compile_workflow.py <yaml> -o <project>/.claude/workflows/.compiled/<name>.js"
          expected: Exit 0; stdout is the path to the compiled .js. On exit 1, surface stderr (an authoring error) to the user and STOP -- do not attempt to run.
        - n: 3
          action: |
            Gather inputs. Read the `inputs:` block of the .workflow.yaml; for each declared
            input, collect a value from the user's request (ask via AskUserQuestion only if a
            required input is missing and cannot be inferred). Assemble them into an args object.
          tool: Read
          expected: A JSON object mapping each declared input name to a value (or {} if none).
        - n: 4
          action: |
            Run the compiled script through the native Workflow tool. Pass the compiled path as
            scriptPath and the gathered inputs as args. This is the opt-in boundary -- the user
            invoked this skill, which authorizes this Workflow-tool call.
          tool: Workflow
          input: "{ scriptPath: <project>/.claude/workflows/.compiled/<name>.js, args: <inputs object> }"
          expected: The workflow's return value (the Workflow tool result).
        - n: 5
          action: Relay the workflow's result to the user in a readable form (the tool result is not shown to them directly).
          tool: none
      checklist:
        - Compiler exited 0 before any Workflow-tool call was made.
        - args keys match the workflow's declared inputs.
        - Results were summarized for the user, not left in raw tool output.
      gotchas:
        - Never run the compiled .js by hand or with node -- it is a Workflow tool script, only the Workflow tool can execute it.
        - Do not edit files under .compiled/ -- they are regenerated from the .workflow.yaml every run.
        - If the compiler reports an error, fix the .workflow.yaml, not the generated JS.
    - id: validate_workflow
      name: Validate a workflow
      keywords: [validate workflow, check workflow, lint workflow, is my workflow valid]
      goal: Report whether a .workflow.yaml is valid without compiling or running it.
      steps:
        - n: 1
          action: Resolve the workflow file (as in run_workflow step 1).
          tool: Glob
        - n: 2
          action: Run the compiler in validate-only mode via the plugin-venv interpreter.
          tool: Bash
          input: "<plugin-venv-python> ${CLAUDE_PLUGIN_ROOT}/scripts/compile_workflow.py <yaml> --validate-only"
          expected: "Exit 0 prints `OK: <name> (<n> step(s))`. Exit 1 prints a located error to stderr -- relay it verbatim."
      checklist:
        - Reported the exact validator message (success or the located error).
    - id: scaffold_workflow
      name: Scaffold a new workflow
      keywords: [new workflow, scaffold workflow, create workflow, workflow template]
      goal: Write a starter .workflow.yaml the user can edit.
      steps:
        - n: 1
          action: |
            Ask the user for the workflow name and a one-line description. Write a starter file to
            <project>/.claude/workflows/<name>.workflow.yaml using the format below: a `name`,
            `description`, an `inputs:` block, one `schemas:` entry, and a `steps:` list with one
            example agent step. Use ${CLAUDE_PLUGIN_ROOT}/examples/review-changes.workflow.yaml as
            the reference for the format. Then offer to validate it (validate_workflow).
          tool: Write
      checklist:
        - The scaffolded file passes validate_workflow.
  narration:
    note: Keep status lines short; name the workflow and the phase being run.
    templates:
      - when: "compiling a workflow"
        template: "Compiling {{NAME}}…"
      - when: "running via the Workflow tool"
        template: "Running {{NAME}} via the Workflow tool…"
    variables:
      "{{NAME}}": "the workflow's `name` field"
```

## The .workflow.yaml format (v1)

See `${CLAUDE_PLUGIN_ROOT}/examples/review-changes.workflow.yaml` for a complete example.
Top-level keys: `name`, `description` (required); `inputs`, `phases`, `schemas`, `output`
(optional); `steps` (required, ordered).

A **step** is either an agent step or a pipeline step (exactly one):

- **agent step** — `agent: { prompt, schema?, model?, agentType?, isolation?, label? }`.
  Add `for_each: "{{ ... }}"` + `mode: parallel` to fan out (the item is bound to `item`).
- **pipeline step** — `pipeline: { over, as, stages: [...] }`. Each stage is an agent step;
  a stage may add `fan_out: { over, as, mode }` to fan out within the stage. Stages run with
  no barrier (item A reaches stage 2 while item B is still in stage 1).

**Templating** — `{{ inputs.X }}`, `{{ steps.ID }}`, `{{ steps.ID[*].field }}` (flatten),
`{{ <as> }}` (pipeline/fan_out item), `{{ <prevStage> .field }}` (preceding stage's result).
Anything outside this grammar is a compile error.
