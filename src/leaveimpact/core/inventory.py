"""The harness's inventory of its runs: what the store held at one snapshot, as plain data
with a strict codec, written by the agent and read by the evaluator.

An evaluation grades the exports it finds in the object store; on their own they cannot say
which runs were admitted and never exported, which attempt is still open, what the ledger
charged, or whether an object in the store is the publication a run's record names. The
inventory says so (the event log step's ruling on the job seam, part 5): every attempt the
store holds with its status, the log position and prefix digest it was read at and its
figures, every publication record as observed, the ledger with its entries, the refused
admissions, and the scope and snapshot it was written for. It is an immutable object
identified by the digest of its bytes; a ledger revision could not identify it, since a
segment start, an approval or a publication changes it with no ledger entry.

Identifiers, digests, kinds and integers only, and no scenario content: an ending's failure
carries its category and site and never its reason text, which may quote what a rule was
reading. The three figures are ruling 9's (an export that will not construct, part 4): known
consumption, retained liability and their total, so a closed attempt with no export is a
cost with its uncertainty and never a zero.

The inventory does not prove that every admission or invocation was logged, that events
describe what happened, or that nothing was spent outside the ledger (ruling 10, part 7); it
lets a separate reader find a harness's implementation mistakes and inconsistencies, and
the evaluator's checks over it are the verification of what the harness published.

The types here are a projection of the agent's own (the attempt state, the ledger entry,
the publication record) onto the one package both sides reach; each field list is the
agent's, with the reason text dropped and the recorded times kept.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from leaveimpact.core.enums import require_member
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    canonical_bytes,
    expect_fields,
    field_of,
    integer_field,
    object_field,
    optional_string_field,
    string_field,
)
from leaveimpact.core.run_account import AccountFigures
from leaveimpact.core.run_ending import Abandonment, ApprovalState, FailureSite, SegmentStatus
from leaveimpact.core.run_parts_json import (
    decode_abandonment,
    decode_failure_site,
    encode_abandonment,
    encode_failure_site,
)
from leaveimpact.core.run_record import FailureCategory, TerminalStatus
from leaveimpact.core.run_timing import require_commit
from leaveimpact.core.run_trace import require_digest, require_integer, require_opaque_id
from leaveimpact.core.timeshape import decode_instant, encode_instant

INVENTORY_FORMAT_VERSION = 1
"""The inventory's own format version, apart from the schema's, the log's and the export's."""


class PublicationStatus(StrEnum):
    """Where an attempt's publication stands; a member is the stored and the wire form.
    Published is never left; failed may return to pending on a retry."""

    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


# --- The pieces ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InventoryScope:
    """What the inventory was written for: the world, the registration and the ledger. The
    attempts listed are every attempt the store holds; the scope says which of them an
    evaluation under this registration reads as its own."""

    world_version: WorldVersion
    registration_commit: str
    ledger_id: str

    def __post_init__(self) -> None:
        require_opaque_id(self.world_version, "the world version")
        require_commit(self.registration_commit, "the registration commit")
        require_opaque_id(self.ledger_id, "a ledger id")


@dataclass(frozen=True, slots=True)
class InventorySnapshot:
    """The one database snapshot the inventory was read from: the schema's version, the
    commit of the code that built it, and the store's clock at the read."""

    schema_version: int
    builder_commit: str
    taken_at: datetime

    def __post_init__(self) -> None:
        require_integer(self.schema_version, "a schema version", minimum=1)
        require_commit(self.builder_commit, "the builder's commit")
        if self.taken_at.tzinfo is None:
            raise ValueError("the snapshot's time is an aware instant")


@dataclass(frozen=True, slots=True)
class InventoryLedgerEntry:
    """One ledger entry as the store holds it: the agent's entry, field for field, with the
    time it was recorded. The kind is carried by its stored name."""

    revision: int
    kind: str
    run_id: str | None
    attempt: int | None
    amount_pico_usd: int
    total_after_pico_usd: int
    authority: str | None
    registration_commit: str | None
    reason: str | None
    recorded_at: datetime

    def __post_init__(self) -> None:
        require_integer(self.revision, "a ledger revision", minimum=1)
        require_opaque_id(self.kind, "an entry kind")
        require_integer(self.amount_pico_usd, "an entry's amount in pico-dollars")
        require_integer(self.total_after_pico_usd, "the committed total in pico-dollars")
        if (self.run_id is None) != (self.attempt is None):
            raise ValueError("an entry names a run and its attempt together or neither")
        if self.run_id is not None:
            require_opaque_id(self.run_id, "a run id")
            require_integer(self.attempt, "an attempt number", minimum=1)


