"""The audit trail: a closed attempt's export as the run's second page states it, everything
the run did in the order it did it, built by pure functions over the export.

The report says what the run concluded; the trail says what it did, so that every evidence
item on the report links to the operation that read it and every claim can be checked
against the record (the demo milestone's entry ruling on the trail). It shows the
operations with their tool, arguments, source and outcome in brief; the model calls with
the configuration they ran under, each dispatch's request identity, what it was shown, the
observation and how the registered table read it, its usage with the anomalies the reading
found, its cost and its count under the registered rule, and the bound it was authorized
under; the answer's tool calls with what became of each and the fact batches with every
statement, admitted or refused and why, and every input no statement could be made of,
whole; the counting operations; the ledger's figures; the approval with its two stamps; the
composition's placements and exclusions; and the ending the report opens with.

Three amounts stay apart (the report step's external read): the observed model spend, the
sum of what the dispatches were priced at, complete or a floor; the ledger's charge, which
the settlement wrote; and the retained liability, the allocations held for sends that were
never priced whole, their difference. A floor is shown as one. "Admitted" on a statement
means it passed the fact-admission rules and says nothing about the key; a quotation is
the model's, read from the recorded source. Every anchor the report links to is minted
here: an operation by its position, a model call and a counting operation by their ids.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import assert_never

from leaveimpact.app.amounts import cost_label, counter_label, dollars, token_label
from leaveimpact.app.public import PublicReplay
from leaveimpact.app.report import EndingView, Instants, ReportHeader, ending_view, header_view
from leaveimpact.core.claims import ClaimType
from leaveimpact.core.counting_operations import (
    CountClientError,
    Counted,
    CountingOperation,
    CountLocalError,
    CountServiceError,
)
from leaveimpact.core.model_calls import (
    AsOperation,
    BrokenStream,
    ClientError,
    CompleteResponse,
    Dispatch,
    HandledAsBatch,
    MalformedBatch,
    ModelCall,
    NoRecordedOutcome,
    ParsedBatch,
    RefusedBeforeSend,
    ServiceError,
    ToolCall,
    Undispatched,
    Unparsed,
    UnresolvedToolCall,
)
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_trace import (
    AbsentOutcome,
    DefectOutcome,
    HarnessOrigin,
    ModelOrigin,
    Operation,
    PrefetchOrigin,
    RecordOutcome,
    RecordsOutcome,
    RefusedCallOutcome,
    UnreachableOutcome,
    thawed_json,
)
from leaveimpact.core.stated import Admitted, PlacementState, Refused, RefusedInput, StatedFact
from leaveimpact.core.token_counting import count_tokens
from leaveimpact.core.values import FactValue, Requirement
from leaveimpact.core.worldtime import DateSpan, InstantSpan

# --- The view ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Moment:
    """A position in the attempt's one event order and the log's accept instant for it."""

    position: int
    recorded_at: datetime | None


@dataclass(frozen=True, slots=True)
class OperationView:
    """One read: who asked, what was asked of which source, and what came back in brief."""

    anchor: str
    at: Moment
    id: str
    origin: str
    origin_anchor: str | None
    tool: str
    source: str
    arguments: str
    outcome: str
    records: tuple[str, ...]
    failed: bool


@dataclass(frozen=True, slots=True)
class StatementView:
    """One entry of a fact batch: a statement admitted or refused, or an input refused."""

    kind: str
    summary: str
    quote: str | None
    target_span: str | None
    reason: str | None
    detail: str | None
    raw: str | None
    excluded: str | None


@dataclass(frozen=True, slots=True)
class BatchView:
    """A fact batch as parsed, or the raw payload the parser could not read."""

    index: int
    entries: tuple[StatementView, ...]
    malformed_raw: str | None
    refused_by: str | None


@dataclass(frozen=True, slots=True)
class ToolCallView:
    """A tool call the model made and what became of it."""

    id: str
    name: str
    disposition: str
    anchor: str | None
    raw: str | None


@dataclass(frozen=True, slots=True)
class AnswerView:
    """What a complete response carried once parsed."""

    text_present: bool
    tool_calls: tuple[ToolCallView, ...]
    batches: tuple[BatchView, ...]


@dataclass(frozen=True, slots=True)
class DispatchView:
    """One permitted send: its identity, what it was shown, what arrived and how it was read,
    what it used and cost, and the bound it was authorized under."""

    number: int
    segment: int
    intent: Moment
    outcome: Moment | None
    request: str
    shown: tuple[Moment, ...]
    observation: str
    attribution: str
    usage: tuple[str, ...]
    anomalies: tuple[str, ...]
    cost: str
    tokens: str
    zero_cost_rule: str | None
    allocation: str
    bound: str
    bound_anchor: str
    output_maximum: int


@dataclass(frozen=True, slots=True)
class CallView:
    """One logical model call with its dispatches and its answer."""

    id: str
    anchor: str
    role: str
    configuration: str
    state: str
    dispatches: tuple[DispatchView, ...]
    answer: AnswerView | None


@dataclass(frozen=True, slots=True)
class CountView:
    """One counting request and its reading."""

    id: str
    anchor: str
    method: str
    counting_identifier: str
    request_digest: str
    segment: int
    start: Moment
    outcome_at: Moment | None
    outcome: str
    reading: str


@dataclass(frozen=True, slots=True)
class ChargesView:
    """The ledger's figures, three amounts apart, and the run's usage aggregate."""

    reserved: str | None
    state: str | None
    kept_reason: str | None
    ledger_revision: int | None
    observed: str
    known: str
    charged: str | None
    retained: str | None
    usage: tuple[str, ...]
    calls: int
    dispatches: int


@dataclass(frozen=True, slots=True)
class ApprovalView:
    """The approval as it stood at termination, with the two stamps when they were logged."""

    state: str
    approver: str | None
    payload_digest: str | None
    requested: Moment | None
    resumed: Moment | None


@dataclass(frozen=True, slots=True)
class CompositionView:
    """Who composed the claims under which policy, and what the composing placed and left out."""

    author: str
    policy: str
    placements: tuple[str, ...]
    exclusions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TrailView:
    """The whole second page."""

    header: ReportHeader
    ending: EndingView
    segments: tuple[str, ...]
    finalization_entered: Moment | None
    operations: tuple[OperationView, ...]
    calls: tuple[CallView, ...]
    counts: tuple[CountView, ...]
    charges: ChargesView
    approval: ApprovalView
    composition: CompositionView


# --- Anchors ---------------------------------------------------------------------------


def operation_anchor(position: int) -> str:
    """The anchor of the operation at ``position``; the report's evidence links use it."""
    return f"op-{position}"


