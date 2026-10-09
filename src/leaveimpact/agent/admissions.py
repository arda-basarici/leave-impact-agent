"""The derived admissions: from an attempt's log to what each complete answer carried and what
of it the gates let in, one function for the export and for the turns.

An admission is decided over the reads logged strictly before the answer that carried the
statement (the event log step's ruling on tool calls, part 9; the composer group's third
point), and it is derived, never stored: the log holds the response as it arrived, and
whoever needs the admissions folds the gates over the same prefix. Two readers need them.
The log reader exports every answer with its batches, and the investigator's turns answer
a fact call with its batch's admissions and compose the review payload from the admitted
statements of every answer. If each derived them on its own the export and the composed
claims could drift apart on a detail nobody compared (the step 6 lesson on one canonical
form), so the derivation lives here and both call it (the graph step, fork 7).

What is derived, per logical call with a complete response: the operations as the trace
holds them, with their positions; the gate over the operations logged strictly below the
outcome's position; each read tool call's disposition the log proves (a result always; a
skip only when the segment that wrote it also wrote the event that made the call next; the
rest the parser's rule); and the answer, parsed under that gate. ``admitted_statements``
flattens every answer's admitted facts in outcome order, then batch and entry order: the
order the composer is given, the order the answers were logged and never the order the
calls were asked in.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from leaveimpact.agent.answer_parse import FACT_TOOL, Resolved, parse_answer, tool_uses
from leaveimpact.agent.log_events import (
    DispatchOutcome,
    HarnessReadKey,
    LoggedEvent,
    ModelReadKey,
    OperationEvent,
    OperationResult,
    OperationSkip,
    PrefetchKey,
    call_id,
    operation_id,
)
from leaveimpact.agent.log_transition import AttemptState, CallEvents, calls_of, operations_of
from leaveimpact.core.admission import admit, run_lexicon
from leaveimpact.core.model_calls import (
    Answer,
    AsOperation,
    CompleteResponse,
    ParsedBatch,
    Undispatched,
)
from leaveimpact.core.read_projection import project_reads
from leaveimpact.core.run_trace import (
    DefectOutcome,
    HarnessOrigin,
    ModelOrigin,
    Operation,
    Origin,
    PrefetchOrigin,
)
from leaveimpact.core.stated import Admission, Admitted, StatedFact

type Gate = Callable[[StatedFact], Admission]


@dataclass(frozen=True, slots=True)
class AnsweredCall:
    """One logical call whose last dispatch holds a complete response: its ordinal, the
    position of that outcome, and the answer parsed under the gate over the reads below it."""

    ordinal: int
    position: int
    answer: Answer


# --- The operations --------------------------------------------------------------------------


def trace_operations(state: AttemptState) -> tuple[Operation, ...]:
    """Every operation the log holds a result for, as the trace holds it, in position order;
    a skip is no operation."""
    return tuple(
        _operation_of(logged)
        for logged in operations_of(state)
        if isinstance(_event(logged).resolution, OperationResult)
    )


def _operation_of(logged: LoggedEvent) -> Operation:
    event = _event(logged)
    result = event.resolution
    assert isinstance(result, OperationResult)
    return Operation(
        operation_id(event.key),
        _origin_of(event.key),
        result.tool,
        result.source,
        result.arguments,
        result.outcome,
        logged.position,
    )


def _origin_of(key: PrefetchKey | ModelReadKey | HarnessReadKey) -> Origin:
    match key:
        case PrefetchKey():
            return PrefetchOrigin()
        case ModelReadKey():
            return ModelOrigin(call_id(key.call))
        case HarnessReadKey():
            return HarnessOrigin(key.policy)


def _event(logged: LoggedEvent) -> OperationEvent:
    event = logged.event
    assert isinstance(event, OperationEvent)
    return event


# --- The gate --------------------------------------------------------------------------------


def gate_before(state: AttemptState, position: int, operations: tuple[Operation, ...]) -> Gate:
    """The gates over the reads logged strictly before ``position``, among ``operations``
    (``trace_operations`` of ``state``, passed in so one call projects them once)."""
    inputs = state.inputs
    assert inputs is not None
    before = tuple(
        operation
        for operation in operations
        if operation.position is not None and operation.position < position
    )
    reads = project_reads(before, inputs.context.today)
    lexicon = run_lexicon(reads)
    return lambda stated: admit(stated, reads, lexicon)


# --- The answers -----------------------------------------------------------------------------


def answer_of(
    state: AttemptState, call: CallEvents, operations: tuple[Operation, ...]
) -> AnsweredCall | None:
    """``call``'s answer under the gate and the dispositions the log proves, or ``None`` when
    its last dispatch holds no complete response."""
    last = call.last_outcome
    if last is None:
        return None
    held = last.event
    assert isinstance(held, DispatchOutcome)
    if not isinstance(held.observation, CompleteResponse):
        return None
    assert held.response is not None
    answer = parse_answer(
        held.response,
        resolved=resolved_of(state, call, last),
        stopping=stopping_of(state, call),
        gate=gate_before(state, last.position, operations),
    )
    return AnsweredCall(call.ordinal, last.position, answer)


def answered_calls(state: AttemptState) -> tuple[AnsweredCall, ...]:
    """Every logical call with a complete response, in ordinal order, which is outcome order
    under sequential dispatch."""
    operations = trace_operations(state)
    answered = (answer_of(state, call, operations) for call in calls_of(state))
    return tuple(call for call in answered if call is not None)


def admitted_statements(state: AttemptState) -> tuple[StatedFact, ...]:
    """The statements the gates admitted, in the order their answers were logged, then batch
    and entry order: what the composer is given."""
    return tuple(
        entry.fact
        for call in answered_calls(state)
        for batch in call.answer.fact_batches
        if isinstance(batch, ParsedBatch)
        for entry in batch.entries
        if isinstance(entry, Admitted)
    )


# --- The dispositions ------------------------------------------------------------------------


def _resolutions_of(state: AttemptState, call: CallEvents) -> dict[str, LoggedEvent]:
    held: dict[str, LoggedEvent] = {}
    for logged in operations_of(state):
        event = _event(logged)
        if isinstance(event.key, ModelReadKey) and event.key.call == call.ordinal:
            held[event.key.tool_call] = logged
    return held


def resolved_of(
    state: AttemptState, call: CallEvents, outcome: LoggedEvent
) -> Mapping[str, Resolved]:
    """Each read tool call's resolution the log proves: a result always; a skip only when
    the segment that wrote it also wrote the event that made the call next."""
    held = _resolutions_of(state, call)
    response = _response_of(outcome)
    resolved: dict[str, Resolved] = {}
    made_next_by = outcome
    for use in tool_uses(response):
        if use.name == FACT_TOOL:
            continue
        logged = held.get(use.id)
        if logged is None:
            continue
        event = _event(logged)
        if isinstance(event.resolution, OperationResult):
            resolved[use.id] = AsOperation(operation_id(event.key))
        elif _same_segment(logged, made_next_by):
            skip = event.resolution
            assert isinstance(skip, OperationSkip)
            resolved[use.id] = Undispatched(skip.reason)
        made_next_by = logged
    return resolved


def stopping_of(state: AttemptState, call: CallEvents) -> frozenset[str]:
    """The ids of ``call``'s read tool calls whose operation holds a durable stopping result."""
    stopping: set[str] = set()
    for tool_call, logged in _resolutions_of(state, call).items():
        resolution = _event(logged).resolution
        if isinstance(resolution, OperationResult) and isinstance(
            resolution.outcome, DefectOutcome
        ):
            stopping.add(tool_call)
    return frozenset(stopping)


def _same_segment(first: LoggedEvent, second: LoggedEvent) -> bool:
    one, two = first.stamp, second.stamp
    return one is not None and two is not None and one.segment == two.segment


def _response_of(outcome: LoggedEvent) -> Mapping[str, object]:
    held = outcome.event
    assert isinstance(held, DispatchOutcome) and held.response is not None
    return held.response


__all__ = [
    "AnsweredCall",
    "Gate",
    "admitted_statements",
    "answer_of",
    "answered_calls",
    "gate_before",
    "resolved_of",
    "stopping_of",
    "trace_operations",
]