@dataclass(frozen=True, slots=True)
class InventoryLedger:
    """The ledger as it stood: its head and every entry in revision order."""

    ledger_id: str
    total_pico_usd: int
    revision: int
    threshold_pico_usd: int | None
    entries: tuple[InventoryLedgerEntry, ...]

    def __post_init__(self) -> None:
        require_opaque_id(self.ledger_id, "a ledger id")
        require_integer(self.total_pico_usd, "the committed total in pico-dollars")
        require_integer(self.revision, "a ledger revision")
        if self.threshold_pico_usd is not None:
            require_integer(self.threshold_pico_usd, "the threshold in pico-dollars")
        revisions = [entry.revision for entry in self.entries]
        if revisions != list(range(1, len(revisions) + 1)):
            raise ValueError(f"the entries are revisions 1 to {len(revisions)}, got {revisions}")
        if len(revisions) != self.revision:
            raise ValueError(
                f"the head is at revision {self.revision} and {len(revisions)} entries are listed"
            )


@dataclass(frozen=True, slots=True)
class AttemptEnding:
    """How a closed attempt ended, without the failure's reason text: the status, the
    failure's category and site when it failed, and the abandon command when one closed it."""

    status: TerminalStatus
    failure_category: FailureCategory | None
    failure_site: FailureSite | None
    abandonment: Abandonment | None

    def __post_init__(self) -> None:
        require_member(self.status, TerminalStatus, "a terminal status")
        if (self.failure_category is None) != (self.failure_site is None):
            raise ValueError("a failure's category and site are given together or neither")
        if (self.failure_category is not None) != (self.status is TerminalStatus.FAILED):
            raise ValueError("a failure is given exactly when the status is failed")


@dataclass(frozen=True, slots=True)
class AttemptStatus:
    """The three fields of ruling 10, part 1: the attempt (its ending when closed), the
    segment, the approval. No field says a worker is alive."""

    ending: AttemptEnding | None
    segment: SegmentStatus
    approval: ApprovalState

    def __post_init__(self) -> None:
        require_member(self.segment, SegmentStatus, "a segment status")
        require_member(self.approval, ApprovalState, "an approval state")

    @property
    def open(self) -> bool:
        return self.ending is None


@dataclass(frozen=True, slots=True)
class PublicationObserved:
    """An attempt's publication record as the snapshot showed it: the agent's record, field
    for field."""

    status: PublicationStatus
    reader_commit: str
    export_format: int
    log_digest: str
    object_identity: str | None
    object_digest: str | None
    incident: str | None
    repaired_from_commit: str | None
    recorded_at: datetime

    def __post_init__(self) -> None:
        require_member(self.status, PublicationStatus, "a publication status")
        require_commit(self.reader_commit, "the reader's commit")
        require_integer(self.export_format, "an export format", minimum=1)
        require_digest(self.log_digest, "the closed log's digest")
        if (self.object_identity is None) != (self.object_digest is None):
            raise ValueError("an object's identity and digest are recorded together or neither")
        if self.object_identity is None:
            if self.status is not PublicationStatus.FAILED:
                raise ValueError("only a failed publication records no object")
        else:
            require_digest(self.object_digest or "", "the object's digest")
            if not self.object_identity:
                raise ValueError("an object identity is a non-empty key")
        if self.repaired_from_commit is not None:
            require_commit(self.repaired_from_commit, "the repaired commit")


