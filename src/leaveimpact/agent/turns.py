"""The investigator's turns: the request of each logical call and the review payload, both pure
functions of the attempt's state.

The skeleton (``graph``) holds the loop's mechanics and asks the system for two things
through ``Turns``: the request of logical call ``n`` given the state before it, and the
payload the run ends with. This module is the investigator's answer (the graph step, forks
1, 3, 4 and 10). Nothing is cached across calls and nothing is read but the log: a worker
that recovers the attempt rebuilds the same bytes a first process sent, and the model node
holds it to that, refusing a restated request whose digest is not the first intent's.

*The shape of a run.* An abstention the prefetch decides (the leave not returned, the
employee enumeration not covered) asks no call: the run goes to its approval with the
empty payload, and neither a count nor a send is made (fork 8). Otherwise reading turns,
then one finalization. A loop turn shows the model the
role's read tools and the fact tool with tool choice ``auto``; the model reads, and may
state facts about what earlier turns returned. The loop ends when an answer holds no read
call (the model stopped reading, whatever its stop reason) or when the account enters
finalization; the system then asks one finalization call, the whole conversation plus the
finalization text, the fact tool alone and forced by name, so the last turn can only state
facts. After it the system asks nothing more. The finalization is requested, never
guaranteed: when the account refuses its allocation the run ends at its cap through the
approval of what it has (amendment 2). A call ended as behaviour, a service error the
registered table reads as the model's own doing, has no answer and stops nothing; it is
read as an answer with no read call, so a loop call ended so is followed by the
finalization, and a finalization ended so ends the asking and the run goes to its approval
with what it has (the close's review, first finding: the first wiring had no reading for
it and raised, closing the run as a harness defect).

*What the request of call* ``n`` *is a function of.* The frozen inputs, the prompt assets
and the events logged strictly below the call's first intent, or every event when the call
has no intent yet (amendment 5 fixes the boundary at the call's first event; a count start
carries the request's digest and no ordinal, so from here only the intent is readable, and
the count-side guard against a recount under another digest is the bound establishment's).
Below that line sit the prefetch operations, each earlier call's response as it arrived,
each of its read calls' logged resolution, and each of its fact calls' derived admissions.

*The first user turn.* The opening asset over the leave id and the stamped ``now``; the
public skill list, which the model needs to write a skill's id and the harness may know
(``core.skills`` is on the allowed side of the lexicon's boundary); then the prefetch as
text, one block per operation in ordinal order, each the tool's name, its arguments and
the surface's envelope as canonical JSON, the same bytes the envelope carries as a tool
result. The prefetch is rendered over the harness's own surface, since the enumerations it
reads are not among the role's tools. No cache point at this step (a cache point changes
the request's bytes and bills under a rate the pricing step has not read).

*The conversation.* Each earlier answered call is its assistant message as arrived,
nothing projected, followed by a user message holding one ``toolResult`` per ``toolUse``
of that message, in content order: a read's logged resolution rendered by the surface, a
skip's unreachable source or ``not_made``, an undispatched call's ``not_made`` with its
derived reason, a fact call's admissions, an unparsed call's fixed correction (amendment
4). A call ended as behaviour contributes no messages, since nothing arrived. The
finalization text joins the last user message, so two user turns never follow each other.
A read call the log leaves unresolved or unreached cannot sit under a request, since the
tools node resolves an answer's reads before the next call is asked and a stopping result
ends the run; meeting one is a defect of this harness.

*The review payload.* The shared composer over the structured projection of every
operation logged, the admitted statements of every answer in the order their answers were
logged, the leave the opening read returned and the universe, under the one composing
policy; an abstention's payload is empty, as is a defect's, and a run at the cap composes
from what it has. Nothing the model wrote is a claim.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from leaveimpact.agent.admissions import (
    AnsweredCall,
    admitted_statements,
    answer_of,
    trace_operations,
)
from leaveimpact.agent.answer_parse import FACT_TOOL, ToolUse, tool_uses
from leaveimpact.agent.assets import FINALIZATION, SYSTEM, PromptAssets
from leaveimpact.agent.composer import compose, rules_only_composition
from leaveimpact.agent.conclusion import abstention_of, defect_of, leave_of, universe_of
from leaveimpact.agent.graph import ReviewPayload, TurnRequest
from leaveimpact.agent.log_events import (
    DispatchOutcome,
    FrozenInputs,
    ModelReadKey,
    OperationEvent,
    OperationKey,
    OperationResult,
    OperationSkip,
    PrefetchKey,
    operation_id,
)
from leaveimpact.agent.log_transition import AttemptState, CallEvents, calls_of, operations_of
from leaveimpact.agent.surface import (
    RenderedResult,
    converse_harness_tools,
    converse_tools,
    render_fact_result,
    render_result,
    render_undispatched,
    render_unparsed,
)
from leaveimpact.core.call_settings import CallConfiguration
from leaveimpact.core.jsonshape import JsonObject, canonical_json
from leaveimpact.core.model_calls import HandledAsBatch, Undispatched, Unparsed
from leaveimpact.core.read_projection import project_reads
from leaveimpact.core.run_trace import Operation, OperationId, thawed_json
from leaveimpact.core.skills import SKILLS
from leaveimpact.core.timeshape import encode_instant
from leaveimpact.core.tools import TOOL_SPECIFICATIONS, Role, ToolSpecification, role_surface
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


@dataclass(frozen=True, slots=True)
class EarlierCall:
    """A settled logical call below the request being built: its events, and its answer or
    ``None`` when it ended as behaviour, after which nothing arrived."""

    events: CallEvents
    answered: AnsweredCall | None


@dataclass(frozen=True, slots=True)
class InvestigatorTurns:
    """The investigator's ``Turns``: see the module."""

    assets: PromptAssets
    role: Role = Role.INVESTIGATOR

    def request_for(self, state: AttemptState, call: int) -> TurnRequest | None:
        """The request of logical call ``call``: the first, a loop or the finalization request;
        ``None`` on an abstention, which the prefetch below the call decides (the run goes to
        its approval with the empty payload and makes no model call, fork 8), and ``None``
        once the finalization call was answered or ended as behaviour. ``ValueError`` when
        ``call`` is neither in progress nor the next, when an earlier call holds no outcome,
        or when the role's configuration holds a setting the request cannot carry."""
        inputs = _inputs(state)
        calls = calls_of(state)
        if call == len(calls) + 1:
            boundary = state.last_position + 1
        elif 1 <= call <= len(calls):
            boundary = calls[call - 1].intents[0].position
        else:
            raise ValueError(f"call {call} is neither in progress nor the next; {len(calls)} held")
        if _abstains(state, boundary):
            return None
        operations = trace_operations(state)
        earlier = tuple(_earlier(state, held, operations) for held in calls if held.ordinal < call)
        entered = state.finalization_entered is not None and state.finalization_entered < boundary
        if _finalization_asked(earlier, state):
            return None
        final = entered or (bool(earlier) and not _reads_in(state, earlier[-1]))
        shown: list[OperationId] = []
        messages = [self._first_message(state, boundary, shown)]
        for held in earlier:
            if held.answered is None:
                continue
            messages.append(_assistant_message(state, held.answered))
            messages.append(self._results_message(state, held.answered, shown))
        if final:
            _append_text(messages[-1], self.assets.text(FINALIZATION))
        body: JsonObject = {
            "system": [{"text": self.assets.text(SYSTEM)}],
            "messages": messages,
            "toolConfig": self._tool_config(final),
            "inferenceConfig": _inference_config(_configuration(inputs, self.role.value)),
        }
        return TurnRequest(self.role.value, body, tuple(shown), final)

    def payload_for(self, state: AttemptState) -> ReviewPayload:
        """The review payload over everything the log holds: empty under a defect or an
        abstention, else the composer's claims over the admitted statements."""
        inputs = _inputs(state)
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

    # --- the messages ----------------------------------------------------------------------

    def _first_message(
        self, state: AttemptState, boundary: int, shown: list[OperationId]
    ) -> JsonObject:
        inputs = _inputs(state)
        context = inputs.context
        opening = self.assets.opening(
            leave_id=str(context.leave_id), now=canonical_json(encode_instant(context.now))
        )
        content: list[JsonObject] = [{"text": opening}, {"text": _skill_list()}]
        for logged in operations_of(state):
            if logged.position >= boundary:
                break
            event = logged.event
            assert isinstance(event, OperationEvent)
            if not isinstance(event.key, PrefetchKey):
                continue
            result = event.resolution
            assert isinstance(result, OperationResult), "a prefetch read is never skipped"
            rendered = render_result(
                result, tool=result.tool, surface=TOOL_SPECIFICATIONS, context=context
            )
            block: JsonObject = {
                "tool": result.tool,
                "arguments": thawed_json(result.arguments),
                "result": rendered.content,
            }
            content.append({"text": canonical_json(block)})
            shown.append(operation_id(event.key))
        return {"role": "user", "content": content}

    def _results_message(
        self, state: AttemptState, answered: AnsweredCall, shown: list[OperationId]
    ) -> JsonObject:
        context = _inputs(state).context
        surface = role_surface(self.role)
        dispositions = {call.id: call.disposition for call in answered.answer.tool_calls}
        held = _held_reads(state, answered.ordinal)
        content: list[JsonObject] = []
        for use in tool_uses(_response_of(state, answered)):
            disposition = dispositions[use.id]
            rendered: RenderedResult
            match disposition:
                case HandledAsBatch(batch=index):
                    rendered = render_fact_result(
                        answered.answer.fact_batches[index], context=context
                    )
                case Unparsed():
                    rendered = render_unparsed(tool=use.name, surface=surface, context=context)
                case Undispatched(reason=reason) if use.id not in held:
                    rendered = render_undispatched(
                        reason, tool=use.name, surface=surface, context=context
                    )
                case _:
                    rendered = _rendered_read(held, use, surface, context, shown)
            content.append(rendered.block(use.id))
        return {"role": "user", "content": content}

    def _tool_config(self, final: bool) -> JsonObject:
        if final:
            return {
                "tools": list(converse_harness_tools()),
                "toolChoice": {"tool": {"name": FACT_TOOL}},
            }
        return {
            "tools": [*converse_tools(self.role), *converse_harness_tools()],
            "toolChoice": {"auto": {}},
        }


