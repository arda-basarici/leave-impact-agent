"""The store's snapshot as plain data, and the inventory built from it, pure.

The store reads what it holds at one instant (the event log step's ruling on the job seam,
part 5) and returns rows and events; nothing here connects. The builder folds each
attempt's log under the registered rules for its status, its figures and the digest of the
prefix it read, projects the ledger and the publication records field for field onto the
``core`` types the evaluator reads, and lists every refused admission. The result is the
inventory object the write-inventory command seals; its identity is the digest of its
bytes.

An attempt admitted under rules that are not the builder's cannot be folded by it: the
transition refuses every event after the admission on the attribution table or the
re-dispatch policy. Such an attempt is listed from its row alone, open or closed, with no
status and no figures, which is what an evaluation under another registration needs of it
(ruling 10, part 9: an open attempt outside the scope blocks nothing). Any other log that
will not fold is an invariant broken, raised naming the run and the attempt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from leaveimpact.agent.ledger import LedgerEntry, LedgerHead
from leaveimpact.agent.log_ending import Ending, status_of
from leaveimpact.agent.log_events import Admitted, LoggedEvent, log_digest
from leaveimpact.agent.log_transition import Rules, fold, rules_differ
from leaveimpact.core.inventory import (
    INVENTORY_FORMAT_VERSION,
    AttemptEnding,
    AttemptStatus,
    Inventory,
    InventoryAttempt,
    InventoryLedger,
    InventoryLedgerEntry,
    InventoryScope,
    InventorySnapshot,
    PublicationObserved,
    PublicationStatus,
    RefusedAdmission,
)
from leaveimpact.core.run_account import figures_of
from leaveimpact.core.run_timing import require_commit

# --- The snapshot --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PublicationRecord:
    """One attempt's publication, apart from its log (ruling 10, part 4): the state, the
    reader's commit and export format, the digest of the closed log it read, the object's
    identity and digest (intended while pending, held once published, absent together for
    a failure before any object was intended), the incident of a failure, the commit a
    repair replaced, and when the record was last written."""

    run_id: str
    attempt: int
    state: PublicationStatus
    reader_commit: str
    export_format: int
    log_digest: str
    object_identity: str | None
    object_digest: str | None
    incident: str | None
    repaired_from_commit: str | None
    recorded_at: datetime

    def __post_init__(self) -> None:
        if (self.object_identity is None) != (self.object_digest is None):
            raise ValueError("an object's identity and digest are recorded together or neither")
        if self.object_identity is None and self.state is not PublicationStatus.FAILED:
            raise ValueError("only a failed publication records no object")


@dataclass(frozen=True, slots=True)
class SnapshotAttempt:
    """One attempt as the snapshot read it: the row's identity, closed value and ledger, the
    log up to the row's position, and the publication record if one was begun."""

    run_id: str
    attempt: int
    closed: bool
    ledger_id: str | None
    events: tuple[LoggedEvent, ...]
    publication: PublicationRecord | None


@dataclass(frozen=True, slots=True)
class SnapshotEntry:
    """A ledger entry with the time it was recorded, which the entry type does not carry."""

    entry: LedgerEntry
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class SnapshotLedger:
    """A ledger as the snapshot read it: its head and every entry in revision order."""

    ledger_id: str
    head: LedgerHead
    entries: tuple[SnapshotEntry, ...]


@dataclass(frozen=True, slots=True)
class RefusedRequest:
    """An admission request the store refused and recorded."""

    request_id: str
    run_id: str
    attempt: int
    reason: str
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class StoreSnapshot:
    """What the store held at one instant: the schema's version, the clock just after the
    snapshot was fixed, every attempt in run and attempt order, the one ledger asked for
    (``None`` before its head exists), and every refused admission."""

    schema_version: int
    taken_at: datetime
    attempts: tuple[SnapshotAttempt, ...]
    ledger: SnapshotLedger | None
    refused: tuple[RefusedRequest, ...]


