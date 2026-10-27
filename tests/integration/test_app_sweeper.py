"""The sweeper over the real stores: a closed public attempt published through the agent's
publish command with its inventory, both sealed in an in-memory object store; the
fifteen-minute close under the decision's session lock with a decision shown waiting on
it (history 2 as a real race); a recorded stop finalized by the terminal worker taking and
releasing the real slot.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta

import pytest

from leaveimpact.adapters.wiring import inventory_publisher_over, run_export_publisher_over
from leaveimpact.agent.commands import (
    CommandRefused,
    InventoryRequest,
    InventoryWritten,
    PublishRequest,
    publish,
    write_inventory,
)
from leaveimpact.agent.inventory import PublicationRecord
from leaveimpact.agent.log_events import Abandoned, Failed, LoggedEvent, SegmentEnded, WorkerStamp
from leaveimpact.agent.log_store import LogStore
from leaveimpact.agent.log_transition import Appended, AttemptState, Refused
from leaveimpact.app.decide import (
    DecideComposition,
    DecideRefusalKind,
    DecideRequest,
    deadline_of,
    decide,
)
from leaveimpact.app.live import Decision, LiveDraft, LiveRow, key_digest_of, public_id_for
from leaveimpact.app.public import PublicationDraft
from leaveimpact.app.store import AppStore
from leaveimpact.app.sweeper import (
    DEMO_SWEEPER,
    CloseWait,
    Finalize,
    Publish,
    RepairRow,
    SweepComposition,
    WriteInventory,
    actions_of,
    perform,
    snapshot_of,
    sweep,
)
from leaveimpact.core import AbandonmentReason
from leaveimpact.core.inventory import PublicationStatus
from tests.integration.log_store_support import Hold, Rig, Scripted, rig, wait_until_blocked
from tests.integration.test_app_start import app_store
from tests.integration.test_log_store import LEDGER, opened, replay
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.test_app_decide import DIGEST, decided, refused
from tests.unit.test_app_start import key
from tests.unit.test_app_sweeper import (
    LIVE,
    awaiting,
    closed_completed,
    public,
    run_of,
    running,
    stopped,
)

pytestmark = pytest.mark.integration

_ = rig  # the fixture, imported for pytest to find

RULES = histories.RULES
CONFIGURATION = replace(LIVE, ledger_id=LEDGER)


def prepared(rig: Rig) -> tuple[LogStore, AppStore]:
    log = opened(rig)
    store = app_store(rig)
    store.ensure_schema()
    return log, store


def replayed(
    log: LogStore,
    store: AppStore,
    number: int,
    events: tuple[LoggedEvent, ...],
    *,
    upto: int | None = None,
) -> LiveRow:
    """The history replayed as the public attempt started under ``key(number)``, its two
    rows written as the start writes them."""
    history = public(events, number)
    state = replay(log, history, upto=upto)
    inputs = state.inputs
    assert inputs is not None
    digest = key_digest_of(key(number))
    with store.start_section() as writer:
        return writer.write(
            PublicationDraft(
                public_id_for(digest),
                run_of(number),
                1,
                inputs.context.world_version,
                inputs.context.scenario_id,
                None,
                "demo-start",
            ),
            LiveDraft(public_id_for(digest), run_of(number), 1, digest, history[0].timestamp),
        )


def composition(log: LogStore, objects: InMemoryObjectStore, **changes: object) -> SweepComposition:
    exporter = run_export_publisher_over(objects)
    inventorier = inventory_publisher_over(objects)

    def publish_export(request: PublishRequest) -> PublicationRecord | CommandRefused:
        return publish(request, log, exporter, rules=RULES)

    def inventory(request: InventoryRequest) -> InventoryWritten:
        return write_inventory(request, log, inventorier, rules=RULES)

    fields: dict[str, object] = {
        "configuration": CONFIGURATION,
        "rules": RULES,
        "harness": cases.REVISION,
        "reader_commit": cases.COMMIT,
        "publish_export": publish_export,
        "write_inventory": inventory,
        "nonces": iter(f"nonce-sweep-{n}" for n in range(1, 100)).__next__,
    }
    fields.update(changes)
    return SweepComposition(**fields)  # type: ignore[arg-type]


def test_a_closed_public_attempt_is_published_with_its_inventory_and_the_row_repaired(
    rig: Rig,
) -> None:
    log, store = prepared(rig)
    row = replayed(log, store, 1, closed_completed())
    objects = InMemoryObjectStore()
    composed = composition(log, objects)
    report = sweep(log, store, composed)
    assert [type(outcome.action) for outcome in report] == [RepairRow, Publish, WriteInventory]
    assert all(outcome.carried for outcome in report), report
    assert report[1].detail == "publication published"
    record = log.publication_of(run_of(1), 1)
    assert record is not None and record.state is PublicationStatus.PUBLISHED
    assert record.object_identity is not None and objects.get(record.object_identity) is not None
    assert len(objects.list_keys("")) == 2, "the export and the inventory"
    repaired = store.live_row_of(row.public_id)
    assert repaired is not None and repaired.decision is Decision.APPROVED
    assert sweep(log, store, composed) == (), "published, recorded and remembered"
    # A fresh process remembers no inventory and writes the scope's once more: a new
    # object, since the inventory carries the instant of the snapshot it was built from.
    restarted = sweep(log, store, composition(log, objects))
    assert [type(outcome.action) for outcome in restarted] == [WriteInventory]
    assert len(objects.list_keys("")) == 3


def test_the_wait_is_closed_under_the_lock_while_a_decision_waits_on_it(rig: Rig) -> None:
    """History 2 as a race on the real store: the sweeper holds the decision's session lock
    at ``serialized`` with its clock at the deadline; a decision scripted a second before
    the deadline is shown waiting on the lock; released, the sweeper closes the attempt
    as cancelled and the decision, reading the log under the lock after it, is refused
    with the log's own reason, nothing appended for it."""
    log, store = prepared(rig)
    row = replayed(log, store, 1, awaiting(), upto=9)
    deadline = deadline_of(log.load(run_of(1), 1, rules=RULES), CONFIGURATION)
    assert deadline is not None
    hold = Hold("serialized")
    # The sweeper reads the clock for the snapshot, under the lock, and for the closure.
    sweeper_log = rig.store(clock=Scripted([deadline, deadline, deadline]), boundary=hold)
    decider_log = rig.store(clock=Scripted([deadline - timedelta(seconds=1)]))
    composed = composition(sweeper_log, InMemoryObjectStore())
    actions = actions_of(
        snapshot_of(sweeper_log, store, composed), CONFIGURATION, harness_commit=cases.COMMIT
    )
    assert actions == (CloseWait(run_of(1), 1),)
    request = DecideRequest(row.public_id, key(1), Decision.APPROVED, DIGEST)
    with ThreadPoolExecutor(max_workers=2) as pool, rig.observer() as observer:
        closing = pool.submit(perform, actions[0], sweeper_log, store, composed)
        hold.wait_reached()
        deciding = pool.submit(
            decide, request, decider_log, app_store(rig), DecideComposition(CONFIGURATION, RULES)
        )
        wait_until_blocked(observer, rig.backend_pid(decider_log))
        hold.release.set()
        outcome = closing.result(timeout=10)
        late = refused(deciding.result(timeout=10), DecideRefusalKind.LOG_REFUSED)
    assert outcome.carried and outcome.detail == "cancelled at position 10"
    assert late.detail == "the attempt is closed at position 10"
    state = log.load(run_of(1), 1, rules=RULES)
    assert state.closed is not None and state.closed.envelope == DEMO_SWEEPER
    assert isinstance(state.closed.event, Abandoned)
    assert state.closed.event.reason is AbandonmentReason.CANCELLED
    assert state.last_position == 10, "nothing appended for the decision"


