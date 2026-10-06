"""The transition function and the ending: every history folds; a mutation of a valid
history (a duplicate, a reorder, a removal, another generation, other content under a held
identifier) is received or refused and never appended; and each ruling's refusal is held
by name, with the three histories group 2 wrote that no fixture holds."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from leaveimpact.agent.log_ending import SegmentStatus, approval_of, ending_of, status_of
from leaveimpact.agent.log_events import (
    Abandoned,
    ApprovalRequested,
    Approved,
    Completed,
    CountKey,
    CountStarted,
    DispatchIntent,
    EventKind,
    Failed,
    FinalizationEntered,
    LoggedEvent,
    OperationEvent,
    Resumed,
    SegmentEnded,
    SegmentStarted,
    WorkerStamp,
    kind_of,
)
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_transition import (
    Received,
    Refused,
    Rules,
    fold,
    next_state,
)
from leaveimpact.core import (
    ApprovalState,
    Approver,
    AttributionKind,
    AttributionTable,
    DispatchPhase,
    DispatchSite,
    FailureCategory,
    HarnessSite,
    HarnessSiteName,
    KeptReason,
    ModelCallId,
    NoRecordedOutcome,
    RedispatchPolicy,
    ReservationState,
    ServiceError,
    TerminalStatus,
    review_payload_digest,
    signed_elapsed_ms,
)
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as h

RULES = h.RULES


def refusal(events: tuple[LoggedEvent, ...], rules: Rules = RULES) -> str:
    """The reason the last of ``events`` is refused after the ones before it."""
    state = fold(events[:-1], rules)
    result = next_state(state, events[-1], rules)
    assert isinstance(result, Refused), result
    return result.reason


def restamped(logged: LoggedEvent, *, position: int | None = None, **stamp: int) -> LoggedEvent:
    held = logged.stamp
    assert held is not None
    envelope = replace(held, **stamp) if stamp else held
    return LoggedEvent(position or logged.position, logged.timestamp, envelope, logged.event)


# --- Every history folds ---------------------------------------------------------------------


@pytest.mark.parametrize("name", list(h.HISTORIES))
def test_every_history_folds_to_a_closed_state(name: str) -> None:
    state = fold(h.HISTORIES[name](), RULES)
    assert state.closed is not None and not state.open
    assert state.last_position == len(h.HISTORIES[name]())
    assert status_of(state).ending == ending_of(state)


# --- Mutations -------------------------------------------------------------------------------


@pytest.mark.parametrize("name", list(h.HISTORIES))
def test_an_identical_re_append_is_received_at_the_first_position(name: str) -> None:
    events = h.HISTORIES[name]()
    for index in range(1, len(events)):
        state = fold(events[:index], RULES)
        again = events[index - 1]
        assert next_state(state, again, RULES) == Received(again.position)
        moved = LoggedEvent(index + 1, again.timestamp, again.envelope, again.event)
        assert next_state(state, moved, RULES) == Received(again.position)


def test_other_content_under_a_held_identifier_is_refused() -> None:
    events = h.HISTORIES["a cut call"]()
    started = next(e for e in events if kind_of(e.event) is EventKind.SEGMENT_STARTED)
    other = SegmentStarted(cases.REVISION, "another-nonce", "launch-1")
    forged = LoggedEvent(started.position, started.timestamp, started.envelope, other)
    state = fold(events, RULES)
    result = next_state(state, forged, RULES)
    assert result == Refused("another content under the identifier of the event at position 2")


def test_a_closed_attempt_rejects_every_later_append() -> None:
    events = h.HISTORIES["a cut call"]()
    state = fold(events, RULES)
    late = restamped(events[-2], position=len(events) + 1)
    result = next_state(state, replace(late, event=SegmentEnded()), RULES)
    assert result == Refused(f"the attempt is closed at position {len(events)}")


def without(events: tuple[LoggedEvent, ...], index: int) -> tuple[LoggedEvent, ...]:
    """``events`` with the one at ``index`` removed and the rest renumbered."""
    return events[:index] + tuple(
        LoggedEvent(e.position - 1, e.timestamp, e.envelope, e.event) for e in events[index + 1 :]
    )


def test_a_removed_event_leaves_what_depended_on_it_refused_and_a_reorder_is_refused() -> None:
    events = h.HISTORIES["a cut call"]()
    kinds = [kind_of(e.event) for e in events]
    count_outcome = kinds.index(EventKind.COUNT_OUTCOME)
    with pytest.raises(ValueError, match="did not count"):
        fold(without(events, count_outcome), RULES)
    approved = kinds.index(EventKind.APPROVED)
    with pytest.raises(ValueError, match="resumes after an approval was given"):
        fold(without(events, approved), RULES)
    with pytest.raises(ValueError, match="no worker has claimed"):
        fold(without(events, kinds.index(EventKind.SEGMENT_STARTED)), RULES)
    # A read nothing depends on can go, and the log is then another log.
    assert fold(without(events, kinds.index(EventKind.OPERATION)), RULES).closed is not None
    swapped = (
        *events[:-2],
        LoggedEvent(
            events[-2].position, events[-1].timestamp, events[-1].envelope, events[-1].event
        ),
        LoggedEvent(
            events[-1].position, events[-2].timestamp, events[-2].envelope, events[-2].event
        ),
    )
    with pytest.raises(ValueError, match="no log holds the event at position"):
        fold(swapped, RULES)


def test_positions_are_dense() -> None:
    events = h.HISTORIES["a cut call"]()
    gap = LoggedEvent(
        events[2].position + 1, events[2].timestamp, events[2].envelope, events[2].event
    )
    assert refusal((*events[:2], gap)) == "positions are dense: the next is 3, got 4"


# --- Ownership and segments ------------------------------------------------------------------


def test_a_stale_generation_appends_nothing() -> None:
    events = h.HISTORIES["an unresolved dispatch followed by an answered one"]()
    second_intent = events[7]
    assert isinstance(second_intent.event, DispatchIntent)
    stale = restamped(second_intent, generation=1, segment=1)
    assert refusal((*events[:7], stale)) == "generation 1 is not the current 2"


def test_a_claim_opens_the_next_segment_under_the_next_generation_at_offset_zero() -> None:
    events = h.HISTORIES["a recovered attempt"]()
    claim = events[3]
    assert isinstance(claim.event, SegmentStarted)
    assert "a claim opens segment 2 under generation 2" in refusal(
        (*events[:3], restamped(claim, generation=3))
    )
    assert refusal((*events[:3], restamped(claim, offset_ms=5))) == "a segment starts at offset 0"


def test_an_ended_segment_appends_nothing_and_offsets_never_fall() -> None:
    events = h.HISTORIES["an approval wait across a restart"]()
    ended = next(i for i, e in enumerate(events) if isinstance(e.event, SegmentEnded))
    after_end = restamped(events[ended], position=ended + 2)
    assert (
        refusal((*events[: ended + 1], replace(after_end, event=Resumed())))
        == "segment 1 has ended"
    )
    earlier = restamped(events[ended], offset_ms=100)
    assert refusal((*events[:ended], earlier)) == "offset 100 is below the segment's last 7000"


def test_no_worker_event_before_a_claim_and_one_admission_only() -> None:
    events = h.HISTORIES["a cut call"]()
    assert refusal((events[0], restamped(events[2], position=2))) == (
        "no worker has claimed the attempt"
    )
    again = LoggedEvent(2, events[0].timestamp, events[0].envelope, events[0].event)
    assert next_state(fold(events[:1], RULES), again, RULES) == Received(1)
    other = replace(again, event=h.Admitted(h.inputs(reservation=5)))
    assert refusal((events[0], other)) == (
        "another content under the identifier of the event at position 1"
    )
    assert refusal((restamped(events[2], position=1),)) == "the first event is the admission"


# --- The registered values -------------------------------------------------------------------


def test_rules_that_differ_from_the_frozen_ones_are_refused() -> None:
    events = h.HISTORIES["a cut call"]()
    other_table = AttributionTable(
        tuple(
            replace(row, redispatch=False) if row.identifier == "unmatched" else row
            for row in cases.TABLE.rows
        )
    )
    assert refusal(events[:2], Rules(other_table, cases.POLICY)) == (
        "the attribution table given is not the one the admission froze"
    )
    assert refusal(events[:2], Rules(cases.TABLE, RedispatchPolicy(2, 0))) == (
        "the re-dispatch policy given is not the one the admission froze"
    )
    assert (
        refusal(events[:2], Rules(None, None))
        == "the registered table and policy are needed and absent"
    )


# --- Dispatches and counts -------------------------------------------------------------------


def test_a_dispatch_intent_after_a_dispatch_whose_row_allows_no_other_is_refused() -> None:
    """Group 1's review, finding 3: ``gave_up`` reads a client error as infrastructure with
    no re-dispatch, so a second dispatch of the call is no history."""
    events = h.HISTORIES["a cut call"]()
    intent_at = next(i for i, e in enumerate(events) if isinstance(e.event, DispatchIntent))
    from leaveimpact.core import ClientError, ClientErrorKind

    timed_out = h.outcome(
        1,
        1,
        ClientError(ClientErrorKind.TIMEOUT, "read timed out"),
        AttributionKind.INFRASTRUCTURE,
        rule="gave_up",
    )
    first = events[: intent_at + 1]
    outcome = restamped(events[intent_at], position=intent_at + 2, offset_ms=700)
    again = restamped(events[intent_at], position=intent_at + 3, offset_ms=800)
    history = (*first, replace(outcome, event=timed_out), replace(again, event=h.intent(1, 2)))
    assert refusal(history) == "call-1 stands failed_by_infrastructure"


def test_a_dispatch_beyond_the_maximum_is_refused() -> None:
    log = h.History()
    log.admit(h.inputs(reservation=10 * cases.ALLOCATION))
    log.claim()
    log.worker(h.count_start("call-1"), offset=400)
    log.worker(h.count_outcome("call-1"), offset=500)
    for number in range(1, 4):
        log.worker(h.intent(1, number), offset=500 + 100 * number)
    assert fold(log.logged(), RULES).open
    log.worker(h.intent(1, 4), offset=900)
    assert refusal(log.logged()) == "call-1 stands failed_by_infrastructure"


def test_a_dispatch_rests_on_a_durable_count_that_counted_this_request() -> None:
    events = h.HISTORIES["a cut call"]()
    intent_at = next(i for i, e in enumerate(events) if isinstance(e.event, DispatchIntent))
    before_the_count = events[: intent_at - 2]
    early = restamped(events[intent_at], position=intent_at - 1)
    assert "which the log does not hold" in refusal((*before_the_count, early))
    other = replace(events[intent_at], event=h.intent(1, name="call-2"))
    assert (
        refusal((*events[:intent_at], other))
        == "the bound rests on 'count/provider_count-1/model-a-base/"
        + cases.request_digest("call-2")[:16]
        + "/1', which the log does not hold"
    )


def test_a_count_is_started_only_while_the_decision_is_to_count() -> None:
    events = h.HISTORIES["a request whose input bound was never established"]()
    third_at = next(
        i
        for i, e in enumerate(events)
        if isinstance(e.event, CountStarted) and e.event.key.ordinal == 3
    )
    fourth = restamped(events[third_at], position=third_at + 2, offset_ms=950)
    key = CountKey(cases.METHOD, cases.COUNTING_MODEL, cases.DIGEST, 4)
    assert refusal(
        (*events[: third_at + 1], replace(fourth, event=CountStarted(key, cases.ROLE)))
    ) == ("the decision for this request is exhausted, not to count")
    wrong_ordinal = replace(
        events[third_at], event=CountStarted(replace(key, ordinal=5), cases.ROLE)
    )
    assert (
        refusal((*events[:third_at], wrong_ordinal))
        == "the next counting request for this request is 3"
    )


def test_the_account_refuses_a_dispatch_that_does_not_fit() -> None:
    reservation = cases.ALLOCATION - 1
    log = h.History()
    log.admit(h.inputs(reservation=reservation))
    log.claim()
    log.worker(h.count_start("call-1"), offset=400)
    log.worker(h.count_outcome("call-1"), offset=500)
    log.worker(h.intent(1), offset=600)
    assert (
        refusal(log.logged()) == "the account does not authorize the dispatch: enter_finalization"
    )


# --- The freeze and the defect ---------------------------------------------------------------


def test_after_an_approval_request_no_dispatch_count_or_resolution_is_appended() -> None:
    events = h.HISTORIES["an abandoned attempt"]()
    requested_at = next(i for i, e in enumerate(events) if isinstance(e.event, ApprovalRequested))
    prefix = events[: requested_at + 1]
    late = restamped(events[requested_at], position=requested_at + 2, offset_ms=4_900)
    assert refusal((*prefix, replace(late, event=h.count_start("call-2")))) == (
        "no counting request after an approval was requested"
    )
    assert refusal((*prefix, replace(late, event=h.intent(2, name="call-2")))) == (
        "no dispatch after an approval was requested"
    )
    read = h.model_read(1, "tu_9", cases.asked("tu_9", "call-1", 1).outcome)
    assert (
        refusal((*prefix, replace(late, event=read)))
        == "no tool resolution after an approval was requested"
    )
    assert refusal((*prefix, replace(late, event=FinalizationEntered()))) == (
        "no finalization after an approval was requested"
    )


def test_a_recorded_defect_is_the_ending_whatever_closes() -> None:
    events = h.HISTORIES["a recorded defect an operator finalized"]()
    defect_at = next(
        i for i, e in enumerate(events) if isinstance(e.event, OperationEvent) and e.position > 7
    )
    prefix = events[: defect_at + 1]
    state = fold(prefix, RULES)
    assert state.defect is not None
    late = restamped(events[defect_at], position=defect_at + 2, offset_ms=1_700)
    assert (
        refusal((*prefix, replace(late, event=h.intent(2, name="call-2"))))
        == "no dispatch after a recorded defect"
    )
    reservation = cases.defect_finalized_by_operator().record.reservation
    assert reservation is not None
    completed = replace(late, event=Completed(h.settlement_of(reservation)))
    assert refusal((*prefix, completed)) == "a completion follows the resume from an approval"
    elsewhere = Failed(
        FailureCategory.INFRASTRUCTURE,
        HarnessSite(HarnessSiteName.PREFETCH),
        "down",
        h.settlement_of(reservation),
    )
    assert (
        refusal((*prefix, replace(late, event=elsewhere)))
        == "a recorded defect at call-1/tu_1 is the ending"
    )
    assert (
        ending_of(fold(events, RULES)).failure
        == cases.defect_finalized_by_operator().record.failure
    )


def test_a_failure_site_names_something_the_log_holds() -> None:
    events = h.HISTORIES["a cut call"]()
    last = events[-1]
    assert isinstance(last.event, Completed)
    site = DispatchSite(ModelCallId("call-1"), 2, DispatchPhase.SEND)
    failed = Failed(FailureCategory.INFRASTRUCTURE, site, "lost", last.event.settlement)
    assert (
        refusal((*events[:-1], replace(last, event=failed))) == "no dispatch 2 of call-1 to fail at"
    )


# --- The approval ----------------------------------------------------------------------------


def test_an_approval_answers_the_requested_digest_once_and_the_resume_follows_it() -> None:
    events = h.HISTORIES["a cut call"]()
    approved_at = next(i for i, e in enumerate(events) if isinstance(e.event, Approved))
    other = replace(events[approved_at], event=Approved(Approver.HUMAN, cases.DIGEST))
    assert (
        refusal((*events[:approved_at], other))
        == "an approval names the digest of the payload that was requested"
    )
    given = events[approved_at]
    twice = LoggedEvent(approved_at + 2, given.timestamp, given.envelope, given.event)
    assert next_state(fold(events[: approved_at + 1], RULES), twice, RULES) == Received(
        given.position
    )
    by_a_human = replace(
        twice, event=Approved(Approver.HUMAN, review_payload_digest((), cases.RULES))
    )
    assert refusal((*events[: approved_at + 1], by_a_human)) == (
        f"another content under the identifier of the event at position {given.position}"
    )
    early = restamped(events[approved_at + 1], position=approved_at)
    assert (
        refusal((*events[: approved_at - 1], early))
        == "a worker resumes after an approval was given"
    )
    assert approval_of(fold(events, RULES)).state is ApprovalState.APPROVED


def test_an_abandonment_names_the_current_generation() -> None:
    events = h.HISTORIES["an abandoned attempt"]()
    last = events[-1]
    assert isinstance(last.event, Abandoned)
    stale = replace(last, event=replace(last.event, expected_generation=0))
    assert (
        refusal((*events[:-1], stale))
        == "the abandon command expects generation 0; the attempt is at 1"
    )


# --- Status ----------------------------------------------------------------------------------


def test_status_is_three_fields_and_never_says_a_worker_is_alive() -> None:
    events = h.HISTORIES["an approval wait across a restart"]()
    never = status_of(fold(events[:1], RULES))
    assert (never.open, never.segment, never.approval) == (
        True,
        SegmentStatus.NEVER_STARTED,
        ApprovalState.NOT_REQUESTED,
    )
    requested = status_of(fold(events[:8], RULES))
    assert (requested.segment, requested.approval) == (
        SegmentStatus.OPEN,
        ApprovalState.REQUESTED_UNAPPROVED,
    )
    stopped = status_of(fold(events[:9], RULES))
    assert stopped.segment is SegmentStatus.STOPPED and stopped.open
    closed = status_of(fold(events, RULES))
    assert closed.ending is not None and closed.ending.status is TerminalStatus.COMPLETED
    assert not hasattr(closed, "running")


# --- Group 2's histories no fixture holds ----------------------------------------------------


def test_history_three_an_approval_across_segments_by_a_human() -> None:
    """The six histories' third, with a human approver: three segments, the request stamped
    in the first and the resume in the third, the killed middle segment's last offset 0."""
    events = list(h.HISTORIES["an approval wait across a restart"]())
    approved_at = next(i for i, e in enumerate(events) if isinstance(e.event, Approved))
    digest = review_payload_digest((), cases.RULES)
    events[approved_at] = LoggedEvent(
        events[approved_at].position,
        events[approved_at].timestamp,
        h.Producer("human:arda"),
        Approved(Approver.HUMAN, digest),
    )
    export = export_of(fold(tuple(events), RULES))
    assert export.record.approval.approver is Approver.HUMAN
    assert [s.last_offset_ms for s in export.record.timing.segments] == [7_900, 0, 2_050]