# --- The build -----------------------------------------------------------------------------


def inventory_of(
    snapshot: StoreSnapshot, scope: InventoryScope, *, builder_commit: str, rules: Rules
) -> Inventory:
    """The inventory of ``snapshot`` for ``scope``, built by the code at ``builder_commit``
    folding under ``rules``; ``ValueError`` for a log that will not fold under the rules it
    froze, or a row that disagrees with its log."""
    require_commit(builder_commit, "the builder's commit")
    if snapshot.ledger is not None and snapshot.ledger.ledger_id != scope.ledger_id:
        raise ValueError(
            f"the snapshot read ledger {snapshot.ledger.ledger_id} and the scope names "
            f"{scope.ledger_id}"
        )
    return Inventory(
        INVENTORY_FORMAT_VERSION,
        scope,
        InventorySnapshot(snapshot.schema_version, builder_commit, snapshot.taken_at),
        None if snapshot.ledger is None else _ledger_of(snapshot.ledger),
        tuple(_attempt_of(each, rules) for each in snapshot.attempts),
        tuple(
            RefusedAdmission(
                each.request_id, each.run_id, each.attempt, each.reason, each.recorded_at
            )
            for each in snapshot.refused
        ),
    )


def _attempt_of(each: SnapshotAttempt, rules: Rules) -> InventoryAttempt:
    where = f"run {each.run_id} attempt {each.attempt}"
    if not each.events or not isinstance(each.events[0].event, Admitted):
        raise ValueError(f"{where}'s log does not begin with its admission")
    inputs = each.events[0].event.inputs
    if (inputs.run_id, inputs.attempt) != (each.run_id, each.attempt):
        raise ValueError(f"{where}'s admission names another attempt")
    status = figures = None
    if rules_differ(inputs, rules) is None:
        try:
            state = fold(each.events, rules)
        except ValueError as exc:
            raise ValueError(f"{where}'s log does not fold: {exc}") from None
        if (state.closed is not None) != each.closed:
            raise ValueError(f"{where}'s row disagrees with its log on whether it is closed")
        found = status_of(state)
        status = AttemptStatus(
            None if found.ending is None else _ending_of(found.ending),
            found.segment,
            found.approval,
        )
        figures = figures_of(state.account)
    return InventoryAttempt(
        each.run_id,
        each.attempt,
        inputs.context.world_version,
        inputs.preregistration_commit,
        each.ledger_id,
        each.closed,
        status,
        len(each.events),
        log_digest(each.events),
        figures,
        None if each.publication is None else _publication_of(each.publication),
    )


def _ending_of(ending: Ending) -> AttemptEnding:
    failure = ending.failure
    return AttemptEnding(
        ending.status,
        None if failure is None else failure.category,
        None if failure is None else failure.site,
        ending.abandonment,
    )


def _publication_of(record: PublicationRecord) -> PublicationObserved:
    return PublicationObserved(
        record.state,
        record.reader_commit,
        record.export_format,
        record.log_digest,
        record.object_identity,
        record.object_digest,
        record.incident,
        record.repaired_from_commit,
        record.recorded_at,
    )


def _ledger_of(read: SnapshotLedger) -> InventoryLedger:
    return InventoryLedger(
        read.ledger_id,
        read.head.total_pico_usd,
        read.head.revision,
        read.head.threshold_pico_usd,
        tuple(
            InventoryLedgerEntry(
                each.entry.revision,
                each.entry.kind.value,
                each.entry.run_id,
                each.entry.attempt,
                each.entry.amount_pico_usd,
                each.entry.total_after_pico_usd,
                each.entry.authority,
                each.entry.registration_commit,
                each.entry.reason,
                each.recorded_at,
            )
            for each in read.entries
        ),
    )


__all__ = [
    "PublicationRecord",
    "RefusedRequest",
    "SnapshotAttempt",
    "SnapshotEntry",
    "SnapshotLedger",
    "StoreSnapshot",
    "inventory_of",
]