@dataclass(frozen=True, slots=True)
class SupersededObject:
    """An object an earlier publication record of the attempt named, replaced by a record
    under another reader: the reader whose record it was, the object's identity and digest,
    and when that record was written. Listed so an object the store holds under the earlier
    reader's key is accounted for and read as superseded, never as an orphan."""

    reader_commit: str
    object_identity: str
    object_digest: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        require_commit(self.reader_commit, "the reader's commit")
        require_digest(self.object_digest, "the object's digest")
        if not self.object_identity:
            raise ValueError("an object identity is a non-empty key")


@dataclass(frozen=True, slots=True)
class InventoryAttempt:
    """One attempt the store holds: its identity and what it was admitted under, whether its
    row is closed, its status and figures, where its log was read (the last position and
    the digest of the log up to it), its publication record if one was begun, and the
    objects earlier records under other readers named.

    The status and the figures are the fold's and are absent together, exactly for an
    attempt admitted under rules that are not the builder's (another registration's
    attribution table or re-dispatch policy), whose log the builder may not fold; its row
    still says open or closed, which is what an evaluation outside its scope needs of it.
    """

    run_id: str
    attempt: int
    world_version: WorldVersion
    registration_commit: str
    ledger_id: str | None
    closed: bool
    status: AttemptStatus | None
    position: int
    prefix_digest: str
    figures: AccountFigures | None
    publication: PublicationObserved | None
    superseded: tuple[SupersededObject, ...]

    def __post_init__(self) -> None:
        require_opaque_id(self.run_id, "a run id")
        require_integer(self.attempt, "an attempt number", minimum=1)
        require_opaque_id(self.world_version, "the world version")
        require_commit(self.registration_commit, "the registration commit")
        if self.ledger_id is not None:
            require_opaque_id(self.ledger_id, "a ledger id")
        require_integer(self.position, "a log position", minimum=1)
        require_digest(self.prefix_digest, "the log prefix's digest")
        if (self.status is None) != (self.figures is None):
            raise ValueError("the status and the figures are the fold's and absent together")
        if self.status is not None and self.status.open == self.closed:
            raise ValueError("the row's closed value is the fold's")
        if self.publication is not None and not self.closed:
            raise ValueError("an open attempt has no publication record")


@dataclass(frozen=True, slots=True)
class RefusedAdmission:
    """An admission request the store refused and recorded: which, for what attempt, why."""

    request_id: str
    run_id: str
    attempt: int
    reason: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        require_opaque_id(self.request_id, "a request identity")
        require_opaque_id(self.run_id, "a run id")
        require_integer(self.attempt, "an attempt number", minimum=1)
        if not self.reason:
            raise ValueError("a refusal carries its reason")


@dataclass(frozen=True, slots=True)
class Inventory:
    """The inventory whole; the attempts in run and attempt order, the refusals in the order
    they were recorded."""

    format_version: int
    scope: InventoryScope
    snapshot: InventorySnapshot
    ledger: InventoryLedger | None
    attempts: tuple[InventoryAttempt, ...]
    refused: tuple[RefusedAdmission, ...]

    def __post_init__(self) -> None:
        if self.format_version != INVENTORY_FORMAT_VERSION:
            raise ValueError(
                f"the inventory format is {INVENTORY_FORMAT_VERSION}, got {self.format_version}"
            )
        if self.ledger is not None and self.ledger.ledger_id != self.scope.ledger_id:
            raise ValueError("the ledger listed is the scope's")
        keys = [(each.run_id, each.attempt) for each in self.attempts]
        if keys != sorted(keys) or len(set(keys)) != len(keys):
            raise ValueError("the attempts are listed once each in run and attempt order")

    def attempt_of(self, run_id: str, attempt: int) -> InventoryAttempt | None:
        for each in self.attempts:
            if (each.run_id, each.attempt) == (run_id, attempt):
                return each
        return None


# --- The codec ----------------------------------------------------------------------------


def inventory_bytes(inventory: Inventory) -> bytes:
    """The canonical bytes of ``inventory``: what is written, hashed and cited."""
    return canonical_bytes(encode_inventory(inventory))


def inventory_digest(content: bytes) -> str:
    """The identity of an inventory: the SHA-256 of its bytes.

    >>> inventory_digest(b"")[:16]
    'e3b0c44298fc1c14'
    """
    return hashlib.sha256(content).hexdigest()


