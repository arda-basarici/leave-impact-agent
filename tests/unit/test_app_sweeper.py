"""The sweeper: the pure function over snapshots (one action per state the histories
name, nothing for the states that are somebody else's), and the driver over the in-memory
stores (the fifteen-minute close under the decision's lock, the orphan, the wall bound,
the finalization through the terminal worker with the slot, the row repair, the
publications through injected commands, and a state that changed under an action read
from the reload and not from a refusal).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import cast

import pytest

from leaveimpact.adapters.wiring import UploadOutcome
from leaveimpact.agent.commands import (
    CommandRefused,
    InventoryRequest,
    InventoryWritten,
    PublishRequest,
)
from leaveimpact.agent.inventory import PublicationRecord
from leaveimpact.agent.log_events import Abandoned, Admitted, LoggedEvent, SegmentEnded, WorkerStamp
from leaveimpact.agent.log_store import SlotHolder
from leaveimpact.agent.log_transition import Appended
from leaveimpact.agent.worker import WorkerEndingKind
from leaveimpact.app.decide import DecideComposition, DecideRefusalKind, DecideRequest, decide
from leaveimpact.app.live import Decision, LiveRow, key_digest_of, public_id_for, run_id_for
from leaveimpact.app.start import DEMO_START
from leaveimpact.app.sweeper import (
    DEMO_SWEEPER,
    CloseUnclaimed,
    CloseWait,
    FenceAndClose,
    Finalize,
    Publish,
    RepairRow,
    SweepAction,
    SweepComposition,
    SweepOutcome,
    SweepSnapshot,
    SweptAttempt,
    WriteInventory,
    actions_of,
    perform,
    snapshot_of,
    sweep,
)
from leaveimpact.core import AbandonmentReason
from leaveimpact.core.inventory import Inventory, InventoryScope, PublicationStatus
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit.app_store_memory import MemoryAppStore
from tests.unit.log_store_memory import LEDGER, MemoryLog
from tests.unit.publishable_fixture import CONFIGURATION
from tests.unit.test_app_decide import DIGEST, FixedClock, decided, refused
from tests.unit.test_app_start import key

RULES = histories.RULES
LIVE = replace(CONFIGURATION, ledger_id=LEDGER, live_runs=True)
WAIT = timedelta(seconds=LIVE.approval_wait_seconds)
WALL = timedelta(seconds=LIVE.attempt_wall_seconds)
ADMITTED = cases.ADMITTED
"""Every fixture history's admission instant; its events sit one second apart after it."""


def public(events: tuple[LoggedEvent, ...], number: int) -> tuple[LoggedEvent, ...]:
    """The history as the log of the public attempt started under ``key(number)``: the
    admission's inputs renamed to the derived run id and its producer the demo's start."""
    first = events[0]
    admitted = first.event
    assert isinstance(admitted, Admitted)
    run_id = run_id_for(key_digest_of(key(number)))
    renamed = replace(
        first, envelope=DEMO_START, event=Admitted(replace(admitted.inputs, run_id=run_id))
    )
    return (renamed, *events[1:])


def run_of(number: int) -> str:
    return run_id_for(key_digest_of(key(number)))


def row_of(number: int, events: tuple[LoggedEvent, ...]) -> LiveRow:
    digest = key_digest_of(key(number))
    return LiveRow(
        public_id_for(digest), run_of(number), 1, digest, events[0].timestamp, None, None
    )


def awaiting() -> tuple[LoggedEvent, ...]:
    """Through the approval request and the segment's end: positions 1 to 9."""
    return histories.HISTORIES["an approval wait across a restart"]()[:9]


def running() -> tuple[LoggedEvent, ...]:
    """Claimed and working, the segment open and nothing requested: positions 1 to 7."""
    return histories.HISTORIES["a cut call"]()[:7]


def stopped() -> tuple[LoggedEvent, ...]:
    """A recorded defect with its segment open, before the operator's finalization."""
    events = histories.HISTORIES["a recorded defect an operator finalized"]()
    assert isinstance(events[-1].event, Abandoned)
    return events[:-1]


def closed_completed() -> tuple[LoggedEvent, ...]:
    return histories.HISTORIES["an approval wait across a restart"]()


def admission_only() -> tuple[LoggedEvent, ...]:
    return histories.HISTORIES["an attempt admitted and never claimed"]()[:1]