# --- Readers -----------------------------------------------------------------------------------


def _inputs(state: AttemptState) -> FrozenInputs:
    inputs = state.inputs
    assert inputs is not None, "a request is built over an admitted attempt"
    return inputs


def _configuration(inputs: FrozenInputs, role: str) -> CallConfiguration:
    configuration = inputs.configuration_of(role)
    if configuration is None:
        raise ValueError(f"{role!r} is not a configured role")
    return configuration


def _inference_config(configuration: CallConfiguration) -> JsonObject:
    config: JsonObject = {}
    for setting in configuration.settings:
        field = INFERENCE_FIELDS.get(setting.name)
        if field is None:
            raise ValueError(f"the setting {setting.name!r} cannot be sent in a Converse request")
        config[field] = thawed_json(setting.value)
    return config


def _skill_list() -> str:
    lines = ["Skill list (id: name):"]
    lines.extend(f"- {skill.id}: {skill.name}" for skill in SKILLS)
    return "\n".join(lines)


def _earlier(
    state: AttemptState, held: CallEvents, operations: tuple[Operation, ...]
) -> EarlierCall:
    """``held`` as a settled call below the request: answered, or ended as behaviour when its
    last dispatch holds an observation that is no complete response. ``ValueError`` when it
    holds no outcome at all, since a call in progress is continued, never followed."""
    if held.last_outcome is None:
        raise ValueError(f"call {held.ordinal} holds no outcome; no request follows it")
    return EarlierCall(held, answer_of(state, held, operations))