def encode_inventory(inventory: Inventory) -> JsonObject:
    return {
        "format_version": inventory.format_version,
        "scope": {
            "world_version": inventory.scope.world_version,
            "registration_commit": inventory.scope.registration_commit,
            "ledger_id": inventory.scope.ledger_id,
        },
        "snapshot": {
            "schema_version": inventory.snapshot.schema_version,
            "builder_commit": inventory.snapshot.builder_commit,
            "taken_at": encode_instant(inventory.snapshot.taken_at),
        },
        "ledger": None if inventory.ledger is None else _encode_ledger(inventory.ledger),
        "attempts": [_encode_attempt(each) for each in inventory.attempts],
        "refused": [_encode_refusal(each) for each in inventory.refused],
    }


def decode_inventory_bytes(content: bytes | str) -> Inventory:
    """The inventory ``content`` encodes; ``ValueError`` names the first field that refuses."""
    try:
        tree = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"an inventory is JSON: {exc.msg} at {exc.pos}") from None
    return decode_inventory(tree)


def decode_inventory(value: object) -> Inventory:
    data = as_object(value, "an inventory")
    expect_fields(
        data,
        ("format_version", "scope", "snapshot", "ledger", "attempts", "refused"),
        "an inventory",
    )
    version = integer_field(data, "format_version")
    if version != INVENTORY_FORMAT_VERSION:
        raise ValueError(f"the inventory format is {INVENTORY_FORMAT_VERSION}, got {version}")
    scope = object_field(data, "scope")
    expect_fields(scope, ("world_version", "registration_commit", "ledger_id"), "the scope")
    snapshot = object_field(data, "snapshot")
    expect_fields(snapshot, ("schema_version", "builder_commit", "taken_at"), "the snapshot")
    ledger = field_of(data, "ledger")
    return Inventory(
        version,
        InventoryScope(
            WorldVersion(string_field(scope, "world_version")),
            string_field(scope, "registration_commit"),
            string_field(scope, "ledger_id"),
        ),
        InventorySnapshot(
            integer_field(snapshot, "schema_version"),
            string_field(snapshot, "builder_commit"),
            decode_instant(field_of(snapshot, "taken_at"), "the snapshot's time"),
        ),
        None if ledger is None else _decode_ledger(as_object(ledger, "the ledger")),
        tuple(
            _decode_attempt(as_object(item, "an attempt")) for item in array_field(data, "attempts")
        ),
        tuple(
            _decode_refusal(as_object(item, "a refusal")) for item in array_field(data, "refused")
        ),
    )


def _encode_ledger(ledger: InventoryLedger) -> JsonObject:
    return {
        "ledger_id": ledger.ledger_id,
        "total_pico_usd": ledger.total_pico_usd,
        "revision": ledger.revision,
        "threshold_pico_usd": ledger.threshold_pico_usd,
        "entries": [
            {
                "revision": entry.revision,
                "kind": entry.kind,
                "run_id": entry.run_id,
                "attempt": entry.attempt,
                "amount_pico_usd": entry.amount_pico_usd,
                "total_after_pico_usd": entry.total_after_pico_usd,
                "authority": entry.authority,
                "registration_commit": entry.registration_commit,
                "reason": entry.reason,
                "recorded_at": encode_instant(entry.recorded_at),
            }
            for entry in ledger.entries
        ],
    }


_ENTRY_FIELDS = (
    "revision",
    "kind",
    "run_id",
    "attempt",
    "amount_pico_usd",
    "total_after_pico_usd",
    "authority",
    "registration_commit",
    "reason",
    "recorded_at",
)


