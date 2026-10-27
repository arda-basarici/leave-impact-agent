"""The public decision over the in-memory stores: the capability, the receipt under the
digest whatever the clock says, the deadline against the log's clock, the log's own
refusals passed through, the row recorded after the log and repaired by a retry when the
process died between the two.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

import pytest

from leaveimpact.agent.log_events import Abandoned, Admitted, Approved, Declined, LoggedEvent
from leaveimpact.agent.log_transition import Appended
from leaveimpact.app.decide import (
    DEMO_VISITOR,
    DecideComposition,
    Decided,
    DecideRefusalKind,
    DecideRefused,
    DecideRequest,
    deadline_of,
    decide,
    decision_name,
)
from leaveimpact.app.live import Decision, LiveRow, key_digest_of, public_id_for, run_id_for
from leaveimpact.core import AbandonmentReason
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit.app_store_memory import MemoryAppStore
from tests.unit.log_store_memory import MemoryLog
from tests.unit.publishable_fixture import CONFIGURATION
from tests.unit.test_app_start import SWEEPER, key

RULES = histories.RULES
LIVE = replace(CONFIGURATION, live_runs=True)
COMPOSITION = DecideComposition(LIVE, RULES)
WAIT = timedelta(seconds=LIVE.approval_wait_seconds)
DIGEST = cases.review_payload_digest((), cases.RULES)
"""The digest of the review payload the fixture histories request approval over."""
KEY = key(1)
KEY_DIGEST = key_digest_of(KEY)
RUN = run_id_for(KEY_DIGEST)
PUBLIC_ID = public_id_for(KEY_DIGEST)
REQUESTED_AT_POSITION = 8
"""Where the approval request sits in the fixture histories used here."""


def under_run(events: tuple[LoggedEvent, ...], run_id: str) -> tuple[LoggedEvent, ...]:
    """The history as the log of ``run_id``'s attempt: the admission's inputs renamed."""
    first = events[0]
    admitted = first.event
    assert isinstance(admitted, Admitted)
    return (replace(first, event=Admitted(replace(admitted.inputs, run_id=run_id))), *events[1:])


def awaiting(upto: int = 9) -> tuple[LoggedEvent, ...]:
    """The fixture history through its approval request and the segment's end (position
    9 by default), under the public run id."""
    return under_run(histories.HISTORIES["an approval wait across a restart"]()[:upto], RUN)


@dataclass
class FixedClock:
    """The log's clock, set by the test."""

    at: datetime

    def __call__(self) -> datetime:
        return self.at


def stores(
    events: tuple[LoggedEvent, ...], *, clock: datetime
) -> tuple[MemoryLog, MemoryAppStore, FixedClock]:
    """The log seeded with ``events`` and the live row of the public attempt they are the
    log of, started under ``KEY``."""
    ticking = FixedClock(clock)
    log = MemoryLog(clock=ticking)
    log.seed(events)
    rows = MemoryAppStore()
    rows.live.append(LiveRow(PUBLIC_ID, RUN, 1, KEY_DIGEST, events[0].timestamp, None, None))
    return log, rows, ticking


def deadline(events: tuple[LoggedEvent, ...]) -> datetime:
    return events[REQUESTED_AT_POSITION - 1].timestamp + WAIT


def request(decision: Decision, *, digest: str = DIGEST, key_given: object = KEY) -> DecideRequest:
    return DecideRequest(PUBLIC_ID, key_given, decision, digest)  # type: ignore[arg-type]


def decided(outcome: object) -> Decided:
    assert isinstance(outcome, Decided), outcome
    return outcome


def refused(outcome: object, kind: DecideRefusalKind) -> DecideRefused:
    assert isinstance(outcome, DecideRefused) and outcome.kind is kind, outcome
    return outcome


def test_the_serialization_name_is_per_attempt() -> None:
    assert decision_name(RUN, 1) != decision_name(RUN, 2)
    assert decision_name("demo-a", 1) != decision_name("demo-b", 1)


