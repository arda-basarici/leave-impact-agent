"""The store on two connections: the races the ruling on one writer lists, each driven to one
order and giving the result the ruling requires, with no sleep anywhere.

The lock-race probe showed the row lock gives the two legal orders of an append against a
takeover and no third; here the store's own commands race. The held side is held at a
named boundary of the store (``locked``: the row lock is held, nothing is written) while
the server's activity view shows the other side waiting on that lock; then the held side is
released and commits, and the waiting side reads the committed row.

- *append against takeover*: whichever commits first stands; a worker whose locking read
  waited on a takeover is fenced and appends nothing.
- *terminal against claim*: terminal first refuses the claim; claim first rejects the
  former owner's terminal append, and nothing is settled.
- *abandonment against claim*: abandonment first closes; claim first makes the expected
  generation stale and the abandonment is refused.
- *two closures*: exactly one closure and one settled entry, whichever came first.
- *a stale caller's state* (the store group's first fork): an outside producer's approval
  between a worker's state and its next append is seen, because the row's counters say the
  state is stale and the store folds the log.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from leaveimpact.agent import ledger
from leaveimpact.agent.log_events import (
    Abandoned,
    Admitted,
    Approved,
    Failed,
    Producer,
    Resumed,
    SegmentEnded,
    SegmentStarted,
    WorkerStamp,
    kind_of,
)
from leaveimpact.agent.log_store import AdmissionReceipt, AdmissionRequest, LogStore
from leaveimpact.agent.log_transition import Appended, AttemptState, Refused, Transition
from leaveimpact.core import (
    AbandonmentReason,
    FailureCategory,
    HarnessSite,
    HarnessSiteName,
)
from tests.integration.log_store_support import Hold, Rig, rig, wait_until_blocked
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories

pytestmark = pytest.mark.integration

RULES = histories.RULES
LEDGER = "ledger-race"
RUN = "run-12"
OPERATOR = Producer("operator")
UNHANDLED = Failed(
    FailureCategory.INFRASTRUCTURE, HarnessSite(HarnessSiteName.UNHANDLED), "a fault", None
)
FENCED = Refused("generation 1 is not the current 2")

_ = rig


def admitted_and_claimed(rig: Rig, *, upto: int = 2) -> tuple[LogStore, AttemptState]:
    """A plain store with the cut-call history admitted and appended through ``upto``
    (the claim alone by default), generation 1."""
    events = histories.HISTORIES["a cut call"]()
    store = rig.store()
    store.set_threshold(
        LEDGER,
        10**15,
        authority="operator:test",
        registration_commit=cases.COMMIT,
        limit_pico_usd=10**15,
    )
    admitted = events[0].event
    assert isinstance(admitted, Admitted) and isinstance(events[0].envelope, Producer)
    receipt = store.admit(
        AdmissionRequest(f"req-{rig.schema}", admitted.inputs, events[0].envelope, LEDGER, RULES)
    )
    assert isinstance(receipt, AdmissionReceipt)
    state = store.load(RUN, 1, rules=RULES)
    for logged in events[1:upto]:
        event = logged.event
        if isinstance(event, SegmentStarted):
            result = store.claim(
                RUN,
                1,
                harness=event.harness,
                nonce=event.nonce,
                launch=event.launch,
                rules=RULES,
                state=state,
            )
        else:
            result = store.append(RUN, 1, logged.envelope, event, rules=RULES, state=state)
        assert isinstance(result, Appended), (logged.position, result)
        state = result.state
    return store, state


def kinds(store: LogStore) -> list[tuple[str, int | None]]:
    return [
        (kind_of(logged.event).value, logged.stamp.generation if logged.stamp else None)
        for logged in store.events(RUN, 1)
    ]


def segment_end(store: LogStore, state: AttemptState) -> Transition:
    stamp = WorkerStamp(state.generation, state.generation, 10)
    return store.append(RUN, 1, stamp, SegmentEnded(), rules=RULES, state=state)


def terminal(store: LogStore, state: AttemptState) -> Transition:
    stamp = WorkerStamp(state.generation, state.generation, 20)
    return store.close_attempt(RUN, 1, stamp, UNHANDLED, rules=RULES, state=state)


def takeover(store: LogStore) -> Transition:
    return store.claim(
        RUN, 1, harness=cases.REVISION, nonce="nonce-taker", launch="launch-2", rules=RULES
    )


def abandonment(store: LogStore, expected_generation: int) -> Transition:
    return store.close_attempt(
        RUN,
        1,
        OPERATOR,
        Abandoned(expected_generation, AbandonmentReason.CANCELLED, None),
        rules=RULES,
    )


def settled_entries(store: LogStore) -> int:
    return [entry.kind for entry in store.ledger_view(LEDGER).entries].count(
        ledger.EntryKind.SETTLED
    )


# --- Append against takeover -----------------------------------------------------------------


def test_a_takeover_first_fences_the_workers_append(rig: Rig) -> None:
    worker, state = admitted_and_claimed(rig)
    hold = Hold("locked")
    taker = rig.store(boundary=hold)
    with rig.observer() as observer, ThreadPoolExecutor(2) as pool:
        taking = pool.submit(takeover, taker)
        hold.wait_reached()
        appending = pool.submit(segment_end, worker, state)
        wait_until_blocked(observer, rig.backend_pid(worker))
        hold.release.set()
        taken = taking.result(10)
        appended = appending.result(10)
    assert isinstance(taken, Appended) and taken.state.generation == 2
    assert appended == FENCED
    assert kinds(worker) == [("admitted", None), ("segment_started", 1), ("segment_started", 2)]


def test_a_worker_first_appends_and_is_fenced_by_the_takeover_after(rig: Rig) -> None:
    plain, state = admitted_and_claimed(rig)
    hold = Hold("locked")
    worker = rig.store(boundary=hold)
    taker = rig.store()
    with rig.observer() as observer, ThreadPoolExecutor(2) as pool:
        appending = pool.submit(segment_end, worker, state)
        hold.wait_reached()
        taking = pool.submit(takeover, taker)
        wait_until_blocked(observer, rig.backend_pid(taker))
        hold.release.set()
        appended = appending.result(10)
        taken = taking.result(10)
    assert isinstance(appended, Appended) and isinstance(taken, Appended)
    assert kinds(plain) == [
        ("admitted", None),
        ("segment_started", 1),
        ("segment_ended", 1),
        ("segment_started", 2),
    ]
    assert terminal(plain, appended.state) == FENCED, "a fenced worker appends no outcome"


# --- Terminal against claim ------------------------------------------------------------------


def test_a_terminal_event_first_refuses_the_claim(rig: Rig) -> None:
    worker, state = admitted_and_claimed(rig)
    hold = Hold("locked")
    closer = rig.store(boundary=hold)
    taker = rig.store()
    with rig.observer() as observer, ThreadPoolExecutor(2) as pool:
        closing = pool.submit(terminal, closer, state)
        hold.wait_reached()
        taking = pool.submit(takeover, taker)
        wait_until_blocked(observer, rig.backend_pid(taker))
        hold.release.set()
        closed = closing.result(10)
        taken = taking.result(10)
    assert isinstance(closed, Appended) and closed.state.closed is not None
    assert taken == Refused("the attempt is closed at position 3")
    assert worker.open_attempts() == () and settled_entries(worker) == 1


def test_a_claim_first_rejects_the_former_owners_terminal_append(rig: Rig) -> None:
    worker, state = admitted_and_claimed(rig)
    hold = Hold("locked")
    taker = rig.store(boundary=hold)
    with rig.observer() as observer, ThreadPoolExecutor(2) as pool:
        taking = pool.submit(takeover, taker)
        hold.wait_reached()
        closing = pool.submit(terminal, worker, state)
        wait_until_blocked(observer, rig.backend_pid(worker))
        hold.release.set()
        taken = taking.result(10)
        closed = closing.result(10)
    assert isinstance(taken, Appended) and taken.state.generation == 2
    assert closed == FENCED
    assert worker.load(RUN, 1, rules=RULES).closed is None and settled_entries(worker) == 0


# --- Abandonment against claim ---------------------------------------------------------------


def test_an_abandonment_first_closes_and_refuses_the_claim(rig: Rig) -> None:
    worker, _ = admitted_and_claimed(rig)
    hold = Hold("locked")
    operator = rig.store(boundary=hold)
    taker = rig.store()
    with rig.observer() as observer, ThreadPoolExecutor(2) as pool:
        abandoning = pool.submit(abandonment, operator, 1)
        hold.wait_reached()
        taking = pool.submit(takeover, taker)
        wait_until_blocked(observer, rig.backend_pid(taker))
        hold.release.set()
        abandoned = abandoning.result(10)
        taken = taking.result(10)
    assert isinstance(abandoned, Appended) and abandoned.state.closed is not None
    assert taken == Refused("the attempt is closed at position 3")
    assert settled_entries(worker) == 1


def test_a_claim_first_makes_the_abandonments_expected_generation_stale(rig: Rig) -> None:
    worker, _ = admitted_and_claimed(rig)
    hold = Hold("locked")
    taker = rig.store(boundary=hold)
    operator = rig.store()
    with rig.observer() as observer, ThreadPoolExecutor(2) as pool:
        taking = pool.submit(takeover, taker)
        hold.wait_reached()
        abandoning = pool.submit(abandonment, operator, 1)
        wait_until_blocked(observer, rig.backend_pid(operator))
        hold.release.set()
        taken = taking.result(10)
        abandoned = abandoning.result(10)
    assert isinstance(taken, Appended) and taken.state.generation == 2
    assert isinstance(abandoned, Refused) and "generation" in abandoned.reason
    assert worker.load(RUN, 1, rules=RULES).closed is None and settled_entries(worker) == 0


# --- Two closures ----------------------------------------------------------------------------


def test_two_closures_racing_give_one_closure_and_one_settlement(rig: Rig) -> None:
    worker, state = admitted_and_claimed(rig)
    hold = Hold("locked")
    closer = rig.store(boundary=hold)
    operator = rig.store()
    with rig.observer() as observer, ThreadPoolExecutor(2) as pool:
        closing = pool.submit(terminal, closer, state)
        hold.wait_reached()
        abandoning = pool.submit(abandonment, operator, 1)
        wait_until_blocked(observer, rig.backend_pid(operator))
        hold.release.set()
        closed = closing.result(10)
        abandoned = abandoning.result(10)
    assert isinstance(closed, Appended)
    assert abandoned == Refused("the attempt is closed at position 3")
    assert settled_entries(worker) == 1
    assert kinds(worker) == [("admitted", None), ("segment_started", 1), ("failed", 1)]


# --- A stale caller's state ------------------------------------------------------------------


def test_a_stale_state_is_folded_and_sees_the_approval_between(rig: Rig) -> None:
    """Through the approval request (position 8 of the cut call) with the worker's store;
    the approval lands through another store; the worker's resume with its stale state is
    appended because the store folded the log, where the transition on the stale state
    alone would have refused it."""
    worker, requested = admitted_and_claimed(rig, upto=8)
    assert requested.frozen and requested.approved is None
    stamp = WorkerStamp(1, 1, 8_800)
    early = worker.append(RUN, 1, stamp, Resumed(), rules=RULES, state=requested)
    assert isinstance(early, Refused), "no resume before an accepted approval"
    events = histories.HISTORIES["a cut call"]()
    approval = events[8]
    assert isinstance(approval.event, Approved)
    outside = rig.store()
    delivered = outside.append(RUN, 1, approval.envelope, approval.event, rules=RULES)
    assert isinstance(delivered, Appended)
    resumed = worker.append(RUN, 1, stamp, Resumed(), rules=RULES, state=requested)
    assert isinstance(resumed, Appended)
    assert resumed.state.approved is not None and resumed.state.last_position == 10
    assert kinds(worker)[-3:] == [("approval_requested", 1), ("approved", None), ("resumed", 1)]
