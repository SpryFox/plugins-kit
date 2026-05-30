"""Typed, validated in-memory model of a workflow document.

Plain dataclasses + hand-rolled validation (no pydantic) so the only runtime
dependency is PyYAML -- which is already present in the repo's test env. Each
class has a ``parse(raw, where)`` classmethod that turns a raw dict (straight off
YAML) into a validated instance, raising WorkflowError with a located message on
any problem. Unknown keys are rejected (typo protection).

The grammar, mirroring the steps-wrap-pipelines format:

    WorkflowDoc
      name, description            required scalars
      inputs: {name: InputSpec}    optional; "x: string" shorthand allowed
      phases: [PhaseSpec]          optional; else inferred from step.phase
      schemas: {name: <json>}      optional named JSON-Schema blocks
      steps: [Step]                required, ordered
        Step = agent-step | pipeline-step   (exactly one)
          agent-step: agent + optional for_each/mode (flat fan-out)
          pipeline-step: pipeline (over/as/stages), each Stage an agent
                         optionally with a nested fan_out
      output                       optional return expression
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Union

from .errors import WorkflowError

VALID_MODELS = {"sonnet", "opus", "haiku"}
VALID_ISOLATION = {"worktree"}
VALID_MODE = {"parallel"}  # v1 exposes only parallel fan-out for flat steps / nested fan_out


# --------------------------------------------------------------------------- #
# small validation helpers
# --------------------------------------------------------------------------- #
def _as_dict(raw: Any, where: str) -> dict:
    if not isinstance(raw, dict):
        raise WorkflowError(f"{where}: expected a mapping, got {type(raw).__name__}")
    return raw


def _req(d: dict, key: str, where: str) -> Any:
    if key not in d or d[key] is None:
        raise WorkflowError(f"{where}: missing required field {key!r}")
    return d[key]


def _str(val: Any, key: str, where: str) -> str:
    if not isinstance(val, str):
        raise WorkflowError(f"{where}: {key!r} must be a string, got {type(val).__name__}")
    return val


def _opt_str(d: dict, key: str, where: str) -> Optional[str]:
    if key not in d or d[key] is None:
        return None
    return _str(d[key], key, where)


def _forbid_extra(d: dict, allowed: set, where: str) -> None:
    extra = sorted(set(d) - allowed)
    if extra:
        raise WorkflowError(
            f"{where}: unknown field(s) {extra}; allowed: {sorted(allowed)}"
        )


def _enum(val: Optional[str], allowed: set, key: str, where: str) -> Optional[str]:
    if val is not None and val not in allowed:
        raise WorkflowError(f"{where}: {key!r} must be one of {sorted(allowed)}, got {val!r}")
    return val


# --------------------------------------------------------------------------- #
# leaf specs
# --------------------------------------------------------------------------- #
@dataclass
class InputSpec:
    type: str = "string"
    description: Optional[str] = None

    @classmethod
    def parse(cls, raw: Any, where: str) -> "InputSpec":
        # shorthand: `diff: string`
        if isinstance(raw, str):
            return cls(type=raw)
        d = _as_dict(raw, where)
        _forbid_extra(d, {"type", "description"}, where)
        return cls(
            type=_opt_str(d, "type", where) or "string",
            description=_opt_str(d, "description", where),
        )


@dataclass
class PhaseSpec:
    id: str
    title: str

    @classmethod
    def parse(cls, raw: Any, where: str) -> "PhaseSpec":
        d = _as_dict(raw, where)
        _forbid_extra(d, {"id", "title"}, where)
        pid = _str(_req(d, "id", where), "id", where)
        return cls(id=pid, title=_opt_str(d, "title", where) or pid)


@dataclass
class AgentSpec:
    prompt: str
    schema: Optional[str] = None  # name of a block in WorkflowDoc.schemas
    model: Optional[str] = None
    agentType: Optional[str] = None
    isolation: Optional[str] = None
    label: Optional[str] = None

    @classmethod
    def parse(cls, raw: Any, where: str) -> "AgentSpec":
        d = _as_dict(raw, where)
        _forbid_extra(
            d, {"prompt", "schema", "model", "agentType", "isolation", "label"}, where
        )
        return cls(
            prompt=_str(_req(d, "prompt", where), "prompt", where),
            schema=_opt_str(d, "schema", where),
            model=_enum(_opt_str(d, "model", where), VALID_MODELS, "model", where),
            agentType=_opt_str(d, "agentType", where),
            isolation=_enum(
                _opt_str(d, "isolation", where), VALID_ISOLATION, "isolation", where
            ),
            label=_opt_str(d, "label", where),
        )


@dataclass
class FanOut:
    over: Union[str, list]
    as_: str
    mode: str = "parallel"

    @classmethod
    def parse(cls, raw: Any, where: str) -> "FanOut":
        d = _as_dict(raw, where)
        _forbid_extra(d, {"over", "as", "mode"}, where)
        over = _req(d, "over", where)
        if not isinstance(over, (str, list)):
            raise WorkflowError(f"{where}: 'over' must be a string expression or a list")
        return cls(
            over=over,
            as_=_str(_req(d, "as", where), "as", where),
            mode=_enum(_opt_str(d, "mode", where) or "parallel", VALID_MODE, "mode", where),
        )


@dataclass
class Stage:
    id: str
    agent: AgentSpec
    phase: Optional[str] = None
    fan_out: Optional[FanOut] = None

    @classmethod
    def parse(cls, raw: Any, where: str) -> "Stage":
        d = _as_dict(raw, where)
        _forbid_extra(d, {"id", "phase", "agent", "fan_out"}, where)
        sid = _str(_req(d, "id", where), "id", where)
        loc = f"{where}.stage[{sid!r}]"
        agent = AgentSpec.parse(_req(d, "agent", loc), f"{loc}.agent")
        fan = d.get("fan_out")
        return cls(
            id=sid,
            agent=agent,
            phase=_opt_str(d, "phase", loc),
            fan_out=FanOut.parse(fan, f"{loc}.fan_out") if fan is not None else None,
        )


@dataclass
class PipelineSpec:
    over: Union[str, list]
    as_: str
    stages: list  # list[Stage]

    @classmethod
    def parse(cls, raw: Any, where: str) -> "PipelineSpec":
        d = _as_dict(raw, where)
        _forbid_extra(d, {"over", "as", "stages"}, where)
        over = _req(d, "over", where)
        if not isinstance(over, (str, list)):
            raise WorkflowError(f"{where}: 'over' must be a string expression or a list")
        raw_stages = _req(d, "stages", where)
        if not isinstance(raw_stages, list) or not raw_stages:
            raise WorkflowError(f"{where}: 'stages' must be a non-empty list")
        stages = [Stage.parse(s, where) for s in raw_stages]
        ids = [s.id for s in stages]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise WorkflowError(f"{where}: duplicate stage id(s) {dupes}")
        return cls(over=over, as_=_str(_req(d, "as", where), "as", where), stages=stages)


@dataclass
class Step:
    id: str
    phase: Optional[str] = None
    agent: Optional[AgentSpec] = None
    for_each: Optional[str] = None
    mode: str = "parallel"
    pipeline: Optional[PipelineSpec] = None

    @property
    def is_pipeline(self) -> bool:
        return self.pipeline is not None

    @classmethod
    def parse(cls, raw: Any, where: str) -> "Step":
        d = _as_dict(raw, where)
        sid = _str(_req(d, "id", where), "id", where)
        loc = f"step {sid!r}"
        _forbid_extra(d, {"id", "phase", "agent", "for_each", "mode", "pipeline"}, loc)

        has_agent = d.get("agent") is not None
        has_pipe = d.get("pipeline") is not None
        if has_agent == has_pipe:
            raise WorkflowError(
                f"{loc}: exactly one of `agent` or `pipeline` is required"
            )
        if has_pipe and d.get("for_each") is not None:
            raise WorkflowError(
                f"{loc}: `for_each` is not allowed on a pipeline step (use pipeline.over)"
            )

        agent = AgentSpec.parse(d["agent"], f"{loc}.agent") if has_agent else None
        pipeline = (
            PipelineSpec.parse(d["pipeline"], f"{loc}.pipeline") if has_pipe else None
        )
        for_each = _opt_str(d, "for_each", loc)
        mode = _enum(_opt_str(d, "mode", loc) or "parallel", VALID_MODE, "mode", loc)
        return cls(
            id=sid, phase=_opt_str(d, "phase", loc), agent=agent,
            for_each=for_each, mode=mode, pipeline=pipeline,
        )


# --------------------------------------------------------------------------- #
# document root
# --------------------------------------------------------------------------- #
@dataclass
class WorkflowDoc:
    name: str
    description: str
    steps: list  # list[Step]
    inputs: dict = field(default_factory=dict)     # name -> InputSpec
    phases: list = field(default_factory=list)      # list[PhaseSpec]
    schemas: dict = field(default_factory=dict)     # name -> raw JSON-schema dict
    output: Optional[str] = None

    @classmethod
    def parse(cls, raw: Any) -> "WorkflowDoc":
        d = _as_dict(raw, "<workflow>")
        _forbid_extra(
            d,
            {"name", "description", "inputs", "phases", "schemas", "steps", "output"},
            "<workflow>",
        )
        name = _str(_req(d, "name", "<workflow>"), "name", "<workflow>")
        description = _str(
            _req(d, "description", "<workflow>"), "description", "<workflow>"
        )

        inputs = {}
        for k, v in _as_dict(d.get("inputs") or {}, "inputs").items():
            inputs[k] = InputSpec.parse(v, f"inputs.{k}")

        phases = [
            PhaseSpec.parse(p, f"phases[{i}]")
            for i, p in enumerate(d.get("phases") or [])
        ]

        schemas = _as_dict(d.get("schemas") or {}, "schemas")
        for sn, sv in schemas.items():
            if not isinstance(sv, dict):
                raise WorkflowError(f"schemas.{sn}: a schema must be a mapping (JSON Schema)")

        raw_steps = _req(d, "steps", "<workflow>")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise WorkflowError("<workflow>: 'steps' must be a non-empty list")
        steps = [Step.parse(s, "steps[]") for s in raw_steps]

        doc = cls(
            name=name, description=description, steps=steps,
            inputs=inputs, phases=phases, schemas=schemas,
            output=_opt_str(d, "output", "<workflow>"),
        )
        doc._validate_cross_refs()
        return doc

    # ----------------------------------------------------------------- #
    def _validate_cross_refs(self) -> None:
        ids = [s.id for s in self.steps]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise WorkflowError(f"<workflow>: duplicate step id(s) {dupes}")

        schema_names = set(self.schemas)
        for step in self.steps:
            for loc, agent in _agents_of(step):
                if agent.schema and agent.schema not in schema_names:
                    raise WorkflowError(
                        f"{loc}: unknown schema {agent.schema!r}; "
                        f"declared schemas: {sorted(schema_names)}"
                    )


def _agents_of(step: Step):
    """Yield (location, AgentSpec) for every agent in a step (flat or pipeline)."""
    if step.agent is not None:
        yield (f"step {step.id!r}.agent", step.agent)
    if step.pipeline is not None:
        for stage in step.pipeline.stages:
            yield (f"step {step.id!r}.pipeline.stage {stage.id!r}.agent", stage.agent)
