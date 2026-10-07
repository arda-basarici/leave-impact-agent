"""The inventory built from a hand-built snapshot: every attempt listed in order with the
fold's status, figures, position and prefix digest, an attempt under another registration's
rules listed from its row alone, the ledger and the publication records projected field for
field, the refusals carried, the forecast figures of the unresolved-dispatch history
reproduced, and a row that disagrees with its log or a log that will not fold refused
naming the attempt; the result round-trips through the codec."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from leaveimpact.agent import ledger
from leaveimpact.agent.inventory import (
    PublicationRecord,
    RefusedRequest,
    SnapshotAttempt,
    SnapshotEntry,
    SnapshotLedger,
    StoreSnapshot,
    inventory_of,
)
from leaveimpact.agent.log_events import Admitted, LoggedEvent, log_digest
from leaveimpact.agent.log_transition import Rules
from leaveimpact.core.inventory import (
    InventoryScope,
    PublicationStatus,
    decode_inventory_bytes,
    inventory_bytes,
)
from leaveimpact.core.run_ending import AbandonmentReason, ApprovalState, SegmentStatus
from leaveimpact.core.run_record import FailureCategory, TerminalStatus
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories

RULES = histories.RULES
AT = datetime(2026, 10, 7, 10, 0, tzinfo=UTC)
BUILDER = "b" * 40
LEDGER = "ledger-test"


def renamed(events: tuple[LoggedEvent, ...], run_id: str) -> tuple[LoggedEvent, ...]:
    """``events`` admitted as ``run_id``, so one snapshot holds several histories."""
    first = events[0]
    assert isinstance(first.event, Admitted)
    admitted = Admitted(replace(first.event.inputs, run_id=run_id))
    return (replace(first, event=admitted), *events[1:])


def attempt(
    events: tuple[LoggedEvent, ...],
    run_id: str,
    *,
    closed: bool,
    publication: PublicationRecord | None = None,
) -> SnapshotAttempt:
    first = events[0]
    assert isinstance(first.event, Admitted)
    reserved = first.event.inputs.reservation_pico_usd
    return SnapshotAttempt(
        run_id, 1, closed, None if reserved is None else LEDGER, events, publication
    )


ABANDONED = renamed(histories.HISTORIES["an abandoned attempt"](), "run-a")
UNRESOLVED = renamed(
    histories.HISTORIES["an unresolved dispatch followed by an answered one"](), "run-b"
)
CUT = renamed(histories.HISTORIES["a cut call"](), "run-c")
OPEN = CUT[:5]
"""The cut call's admission, claim and first reads: an attempt with its segment open."""
FAILED_RECORD = PublicationRecord(
    "run-a",
    1,
    PublicationStatus.FAILED,
    cases.COMMIT,
    3,
    "e" * 64,
    "runs/x",
    "f" * 64,
    "Boom",
    None,
    AT,
)


def head_and_entries() -> SnapshotLedger:
    head = ledger.LedgerHead()
    threshold, head = ledger.threshold_set(
        head, 10**15, authority="operator:test", registration_commit=cases.COMMIT
    )
    admitted, head = ledger.admitted(head, "run-a", 1, 5_000_000_000)
    refused, head = ledger.refused(head, "run-z", 1, 10**16, reason="no room")
    settled, head = ledger.settled(
        head, "run-a", 1, reservation_pico_usd=5_000_000_000, charged_pico_usd=297_000_000
    )
    entries = tuple(SnapshotEntry(entry, AT) for entry in (threshold, admitted, refused, settled))
    return SnapshotLedger(LEDGER, head, entries)


SNAPSHOT = StoreSnapshot(
    2,
    AT,
    (
        attempt(ABANDONED, "run-a", closed=True, publication=FAILED_RECORD),
        attempt(UNRESOLVED, "run-b", closed=True),
        attempt(OPEN, "run-c", closed=False),
    ),
    head_and_entries(),
    (RefusedRequest("req-z", "run-z", 1, "no room", AT),),
)
WORLD_VERSION = cases.CONTEXT.world_version
SCOPE = InventoryScope(WORLD_VERSION, cases.COMMIT, LEDGER)


def test_every_attempt_is_listed_in_order_with_the_folds_status_and_where_it_was_read() -> None:
    inventory = inventory_of(SNAPSHOT, SCOPE, builder_commit=BUILDER, rules=RULES)
    assert [(a.run_id, a.attempt) for a in inventory.attempts] == [
        ("run-a", 1),
        ("run-b", 1),
        ("run-c", 1),
    ]
    abandoned, unresolved, open_one = inventory.attempts
    assert abandoned.closed and abandoned.status is not None and abandoned.status.ending is not None
    assert abandoned.status.ending.status is TerminalStatus.FAILED
    assert abandoned.status.ending.failure_category is FailureCategory.INFRASTRUCTURE
    assert abandoned.status.ending.abandonment is not None
    assert abandoned.status.ending.abandonment.reason is AbandonmentReason.CANCELLED
    assert abandoned.status.segment is SegmentStatus.OPEN, "the worker never ended it"
    assert abandoned.status.approval is ApprovalState.REQUESTED_UNAPPROVED
    assert (abandoned.position, abandoned.prefix_digest) == (len(ABANDONED), log_digest(ABANDONED))
    assert (
        abandoned.publication is not None
        and abandoned.publication.status is PublicationStatus.FAILED
    )
    assert (
        abandoned.publication.incident == "Boom"
        and abandoned.publication.reader_commit == cases.COMMIT
    )
    assert unresolved.status is not None and unresolved.status.ending is not None
    assert unresolved.status.ending.status is TerminalStatus.COMPLETED
    assert not open_one.closed and open_one.status is not None and open_one.status.ending is None
    assert open_one.status.segment is SegmentStatus.OPEN and open_one.publication is None
    assert (open_one.position, open_one.prefix_digest) == (5, log_digest(OPEN))
    assert open_one.world_version == WORLD_VERSION
    assert open_one.registration_commit == cases.COMMIT and open_one.ledger_id == LEDGER


