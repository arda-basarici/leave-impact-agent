"""The parts of a request and of a review payload that every model system builds the same
way: the first user message over the prefetch, a logged operation as the text block the
model is shown, the inference settings, the finalization's tool configuration, and the
composed payload.

The investigator (``turns``) and the two one-call baselines (``one_call``) are peers under
the skeleton, each supplying ``Turns`` of its own; what they share is here so that the
comparison between them is about what each shows the model and nothing about how a block
is rendered or a setting is sent (the baselines step, forks 2 and 9). Everything is pure over
the attempt's state, the frozen inputs and the prompt assets, as the turns are.

*The first user message* opens with the opening asset over the leave id and the stamped
``now``, then the public skill list, which the model needs to write a skill's id and the
harness may know (``core.skills`` is on the allowed side of the lexicon's boundary), then
the prefetch as text, one block per operation in ordinal order, each the tool's name, its
arguments and the surface's envelope as canonical JSON, the same bytes the envelope carries
as a tool result. A block is rendered over the harness's own surface, since the enumerations
the prefetch reads and the reads a preparation issues are not among any role's tools. No
cache point (a cache point changes the request's bytes and bills under a rate the pricing
step has not read).

*The composed payload* is the shared composer over the structured projection of every
operation logged, the admitted statements of every answer in the order their answers were
logged, the leave the opening read returned and the universe, under the one composing
policy; an abstention's payload is empty, as is a defect's, and a run at the cap composes
from what it has. Nothing the model wrote is a claim.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import cast

from leaveimpact.agent.admissions import admitted_statements, trace_operations
from leaveimpact.agent.answer_parse import FACT_TOOL
from leaveimpact.agent.assets import PromptAssets
from leaveimpact.agent.composer import compose, rules_only_composition
from leaveimpact.agent.conclusion import abstention_of, defect_of, leave_of, universe_of
from leaveimpact.agent.graph import ReviewPayload
from leaveimpact.agent.log_events import (
    FrozenInputs,
    OperationEvent,
    OperationResult,
    PrefetchKey,
    operation_id,
)
from leaveimpact.agent.log_transition import AttemptState, operations_of
from leaveimpact.agent.surface import converse_harness_tools, render_result
from leaveimpact.core.call_settings import CallConfiguration
from leaveimpact.core.jsonshape import JsonObject, canonical_json
from leaveimpact.core.read_projection import project_reads
from leaveimpact.core.run_trace import OperationId, thawed_json
from leaveimpact.core.skills import SKILLS
from leaveimpact.core.timeshape import encode_instant
from leaveimpact.core.tools import TOOL_SPECIFICATIONS
from leaveimpact.core.worldtime import RunContext

INFERENCE_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "max_tokens": "maxTokens",
        "temperature": "temperature",
        "top_p": "topP",
        "stop_sequences": "stopSequences",
    }
)
"""The registered settings a role's configuration may hold, by the Converse field each is
sent as; a setting outside this table cannot be sent and refuses the request."""


def frozen_inputs(state: AttemptState) -> FrozenInputs:
    """The admitted inputs ``state`` holds; a request is built over an admitted attempt."""
    inputs = state.inputs
    assert inputs is not None, "a request is built over an admitted attempt"
    return inputs


def configured(inputs: FrozenInputs, role: str) -> CallConfiguration:
    """``role``'s model configuration; ``ValueError`` for a role the inputs do not configure."""
    configuration = inputs.configuration_of(role)
    if configuration is None:
        raise ValueError(f"{role!r} is not a configured role")
    return configuration


def inference_config(configuration: CallConfiguration) -> JsonObject:
    """The Converse ``inferenceConfig`` of ``configuration``'s settings; ``ValueError`` for a
    setting the table above cannot send."""
    config: JsonObject = {}
    for setting in configuration.settings:
        field = INFERENCE_FIELDS.get(setting.name)
        if field is None:
            raise ValueError(f"the setting {setting.name!r} cannot be sent in a Converse request")
        config[field] = thawed_json(setting.value)
    return config


def skill_list() -> str:
    """The public skill list as the first message states it, one ``id: name`` line each."""
    lines = ["Skill list (id: name):"]
    lines.extend(f"- {skill.id}: {skill.name}" for skill in SKILLS)
    return "\n".join(lines)


def operation_text(result: OperationResult, context: RunContext) -> str:
    """One logged operation as the text block the model is shown: the tool, its arguments and
    the surface's envelope, canonical JSON, rendered over the harness's own surface."""
    rendered = render_result(result, tool=result.tool, surface=TOOL_SPECIFICATIONS, context=context)
    block: JsonObject = {
        "tool": result.tool,
        "arguments": thawed_json(result.arguments),
        "result": rendered.content,
    }
    return canonical_json(block)


def opening_message(
    assets: PromptAssets, state: AttemptState, boundary: int, shown: list[OperationId]
) -> JsonObject:
    """The first user message over the prefetch operations logged below ``boundary``: the
    opening, the skill list, one text block per prefetch operation; each operation shown is
    appended to ``shown``, in order."""
    inputs = frozen_inputs(state)
    context = inputs.context
    opening = assets.opening(
        leave_id=str(context.leave_id), now=canonical_json(encode_instant(context.now))
    )
    content: list[JsonObject] = [{"text": opening}, {"text": skill_list()}]
    for logged in operations_of(state):
        if logged.position >= boundary:
            break
        event = logged.event
        assert isinstance(event, OperationEvent)
        if not isinstance(event.key, PrefetchKey):
            continue
        result = event.resolution
        assert isinstance(result, OperationResult), "a prefetch read is never skipped"
        content.append({"text": operation_text(result, context)})
        shown.append(operation_id(event.key))
    return {"role": "user", "content": content}


def append_text(message: JsonObject, text: str) -> None:
    """``text`` as one more block of ``message``'s content, so two user turns never follow
    each other."""
    content = cast("list[JsonObject]", message["content"])
    content.append({"text": text})


def fact_forced_tool_config() -> JsonObject:
    """The finalization's tool configuration: the harness's own tools alone, the fact tool
    forced by name, so the turn can only state facts."""
    return {
        "tools": list(converse_harness_tools()),
        "toolChoice": {"tool": {"name": FACT_TOOL}},
    }


def composed_payload(state: AttemptState) -> ReviewPayload:
    """The review payload over everything the log holds: empty under a defect or an
    abstention, else the composer's claims over the admitted statements (see the module)."""
    inputs = frozen_inputs(state)
    operations = trace_operations(state)
    projection = project_reads(operations, inputs.context.today)
    leave = leave_of(operations, inputs.context)
    if defect_of(operations, projection, inputs.context, leave) is not None:
        return ReviewPayload((), rules_only_composition())
    if abstention_of(projection, leave) is not None:
        return ReviewPayload((), rules_only_composition())
    assert leave is not None
    composed = compose(
        projection, admitted_statements(state), inputs.context, leave, universe_of(projection)
    )
    return ReviewPayload(composed.claims, composed.composition)


__all__ = [
    "INFERENCE_FIELDS",
    "append_text",
    "composed_payload",
    "configured",
    "fact_forced_tool_config",
    "frozen_inputs",
    "inference_config",
    "opening_message",
    "operation_text",
    "skill_list",
]