def call_anchor(call_id: str) -> str:
    return f"call-{call_id}"


def count_anchor(count_id: str) -> str:
    return f"count-{count_id}"


# --- The pieces ----------------------------------------------------------------------


def _moment(position: int, instants: Instants) -> Moment:
    return Moment(position, instants.get(position))


def _json(value: object) -> str:
    return json.dumps(thawed_json(value), sort_keys=True, ensure_ascii=False)


def _short(digest: str) -> str:
    return f"{digest[:12]}…" if len(digest) > 12 else digest


def _record_label(kind: str, id: str) -> str:
    return f"{kind} {id}"


def _operation(operation: Operation, instants: Instants) -> OperationView:
    assert operation.position is not None, "an exported operation holds its position"
    origin = operation.origin
    origin_anchor: str | None = None
    match origin:
        case PrefetchOrigin():
            who = "the frozen prefetch"
        case HarnessOrigin():
            who = f"the harness under {origin.policy}"
        case ModelOrigin():
            who = f"model call {origin.model_call}"
            origin_anchor = call_anchor(origin.model_call)
        case _:
            assert_never(origin)
    outcome = operation.outcome
    records: tuple[str, ...] = ()
    failed = False
    match outcome:
        case RecordOutcome():
            brief = "one record"
            records = (_record_label(outcome.record.kind.value, outcome.record.ref.id),)
        case AbsentOutcome():
            brief = "no such record (evidence of absence)"
        case RecordsOutcome():
            count = len(outcome.records)
            brief = f"{count} record{'' if count == 1 else 's'}"
            records = tuple(_record_label(r.kind.value, r.ref.id) for r in outcome.records)
        case UnreachableOutcome():
            brief = f"{outcome.source.value} unreachable: {outcome.reason}"
            failed = True
        case DefectOutcome():
            brief = f"malformed record at {outcome.locator}: {outcome.reason}"
            failed = True
        case RefusedCallOutcome():
            brief = f"call refused before any source was asked: {outcome.reason}"
        case _:
            assert_never(outcome)
    return OperationView(
        anchor=operation_anchor(operation.position),
        at=_moment(operation.position, instants),
        id=operation.id,
        origin=who,
        origin_anchor=origin_anchor,
        tool=operation.tool,
        source="no source" if operation.source is None else operation.source.value,
        arguments=_json(operation.arguments),
        outcome=brief,
        records=records,
        failed=failed,
    )