@dataclass
class Recording:
    """The publication commands as fakes: what they were asked, and what they answer."""

    published: list[PublishRequest] = field(default_factory=list[PublishRequest])
    inventoried: list[InventoryRequest] = field(default_factory=list[InventoryRequest])
    answer: PublicationStatus = PublicationStatus.PUBLISHED

    def publish(self, request: PublishRequest) -> PublicationRecord | CommandRefused:
        self.published.append(request)
        return record(request.run_id, request.attempt, self.answer)

    def inventory(self, request: InventoryRequest) -> InventoryWritten:
        self.inventoried.append(request)
        return InventoryWritten("d" * 64, "key", UploadOutcome.CREATED, cast(Inventory, None))


def record(run_id: str, attempt: int, state: PublicationStatus) -> PublicationRecord:
    return PublicationRecord(
        run_id,
        attempt,
        state,
        cases.COMMIT,
        4,
        "0" * 64,
        "key",
        "1" * 64,
        None,
        None,
        ADMITTED,
    )


def composition(recording: Recording, **changes: object) -> SweepComposition:
    fields: dict[str, object] = {
        "configuration": LIVE,
        "rules": RULES,
        "harness": cases.REVISION,
        "reader_commit": cases.COMMIT,
        "publish_export": recording.publish,
        "write_inventory": recording.inventory,
        "nonces": iter(f"nonce-sweep-{n}" for n in range(1, 100)).__next__,
    }
    fields.update(changes)
    return SweepComposition(**fields)  # type: ignore[arg-type]


def stores(clock: datetime) -> tuple[MemoryLog, MemoryAppStore, FixedClock]:
    ticking = FixedClock(clock)
    return MemoryLog(clock=ticking), MemoryAppStore(), ticking


def seeded(
    log: MemoryLog,
    rows: MemoryAppStore,
    number: int,
    events: tuple[LoggedEvent, ...],
    *,
    row: bool = True,
) -> tuple[LoggedEvent, ...]:
    history = public(events, number)
    log.seed(history)
    if row:
        rows.live.append(row_of(number, history))
    return history


def swept(
    log: MemoryLog, number: int, events: tuple[LoggedEvent, ...], row: LiveRow | None
) -> SweptAttempt:
    history = public(events, number)
    return SweptAttempt(
        run_of(number),
        1,
        history[0].timestamp,
        log.load(run_of(number), 1, rules=RULES),
        row,
        log.publication_of(run_of(number), 1),
    )


def snapshot(
    at: datetime, *attempts: SweptAttempt, slot: SlotHolder | None = None
) -> SweepSnapshot:
    return SweepSnapshot(at, attempts, slot)


def kinds(actions: tuple[SweepAction, ...]) -> list[type[SweepAction]]:
    return [type(action) for action in actions]


# --- the pure function -------------------------------------------------------------------


def test_a_wait_is_closed_at_its_deadline_and_not_before() -> None:
    log, rows, _ = stores(ADMITTED)
    history = seeded(log, rows, 1, awaiting())
    requested_at = history[7].timestamp
    attempt = swept(log, 1, awaiting(), rows.live[0])
    assert actions_of(snapshot(requested_at + WAIT - timedelta(seconds=1), attempt), LIVE) == ()
    assert actions_of(snapshot(requested_at + WAIT, attempt), LIVE) == (CloseWait(run_of(1), 1),)


def test_an_approval_given_is_not_a_wait_and_a_clean_pause_gets_nothing() -> None:
    """Histories 6 and 12: approved and resumed with the deadline long past, nothing closes;
    a segment cleanly ended with nothing requested is the worker's recovery, not the
    sweeper's. The row of the approved attempt is repaired when it says undecided."""
    log, rows, _ = stores(ADMITTED)
    seeded(log, rows, 1, closed_completed()[:13])  # approved, claimed again, resumed
    approved = swept(log, 1, closed_completed()[:13], rows.live[0])
    late = ADMITTED + timedelta(days=1)
    # The resumed segment holds the slot inside the wall: the wait is over, the wall is not.
    slot = SlotHolder(run_of(1), 1, 3, "launch-1", late - WALL + timedelta(seconds=1))
    actions = actions_of(snapshot(late, approved, slot=slot), LIVE)
    assert actions == (
        RepairRow(rows.live[0].public_id, Decision.APPROVED, approved.state.events[10].timestamp),
    )
    decided_row = replace(rows.live[0], decision=Decision.APPROVED, decided_at=ADMITTED)
    assert actions_of(snapshot(late, replace(approved, row=decided_row), slot=slot), LIVE) == ()
    seeded(log, rows, 2, running())
    ended = log.append(run_of(2), 1, WorkerStamp(1, 1, 2_000), SegmentEnded(), rules=RULES)
    assert isinstance(ended, Appended)
    paused = swept(log, 2, running(), rows.live[1])
    assert paused.state.current_segment is not None and paused.state.current_segment.ended
    assert actions_of(snapshot(late, paused), LIVE) == ()


