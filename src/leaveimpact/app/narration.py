"""The narration: an attempt's log as one deterministic line per event, each claiming only
what its event establishes, built by pure functions over the folded state (the demo
milestone's entry ruling on narration from the log, and the narration step's forks).

The report says what the run concluded and the trail what it did; the narration says what
happened, in order, as it happened, and is the one text the live stream and the replay
timeline show, so a visitor watching a run and a reader of its replay read the same lines.
No narration event exists and no line holds model prose: a dispatch intent is an
authorization, an outcome holds what arrived and not a composed report, a count of
statements is the admissions module's reading over the reads logged before the answer, and
every outcome variant of every kind has its own truthful line. The vision's "Hypothesis:"
line is prose the log never records and is not here.

**Each line depends on the log prefix up to its event and on nothing after it.** The lines
are built by replaying the log through the transition function, so the state before an
event is in hand (a claim is first, a resumption or a recovery by the same reading the
recovery count uses), and the counts an answer line states are derived from the state just
after its outcome, never from the whole log: a tool call's later disposition is not on the
line, since it is settled by events the line's position has not reached. The acceptance
pins the property as an equality: the lines over any prefix are the prefix of the lines over
the whole, for every history the suite holds.

A line names no person and no producer identity: the admitter, an approver and an
abandoning operator are "a human", "an operator" or "the registered automatic policy",
since a public page names people exactly when the run read their record (the report step).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import assert_never

from leaveimpact.agent.admissions import answer_of
from leaveimpact.agent.log_events import (
    Abandoned,
    Admitted,
    ApprovalRequested,
    Approved,
    CapExhausted,
    Completed,
    CountOutcomeLogged,
    CountStarted,
    Declined,
    DispatchIntent,
    DispatchOutcome,
    EventKind,
    Failed,
    FinalizationEntered,
    HarnessReadKey,
    LoggedEvent,
    LoggedSettlement,
    ModelReadKey,
    OperationEvent,
    OperationResult,
    OperationSkip,
    PrefetchKey,
    Resumed,
    SegmentEnded,
    SegmentStarted,
    kind_of,
)
from leaveimpact.agent.log_transition import (
    Appended,
    AttemptState,
    ClaimKind,
    Rules,
    call_of,
    next_claim,
    next_state,
    trace_operations,
)
from leaveimpact.app.amounts import dollars
from leaveimpact.core.counting_operations import (
    CountClientError,
    Counted,
    CountLocalError,
    CountOutcome,
    CountServiceError,
)
from leaveimpact.core.input_bound import CountResult
from leaveimpact.core.model_calls import (
    Answer,
    AttributionKind,
    BrokenStream,
    ClientError,
    CompleteResponse,
    MalformedBatch,
    NoRecordedOutcome,
    ParsedBatch,
    RefusedBeforeSend,
    ServiceError,
    UndispatchedReason,
)
from leaveimpact.core.run_ending import (
    AbandonmentReason,
    Approver,
    DispatchSite,
    FailureSite,
    HarnessSite,
    InputBoundSite,
    OperationSite,
)
from leaveimpact.core.run_record import Failure, FailureCategory
from leaveimpact.core.run_trace import (
    AbsentOutcome,
    DefectOutcome,
    Outcome,
    RecordOutcome,
    RecordsOutcome,
    RefusedCallOutcome,
    UnreachableOutcome,
)
from leaveimpact.core.stated import Admitted as AdmittedFact
from leaveimpact.core.stated import Refused, RefusedInput


@dataclass(frozen=True, slots=True)
class Line:
    """One event as the timeline shows it: its position, the instant the log accepted it,
    its kind, and the sentence. Plain data, printed by the page and sent by the stream."""

    position: int
    recorded_at: datetime
    kind: EventKind
    text: str


@dataclass(frozen=True, slots=True)
class TimelineView:
    """The timeline page's view: the lines so far, whether the attempt is still open (the
    page then follows the stream from ``last_position``), and that position."""

    lines: tuple[Line, ...]
    open: bool
    last_position: int


def timeline_view(state: AttemptState, rules: Rules) -> TimelineView:
    """The timeline of ``state``: its narration, and where a live page's stream starts."""
    lines = narration(state, rules)
    return TimelineView(lines, state.closed is None, state.last_position)


def narration(state: AttemptState, rules: Rules) -> tuple[Line, ...]:
    """Every event of ``state`` as a line, in position order, built by replaying the log
    under ``rules`` so each line reads the state before its event; the kinds and positions
    are the events' own. ``rules`` are the ones the state was folded under."""
    return extend(AttemptState(), state.events, rules)[1]