def _value(value: FactValue) -> str:
    match value:
        case EntityRef():
            return value.id
        case str():
            return value
        case DateSpan() | InstantSpan():
            return f"{value.start.isoformat()} to {value.end.isoformat()}"
        case Requirement():
            return f"a requirement of at least {value.count} with {len(value.criteria)} criteria"
        case date():
            return value.isoformat()
        case _:
            assert_never(value)


def _statement_summary(fact: StatedFact) -> str:
    return (
        f"{fact.predicate.value} of {fact.subject.id} is {_value(fact.value)}, read from "
        f"{fact.carrier.id}"
    )


def _entry(
    entry: Admitted | Refused | RefusedInput, excluded: dict[StatedFact, str]
) -> StatementView:
    match entry:
        case Admitted():
            return StatementView(
                "admitted",
                _statement_summary(entry.fact),
                entry.fact.quote,
                entry.fact.target_span,
                None,
                None,
                None,
                excluded.get(entry.fact),
            )
        case Refused():
            return StatementView(
                "refused",
                _statement_summary(entry.fact),
                entry.fact.quote,
                entry.fact.target_span,
                entry.reason.value.replace("_", " "),
                entry.detail,
                None,
                None,
            )
        case RefusedInput():
            return StatementView(
                "refused input",
                "no statement could be made of this entry",
                None,
                None,
                entry.reason.value.replace("_", " "),
                entry.detail,
                entry.raw,
                None,
            )
        case _:
            assert_never(entry)


def _tool_call(call: ToolCall, export: RunExport) -> ToolCallView:
    disposition = call.disposition
    anchor: str | None = None
    raw: str | None = None
    match disposition:
        case AsOperation():
            operation = export.trace.operation(disposition.operation)
            became = f"became operation {disposition.operation}"
            if operation is not None and operation.position is not None:
                anchor = operation_anchor(operation.position)
        case HandledAsBatch():
            became = f"handled by the harness as fact batch {disposition.batch}"
        case Unparsed():
            became = f"arguments unparsed, refused by {disposition.refused_by.parser}"
            raw = disposition.raw_arguments
        case Undispatched():
            became = f"never dispatched: {disposition.reason.value.replace('_', ' ')}"
        case UnresolvedToolCall():
            became = "unresolved: no result was logged and nothing shows it was never reached"
        case _:
            assert_never(disposition)
    return ToolCallView(call.id, call.name, became, anchor, raw)


def _observation(dispatch: Dispatch) -> str:
    observation = dispatch.observation
    match observation:
        case CompleteResponse():
            retries = (
                "" if not observation.sdk_retries else f", {observation.sdk_retries} SDK retries"
            )
            return (
                f"complete response, stop reason {observation.stop_reason}, "
                f"{observation.provider_latency_ms} ms{retries}"
            )
        case BrokenStream():
            return f"broken stream: {observation.reason}"
        case ServiceError():
            return (
                f"service error {observation.http_status} {observation.code} "
                f"({observation.message_signature})"
            )
        case ClientError():
            return f"client error, {observation.kind.value}: {observation.reason}"
        case RefusedBeforeSend():
            return f"refused before send: {observation.reason}"
        case NoRecordedOutcome():
            return "no outcome recorded: zero sends or one, and nothing says which"
        case _:
            assert_never(observation)


