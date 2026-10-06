"""The ledger's pure half: an admission grows the total by its reservation and a settlement
replaces that reservation with the charge, a refusal and a threshold advance the revision
and move no money, the threshold is refused above the registered limit and below the
committed total, a reservation is refused with no threshold and above the room, every head
rebuilds from its entries, and an entry's shape is checked by kind."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from leaveimpact.agent import ledger
from leaveimpact.agent.ledger import EntryKind, LedgerEntry, LedgerHead

COMMIT = "c" * 40


def _opened(threshold: int = 1_000) -> tuple[list[LedgerEntry], LedgerHead]:
    entry, head = ledger.threshold_set(
        LedgerHead(), threshold, authority="operator:arda", registration_commit=COMMIT
    )
    return [entry], head


def test_the_first_threshold_opens_the_ledger_at_revision_one() -> None:
    entries, head = _opened(1_000)
    assert head == LedgerHead(0, 1, 1_000)
    assert entries[0].kind is EntryKind.THRESHOLD_SET and entries[0].amount_pico_usd == 1_000
    assert LedgerHead().room_pico_usd == 0 and head.room_pico_usd == 1_000


def test_an_admission_holds_its_reservation_and_a_settlement_replaces_it() -> None:
    entries, head = _opened(1_000)
    admitted, head = ledger.admitted(head, "run-1", 1, 300)
    assert (head.total_pico_usd, head.revision) == (300, 2)
    settled, head = ledger.settled(head, "run-1", 1, reservation_pico_usd=300, charged_pico_usd=120)
    assert (head.total_pico_usd, head.revision) == (120, 3)
    assert settled.amount_pico_usd == 120 and admitted.amount_pico_usd == 300
    entries += [admitted, settled]
    assert ledger.fold(entries) == head


def test_a_kept_settlement_may_charge_the_whole_reservation() -> None:
    _, head = _opened(1_000)
    _, head = ledger.admitted(head, "run-1", 1, 300)
    _, head = ledger.settled(head, "run-1", 1, reservation_pico_usd=300, charged_pico_usd=300)
    assert head.total_pico_usd == 300


def test_a_refusal_and_a_threshold_change_advance_the_revision_and_move_no_money() -> None:
    _, head = _opened(1_000)
    _, head = ledger.admitted(head, "run-1", 1, 900)
    refused, head = ledger.refused(head, "run-2", 1, 200, reason="over the room")
    assert (head.total_pico_usd, head.revision) == (900, 3)
    assert refused.reason == "over the room" and refused.total_after_pico_usd == 900
    raised, head = ledger.threshold_set(
        head, 2_000, authority="operator:arda", registration_commit=COMMIT
    )
    assert head == LedgerHead(900, 4, 2_000) and raised.total_after_pico_usd == 900


def test_an_import_adds_spend_made_outside_the_log() -> None:
    _, head = _opened(1_000)
    entry, head = ledger.imported(head, 50, authority="import:spike", registration_commit=COMMIT)
    assert head.total_pico_usd == 50 and entry.run_id is None and entry.attempt is None


def test_a_reservation_is_refused_with_no_threshold_and_above_the_room() -> None:
    assert ledger.reservation_refusal(LedgerHead(), 1) == "no threshold is set on the ledger"
    _, head = _opened(1_000)
    _, head = ledger.admitted(head, "run-1", 1, 900)
    assert ledger.reservation_refusal(head, 100) is None
    refusal = ledger.reservation_refusal(head, 101)
    assert refusal is not None and "exceeds the room of 100" in refusal
    assert ledger.reservation_refusal(head, 0) is None


def test_a_threshold_is_refused_above_the_limit_and_below_the_committed_total() -> None:
    _, head = _opened(1_000)
    _, head = ledger.admitted(head, "run-1", 1, 900)
    assert ledger.threshold_refusal(head, 950, limit_pico_usd=5_000) is None
    assert ledger.threshold_refusal(head, 900, limit_pico_usd=5_000) is None
    below = ledger.threshold_refusal(head, 899, limit_pico_usd=5_000)
    assert below is not None and "below the committed total of 900" in below
    above = ledger.threshold_refusal(head, 5_001, limit_pico_usd=5_000)
    assert above is not None and "above the registered limit of 5000" in above


def test_apply_refuses_a_revision_that_is_not_the_next() -> None:
    _, head = _opened()
    with pytest.raises(ValueError, match="dense: the next is 2, got 3"):
        ledger.apply(head, LedgerEntry(3, EntryKind.ADMITTED, "run-1", 1, 10, 10))


@pytest.mark.parametrize(
    ("build", "complaint"),
    [
        (lambda: LedgerEntry(1, EntryKind.ADMITTED, None, None, 1, 1), "exactly when it is about"),
        (
            lambda: LedgerEntry(1, EntryKind.THRESHOLD_SET, "run-1", 1, 1, 0),
            "exactly when it is about",
        ),
        (lambda: LedgerEntry(1, EntryKind.ADMITTED, "run-1", None, 1, 1), "together or neither"),
        (
            lambda: LedgerEntry(1, EntryKind.ADMITTED, "run-1", 1, 1, 1, reason="x"),
            "exactly on a refusal",
        ),
        (
            lambda: LedgerEntry(1, EntryKind.THRESHOLD_SET, None, None, 1, 0),
            "exactly on a threshold or an import",
        ),
    ],
    ids=["admitted-without-attempt", "threshold-with-attempt", "half-named", "reason", "authority"],
)
def test_an_entry_is_checked_by_kind(build: Callable[[], LedgerEntry], complaint: str) -> None:
    with pytest.raises(ValueError, match=complaint):
        build()