def test_an_unclaimed_attempt_is_closed_once_older_than_the_wait_row_or_not() -> None:
    """History 7's orphan and fork 5's attempt the slot never came free for."""
    log, rows, _ = stores(ADMITTED)
    seeded(log, rows, 1, admission_only(), row=False)
    seeded(log, rows, 2, admission_only())
    orphan = swept(log, 1, admission_only(), None)
    waiting = swept(log, 2, admission_only(), rows.live[0])
    young = ADMITTED + WAIT - timedelta(seconds=1)
    assert actions_of(snapshot(young, orphan, waiting), LIVE) == ()
    assert actions_of(snapshot(ADMITTED + WAIT, orphan, waiting), LIVE) == (
        CloseUnclaimed(run_of(1), 1),
        CloseUnclaimed(run_of(2), 1),
    )


def test_a_recorded_stop_is_finalized_whatever_the_clock() -> None:
    log, rows, _ = stores(ADMITTED)
    seeded(log, rows, 1, stopped())
    attempt = swept(log, 1, stopped(), rows.live[0])
    assert attempt.state.stopped is not None and attempt.state.closed is None
    assert actions_of(snapshot(ADMITTED, attempt), LIVE) == (Finalize(run_of(1), 1),)


def test_the_wall_bound_fences_the_public_holder_past_it_and_nobody_else() -> None:
    """History 10 and fork 5: inside the wall the holder is left alone (no liveness rule);
    past it, a holder with a live row is fenced at the slot's generation; a holder with no
    row is not the sweeper's, and the bound is measured from the claim, not the admission."""
    log, rows, _ = stores(ADMITTED)
    seeded(log, rows, 1, running())
    claimed_at = ADMITTED + timedelta(hours=1)
    slot = SlotHolder(run_of(1), 1, 1, "launch-1", claimed_at)
    with_row = swept(log, 1, running(), rows.live[0])
    inside = claimed_at + WALL - timedelta(seconds=1)
    assert actions_of(snapshot(inside, with_row, slot=slot), LIVE) == ()
    assert actions_of(snapshot(claimed_at + WALL, with_row, slot=slot), LIVE) == (
        FenceAndClose(run_of(1), 1, 1),
    )
    no_row = replace(with_row, row=None)
    assert actions_of(snapshot(claimed_at + WALL, no_row, slot=slot), LIVE) == ()
    other_holder = SlotHolder("run-operator", 1, 1, "launch-2", ADMITTED)
    assert actions_of(snapshot(claimed_at + WALL, with_row, slot=other_holder), LIVE) == ()


def test_closed_attempts_are_published_and_one_inventory_per_scope_follows() -> None:
    log, rows, _ = stores(ADMITTED)
    seeded(log, rows, 1, closed_completed())
    seeded(log, rows, 2, closed_completed())
    seeded(log, rows, 3, closed_completed())
    log.publications[(run_of(3), 1)] = record(run_of(3), 1, PublicationStatus.PUBLISHED)
    log.publications[(run_of(2), 1)] = record(run_of(2), 1, PublicationStatus.FAILED)
    first, second, third = (swept(log, n, closed_completed(), rows.live[n - 1]) for n in (1, 2, 3))
    inputs = first.state.inputs
    assert inputs is not None
    actions = actions_of(snapshot(ADMITTED, first, second, third), LIVE)
    # Each row says undecided while its log holds the approval: repaired first, per attempt.
    assert [action for action in actions if not isinstance(action, RepairRow)] == [
        Publish(run_of(1), 1),
        Publish(run_of(2), 1),
        WriteInventory(inputs.context.world_version, inputs.preregistration_commit),
    ]
    assert kinds(actions) == [RepairRow, Publish, RepairRow, Publish, RepairRow, WriteInventory]