def test_a_recorded_stop_is_finalized_through_the_real_slot(rig: Rig) -> None:
    log, store = prepared(rig)
    replayed(log, store, 1, stopped())
    held = log.execution_slot()
    assert held is not None and (held.run_id, held.generation) == (run_of(1), 1), (
        "the dead worker's claim holds the slot"
    )
    report = sweep(log, store, composition(log, InMemoryObjectStore()))
    assert [outcome.action for outcome in report] == [Finalize(run_of(1), 1)]
    assert report[0].carried and report[0].detail == "closed: failed"
    state = log.load(run_of(1), 1, rules=RULES)
    assert state.closed is not None and isinstance(state.closed.event, Failed)
    assert state.generation == 2, "claimed by the terminal worker at the next generation"
    assert log.execution_slot() is None, "the claim took the slot and the closure released it"


def test_a_decision_in_time_leaves_the_pass_at_the_deadline_nothing_to_close(rig: Rig) -> None:
    """History 1 on the real store, and the row repaired by the pass if the decision's own
    record of it was lost."""
    log, store = prepared(rig)
    row = replayed(log, store, 1, awaiting(), upto=9)
    approved = decided(
        decide(
            DecideRequest(row.public_id, key(1), Decision.APPROVED, DIGEST),
            log,
            store,
            DecideComposition(CONFIGURATION, RULES),
        )
    )
    deadline = deadline_of(log.load(run_of(1), 1, rules=RULES), CONFIGURATION)
    assert deadline is not None
    later = rig.store(clock=Scripted([deadline + timedelta(hours=1)]))
    assert sweep(later, store, composition(later, InMemoryObjectStore())) == ()
    assert log.load(run_of(1), 1, rules=RULES).closed is None
    assert store.live_row_of(row.public_id) == approved.row


def test_a_closures_precondition_is_read_on_the_state_the_store_folds_under_the_lock(
    rig: Rig,
) -> None:
    """The store's precondition on the real store: the sweeper decided on a state it read;
    the worker's segment end then landed through another store; the closure hands the
    stale state in and the store folds the current log under the lock, so the precondition
    reads the ended segment and refuses without appending or settling anything."""
    log, store = prepared(rig)
    replayed(log, store, 1, running())
    stale = log.load(run_of(1), 1, rules=RULES)
    worker = rig.store()
    ended = worker.append(run_of(1), 1, WorkerStamp(1, 1, 2_000), SegmentEnded(), rules=RULES)
    assert isinstance(ended, Appended)

    def still_open(current: AttemptState) -> str | None:
        segment = current.current_segment
        return None if segment is not None and not segment.ended else "the segment ended"

    refused = log.close_attempt(
        run_of(1),
        1,
        DEMO_SWEEPER,
        Abandoned(stale.generation, AbandonmentReason.INTERRUPTED, None),
        rules=RULES,
        state=stale,
        precondition=still_open,
    )
    assert refused == Refused("the segment ended")
    latest = log.load(run_of(1), 1, rules=RULES)
    assert latest.closed is None and latest.last_position == ended.state.last_position
    assert log.execution_slot() is None, "the end released the slot; the closure took nothing"
