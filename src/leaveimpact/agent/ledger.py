"""The shared ledger's pure half: its entries, its head, and the decisions the store applies.

The ledger is where every run's money meets the one threshold an authority set for the
measurement (the event log step's ruling on the ledger, parts 7 to 10). It is append-only
entries of five kinds and one head holding the committed total and the revision, the
revision being the count of entries written, refusals and threshold changes included. An
open attempt holds its full reservation against the threshold; at closure that is
replaced by what its dispatches cost, and a kept reservation stays as the held amount. A
threshold is applied prospectively, never above the registered limit and never below the
committed total, so no allowance already given is shrunk.

Everything here is a function of a head and an entry's inputs; the PostgreSQL module
locks the head row, calls these, and writes what they return. ``fold`` rebuilds a head
from its entries so a stored head can be checked against its own history.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.run_trace import require_integer, require_opaque_id


class EntryKind(StrEnum):
    """The five kinds of entry, closed; a member is the stored form."""

    THRESHOLD_SET = "threshold_set"
    ADMITTED = "admitted"
    REFUSED = "refused"
    SETTLED = "settled"
    IMPORTED = "imported"


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One appended entry: its revision, its kind, the attempt it concerns (none for a
    threshold or an import), the kind's amount (the threshold set, the reservation
    admitted or refused, the amount charged at settlement, the amount imported), the
    committed total after it, and for a threshold or an import who set it and from which
    registration commit; a refusal carries its reason."""

    revision: int
    kind: EntryKind
    run_id: str | None
    attempt: int | None
    amount_pico_usd: int
    total_after_pico_usd: int
    authority: str | None = None
    registration_commit: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        require_integer(self.revision, "a ledger revision", minimum=1)
        require_integer(self.amount_pico_usd, "an entry's amount in pico-dollars")
        require_integer(self.total_after_pico_usd, "the committed total in pico-dollars")
        if (self.run_id is None) != (self.attempt is None):
            raise ValueError("an entry names a run and its attempt together or neither")
        if self.run_id is not None:
            require_opaque_id(self.run_id, "a run id")
            require_integer(self.attempt, "an attempt number", minimum=1)
        about_an_attempt = self.kind in (EntryKind.ADMITTED, EntryKind.REFUSED, EntryKind.SETTLED)
        if about_an_attempt != (self.run_id is not None):
            raise ValueError(
                f"a {self.kind.value} entry names an attempt exactly when it is about one"
            )
        if (self.reason is not None) != (self.kind is EntryKind.REFUSED):
            raise ValueError("a reason is given exactly on a refusal")
        if (self.authority is not None) != (not about_an_attempt):
            raise ValueError("an authority is named exactly on a threshold or an import")


@dataclass(frozen=True, slots=True)
class LedgerHead:
    """The head as it stands: the committed total, the revision, and the threshold in force,
    ``None`` until the first threshold entry.

    >>> LedgerHead().room_pico_usd
    0
    """

    total_pico_usd: int = 0
    revision: int = 0
    threshold_pico_usd: int | None = None

    @property
    def room_pico_usd(self) -> int:
        """What the threshold still admits; nothing before a threshold is set."""
        if self.threshold_pico_usd is None:
            return 0
        return max(0, self.threshold_pico_usd - self.total_pico_usd)


# --- Decisions -------------------------------------------------------------------------------


def reservation_refusal(head: LedgerHead, amount_pico_usd: int) -> str | None:
    """Why ``head`` refuses a reservation of ``amount_pico_usd``, or ``None`` when it fits.

    >>> reservation_refusal(LedgerHead(), 10)
    'no threshold is set on the ledger'
    >>> reservation_refusal(LedgerHead(90, 3, 100), 10) is None
    True
    >>> reservation_refusal(LedgerHead(90, 3, 100), 11)
    'a reservation of 11 pico-dollars exceeds the room of 10 under the threshold of 100'
    """
    require_integer(amount_pico_usd, "a reservation in pico-dollars")
    if head.threshold_pico_usd is None:
        return "no threshold is set on the ledger"
    if amount_pico_usd > head.room_pico_usd:
        return (
            f"a reservation of {amount_pico_usd} pico-dollars exceeds the room of "
            f"{head.room_pico_usd} under the threshold of {head.threshold_pico_usd}"
        )
    return None


def threshold_refusal(head: LedgerHead, amount_pico_usd: int, *, limit_pico_usd: int) -> str | None:
    """Why ``head`` refuses a threshold of ``amount_pico_usd`` under the registered
    ``limit_pico_usd``, or ``None``: never above the limit, never below the committed total.

    >>> threshold_refusal(LedgerHead(50, 2, 80), 100, limit_pico_usd=90)
    'a threshold of 100 pico-dollars is above the registered limit of 90'
    >>> threshold_refusal(LedgerHead(50, 2, 80), 40, limit_pico_usd=90)
    'a threshold of 40 pico-dollars is below the committed total of 50'
    """
    require_integer(amount_pico_usd, "a threshold in pico-dollars")
    require_integer(limit_pico_usd, "the registered limit in pico-dollars")
    if amount_pico_usd > limit_pico_usd:
        return (
            f"a threshold of {amount_pico_usd} pico-dollars is above the registered limit of "
            f"{limit_pico_usd}"
        )
    if amount_pico_usd < head.total_pico_usd:
        return (
            f"a threshold of {amount_pico_usd} pico-dollars is below the committed total of "
            f"{head.total_pico_usd}"
        )
    return None