def test_a_row_is_repaired_from_a_decline_the_log_holds() -> None:
    log, rows, _ = stores(ADMITTED)
    declined = histories.HISTORIES["a declined attempt"]()
    seeded(log, rows, 1, declined)
    log.publications[(run_of(1), 1)] = record(run_of(1), 1, PublicationStatus.PUBLISHED)
    attempt = swept(log, 1, declined, rows.live[0])
    closed = attempt.state.closed
    assert closed is not None
    assert actions_of(snapshot(ADMITTED, attempt), LIVE) == (
        RepairRow(rows.live[0].public_id, Decision.DECLINED, closed.timestamp),
    )
    repaired = replace(rows.live[0], decision=Decision.DECLINED, decided_at=closed.timestamp)
    assert actions_of(snapshot(ADMITTED, replace(attempt, row=repaired)), LIVE) == ()


# --- the driver over the in-memory stores -------------------------------------------------


def test_the_wait_is_closed_under_the_decisions_lock_and_the_click_after_is_late() -> None:
    """History 2 end to end: cancelled by the sweeper at the deadline, the reservation
    settled, and the decision after it refused as late."""
    log, rows, clock = stores(ADMITTED)
    history = seeded(log, rows, 1, awaiting())
    clock.at = history[7].timestamp + WAIT
    report = sweep(log, rows, composition(Recording()))
    assert [outcome.action for outcome in report] == [CloseWait(run_of(1), 1)]
    assert report[0].carried and report[0].detail == "cancelled at position 10"
    state = log.load(run_of(1), 1, rules=RULES)
    assert state.closed is not None and state.closed.envelope == DEMO_SWEEPER
    assert isinstance(state.closed.event, Abandoned)
    assert state.closed.event.reason is AbandonmentReason.CANCELLED
    assert state.closed.event.settlement is not None
    late = refused(
        decide(
            DecideRequest(rows.live[0].public_id, key(1), Decision.APPROVED, DIGEST),
            log,
            rows,
            DecideComposition(LIVE, RULES),
        ),
        DecideRefusalKind.LATE,
    )
    assert late.detail == "the wait for a decision has ended"
    after = sweep(log, rows, composition(Recording()))
    assert kinds([outcome.action for outcome in after]) == [Publish, WriteInventory]  # type: ignore[arg-type]


def test_a_decision_before_the_sweeper_leaves_nothing_to_close() -> None:
    """History 1: the approval is in the log before the deadline; the pass at the deadline
    finds the wait over and changes nothing."""
    log, rows, clock = stores(ADMITTED)
    history = seeded(log, rows, 1, awaiting())
    clock.at = history[7].timestamp + WAIT - timedelta(seconds=1)
    decided(
        decide(
            DecideRequest(rows.live[0].public_id, key(1), Decision.APPROVED, DIGEST),
            log,
            rows,
            DecideComposition(LIVE, RULES),
        )
    )
    clock.at = history[7].timestamp + WAIT
    assert sweep(log, rows, composition(Recording())) == ()
    assert log.load(run_of(1), 1, rules=RULES).closed is None


def test_a_decision_landing_between_the_snapshot_and_the_close_is_read_from_the_reload() -> None:
    log, rows, clock = stores(ADMITTED)
    history = seeded(log, rows, 1, awaiting())
    clock.at = history[7].timestamp + WAIT
    composed = composition(Recording())
    actions = actions_of(snapshot_of(log, rows, composed), LIVE)
    assert actions == (CloseWait(run_of(1), 1),)
    clock.at = history[7].timestamp + WAIT - timedelta(seconds=1)
    approved = decided(
        decide(
            DecideRequest(rows.live[0].public_id, key(1), Decision.APPROVED, DIGEST),
            log,
            rows,
            DecideComposition(LIVE, RULES),
        )
    )
    clock.at = history[7].timestamp + WAIT
    outcome = perform(actions[0], log, rows, composed)
    assert outcome == SweepOutcome(actions[0], True, f"approved at position {approved.position}")
    assert log.load(run_of(1), 1, rules=RULES).closed is None