def test_history_four_unresolved_dispatches_with_retained_liability() -> None:
    """The six histories' fourth, under a re-dispatch maximum of 2: two intents of one call
    with no outcome, the third segment's worker finding the maximum reached and failing the
    attempt at the send, the settlement kept for the unresolved dispatch."""
    policy = RedispatchPolicy(2, 0)
    rules = Rules(cases.TABLE, policy)
    frozen = replace(h.inputs(reservation=30_000_000_000), redispatch=policy)
    log = h.History()
    log.admit(frozen)
    log.claim()
    log.worker(h.prefetch(1, "work_items", cases.Source.JIRA), offset=100)
    log.worker(h.count_start("call-1"), offset=400)
    log.worker(h.count_outcome("call-1"), offset=500)
    log.worker(h.intent(1), offset=600)
    log.claim()
    log.worker(h.intent(1, 2), offset=300)
    log.claim()
    settlement = h.LoggedSettlement(
        2 * cases.ALLOCATION, ReservationState.KEPT, KeptReason.UNRESOLVED_DISPATCH, 7
    )
    log.worker(
        Failed(
            FailureCategory.INFRASTRUCTURE,
            DispatchSite(ModelCallId("call-1"), 2, DispatchPhase.SEND),
            "exhausted",
            settlement,
        ),
        offset=200,
    )
    state = fold(log.logged(), rules)
    assert state.account.pico_usd == 2 * cases.ALLOCATION
    export = export_of(state)
    (call,) = export.trace.model_calls
    assert [d.observation for d in call.dispatches] == [NoRecordedOutcome(), NoRecordedOutcome()]
    assert export.record.reservation is not None
    assert export.record.reservation.kept_reason is KeptReason.UNRESOLVED_DISPATCH
    assert export.record.reservation.charged_pico_usd == 2 * cases.ALLOCATION
    before_the_failure = log.logged()[:-1]
    third = LoggedEvent(
        len(log.events), log.events[-1].timestamp, WorkerStamp(3, 3, 300), h.intent(1, 3)
    )
    assert next_state(fold(before_the_failure, rules), third, rules) == Refused(
        "call-1 stands failed_by_infrastructure"
    )