# --- The entries, each with the head after it -------------------------------------------------


def threshold_set(
    head: LedgerHead, amount_pico_usd: int, *, authority: str, registration_commit: str
) -> tuple[LedgerEntry, LedgerHead]:
    """The entry setting the threshold to ``amount_pico_usd``; the decision is the caller's
    (``threshold_refusal``), this writes it."""
    entry = LedgerEntry(
        head.revision + 1,
        EntryKind.THRESHOLD_SET,
        None,
        None,
        amount_pico_usd,
        head.total_pico_usd,
        authority=authority,
        registration_commit=registration_commit,
    )
    return entry, apply(head, entry)


def admitted(
    head: LedgerHead, run_id: str, attempt: int, reservation_pico_usd: int
) -> tuple[LedgerEntry, LedgerHead]:
    """The entry reserving ``reservation_pico_usd`` for the attempt; the total grows by it."""
    entry = LedgerEntry(
        head.revision + 1,
        EntryKind.ADMITTED,
        run_id,
        attempt,
        reservation_pico_usd,
        head.total_pico_usd + reservation_pico_usd,
    )
    return entry, apply(head, entry)


def refused(
    head: LedgerHead, run_id: str, attempt: int, reservation_pico_usd: int, *, reason: str
) -> tuple[LedgerEntry, LedgerHead]:
    """The entry recording that the ledger refused the attempt's reservation; the total is
    unchanged and the revision advances, as the ruling counts refusals."""
    entry = LedgerEntry(
        head.revision + 1,
        EntryKind.REFUSED,
        run_id,
        attempt,
        reservation_pico_usd,
        head.total_pico_usd,
        reason=reason,
    )
    return entry, apply(head, entry)


def settled(
    head: LedgerHead,
    run_id: str,
    attempt: int,
    *,
    reservation_pico_usd: int,
    charged_pico_usd: int,
) -> tuple[LedgerEntry, LedgerHead]:
    """The entry replacing the attempt's reservation with what it was charged.

    >>> head = LedgerHead(100, 2, 500)
    >>> entry, after = settled(head, "run-1", 1, reservation_pico_usd=100, charged_pico_usd=35)
    >>> entry.amount_pico_usd, after.total_pico_usd, after.revision
    (35, 35, 3)
    """
    require_integer(reservation_pico_usd, "the reservation in pico-dollars")
    require_integer(charged_pico_usd, "the amount charged in pico-dollars")
    entry = LedgerEntry(
        head.revision + 1,
        EntryKind.SETTLED,
        run_id,
        attempt,
        charged_pico_usd,
        head.total_pico_usd - reservation_pico_usd + charged_pico_usd,
    )
    return entry, apply(head, entry)


def imported(
    head: LedgerHead, amount_pico_usd: int, *, authority: str, registration_commit: str
) -> tuple[LedgerEntry, LedgerHead]:
    """The entry adding spend made outside the log (the spike's usage) to the total."""
    entry = LedgerEntry(
        head.revision + 1,
        EntryKind.IMPORTED,
        None,
        None,
        amount_pico_usd,
        head.total_pico_usd + amount_pico_usd,
        authority=authority,
        registration_commit=registration_commit,
    )
    return entry, apply(head, entry)


# --- Reading back --------------------------------------------------------------------------


def apply(head: LedgerHead, entry: LedgerEntry) -> LedgerHead:
    """The head after ``entry``; ``ValueError`` unless the entry is the next revision."""
    if entry.revision != head.revision + 1:
        raise ValueError(
            f"ledger revisions are dense: the next is {head.revision + 1}, got {entry.revision}"
        )
    threshold = (
        entry.amount_pico_usd if entry.kind is EntryKind.THRESHOLD_SET else head.threshold_pico_usd
    )
    return LedgerHead(entry.total_after_pico_usd, entry.revision, threshold)


def fold(entries: Iterable[LedgerEntry]) -> LedgerHead:
    """The head a sequence of entries builds from the empty ledger."""
    head = LedgerHead()
    for entry in entries:
        head = apply(head, entry)
    return head


__all__ = [
    "EntryKind",
    "LedgerEntry",
    "LedgerHead",
    "admitted",
    "apply",
    "fold",
    "imported",
    "refused",
    "reservation_refusal",
    "settled",
    "threshold_refusal",
    "threshold_set",
]