def _reads_in(state: AttemptState, earlier: EarlierCall) -> bool:
    """Whether the call's answer holds a read call the loop dispatched or skipped: a call of
    a read tool with an object for its input, under the ``tool_use`` stop (the graph's own
    count), which became an operation or a skip for the cap or an unreachable source. Read
    off the resolutions the log holds for the call, as the results message is, and not off
    the reader's dispositions: those leave a skip unresolved when a later segment wrote it
    (the reader's conservative rule), so the same log would have given a loop request on
    the first process and the finalization on a recovery (the close's review, second
    finding). A call ended as behaviour holds none."""
    if earlier.answered is None:
        return False
    held = _held_reads(state, earlier.events.ordinal)
    return any(
        use.id in held
        for use in tool_uses(_response_of(state, earlier.answered))
        if use.name != FACT_TOOL
    )


def _abstains(state: AttemptState, boundary: int) -> bool:
    """Whether the operations logged below ``boundary`` decide an abstention: the leave not
    returned or the universe not covered, both facts of the prefetch, so a request in
    progress reads the same answer as the first."""
    inputs = _inputs(state)
    operations = tuple(
        op for op in trace_operations(state) if op.position is not None and op.position < boundary
    )
    projection = project_reads(operations, inputs.context.today)
    return abstention_of(projection, leave_of(operations, inputs.context)) is not None