def _dispatch(dispatch: Dispatch, export: RunExport, instants: Instants) -> DispatchView:
    usage = dispatch.usage
    counters: tuple[str, ...] = ()
    anomalies: tuple[str, ...] = ()
    tokens = "not counted"
    if usage is not None:
        counters = tuple(
            counter_label(name, value, 1, 1) for name, value in usage.counters.counters
        )
        anomalies = tuple(
            f"{anomaly.kind.value.replace('_', ' ')} in {anomaly.field}"
            for anomaly in usage.anomalies
        )
        # The configuration alone proves which absent counters mean zero; the page shows the
        # floor the counting rule gives with nothing assumed.
        tokens = token_label(count_tokens(export.record.caps.counting_rule, usage, frozenset()))
    shown: list[Moment] = []
    for read in dispatch.input_reads:
        operation = export.trace.operation(read)
        if operation is not None and operation.position is not None:
            shown.append(_moment(operation.position, instants))
    request = dispatch.request
    bound = dispatch.bound
    return DispatchView(
        number=dispatch.number,
        segment=dispatch.segment,
        intent=_moment(dispatch.intent_position, instants),
        outcome=(
            None
            if dispatch.outcome_position is None
            else _moment(dispatch.outcome_position, instants)
        ),
        request=(
            f"{request.operation} to {request.requested_profile} in {request.client_region}, "
            f"request digest {_short(request.request_digest)}"
        ),
        shown=tuple(shown),
        observation=_observation(dispatch),
        attribution=(
            f"read as {dispatch.attribution.kind.value} by the rule {dispatch.attribution.rule}"
        ),
        usage=counters,
        anomalies=anomalies,
        cost=cost_label(dispatch.cost),
        tokens=tokens,
        zero_cost_rule=dispatch.zero_cost_rule,
        allocation=f"{dollars(dispatch.allocation)} and {dispatch.allocation_tokens:,} tokens",
        bound=(
            f"input bounded at {bound.input_tokens:,} tokens by {bound.method.name} v"
            f"{bound.method.version} against {bound.counting_identifier}"
        ),
        bound_anchor=count_anchor(bound.evidence),
        output_maximum=dispatch.output_maximum,
    )


def _call(call: ModelCall, export: RunExport, instants: Instants) -> CallView:
    configured = dict(export.record.model_configurations).get(call.role)
    if configured is None:
        configuration = "no recorded configuration"
    else:
        settings = ", ".join(f"{s.name}={_json(s.value)}" for s in configured.settings)
        configuration = f"{configured.model_id}" + (f" with {settings}" if settings else "")
    excluded = {
        left_out.fact: left_out.reason.value.replace("_", " ")
        for left_out in export.trace.composition.exclusions
    }
    answer: AnswerView | None = None
    if call.answer is not None:
        batches: list[BatchView] = []
        for index, batch in enumerate(call.answer.fact_batches):
            match batch:
                case ParsedBatch():
                    batches.append(
                        BatchView(
                            index, tuple(_entry(e, excluded) for e in batch.entries), None, None
                        )
                    )
                case MalformedBatch():
                    batches.append(BatchView(index, (), batch.raw, batch.refused_by.parser))
                case _:
                    assert_never(batch)
        answer = AnswerView(
            call.answer.text_present,
            tuple(_tool_call(t, export) for t in call.answer.tool_calls),
            tuple(batches),
        )
    return CallView(
        id=call.id,
        anchor=call_anchor(call.id),
        role=call.role,
        configuration=configuration,
        state=call.state.value.replace("_", " "),
        dispatches=tuple(_dispatch(d, export, instants) for d in call.dispatches),
        answer=answer,
    )


def _count(count: CountingOperation, instants: Instants) -> CountView:
    outcome = count.outcome
    match outcome:
        case Counted():
            brief = f"counted {outcome.input_tokens:,} input tokens in {outcome.latency_ms} ms"
        case CountServiceError():
            brief = (
                f"service error {outcome.http_status} {outcome.code} "
                f"({outcome.message_signature}) after {outcome.latency_ms} ms"
            )
        case CountClientError():
            brief = f"client error, {outcome.kind.value}, after {outcome.latency_ms} ms"
        case CountLocalError():
            brief = f"local error: {outcome.exception_type}"
        case NoRecordedOutcome():
            brief = "no outcome recorded"
        case _:
            assert_never(outcome)
    return CountView(
        id=count.id,
        anchor=count_anchor(count.id),
        method=f"{count.method.name} v{count.method.version}",
        counting_identifier=count.counting_identifier,
        request_digest=_short(count.request_digest),
        segment=count.segment,
        start=_moment(count.start_position, instants),
        outcome_at=(
            None if count.outcome_position is None else _moment(count.outcome_position, instants)
        ),
        outcome=brief,
        reading=count.reading.value,
    )