def test_an_approval_before_the_deadline_lands_on_the_log_and_the_row() -> None:
    events = awaiting()
    log, rows, _ = stores(events, clock=deadline(events) - timedelta(seconds=1))
    outcome = decided(decide(request(Decision.APPROVED), log, rows, COMPOSITION))
    assert not outcome.repeated and outcome.position == len(events) + 1
    logged = log.events(RUN, 1)[-1]
    assert isinstance(logged.event, Approved) and logged.event.payload_digest == DIGEST
    assert logged.envelope == DEMO_VISITOR
    assert outcome.row.decision is Decision.APPROVED
    assert outcome.row.decided_at == logged.timestamp, "the row says the log's instant"
    assert rows.live_row_of(PUBLIC_ID) == outcome.row


def test_a_decline_before_the_deadline_closes_the_attempt_and_the_row_says_so() -> None:
    events = awaiting()
    log, rows, _ = stores(events, clock=deadline(events) - timedelta(seconds=1))
    outcome = decided(decide(request(Decision.DECLINED), log, rows, COMPOSITION))
    state = log.load(RUN, 1, rules=RULES)
    assert state.closed is not None and state.closed.position == outcome.position
    assert isinstance(state.closed.event, Declined)
    assert state.closed.event.settlement is not None, "the store settled the reservation"
    assert outcome.row.decision is Decision.DECLINED
    assert outcome.row.decided_at == state.closed.timestamp


@pytest.mark.parametrize("decision", [Decision.APPROVED, Decision.DECLINED])
def test_the_same_decision_repeated_after_the_deadline_is_the_receipt(decision: Decision) -> None:
    """History 16: the retry after the capability check answers with what the log holds
    whatever the clock says, and the deadline refuses a new decision only."""
    events = awaiting()
    log, rows, clock = stores(events, clock=deadline(events) - timedelta(seconds=1))
    first = decided(decide(request(decision), log, rows, COMPOSITION))
    clock.at = deadline(events) + timedelta(hours=1)
    again = decided(decide(request(decision), log, rows, COMPOSITION))
    assert again.repeated and again.position == first.position and again.row == first.row
    assert len(log.events(RUN, 1)) == len(events) + 1, "nothing appended twice"


def test_no_live_row_and_a_wrong_key_are_refused_before_the_log_is_read() -> None:
    events = awaiting()
    log, rows, _ = stores(events, clock=deadline(events) - timedelta(seconds=1))
    other = replace(request(Decision.APPROVED), public_id=public_id_for(key_digest_of(key(2))))
    refused(decide(other, log, rows, COMPOSITION), DecideRefusalKind.NOT_LIVE)
    refused(
        decide(request(Decision.APPROVED, key_given=key(2)), log, rows, COMPOSITION),
        DecideRefusalKind.CAPABILITY,
    )
    refused(
        decide(replace(request(Decision.APPROVED), key=None), log, rows, COMPOSITION),
        DecideRefusalKind.CAPABILITY,
    )
    assert len(log.events(RUN, 1)) == len(events)
    assert rows.live_row_of(PUBLIC_ID) is not None
    assert rows.live_row_of(PUBLIC_ID).decision is None  # type: ignore[union-attr]


def test_before_any_request_the_decision_is_refused_by_name() -> None:
    events = awaiting(upto=7)
    log, rows, _ = stores(events, clock=events[-1].timestamp)
    assert deadline_of(log.load(RUN, 1, rules=RULES), LIVE) is None
    refused(
        decide(request(Decision.APPROVED), log, rows, COMPOSITION), DecideRefusalKind.NO_REQUEST
    )


@pytest.mark.parametrize("late_by", [timedelta(0), timedelta(seconds=1), timedelta(days=1)])
def test_a_decision_at_or_past_the_deadline_is_late_and_names_the_wait(late_by: timedelta) -> None:
    """History 5: refused before the sweeper runs; admitted strictly before the deadline, so
    the deadline itself is late. The refusal names the wait and never the clock."""
    events = awaiting()
    log, rows, _ = stores(events, clock=deadline(events) + late_by)
    outcome = decide(request(Decision.APPROVED), log, rows, COMPOSITION)
    late = refused(outcome, DecideRefusalKind.LATE)
    assert "wait" in late.detail and not any(character.isdigit() for character in late.detail)
    assert len(log.events(RUN, 1)) == len(events)
    assert rows.live_row_of(PUBLIC_ID).decision is None  # type: ignore[union-attr]


