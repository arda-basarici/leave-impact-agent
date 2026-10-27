"""The public decision over the real stores: the approval on the log and the row, the
decision blocked on the log's session lock across the deadline (history 15 of the
live-path commands step: the clock is read after the lock, the one that waited past the
deadline is refused as late, equality included), and the crash between the log's commit
and the row's record repaired by the retry.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta

import pytest

from leaveimpact.agent.log_events import Approved
from leaveimpact.agent.log_store import LogStore
from leaveimpact.app.decide import (
    DEMO_VISITOR,
    DecideComposition,
    DecideRefusalKind,
    DecideRequest,
    deadline_of,
    decide,
)
from leaveimpact.app.live import Decision, LiveDraft, LiveRow
from leaveimpact.app.public import PublicationDraft
from leaveimpact.app.store import AppStore, AppStoreInvariantBroken
from tests.integration.log_store_support import Hold, Rig, Scripted, rig, wait_until_blocked
from tests.integration.test_app_start import app_store
from tests.integration.test_log_store import opened, replay, under_run
from tests.unit import log_histories as histories
from tests.unit.publishable_fixture import CONFIGURATION
from tests.unit.test_app_decide import (
    DIGEST,
    KEY,
    KEY_DIGEST,
    PUBLIC_ID,
    RUN,
    DiesOnce,
    decided,
    refused,
)

pytestmark = pytest.mark.integration

_ = rig  # the fixture, imported for pytest to find

RULES = histories.RULES
LIVE = replace(CONFIGURATION, live_runs=True)
COMPOSITION = DecideComposition(LIVE, RULES)
WAIT = timedelta(seconds=LIVE.approval_wait_seconds)


def awaiting(rig: Rig) -> tuple[LogStore, AppStore, LiveRow]:
    """The fixture history replayed through its approval request and the segment's end
    under the public run id, the app schema applied, and the attempt's two rows written as
    the start writes them."""
    log = opened(rig)
    events = under_run(histories.HISTORIES["an approval wait across a restart"](), RUN)
    state = replay(log, events, upto=9)
    assert state.approval_requested is not None and state.approved is None
    inputs = state.inputs
    assert inputs is not None
    store = app_store(rig)
    store.ensure_schema()
    with store.start_section() as writer:
        row = writer.write(
            PublicationDraft(
                PUBLIC_ID,
                RUN,
                1,
                inputs.context.world_version,
                inputs.context.scenario_id,
                None,
                "demo-start",
            ),
            LiveDraft(PUBLIC_ID, RUN, 1, KEY_DIGEST, events[0].timestamp),
        )
    return log, store, row


def request(decision: Decision) -> DecideRequest:
    return DecideRequest(PUBLIC_ID, KEY, decision, DIGEST)


def test_an_approval_lands_on_the_log_and_the_row_and_the_decline_after_is_refused(
    rig: Rig,
) -> None:
    log, store, _ = awaiting(rig)
    outcome = decided(decide(request(Decision.APPROVED), log, store, COMPOSITION))
    state = log.load(RUN, 1, rules=RULES)
    given = state.approved
    assert given is not None and given.position == outcome.position
    assert isinstance(given.event, Approved) and given.envelope == DEMO_VISITOR
    assert outcome.row.decision is Decision.APPROVED and outcome.row.decided_at == given.timestamp
    assert store.live_row_of(PUBLIC_ID) == outcome.row
    assert store.live_row_of_attempt(RUN, 1) == outcome.row
    assert store.live_row_of_attempt(RUN, 2) is None
    late = refused(
        decide(request(Decision.DECLINED), log, store, COMPOSITION), DecideRefusalKind.LOG_REFUSED
    )
    assert late.detail == f"an approval is already given at position {outcome.position}"
    again = decided(decide(request(Decision.APPROVED), log, store, COMPOSITION))
    assert again.repeated and again.row == outcome.row


def test_a_decision_blocked_on_the_lock_across_the_deadline_is_late(rig: Rig) -> None:
    """History 15: A holds the log's session lock at ``serialized`` with its clock scripted a
    second before the deadline; B, scripted at the deadline itself, is shown waiting on the
    lock by the server; released, A is admitted and B is refused as late with nothing
    appended, since the clock is read after the lock and the deadline is not before it."""
    log, store, _ = awaiting(rig)
    deadline = deadline_of(log.load(RUN, 1, rules=RULES), LIVE)
    assert deadline is not None
    hold = Hold("serialized")
    before = deadline - timedelta(seconds=1)
    # A reads the clock once for the deadline and once for the approval's timestamp.
    a_log = rig.store(clock=Scripted([before, before]), boundary=hold)
    b_log = rig.store(clock=Scripted([deadline]))
    a_store, b_store = app_store(rig), app_store(rig)
    with ThreadPoolExecutor(max_workers=2) as pool, rig.observer() as observer:
        a = pool.submit(decide, request(Decision.APPROVED), a_log, a_store, COMPOSITION)
        hold.wait_reached()
        b = pool.submit(decide, request(Decision.DECLINED), b_log, b_store, COMPOSITION)
        wait_until_blocked(observer, rig.backend_pid(b_log))
        hold.release.set()
        admitted = decided(a.result(timeout=10))
        late = refused(b.result(timeout=10), DecideRefusalKind.LATE)
    assert not admitted.repeated and late.detail == "the wait for a decision has ended"
    state = log.load(RUN, 1, rules=RULES)
    assert state.approved is not None and state.approved.timestamp == before
    assert state.last_position == admitted.position, "nothing appended for B"
    assert store.live_row_of(PUBLIC_ID) == admitted.row


def test_a_crash_between_the_logs_commit_and_the_row_is_repaired_by_the_retry(rig: Rig) -> None:
    """History 3 on the real store: the log holds the decision, the row says undecided; the
    retry answers with the receipt and records the row."""
    log, store, _ = awaiting(rig)
    dying = app_store(rig, boundary=DiesOnce("decide-before-record"))
    with pytest.raises(RuntimeError, match="the process died"):
        decide(request(Decision.DECLINED), log, dying, COMPOSITION)
    closed = log.load(RUN, 1, rules=RULES).closed
    assert closed is not None
    undecided = store.live_row_of(PUBLIC_ID)
    assert undecided is not None and undecided.decision is None
    repaired = decided(decide(request(Decision.DECLINED), log, store, COMPOSITION))
    assert repaired.repeated and repaired.position == closed.position
    assert repaired.row.decision is Decision.DECLINED
    assert repaired.row.decided_at == closed.timestamp
    assert store.live_row_of(PUBLIC_ID) == repaired.row


def test_a_decision_recorded_on_no_row_is_an_invariant_by_name(rig: Rig) -> None:
    _, store, row = awaiting(rig)
    with pytest.raises(AppStoreInvariantBroken, match="no live row holds"):
        store.record_decision("live-" + "0" * 32, Decision.APPROVED, row.started_at)  # type: ignore[arg-type]