def _finalization_asked(earlier: tuple[EarlierCall, ...], state: AttemptState) -> bool:
    """Whether one of ``earlier`` was the finalization call, answered or ended as behaviour:
    the finalization event lies below its first intent, or the call before it held no read."""
    for index, held in enumerate(earlier):
        first_intent = held.events.intents[0].position
        entered = state.finalization_entered is not None and (
            state.finalization_entered < first_intent
        )
        if entered or (index > 0 and not _reads_in(state, earlier[index - 1])):
            return True
    return False


def _response_of(state: AttemptState, answered: AnsweredCall) -> Mapping[str, object]:
    logged = state.events[answered.position - 1]
    assert logged.position == answered.position
    event = logged.event
    assert isinstance(event, DispatchOutcome) and event.response is not None
    return event.response


def _assistant_message(state: AttemptState, answered: AnsweredCall) -> JsonObject:
    response = cast("Mapping[str, object]", thawed_json(_response_of(state, answered)))
    output = cast("Mapping[str, object]", response["output"])
    return cast(JsonObject, output["message"])


def _held_reads(state: AttemptState, ordinal: int) -> dict[str, OperationEvent]:
    held: dict[str, OperationEvent] = {}
    for logged in operations_of(state):
        event = logged.event
        assert isinstance(event, OperationEvent)
        key: OperationKey = event.key
        if isinstance(key, ModelReadKey) and key.call == ordinal:
            held[key.tool_call] = event
    return held


def _rendered_read(
    held: Mapping[str, OperationEvent],
    use: ToolUse,
    surface: tuple[ToolSpecification, ...],
    context: RunContext,
    shown: list[OperationId],
) -> RenderedResult:
    event = held.get(use.id)
    if event is None:
        raise ValueError(
            f"tool call {use.id} has no logged resolution; a request follows resolved answers"
        )
    resolution = event.resolution
    if isinstance(resolution, OperationResult):
        shown.append(operation_id(event.key))
    else:
        assert isinstance(resolution, OperationSkip)
    return render_result(resolution, tool=use.name, surface=surface, context=context)


def _append_text(message: JsonObject, text: str) -> None:
    content = cast("list[JsonObject]", message["content"])
    content.append({"text": text})


__all__ = ["INFERENCE_FIELDS", "InvestigatorTurns"]