def test_an_orphan_is_closed_at_the_waits_deadline_from_its_admission() -> None:
    """History 7: an admission by the demo's start with no live row, never claimed, closed
    as cancelled once the wait has passed since the admission, settled with nothing
    charged."""
    log, rows, clock = stores(ADMITTED)
    seeded(log, rows, 1, admission_only(), row=False)
    clock.at = ADMITTED + WAIT - timedelta(seconds=1)
    assert sweep(log, rows, composition(Recording())) == ()
    clock.at = ADMITTED + WAIT
    report = sweep(log, rows, composition(Recording()))
    assert [outcome.action for outcome in report] == [CloseUnclaimed(run_of(1), 1)]
    assert report[0].carried
    state = log.load(run_of(1), 1, rules=RULES)
    assert state.closed is not None and isinstance(state.closed.event, Abandoned)
    settlement = state.closed.event.settlement
    assert settlement is not None and settlement.charged_pico_usd == 0


def test_a_claim_landing_between_the_snapshot_and_the_close_leaves_the_attempt_open() -> None:
    log, rows, clock = stores(ADMITTED)
    seeded(log, rows, 1, admission_only())
    clock.at = ADMITTED + WAIT
    composed = composition(Recording())
    actions = actions_of(snapshot_of(log, rows, composed), LIVE)
    assert actions == (CloseUnclaimed(run_of(1), 1),)
    claimed = log.claim(
        run_of(1), 1, harness=cases.REVISION, nonce="nonce-w", launch="launch-w", rules=RULES
    )
    assert isinstance(claimed, Appended)
    outcome = perform(actions[0], log, rows, composed)
    assert outcome == SweepOutcome(actions[0], True, "claimed meanwhile")
    assert log.load(run_of(1), 1, rules=RULES).closed is None


def test_the_holder_past_the_wall_is_fenced_and_closed_with_the_slot_released() -> None:
    log, rows, clock = stores(ADMITTED)
    history = seeded(log, rows, 1, running())
    claimed_at = history[1].timestamp
    log.slot = SlotHolder(run_of(1), 1, 1, "launch-1", claimed_at)
    clock.at = claimed_at + WALL
    report = sweep(log, rows, composition(Recording()))
    assert [outcome.action for outcome in report] == [FenceAndClose(run_of(1), 1, 1)]
    assert report[0].carried and report[0].detail == "interrupted at position 8"
    state = log.load(run_of(1), 1, rules=RULES)
    assert state.closed is not None and isinstance(state.closed.event, Abandoned)
    assert state.closed.event.reason is AbandonmentReason.INTERRUPTED
    assert state.closed.event.expected_generation == 1
    assert state.closed.event.settlement is not None
    assert log.execution_slot() is None, "closure released the slot by ownership"


def test_a_takeover_between_the_snapshot_and_the_fence_is_left_to_the_new_generation() -> None:
    log, rows, clock = stores(ADMITTED)
    history = seeded(log, rows, 1, running())
    log.slot = SlotHolder(run_of(1), 1, 1, "launch-1", history[1].timestamp)
    clock.at = history[1].timestamp + WALL
    composed = composition(Recording())
    actions = actions_of(snapshot_of(log, rows, composed), LIVE)
    assert actions == (FenceAndClose(run_of(1), 1, 1),)
    taken = log.claim(
        run_of(1), 1, harness=cases.REVISION, nonce="nonce-2", launch="launch-2", rules=RULES
    )
    assert isinstance(taken, Appended) and taken.state.generation == 2
    outcome = perform(actions[0], log, rows, composed)
    assert outcome == SweepOutcome(actions[0], True, "taken over by generation 2")
    assert log.load(run_of(1), 1, rules=RULES).closed is None


def test_a_recorded_stop_is_finalized_through_the_terminal_worker_taking_the_slot() -> None:
    log, rows, clock = stores(ADMITTED)
    seeded(log, rows, 1, stopped())
    clock.at = ADMITTED + timedelta(minutes=1)
    report = sweep(log, rows, composition(Recording()))
    assert [outcome.action for outcome in report] == [Finalize(run_of(1), 1)]
    assert report[0].carried and report[0].detail == f"{WorkerEndingKind.CLOSED.value}: failed"
    state = log.load(run_of(1), 1, rules=RULES)
    assert state.closed is not None and state.generation == 2, "claimed at the next generation"
    claim = state.events[-2]
    assert claim.stamp is not None and claim.stamp.generation == 2
    assert log.execution_slot() is None, "the claim took the slot and the closure released it"