def extend(
    state: AttemptState, events: Iterable[LoggedEvent], rules: Rules
) -> tuple[AttemptState, tuple[Line, ...]]:
    """``state`` carried forward over ``events``, the next events of its log in position
    order, and one line per event, each built from the state before its event exactly as
    ``narration`` builds it from the first event; ``narration`` is this from the empty
    state. The stream keeps a subscription's state and extends it by the events past its
    position each tick, so an event is folded once per subscription and a tick costs the
    new events and not the log's length (the live pages step: a whole re-fold every tick
    cost up to 0.69 s of CPU on the instance, ``probes/tick-cost``). The property the
    acceptance pins, that the lines over a prefix are the prefix of the lines over the
    whole, is what makes the extension of a prefix equal the whole."""
    lines: list[Line] = []
    before = state
    for logged in events:
        transition = next_state(before, logged, rules)
        assert isinstance(transition, Appended), "a stored log replays under its rules"
        after = transition.state
        text = _text(before, after, logged)
        if before.stopped is None and after.stopped is not None:
            text += _stop_suffix(after.stopped)
        lines.append(Line(logged.position, logged.timestamp, kind_of(logged.event), text))
        before = after
    return before, tuple(lines)


# --- One line per kind ----------------------------------------------------------------------


def _text(before: AttemptState, after: AttemptState, logged: LoggedEvent) -> str:
    event = logged.event
    match event:
        case Admitted():
            return _admitted(event)
        case SegmentStarted():
            stamp = logged.stamp
            assert stamp is not None
            return _claimed(before, event, stamp.segment)
        case SegmentEnded():
            stamp = logged.stamp
            assert stamp is not None
            return _segment_ended(before, stamp.segment)
        case OperationEvent():
            return _operation(event)
        case CountStarted():
            key = event.key
            return (
                f"a counting request was started for role {event.role} on "
                f"{key.counting_identifier} (request {_short(key.request_digest)}, "
                f"number {key.ordinal} under that key)"
            )
        case CountOutcomeLogged():
            return _count_outcome(event.outcome, event.reading)
        case DispatchIntent():
            return _intent(event)
        case DispatchOutcome():
            return _outcome(after, logged.position, event)
        case FinalizationEntered():
            return "the run stopped investigating and began to finalize"
        case ApprovalRequested():
            frozen = f"the review payload is frozen with {_n(len(event.claims), 'claim')}"
            if event.at_cap:
                return (
                    f"{frozen}, at the cap; the run awaits the decision and will report what it has"
                )
            return f"{frozen}; the run awaits the decision"
        case Approved():
            return f"{_approver(event.approver)} approved the review payload"
        case Resumed():
            return "the worker resumed after the approval"
        case Completed():
            return "the run completed: the system produced its final claims" + _settled(
                event.settlement
            )
        case CapExhausted():
            return "the run ended at the cap: the system reported what it had" + _settled(
                event.settlement
            )
        case Abandoned():
            return _abandoned(event.reason) + _settled(event.settlement)
        case Declined():
            return "a person declined the plan; the attempt is closed" + _settled(
                event.settlement
            )
        case Failed():
            return (
                f"the run failed: {_category(event.category)} at {_site(event.site)}: "
                f"{event.reason}" + _settled(event.settlement)
            )
        case _ as unreachable:
            assert_never(unreachable)


def _admitted(event: Admitted) -> str:
    inputs = event.inputs
    context = inputs.context
    return (
        f"run admitted: scenario {context.scenario_id} of world "
        f"{_short(context.world_version)}, attempt {inputs.attempt}, system "
        f"{inputs.system.kind.value} ({inputs.system.variant}), corpus level "
        f"{inputs.corpus_level}; its inputs and the registered rules are frozen"
    )


def _claimed(before: AttemptState, event: SegmentStarted, segment: int) -> str:
    commit = _short(event.harness.commit)
    match next_claim(before):
        case ClaimKind.FIRST:
            head = f"a worker claimed the attempt (segment {segment}) on harness commit {commit}"
        case ClaimKind.RESUMPTION:
            head = (
                f"a worker claimed the attempt to resume it after the approval (segment "
                f"{segment}) on harness commit {commit}"
            )
        case ClaimKind.RECOVERY:
            head = (
                f"a worker recovered the attempt (segment {segment}, recovery "
                f"{before.recoveries + 1}) on harness commit {commit}"
            )
        case _ as unreachable:
            assert_never(unreachable)
    override = event.override
    if override is None:
        return head
    return (
        f"{head}, under an operator's override of the first segment's commit "
        f"{_short(override.from_commit)}"
    )


def _segment_ended(before: AttemptState, segment: int) -> str:
    if before.frozen and before.approved is None:
        return (
            f"the worker stopped cleanly (segment {segment}); the run awaits the decision on "
            "its review payload"
        )
    return (
        f"the worker stopped cleanly (segment {segment}) without ending the run; it awaits a "
        "worker to continue it or an abandonment"
    )