def _decode_ledger(data: Mapping[str, object]) -> InventoryLedger:
    expect_fields(
        data,
        ("ledger_id", "total_pico_usd", "revision", "threshold_pico_usd", "entries"),
        "the ledger",
    )
    threshold = field_of(data, "threshold_pico_usd")
    entries: list[InventoryLedgerEntry] = []
    for item in array_field(data, "entries"):
        entry = as_object(item, "a ledger entry")
        expect_fields(entry, _ENTRY_FIELDS, "a ledger entry")
        attempt = field_of(entry, "attempt")
        entries.append(
            InventoryLedgerEntry(
                integer_field(entry, "revision"),
                string_field(entry, "kind"),
                optional_string_field(entry, "run_id"),
                None if attempt is None else integer_field(entry, "attempt"),
                integer_field(entry, "amount_pico_usd"),
                integer_field(entry, "total_after_pico_usd"),
                optional_string_field(entry, "authority"),
                optional_string_field(entry, "registration_commit"),
                optional_string_field(entry, "reason"),
                decode_instant(field_of(entry, "recorded_at"), "an entry's time"),
            )
        )
    return InventoryLedger(
        string_field(data, "ledger_id"),
        integer_field(data, "total_pico_usd"),
        integer_field(data, "revision"),
        None if threshold is None else integer_field(data, "threshold_pico_usd"),
        tuple(entries),
    )


def _encode_attempt(each: InventoryAttempt) -> JsonObject:
    return {
        "run_id": each.run_id,
        "attempt": each.attempt,
        "world_version": each.world_version,
        "registration_commit": each.registration_commit,
        "ledger_id": each.ledger_id,
        "closed": each.closed,
        "status": None if each.status is None else _encode_status(each.status),
        "position": each.position,
        "prefix_digest": each.prefix_digest,
        "figures": None if each.figures is None else _encode_figures(each.figures),
        "publication": None if each.publication is None else _encode_publication(each.publication),
        "superseded": [
            {
                "reader_commit": one.reader_commit,
                "object_identity": one.object_identity,
                "object_digest": one.object_digest,
                "recorded_at": encode_instant(one.recorded_at),
            }
            for one in each.superseded
        ],
    }


def _encode_status(status: AttemptStatus) -> JsonObject:
    return {
        "ending": None if status.ending is None else _encode_ending(status.ending),
        "segment": status.segment.value,
        "approval": status.approval.value,
    }


def _encode_figures(figures: AccountFigures) -> JsonObject:
    return {
        "known_pico_usd": figures.known_pico_usd,
        "retained_pico_usd": figures.retained_pico_usd,
        "total_pico_usd": figures.total_pico_usd,
    }


def _encode_ending(ending: AttemptEnding) -> JsonObject:
    return {
        "status": ending.status.value,
        "failure_category": None
        if ending.failure_category is None
        else ending.failure_category.value,
        "failure_site": None
        if ending.failure_site is None
        else encode_failure_site(ending.failure_site),
        "abandonment": encode_abandonment(ending.abandonment),
    }


def _encode_publication(publication: PublicationObserved) -> JsonObject:
    return {
        "status": publication.status.value,
        "reader_commit": publication.reader_commit,
        "export_format": publication.export_format,
        "log_digest": publication.log_digest,
        "object_identity": publication.object_identity,
        "object_digest": publication.object_digest,
        "incident": publication.incident,
        "repaired_from_commit": publication.repaired_from_commit,
        "recorded_at": encode_instant(publication.recorded_at),
    }


_ATTEMPT_FIELDS = (
    "run_id",
    "attempt",
    "world_version",
    "registration_commit",
    "ledger_id",
    "closed",
    "status",
    "position",
    "prefix_digest",
    "figures",
    "publication",
    "superseded",
)
_PUBLICATION_FIELDS = (
    "status",
    "reader_commit",
    "export_format",
    "log_digest",
    "object_identity",
    "object_digest",
    "incident",
    "repaired_from_commit",
    "recorded_at",
)


def _decode_attempt(data: Mapping[str, object]) -> InventoryAttempt:
    expect_fields(data, _ATTEMPT_FIELDS, "an attempt")
    closed = field_of(data, "closed")
    if not isinstance(closed, bool):
        raise ValueError(f"closed is a boolean, got {type(closed).__name__}")
    status = field_of(data, "status")
    figures = field_of(data, "figures")
    publication = field_of(data, "publication")
    return InventoryAttempt(
        string_field(data, "run_id"),
        integer_field(data, "attempt"),
        WorldVersion(string_field(data, "world_version")),
        string_field(data, "registration_commit"),
        optional_string_field(data, "ledger_id"),
        closed,
        None if status is None else _decode_status(as_object(status, "an attempt's status")),
        integer_field(data, "position"),
        string_field(data, "prefix_digest"),
        None if figures is None else _decode_figures(as_object(figures, "the figures")),
        None
        if publication is None
        else _decode_publication(as_object(publication, "a publication record")),
        tuple(
            _decode_superseded(as_object(item, "a superseded object"))
            for item in array_field(data, "superseded")
        ),
    )