def test_history_five_a_negative_elapsed_time_is_kept_as_logged() -> None:
    """The six histories' fifth: the log's clock stepped back between the admission and the
    terminal event; both instants are exported as logged and the difference is negative."""
    events = list(h.HISTORIES["a cut call"]())
    last = events[-1]
    events[-1] = LoggedEvent(
        last.position, cases.ADMITTED - timedelta(milliseconds=300), last.envelope, last.event
    )
    export = export_of(fold(tuple(events), RULES))
    assert signed_elapsed_ms(export.record.timing) == -300
    assert export.record.status is TerminalStatus.COMPLETED


def test_a_segment_end_is_a_transition_and_not_a_timing_marker() -> None:
    """After a clean stop the attempt stays open for a claim and the segment appends
    nothing more; the Nova fixture's service error is an observation like any other."""
    events = h.HISTORIES["the Nova signature beside another model error"]()
    error = events[6]
    assert isinstance(error.event, h.DispatchOutcome)
    assert isinstance(error.event.observation, ServiceError)
    assert error.event.attribution.kind is AttributionKind.BEHAVIOUR
    stopped = (
        *events[:7],
        replace(restamped(error, position=8, offset_ms=1_600), event=SegmentEnded()),
    )
    state = fold(stopped, RULES)
    assert state.open and status_of(state).segment is SegmentStatus.STOPPED