def _operation(event: OperationEvent) -> str:
    key = event.key
    match key:
        case PrefetchKey():
            who = f"the frozen prefetch's read {key.ordinal}"
        case ModelReadKey():
            who = f"the read model call {key.call} asked for in tool call {key.tool_call}"
        case HarnessReadKey():
            who = f"the harness's read {key.ordinal} under {key.policy}"
        case _ as unreachable:
            assert_never(unreachable)
    resolution = event.resolution
    match resolution:
        case OperationSkip():
            return f"{who} was not run: {_skip_reason(resolution.reason)}"
        case OperationResult():
            source = "no source" if resolution.source is None else resolution.source.value
            return f"{who}: {resolution.tool} on {source}, {_outcome_brief(resolution.outcome)}"
        case _ as unreachable:
            assert_never(unreachable)


def _skip_reason(reason: UndispatchedReason) -> str:
    if reason is UndispatchedReason.CAP:
        return "the cap was reached"
    assert reason is UndispatchedReason.SOURCE_UNREACHABLE, "a skip is for the cap or a source"
    return "the source was already unreachable in this run"


def _outcome_brief(outcome: Outcome) -> str:
    match outcome:
        case RecordOutcome():
            record = outcome.record
            return f"one record ({record.kind.value} {record.ref.id})"
        case AbsentOutcome():
            return "no such record (evidence of absence)"
        case RecordsOutcome():
            return _n(len(outcome.records), "record")
        case UnreachableOutcome():
            return f"{outcome.source.value} unreachable: {outcome.reason}"
        case DefectOutcome():
            return f"a malformed record at {outcome.locator}: {outcome.reason}"
        case RefusedCallOutcome():
            return f"the call was refused before any source was asked: {outcome.reason}"
        case _ as unreachable:
            assert_never(unreachable)


def _count_outcome(outcome: CountOutcome, reading: CountResult) -> str:
    match outcome:
        case Counted():
            detail = f"{outcome.input_tokens:,} input tokens"
        case CountServiceError():
            detail = f"service error {outcome.http_status} {outcome.code}"
        case CountClientError():
            detail = f"the client gave up, {outcome.kind.value}"
        case CountLocalError():
            detail = f"a local error, {outcome.exception_type}"
        case NoRecordedOutcome():
            raise ValueError("a logged count outcome records an outcome")
        case _ as unreachable:
            assert_never(unreachable)
    match reading:
        case CountResult.COUNTED:
            return f"the counting request answered: {detail}; read as counted"
        case CountResult.FAILED:
            return f"the counting request failed on a transient cause ({detail}); read as failed"
        case CountResult.REFUSED:
            return (
                f"the counting request was refused ({detail}); read as a misconfiguration, "
                "which no retry answers"
            )
        case CountResult.UNCLASSIFIED:
            return f"the counting request failed in a way the method does not classify ({detail})"
        case CountResult.UNRESOLVED:
            raise ValueError("a recorded outcome is never read as unresolved")
        case _ as unreachable:
            assert_never(unreachable)


def _intent(event: DispatchIntent) -> str:
    return (
        f"model call {event.call} authorized (dispatch {event.number}, role {event.role}): "
        f"{_n(len(event.input_reads), 'read')} shown, input bounded at "
        f"{event.bound.input_tokens:,} tokens, output at most {event.output_maximum:,} "
        f"tokens, worst case {event.allocation_tokens:,} tokens and "
        f"{dollars(event.allocation_pico_usd)}"
    )


def _outcome(after: AttemptState, position: int, event: DispatchOutcome) -> str:
    head = f"model call {event.call}, dispatch {event.number}"
    reading = _reading(event.attribution.kind, event.attribution.rule)
    observation = event.observation
    match observation:
        case CompleteResponse():
            retries = (
                ""
                if not observation.sdk_retries
                else f", {observation.sdk_retries} SDK retries beneath the dispatch"
            )
            arrived = (
                f"{head} answered: a complete response (stop reason {observation.stop_reason}, "
                f"{observation.provider_latency_ms:,} ms{retries}); "
            )
            # The transition settles a call on its complete response, so its answer is
            # derivable from the state just after this event. A body the parser cannot read
            # (no output object, no content list) is accepted by the log and followed by a
            # failure at the dispatch's parse phase, which the reader consults and this line
            # may not, since it lies in the future: the line says the answer could not be
            # read, and nothing more (the external read of the step's commits, second
            # finding).
            call = call_of(after, event.call)
            assert call is not None, "a dispatch outcome follows its intent"
            try:
                answered = answer_of(after, call, trace_operations(after))
            except ValueError as error:
                return f"{arrived}the response could not be read as an answer ({error}); {reading}"
            assert answered is not None and answered.position == position
            return arrived + _answer_brief(answered.answer) + f"; {reading}"
        case BrokenStream():
            return f"{head}: the stream broke ({observation.reason}); {reading}"
        case ServiceError():
            return (
                f"{head}: the service answered an error ({observation.http_status} "
                f"{observation.code}: {observation.message_signature}); {reading}"
            )
        case ClientError():
            return (
                f"{head}: the client gave up with no answer ({observation.kind.value}: "
                f"{observation.reason}), so whether the request ran is unknown; {reading}"
            )
        case RefusedBeforeSend():
            return (
                f"{head}: the client refused the request before sending it "
                f"({observation.reason}); {reading}"
            )
        case NoRecordedOutcome():
            raise ValueError("a logged dispatch outcome records an outcome")
        case _ as unreachable:
            assert_never(unreachable)