def _charges(export: RunExport) -> ChargesView:
    record = export.record
    reservation = record.reservation
    known = sum(
        dispatch.cost.pico_usd for dispatch in export.trace.dispatches if dispatch.cost is not None
    )
    usage = record.usage
    return ChargesView(
        reserved=None if reservation is None else dollars(reservation.pico_usd),
        state=None if reservation is None else reservation.state.value,
        kept_reason=(
            None
            if reservation is None or reservation.kept_reason is None
            else reservation.kept_reason.value.replace("_", " ")
        ),
        ledger_revision=None if reservation is None else reservation.ledger_revision,
        observed=cost_label(record.cost),
        known=dollars(known),
        charged=None if reservation is None else dollars(reservation.charged_pico_usd),
        retained=(
            None if reservation is None else dollars(max(reservation.charged_pico_usd - known, 0))
        ),
        usage=tuple(
            counter_label(name, value, reported, usage.dispatches)
            for name, value, reported in usage.counters
        ),
        calls=usage.model_calls,
        dispatches=usage.dispatches,
    )


def _approval(export: RunExport, instants: Instants) -> ApprovalView:
    approval = export.record.approval
    timing = export.record.timing
    return ApprovalView(
        state=approval.state.value.replace("_", " "),
        approver=None if approval.approver is None else approval.approver.value,
        payload_digest=None if approval.payload_digest is None else _short(approval.payload_digest),
        requested=(
            None
            if timing.approval_requested is None
            else _moment(timing.approval_requested.position, instants)
        ),
        resumed=(
            None
            if timing.approval_resumed is None
            else _moment(timing.approval_resumed.position, instants)
        ),
    )


def _composition(export: RunExport) -> CompositionView:
    composition = export.trace.composition
    placements: list[str] = []
    for placement in composition.placements:
        where = placement.placement
        match where.state:
            case PlacementState.PLACED:
                bound = f"placed on {where.artifact.id if where.artifact else 'nothing'}"
            case PlacementState.UNPLACED:
                bound = "unplaced: no read title equals the span"
            case PlacementState.AMBIGUOUS:
                bound = f"ambiguous among {', '.join(ref.id for ref in where.among)}"
            case _:
                assert_never(where.state)
        span = placement.fact.target_span or ""
        placements.append(f"the requirement of {placement.fact.carrier.id} on “{span}”: {bound}")
    exclusions = tuple(
        f"{_statement_summary(left_out.fact)}: {left_out.reason.value.replace('_', ' ')}"
        for left_out in composition.exclusions
    )
    return CompositionView(
        author=composition.author.value,
        policy=f"{composition.policy.identifier} ({_short(composition.policy.digest)})",
        placements=tuple(placements),
        exclusions=exclusions,
    )


def trail_view(replay: PublicReplay, export: RunExport, instants: Instants) -> TrailView:
    """The trail page for ``export`` under the public name ``replay`` gives it, each
    position's log instant from ``instants``; pure, and total over any export the type
    admits."""
    trace = export.trace
    timing = export.record.timing
    segments = tuple(
        f"segment {segment.number}: harness {segment.harness.commit[:12]}… "
        f"({segment.harness.tree.value}), last offset {segment.last_offset_ms:,} ms, "
        f"end {'recorded' if segment.end_recorded else 'not recorded'}"
        for segment in timing.segments
    )
    has_impact = any(claim.claim_type is ClaimType.IMPACT for claim in trace.claims)
    return TrailView(
        header=header_view(replay, export),
        ending=ending_view(export, empty=not has_impact),
        segments=segments,
        finalization_entered=(
            None
            if trace.finalization_entered is None
            else _moment(trace.finalization_entered, instants)
        ),
        operations=tuple(_operation(op, instants) for op in trace.operations),
        calls=tuple(_call(call, export, instants) for call in trace.model_calls),
        counts=tuple(_count(count, instants) for count in trace.counting_operations),
        charges=_charges(export),
        approval=_approval(export, instants),
        composition=_composition(export),
    )


__all__ = [
    "AnswerView",
    "ApprovalView",
    "BatchView",
    "CallView",
    "ChargesView",
    "CompositionView",
    "CountView",
    "DispatchView",
    "Moment",
    "OperationView",
    "StatementView",
    "ToolCallView",
    "TrailView",
    "call_anchor",
    "count_anchor",
    "operation_anchor",
    "trail_view",
]