def test_a_finalization_refused_on_a_held_slot_is_reported_and_left_for_the_next_pass() -> None:
    log, rows, clock = stores(ADMITTED)
    seeded(log, rows, 1, stopped())
    log.slot = SlotHolder("run-other", 1, 1, "launch-9", ADMITTED)
    clock.at = ADMITTED + timedelta(minutes=1)
    report = sweep(log, rows, composition(Recording()))
    assert len(report) == 1 and not report[0].carried
    assert report[0].detail.startswith(f"{WorkerEndingKind.CLAIM_REFUSED.value}: ")
    assert "run-other" in report[0].detail
    assert log.load(run_of(1), 1, rules=RULES).closed is None
    assert log.execution_slot() is not None and log.execution_slot().run_id == "run-other"  # type: ignore[union-attr]


def test_publications_go_through_the_injected_commands_with_the_scope_from_the_inputs() -> None:
    log, rows, clock = stores(ADMITTED)
    seeded(log, rows, 1, closed_completed())
    seeded(log, rows, 2, closed_completed())
    clock.at = ADMITTED + timedelta(minutes=1)
    recording = Recording()
    report = sweep(log, rows, composition(recording))
    inputs = log.load(run_of(1), 1, rules=RULES).inputs
    assert inputs is not None
    # The two were admitted at one instant, so the listing orders them by run id.
    ordered = sorted((run_of(1), run_of(2)))
    assert [outcome.action for outcome in report if not isinstance(outcome.action, RepairRow)] == [
        Publish(ordered[0], 1),
        Publish(ordered[1], 1),
        WriteInventory(inputs.context.world_version, inputs.preregistration_commit),
    ]
    assert all(outcome.carried for outcome in report)
    assert recording.published == [
        PublishRequest(ordered[0], 1, cases.COMMIT),
        PublishRequest(ordered[1], 1, cases.COMMIT),
    ]
    assert recording.inventoried == [
        InventoryRequest(
            InventoryScope(inputs.context.world_version, inputs.preregistration_commit, LEDGER),
            cases.COMMIT,
        )
    ]
    failing = Recording(answer=PublicationStatus.FAILED)
    report = sweep(log, rows, composition(failing))
    assert [outcome.carried for outcome in report] == [False, False, True], "rows repaired already"
    assert report[0].detail == "publication failed"


def test_the_lookback_bounds_the_closed_attempts_listed_and_never_the_open_ones() -> None:
    log, rows, clock = stores(ADMITTED)
    seeded(log, rows, 1, closed_completed())
    seeded(log, rows, 2, awaiting())
    clock.at = ADMITTED + timedelta(days=8)
    composed = composition(Recording())
    listed = snapshot_of(log, rows, composed)
    assert [each.run_id for each in listed.attempts] == [run_of(2)]
    wide = composition(Recording(), lookback=timedelta(days=9))
    assert {each.run_id for each in snapshot_of(log, rows, wide).attempts} == {run_of(1), run_of(2)}


def test_a_row_repair_writes_the_logs_decision_onto_the_row() -> None:
    log, rows, clock = stores(ADMITTED)
    declined = histories.HISTORIES["a declined attempt"]()
    seeded(log, rows, 1, declined)
    log.publications[(run_of(1), 1)] = record(run_of(1), 1, PublicationStatus.PUBLISHED)
    clock.at = ADMITTED + timedelta(minutes=1)
    report = sweep(log, rows, composition(Recording()))
    closed = log.load(run_of(1), 1, rules=RULES).closed
    assert closed is not None
    assert [outcome.action for outcome in report] == [
        RepairRow(rows.live[0].public_id, Decision.DECLINED, closed.timestamp)
    ]
    assert (
        rows.live[0].decision is Decision.DECLINED and rows.live[0].decided_at == closed.timestamp
    )
    assert sweep(log, rows, composition(Recording())) == ()


def test_an_action_the_driver_does_not_know_raises() -> None:
    @dataclass(frozen=True)
    class Unknown:
        run_id: str

    log, rows, _ = stores(ADMITTED)
    with pytest.raises(TypeError, match="Unknown"):
        perform(cast(SweepAction, Unknown("r")), log, rows, composition(Recording()))