def test_the_unresolved_dispatch_history_reproduces_the_forecast_figures() -> None:
    """Group 2's sixth history, the inventory's view of the unresolved dispatch beside the
    answered one: the known consumption is the answered dispatch's priced cost, the
    retained liability the unresolved dispatch's whole allocation, and their total the
    charged amount the export fixture's reservation pins. The step's rulings file had
    written the retained figure by hand as 17,457,000,000 and the total as 17,754,000,000;
    no fixture held those, and this test pins the fixture's."""
    inventory = inventory_of(SNAPSHOT, SCOPE, builder_commit=BUILDER, rules=RULES)
    figures = inventory.attempts[1].figures
    assert figures is not None
    reservation = cases.unresolved_then_answered().record.reservation
    assert reservation is not None
    assert (figures.known_pico_usd, figures.retained_pico_usd, figures.total_pico_usd) == (
        297_000_000,
        8_448_000_000,
        8_745_000_000,
    )
    assert figures.total_pico_usd == reservation.charged_pico_usd


def test_the_ledger_and_the_refusals_are_carried_field_for_field() -> None:
    inventory = inventory_of(SNAPSHOT, SCOPE, builder_commit=BUILDER, rules=RULES)
    assert inventory.ledger is not None
    assert (inventory.ledger.revision, inventory.ledger.total_pico_usd) == (4, 297_000_000)
    assert inventory.ledger.threshold_pico_usd == 10**15
    assert [e.kind for e in inventory.ledger.entries] == [
        "threshold_set",
        "admitted",
        "refused",
        "settled",
    ]
    assert inventory.ledger.entries[2].reason == "no room"
    assert inventory.ledger.entries[0].authority == "operator:test"
    assert all(e.recorded_at == AT for e in inventory.ledger.entries)
    assert inventory.refused[0].request_id == "req-z" and inventory.refused[0].reason == "no room"
    assert (inventory.snapshot.schema_version, inventory.snapshot.builder_commit) == (2, BUILDER)
    assert inventory.snapshot.taken_at == AT and inventory.scope == SCOPE


def test_an_attempt_under_another_registrations_rules_is_listed_from_its_row_alone() -> None:
    foreign = Rules(None, None)
    inventory = inventory_of(SNAPSHOT, SCOPE, builder_commit=BUILDER, rules=foreign)
    assert [a.status for a in inventory.attempts] == [None, None, None]
    assert [a.figures for a in inventory.attempts] == [None, None, None]
    assert [a.closed for a in inventory.attempts] == [True, True, False]
    assert inventory.attempts[0].prefix_digest == log_digest(ABANDONED)


def test_the_inventory_round_trips_through_the_codec() -> None:
    inventory = inventory_of(SNAPSHOT, SCOPE, builder_commit=BUILDER, rules=RULES)
    assert decode_inventory_bytes(inventory_bytes(inventory)) == inventory


def test_a_row_that_disagrees_with_its_log_is_refused_naming_the_attempt() -> None:
    disagreeing = replace(SNAPSHOT, attempts=(attempt(ABANDONED, "run-a", closed=False),))
    with pytest.raises(ValueError, match="run run-a attempt 1's row disagrees with its log"):
        inventory_of(disagreeing, SCOPE, builder_commit=BUILDER, rules=RULES)


def test_a_log_that_will_not_fold_under_its_own_rules_is_refused_naming_the_attempt() -> None:
    reordered = (*CUT[:2], CUT[3], CUT[2], *CUT[4:])
    broken = replace(SNAPSHOT, attempts=(attempt(reordered, "run-c", closed=True),))
    with pytest.raises(ValueError, match="run run-c attempt 1's log does not fold"):
        inventory_of(broken, SCOPE, builder_commit=BUILDER, rules=RULES)


def test_a_log_not_beginning_with_its_admission_is_refused() -> None:
    headless = replace(SNAPSHOT, attempts=(attempt(CUT, "run-c", closed=True),))
    beheaded = replace(headless, attempts=(replace(headless.attempts[0], events=CUT[1:]),))
    with pytest.raises(ValueError, match="does not begin with its admission"):
        inventory_of(beheaded, SCOPE, builder_commit=BUILDER, rules=RULES)


def test_a_snapshot_of_another_ledger_than_the_scopes_is_refused() -> None:
    other = replace(SNAPSHOT, ledger=replace(head_and_entries(), ledger_id="ledger-other"))
    with pytest.raises(
        ValueError, match="read ledger ledger-other and the scope names ledger-test"
    ):
        inventory_of(other, SCOPE, builder_commit=BUILDER, rules=RULES)
