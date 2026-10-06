"""The log reader: a closed attempt's log to its format 3 export.

The log fixes what happened and publication fixes what evidence can be delivered (the event
log step's ruling on an export that will not construct). The reader folds the transition
function over the log, then builds the export from the state and the frozen inputs alone:
no claim, no segment, no connection, no worker and no graph. Every field of the export is
either held by an event (the frozen inputs, an intent's bound, an outcome's observation,
the settlement the closer wrote) or derived from the events by a function the worker also
runs (the answer by the parser over the response body, the admissions by the gates over
the reads logged before the answer, a dispatch's cost by the pricing, the ending by the
ending function, the segments' last offsets by their events).

Where the export's shape and the log's meet:

- *positions* are the log's, so the exported subset has gaps where an admission, a segment
  boundary or an outside event sat;
- *identifiers* are the events' keys rendered;
- *the answer* of a call whose last dispatch holds a complete response is derived, unless
  the attempt failed at that dispatch's parse or record phase, where the response is kept
  and no answer is invented;
- *a read tool call's disposition* is what the log proves (ruling 7 parts 6 and 7): the
  operation it became; a skip, honoured only when the segment that wrote it also wrote the
  event that made the call next; unreached, when an earlier call of the answer stopped the
  sequence or was never resolved; unresolved otherwise;
- *the claims and the composition* are the review payload the approval request froze, and
  empty under the frozen policy when none was requested;
- *the reservation* is the admitted amount with the settlement the closing event holds.

The export's own constructor checks what it builds; a refusal there is a publication
incident, recorded apart from the attempt's log, and never changes the log or the ending.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from leaveimpact.agent.answer_parse import (
    FACT_TOOL,
    Resolved,
    parse_answer,
    reported_usage,
    tool_uses,
)
from leaveimpact.agent.fact_entries import refused_by
from leaveimpact.agent.log_ending import approval_of, ending_of
from leaveimpact.agent.log_events import (
    ApprovalRequested,
    CountOutcomeLogged,
    DispatchIntent,
    DispatchOutcome,
    HarnessReadKey,
    LoggedEvent,
    ModelReadKey,
    OperationEvent,
    OperationResult,
    OperationSkip,
    PrefetchKey,
    call_id,
    count_id,
    operation_id,
)
from leaveimpact.agent.log_transition import (
    AttemptState,
    CallEvents,
    CountEvents,
    calls_of,
    counts_of,
    operations_of,
)
from leaveimpact.core.admission import admit, run_lexicon
from leaveimpact.core.claims import Claim
from leaveimpact.core.counting_operations import CountingOperation
from leaveimpact.core.input_bound import CountResult
from leaveimpact.core.model_calls import (
    UNRESOLVED_RULE,
    Answer,
    AsOperation,
    Attribution,
    AttributionKind,
    CompleteResponse,
    Dispatch,
    ModelCall,
    NoRecordedOutcome,
    RequestIdentity,
    Undispatched,
)
from leaveimpact.core.pricing import aggregate_usage, cost_of_reported, run_cost
from leaveimpact.core.read_condition import observed_condition
from leaveimpact.core.read_projection import project_reads
from leaveimpact.core.run_ending import Composition, DispatchPhase, DispatchSite, Reservation
from leaveimpact.core.run_export import EXPORT_FORMAT_VERSION, RunExport, RunTrace
from leaveimpact.core.run_record import Failure, RunRecord
from leaveimpact.core.run_timing import Segment, Stamp, Timing
from leaveimpact.core.run_trace import (
    Cost,
    DefectOutcome,
    HarnessOrigin,
    ModelOrigin,
    Operation,
    Origin,
    PrefetchOrigin,
)
from leaveimpact.core.stated import Admission, StatedFact


def export_of(state: AttemptState) -> RunExport:
    """The format 3 export of the closed attempt ``state`` holds; ``ValueError`` while it is
    open, when the frozen parser is not this code's, or when the export's constructor
    refuses what the log states."""
    inputs = state.inputs
    closed = state.closed
    if inputs is None or closed is None:
        raise ValueError("an export is built from a closed attempt")
    if inputs.parser != refused_by():
        raise ValueError(
            f"the admission froze the parser {inputs.parser.parser!r} with schema "
            f"{inputs.parser.schema_digest[:12]}; this reader's is {refused_by().parser!r}"
        )
    ending = ending_of(state)
    operations = tuple(
        _operation_of(logged) for logged in operations_of(state) if _is_result(logged)
    )
    calls = tuple(
        _call_of(state, call, operations, failure=ending.failure) for call in calls_of(state)
    )
    counts = tuple(_count_of(count) for count in counts_of(state))
    claims, composition = _payload_of(state)
    record = RunRecord(
        observed_condition=observed_condition(operations).condition,
        outage=inputs.outage,
        corpus_level=inputs.corpus_level,
        preregistration_commit=inputs.preregistration_commit,
        attribution_table=inputs.attribution_table,
        model_configurations=inputs.model_configurations,
        pricing_selections=inputs.pricing_selections,
        prompt_digests=inputs.prompt_digests,
        tool_surface_digests=inputs.tool_surface_digests,
        system=inputs.system,
        retrieval=inputs.retrieval,
        prefetch_rule=inputs.prefetch_rule,
        caps=inputs.caps,
        status=ending.status,
        failure=ending.failure,
        abandonment=ending.abandonment,
        timing=_timing_of(state),
        usage=aggregate_usage(calls),
        cost=run_cost(calls),
        reservation=_reservation_of(state),
        approval=approval_of(state),
        pricing=inputs.pricing,
    )
    return RunExport(
        EXPORT_FORMAT_VERSION,
        inputs.run_id,
        inputs.attempt,
        inputs.context,
        record,
        RunTrace(calls, operations, claims, composition, counts, state.finalization_entered),
    )


# --- Timing and the reservation --------------------------------------------------------------


def _timing_of(state: AttemptState) -> Timing:
    closed = state.closed
    assert closed is not None
    return Timing(
        tuple(
            Segment(segment.number, segment.harness, segment.last_offset_ms, segment.ended)
            for segment in state.segments
        ),
        state.events[0].timestamp,
        closed.timestamp,
        _stamp_of(state.approval_requested),
        _stamp_of(state.resumed),
    )


def _stamp_of(logged: LoggedEvent | None) -> Stamp | None:
    if logged is None:
        return None
    stamp = logged.stamp
    assert stamp is not None
    return Stamp(stamp.segment, stamp.offset_ms, logged.position)


def _reservation_of(state: AttemptState) -> Reservation | None:
    inputs, closing = state.inputs, state.closing
    assert inputs is not None and closing is not None
    if inputs.reservation_pico_usd is None:
        return None
    settlement = closing.settlement
    assert settlement is not None
    return Reservation(
        inputs.reservation_pico_usd,
        settlement.state,
        settlement.kept_reason,
        settlement.ledger_revision,
        settlement.charged_pico_usd,
    )


def _payload_of(state: AttemptState) -> tuple[tuple[Claim, ...], Composition]:
    inputs = state.inputs
    assert inputs is not None
    request = state.approval_requested
    if request is None:
        return (), Composition(inputs.claim_author, inputs.composing_policy, (), ())
    asked = request.event
    assert isinstance(asked, ApprovalRequested)
    return asked.claims, asked.composition


# --- Operations and counts -------------------------------------------------------------------


def _is_result(logged: LoggedEvent) -> bool:
    event = logged.event
    assert isinstance(event, OperationEvent)
    return isinstance(event.resolution, OperationResult)


def _operation_of(logged: LoggedEvent) -> Operation:
    event = logged.event
    assert isinstance(event, OperationEvent)
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


def _count_of(count: CountEvents) -> CountingOperation:
    start_stamp = count.start.stamp
    assert start_stamp is not None
    if count.outcome is None:
        outcome, reading, position = NoRecordedOutcome(), CountResult.UNRESOLVED, None
    else:
        logged = count.outcome.event
        assert isinstance(logged, CountOutcomeLogged)
        outcome, reading, position = logged.outcome, logged.reading, count.outcome.position
    return CountingOperation(
        count_id(count.key),
        count.key.method,
        count.key.counting_identifier,
        count.key.request_digest,
        start_stamp.segment,
        count.start.position,
        position,
        outcome,
        reading,
    )


# --- Model calls -----------------------------------------------------------------------------


def _call_of(
    state: AttemptState,
    call: CallEvents,
    operations: tuple[Operation, ...],
    *,
    failure: Failure | None,
) -> ModelCall:
    inputs = state.inputs
    assert inputs is not None
    identifier = call_id(call.ordinal)
    dispatches = tuple(_dispatch_of(state, call, intent) for intent in call.intents)
    last = call.last_outcome
    answer: Answer | None = None
    if last is not None:
        held = last.event
        assert isinstance(held, DispatchOutcome)
        if isinstance(held.observation, CompleteResponse) and not _parse_failed(
            failure, identifier, call.last_number
        ):
            assert held.response is not None
            answer = parse_answer(
                held.response,
                resolved=_resolved_of(state, call, last),
                stopping=_stopping_of(state, call),
                gate=_gate_before(state, last.position, operations),
            )
    return ModelCall(identifier, call.role, dispatches, answer)


def _parse_failed(failure: Failure | None, call: str, number: int) -> bool:
    if failure is None:
        return False
    held = failure.site
    return (
        isinstance(held, DispatchSite)
        and held.model_call == call
        and held.dispatch == number
        and held.phase in (DispatchPhase.PARSE, DispatchPhase.RECORD)
    )


def _dispatch_of(state: AttemptState, call: CallEvents, intent: LoggedEvent) -> Dispatch:
    inputs = state.inputs
    assert inputs is not None
    asked = intent.event
    assert isinstance(asked, DispatchIntent)
    stamp = intent.stamp
    assert stamp is not None
    logged = call.outcomes.get(asked.number)
    selection = inputs.selection_of(asked.role)
    assert selection is not None
    if logged is None:
        observation, attribution = (
            NoRecordedOutcome(),
            Attribution(AttributionKind.UNRESOLVED, UNRESOLVED_RULE),
        )
        usage, cost, zero_cost_rule, sent_body_digest, outcome_position = (
            None,
            None,
            None,
            None,
            None,
        )
    else:
        held = logged.event
        assert isinstance(held, DispatchOutcome)
        observation, attribution = held.observation, held.attribution
        usage = None if held.response is None else reported_usage(held.response)
        zero_cost_rule, sent_body_digest, outcome_position = (
            held.zero_cost_rule,
            held.sent_body_digest,
            logged.position,
        )
        if zero_cost_rule is not None:
            cost = Cost(0, True)
        elif usage is not None:
            cost = cost_of_reported(usage, selection, inputs.pricing)
        else:
            cost = None
    return Dispatch(
        number=asked.number,
        segment=stamp.segment,
        intent_position=intent.position,
        outcome_position=outcome_position,
        request=RequestIdentity(
            asked.request_digest,
            asked.operation,
            asked.requested_profile,
            asked.client_region,
            sent_body_digest,
        ),
        input_reads=asked.input_reads,
        observation=observation,
        attribution=attribution,
        usage=usage,
        cost=cost,
        zero_cost_rule=zero_cost_rule,
        allocation=asked.allocation_pico_usd,
        allocation_tokens=asked.allocation_tokens,
        bound=asked.bound,
        output_maximum=asked.output_maximum,
    )


def _resolutions_of(state: AttemptState, call: CallEvents) -> dict[str, LoggedEvent]:
    held: dict[str, LoggedEvent] = {}
    for logged in operations_of(state):
        event = logged.event
        assert isinstance(event, OperationEvent)
        if isinstance(event.key, ModelReadKey) and event.key.call == call.ordinal:
            held[event.key.tool_call] = logged
    return held


def _resolved_of(
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
        event = logged.event
        assert isinstance(event, OperationEvent)
        if isinstance(event.resolution, OperationResult):
            resolved[use.id] = AsOperation(operation_id(event.key))
        elif _same_segment(logged, made_next_by):
            skip = event.resolution
            assert isinstance(skip, OperationSkip)
            resolved[use.id] = Undispatched(skip.reason)
        made_next_by = logged
    return resolved


def _stopping_of(state: AttemptState, call: CallEvents) -> frozenset[str]:
    stopping: set[str] = set()
    for tool_call, logged in _resolutions_of(state, call).items():
        event = logged.event
        assert isinstance(event, OperationEvent)
        resolution = event.resolution
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


def _gate_before(
    state: AttemptState, position: int, operations: tuple[Operation, ...]
) -> Callable[[StatedFact], Admission]:
    """The gates over the reads logged strictly before ``position``."""
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


__all__ = ["export_of"]