def test_the_sweepers_close_then_the_click_is_one_way() -> None:
    """History 2: the sweeper abandoned the attempt at the deadline; the click after it is
    refused as late, and nothing is appended. Before the deadline, an attempt closed by
    something else is refused with the log's own reason."""
    events = awaiting()
    log, rows, clock = stores(events, clock=deadline(events) + timedelta(seconds=1))
    state = log.load(RUN, 1, rules=RULES)
    closed = log.close_attempt(
        RUN, 1, SWEEPER, Abandoned(state.generation, AbandonmentReason.CANCELLED, None), rules=RULES
    )
    assert isinstance(closed, Appended)
    refused(decide(request(Decision.APPROVED), log, rows, COMPOSITION), DecideRefusalKind.LATE)
    clock.at = deadline(events) - timedelta(seconds=1)
    early = refused(
        decide(request(Decision.APPROVED), log, rows, COMPOSITION), DecideRefusalKind.LOG_REFUSED
    )
    assert early.detail == f"the attempt is closed at position {closed.state.last_position}"


def test_approve_and_decline_under_one_digest_order_through_the_logs_refusals() -> None:
    """History 4: the second decision re-reads the log under the lock and the log's own
    refusals apply, in both orders."""
    events = awaiting()
    log, rows, _ = stores(events, clock=deadline(events) - timedelta(seconds=1))
    approved = decided(decide(request(Decision.APPROVED), log, rows, COMPOSITION))
    late_decline = refused(
        decide(request(Decision.DECLINED), log, rows, COMPOSITION), DecideRefusalKind.LOG_REFUSED
    )
    assert late_decline.detail == f"an approval is already given at position {approved.position}"
    assert rows.live_row_of(PUBLIC_ID).decision is Decision.APPROVED  # type: ignore[union-attr]
    log, rows, _ = stores(events, clock=deadline(events) - timedelta(seconds=1))
    declined = decided(decide(request(Decision.DECLINED), log, rows, COMPOSITION))
    late_approval = refused(
        decide(request(Decision.APPROVED), log, rows, COMPOSITION), DecideRefusalKind.LOG_REFUSED
    )
    assert late_approval.detail == f"the attempt is closed at position {declined.position}"
    assert rows.live_row_of(PUBLIC_ID).decision is Decision.DECLINED  # type: ignore[union-attr]


def test_a_digest_that_is_not_the_requests_is_the_logs_refusal() -> None:
    events = awaiting()
    log, rows, _ = stores(events, clock=deadline(events) - timedelta(seconds=1))
    wrong = refused(
        decide(request(Decision.DECLINED, digest="0" * 64), log, rows, COMPOSITION),
        DecideRefusalKind.LOG_REFUSED,
    )
    assert wrong.detail == "the digest given is not the requested payload's"
    assert log.load(RUN, 1, rules=RULES).closed is None


@dataclass
class DiesOnce:
    """A boundary that raises the first time it reaches ``at``: the process dying with the
    log decided and the row not yet recorded."""

    at: str
    died: bool = False

    def __call__(self, name: str) -> None:
        if name == self.at and not self.died:
            self.died = True
            raise RuntimeError("the process died")


@pytest.mark.parametrize("decision", [Decision.APPROVED, Decision.DECLINED])
def test_a_crash_between_the_logs_commit_and_the_row_is_repaired_by_the_retry(
    decision: Decision,
) -> None:
    """Histories 3 and 13: the log holds the decision and the row says undecided; the retry,
    after the capability check, answers with the receipt and writes the row then."""
    events = awaiting()
    log, rows, clock = stores(events, clock=deadline(events) - timedelta(seconds=1))
    rows.boundary = DiesOnce("decide-before-record")
    with pytest.raises(RuntimeError, match="the process died"):
        decide(request(decision), log, rows, COMPOSITION)
    assert len(log.events(RUN, 1)) == len(events) + 1, "the log decided"
    assert rows.live_row_of(PUBLIC_ID).decision is None  # type: ignore[union-attr]
    clock.at = deadline(events) + timedelta(hours=1)
    repaired = decided(decide(request(decision), log, rows, COMPOSITION))
    assert repaired.repeated and repaired.position == len(events) + 1
    assert repaired.row.decision is decision
    assert repaired.row.decided_at == log.events(RUN, 1)[-1].timestamp
    assert rows.live_row_of(PUBLIC_ID) == repaired.row