def _decode_superseded(data: Mapping[str, object]) -> SupersededObject:
    expect_fields(
        data,
        ("reader_commit", "object_identity", "object_digest", "recorded_at"),
        "a superseded object",
    )
    return SupersededObject(
        string_field(data, "reader_commit"),
        string_field(data, "object_identity"),
        string_field(data, "object_digest"),
        decode_instant(field_of(data, "recorded_at"), "the record's time"),
    )


def _decode_status(data: Mapping[str, object]) -> AttemptStatus:
    expect_fields(data, ("ending", "segment", "approval"), "an attempt's status")
    ending = field_of(data, "ending")
    return AttemptStatus(
        None if ending is None else _decode_ending(as_object(ending, "an ending")),
        SegmentStatus(string_field(data, "segment")),
        ApprovalState(string_field(data, "approval")),
    )


def _decode_figures(data: Mapping[str, object]) -> AccountFigures:
    expect_fields(data, ("known_pico_usd", "retained_pico_usd", "total_pico_usd"), "the figures")
    return AccountFigures(
        integer_field(data, "known_pico_usd"),
        integer_field(data, "retained_pico_usd"),
        integer_field(data, "total_pico_usd"),
    )


def _decode_ending(data: Mapping[str, object]) -> AttemptEnding:
    expect_fields(data, ("status", "failure_category", "failure_site", "abandonment"), "an ending")
    category = optional_string_field(data, "failure_category")
    site = field_of(data, "failure_site")
    return AttemptEnding(
        TerminalStatus(string_field(data, "status")),
        None if category is None else FailureCategory(category),
        None if site is None else decode_failure_site(as_object(site, "a failure site")),
        decode_abandonment(field_of(data, "abandonment")),
    )


def _decode_publication(data: Mapping[str, object]) -> PublicationObserved:
    expect_fields(data, _PUBLICATION_FIELDS, "a publication record")
    return PublicationObserved(
        PublicationStatus(string_field(data, "status")),
        string_field(data, "reader_commit"),
        integer_field(data, "export_format"),
        string_field(data, "log_digest"),
        optional_string_field(data, "object_identity"),
        optional_string_field(data, "object_digest"),
        optional_string_field(data, "incident"),
        optional_string_field(data, "repaired_from_commit"),
        decode_instant(field_of(data, "recorded_at"), "the record's time"),
    )


def _encode_refusal(each: RefusedAdmission) -> JsonObject:
    return {
        "request_id": each.request_id,
        "run_id": each.run_id,
        "attempt": each.attempt,
        "reason": each.reason,
        "recorded_at": encode_instant(each.recorded_at),
    }


def _decode_refusal(data: Mapping[str, object]) -> RefusedAdmission:
    expect_fields(data, ("request_id", "run_id", "attempt", "reason", "recorded_at"), "a refusal")
    return RefusedAdmission(
        string_field(data, "request_id"),
        string_field(data, "run_id"),
        integer_field(data, "attempt"),
        string_field(data, "reason"),
        decode_instant(field_of(data, "recorded_at"), "the refusal's time"),
    )


__all__ = [
    "INVENTORY_FORMAT_VERSION",
    "AttemptEnding",
    "AttemptStatus",
    "Inventory",
    "InventoryAttempt",
    "InventoryLedger",
    "InventoryLedgerEntry",
    "InventoryScope",
    "InventorySnapshot",
    "PublicationObserved",
    "PublicationStatus",
    "RefusedAdmission",
    "SupersededObject",
    "decode_inventory",
    "decode_inventory_bytes",
    "encode_inventory",
    "inventory_bytes",
    "inventory_digest",
]