def _answer_brief(answer: Answer) -> str:
    admitted = refused = inputs = unreadable = 0
    for batch in answer.fact_batches:
        match batch:
            case ParsedBatch():
                for entry in batch.entries:
                    match entry:
                        case AdmittedFact():
                            admitted += 1
                        case Refused():
                            refused += 1
                        case RefusedInput():
                            inputs += 1
                        case _ as unreachable:
                            assert_never(unreachable)
            case MalformedBatch():
                unreadable += 1
            case _ as unreachable:
                assert_never(unreachable)
    parts = [
        _n(len(answer.tool_calls), "tool call"),
        f"{_n(admitted + refused, 'statement')} made, {admitted} admitted by the gates, "
        f"{refused} refused",
    ]
    if inputs:
        parts.append(f"{_n(inputs, 'input')} no statement could be made of")
    if unreadable:
        parts.append(f"{_n(unreadable, 'fact payload')} unreadable")
    return ", ".join(parts)


def _reading(kind: AttributionKind, rule: str) -> str:
    match kind:
        case AttributionKind.BEHAVIOUR:
            how = "the model's behaviour"
        case AttributionKind.INFRASTRUCTURE:
            how = "an infrastructure fault"
        case AttributionKind.DEFECT:
            how = "a defect"
        case AttributionKind.UNRESOLVED:
            raise ValueError("a recorded outcome is never read as unresolved")
        case _ as unreachable:
            assert_never(unreachable)
    return f"read as {how} under rule {rule}"


def _approver(approver: Approver) -> str:
    match approver:
        case Approver.AUTOMATIC:
            return "the registered automatic policy"
        case Approver.HUMAN:
            return "a human"
        case _ as unreachable:
            assert_never(unreachable)


def _abandoned(reason: AbandonmentReason) -> str:
    match reason:
        case AbandonmentReason.CANCELLED:
            return "an operator cancelled the attempt; it is abandoned"
        case AbandonmentReason.INTERRUPTED:
            return "the attempt lost its worker and was judged not resumable; it is abandoned"
        case _ as unreachable:
            assert_never(unreachable)


def _settled(settlement: LoggedSettlement | None) -> str:
    if settlement is None:
        return ""
    kept = "" if settlement.kept_reason is None else f" ({_words(settlement.kept_reason.value)})"
    return (
        f"; the reservation was {settlement.state.value}{kept}, "
        f"{dollars(settlement.charged_pico_usd)} charged"
    )


def _stop_suffix(failure: Failure) -> str:
    return f"; the run is stopped here by {_category(failure.category)} at {_site(failure.site)}"


def _category(category: FailureCategory) -> str:
    match category:
        case FailureCategory.DEFECT:
            return "a defect"
        case FailureCategory.INFRASTRUCTURE:
            return "an infrastructure fault"
        case _ as unreachable:
            assert_never(unreachable)


def _site(site: FailureSite) -> str:
    match site:
        case OperationSite():
            return f"operation {site.operation}"
        case DispatchSite():
            return f"{site.model_call} dispatch {site.dispatch} ({site.phase.value})"
        case InputBoundSite():
            return f"counting operation {site.counting_operation}"
        case HarnessSite():
            return f"the harness ({_words(site.site.value)})"
        case _ as unreachable:
            assert_never(unreachable)


# --- Wording ----------------------------------------------------------------------------------


def _n(count: int, noun: str) -> str:
    """``count`` with ``noun``, pluralized by an ``s``.

    >>> _n(1, "read"), _n(0, "read"), _n(2, "claim")
    ('1 read', '0 reads', '2 claims')
    """
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _short(digest: str) -> str:
    """A digest or a commit shortened to twelve characters.

    >>> _short("a" * 64)
    'aaaaaaaaaaaa…'
    """
    return f"{digest[:12]}…"


def _words(member: str) -> str:
    """A wire-format member as words.

    >>> _words("usage_incomplete")
    'usage incomplete'
    """
    return member.replace("_", " ")


__all__ = ["Line", "TimelineView", "narration", "timeline_view"]
