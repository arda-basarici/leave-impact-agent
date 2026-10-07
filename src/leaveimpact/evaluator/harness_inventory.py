"""The harness's inventory as the evaluator reads it: the one object an evaluation names,
verified against its name, and what the listing of stored objects is held to under it.

The harness writes an inventory of every attempt its store holds (the event log step's
ruling on the job seam, part 5), an immutable object named by the digest of its bytes
under the runs prefix the evaluator already lists. An evaluation names the inventory it
read, and that name is an input and never a choice made from the listing: the latest by
instant would name what was read only after the fact, and two objects at one instant would
be told apart by the listing's unspecified order (the second sitting's first fork). What
the inventory then settles, and this module decides from it with nothing else:

- *The standing of a stored key* (ruling 10 part 6), from the key alone before any byte is
  decoded: a listed attempt's published object is current; the object a pending or a
  failed record names is unfinished, an upload with no record of success; an object an
  earlier record under another reader named is superseded, listed and not current; any
  other object under a listed attempt's prefix is an orphan; an object under no listed
  attempt's prefix is unlisted, published after the snapshot or by another harness, and
  invalidates nothing, since the evaluation is of the snapshot (part 9's last sentence).
- *Whether the store is the snapshot's*: every published object listed for this world is
  present with its digest, or the evaluation is refused by the key's name (part 6). The
  inventory lists every attempt the store holds, of every world the deployment ran
  (part 5), and the evaluation lists one world's prefix, so the inventory is narrowed to
  the world's attempts before anything is held to it (the second sitting's review, first
  finding: a mixed-world inventory refused a valid evaluation, and a foreign open attempt
  counted as admitted).
- *Which attempts are the evaluation's*: those of this world whose registration commit
  resolves to the evaluation's own registration bytes, the rule an export is held to
  (``artifact``), the inventory carrying no scenario content that could place one in an arm.
- *The attempts with no export* (part 8): open, or closed without a published record, each
  with its ending and the ledger's three figures, which the attempt history takes beside
  the exported ones so that a run with one has no counted result, and the whole's
  coverage counts apart from the claim measures.

Imports ``core`` for the inventory's types and the layout for its keys; never ``agent``,
whose store it must not read (the ruling on placement, part 1).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from leaveimpact.adapters.object_store.layout import inventory_key, inventory_prefix, run_prefix
from leaveimpact.core import (
    AccountFigures,
    AttemptEnding,
    Inventory,
    InventoryAttempt,
    PublicationStatus,
    decode_inventory_bytes,
)
from leaveimpact.core.ids import WorldVersion

# --- The named inventory -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HarnessInventoryRead:
    """What an evaluation read as the harness's inventory, by identity: its key and digest,
    its format, the snapshot it was taken from, its scope, and how much it lists."""

    key: str
    digest: str
    format_version: int
    schema_version: int
    builder_commit: str
    taken_at: datetime
    world_version: str
    registration_commit: str
    ledger_id: str
    attempts: int
    refused: int


def read_inventory(
    version: WorldVersion, digest: str, content: bytes
) -> tuple[Inventory, HarnessInventoryRead]:
    """The inventory named ``digest`` for the world ``version``, from the bytes read at its key.

    Raises ``ValueError`` when the bytes do not digest to the name, when they are not an
    inventory, or when the inventory is of another world. The message names the key, the
    digests and the versions and never the content: the decoder's own message quotes the
    value it refused, and the evaluation job's log is public (the second sitting's review,
    second finding), so it is dropped whole.
    """
    key = inventory_key(version, digest)
    read = hashlib.sha256(content).hexdigest()
    if read != digest:
        raise ValueError(f"the object at {key} does not digest to its name: read {read}")
    try:
        inventory = decode_inventory_bytes(content)
    except ValueError:
        inventory = None
    # Raised after the handler has ended, so the decoder's exception is no part of what a
    # traceback prints either.
    if inventory is None:
        raise ValueError(f"the object at {key} does not decode as an inventory")
    if inventory.scope.world_version != version:
        # The stored version is the object's own text, validated as an identifier and no
        # more, so it is not printed: the refusal names the key and the evaluation's world.
        raise ValueError(
            f"the inventory at {key} is of another world than the evaluation's, {version}"
        )
    return inventory, HarnessInventoryRead(
        key=key,
        digest=digest,
        format_version=inventory.format_version,
        schema_version=inventory.snapshot.schema_version,
        builder_commit=inventory.snapshot.builder_commit,
        taken_at=inventory.snapshot.taken_at,
        world_version=inventory.scope.world_version,
        registration_commit=inventory.scope.registration_commit,
        ledger_id=inventory.scope.ledger_id,
        attempts=len(inventory.attempts),
        refused=len(inventory.refused),
    )


def is_inventory_object(version: WorldVersion, key: str) -> bool:
    """Whether ``key`` lies under the inventory prefix, which the publication scope excludes."""
    return key.startswith(inventory_prefix(version))


def attempts_of_world(inventory: Inventory, version: WorldVersion) -> tuple[InventoryAttempt, ...]:
    """The attempts of ``inventory`` admitted for the world ``version``, in the inventory's
    order: what an evaluation of that world is held to, the other worlds' being listed and
    none of its concern."""
    return tuple(attempt for attempt in inventory.attempts if attempt.world_version == version)


# --- The standing of a stored key ----------------------------------------------------------


class ObjectStanding(StrEnum):
    """What the inventory says of one key under the runs prefix, decided from the key alone."""

    CURRENT = "current"
    """The published object of a listed attempt."""
    UNFINISHED = "unfinished"
    """The object a listed attempt's pending or failed record names: uploaded, perhaps, with
    no record of success."""
    SUPERSEDED = "superseded"
    """An object an earlier record of a listed attempt named under another reader."""
    ORPHAN = "orphan"
    """Under a listed attempt's prefix and named by no record of it."""
    UNLISTED = "unlisted"
    """Under no listed attempt's prefix: published after the snapshot, or by another harness."""


def standing_of(inventory: Inventory, version: WorldVersion, key: str) -> ObjectStanding:
    """The standing of ``key`` under ``inventory``, a key under the runs prefix and outside
    the inventory prefix."""
    for attempt in inventory.attempts:
        publication = attempt.publication
        if publication is not None and publication.object_identity == key:
            if publication.status is PublicationStatus.PUBLISHED:
                return ObjectStanding.CURRENT
            return ObjectStanding.UNFINISHED
        if any(each.object_identity == key for each in attempt.superseded):
            return ObjectStanding.SUPERSEDED
    for attempt in inventory.attempts:
        if key.startswith(run_prefix(version, attempt.run_id, attempt.attempt)):
            return ObjectStanding.ORPHAN
    return ObjectStanding.UNLISTED


@dataclass(frozen=True, slots=True)
class MissingPublication:
    """A published object the inventory lists that the store does not hold as listed: absent
    from the listing, or present with other bytes."""

    run_id: str
    attempt: int
    key: str
    absent: bool

    @property
    def reason(self) -> str:
        return "is not in the listing" if self.absent else "holds other bytes than recorded"


def missing_publications(
    inventory: Inventory, version: WorldVersion, digests: Mapping[str, str]
) -> tuple[MissingPublication, ...]:
    """Every published object ``inventory`` lists for the world ``version`` that ``digests``,
    the listed keys with the digest of the bytes read at each, does not hold as recorded,
    in the inventory's order. Empty exactly when the store is the snapshot's for that
    world."""
    missing: list[MissingPublication] = []
    for attempt in attempts_of_world(inventory, version):
        publication = attempt.publication
        if publication is None or publication.status is not PublicationStatus.PUBLISHED:
            continue
        key = publication.object_identity
        assert key is not None  # a published record names its object (``core.inventory``)
        read = digests.get(key)
        if read is None:
            missing.append(MissingPublication(attempt.run_id, attempt.attempt, key, True))
        elif read != publication.object_digest:
            missing.append(MissingPublication(attempt.run_id, attempt.attempt, key, False))
    return tuple(missing)


# --- The evaluation's attempts -------------------------------------------------------------


def in_scope(
    attempt: InventoryAttempt,
    registrations_at: Mapping[str, bytes | None],
    registration_content: bytes,
) -> bool:
    """Whether ``attempt`` was admitted under this evaluation's registration: the bytes at
    its registration commit are the evaluation's own, the rule an export is held to."""
    return registrations_at.get(attempt.registration_commit) == registration_content


def scoped_attempts(
    inventory: Inventory,
    version: WorldVersion,
    registrations_at: Mapping[str, bytes | None],
    registration_content: bytes,
) -> tuple[InventoryAttempt, ...]:
    """The attempts of ``inventory`` in this evaluation's scope, of the world ``version`` and
    under its registration, in the inventory's order."""
    return tuple(
        attempt
        for attempt in attempts_of_world(inventory, version)
        if in_scope(attempt, registrations_at, registration_content)
    )


def open_attempts(attempts: Iterable[InventoryAttempt]) -> tuple[InventoryAttempt, ...]:
    """Those of ``attempts`` whose row is open: what a reported evaluation refuses on."""
    return tuple(attempt for attempt in attempts if not attempt.closed)


class UnexportedStatus(StrEnum):
    """Why an attempt has no export; a member is the wire format."""

    OPEN = "open"
    CLOSED_WITHOUT_EXPORT = "closed_without_export"


@dataclass(frozen=True, slots=True)
class UnexportedAttempt:
    """An attempt the inventory lists with no published export: open, or closed with no
    record or a record not published. ``ending`` is the fold's, absent for an open attempt
    and for one admitted under rules the builder could not fold; ``publication`` is the
    record's status, absent when none was begun, and failed exactly for a publication
    incident; ``figures`` are the ledger's three numbers, its cost with its uncertainty."""

    run_id: str
    attempt: int
    status: UnexportedStatus
    ending: AttemptEnding | None
    publication: PublicationStatus | None
    figures: AccountFigures | None

    @property
    def incident(self) -> bool:
        return self.publication is PublicationStatus.FAILED


def unexported_attempts(attempts: Iterable[InventoryAttempt]) -> tuple[UnexportedAttempt, ...]:
    """Those of ``attempts`` with no published export, each as the inventory shows it."""
    held: list[UnexportedAttempt] = []
    for attempt in attempts:
        publication = attempt.publication
        if publication is not None and publication.status is PublicationStatus.PUBLISHED:
            continue
        status = UnexportedStatus.CLOSED_WITHOUT_EXPORT if attempt.closed else UnexportedStatus.OPEN
        held.append(
            UnexportedAttempt(
                attempt.run_id,
                attempt.attempt,
                status,
                None if attempt.status is None else attempt.status.ending,
                None if publication is None else publication.status,
                attempt.figures,
            )
        )
    return tuple(held)


def unexported_by_run(
    unexported: Iterable[UnexportedAttempt],
) -> dict[str, tuple[UnexportedAttempt, ...]]:
    """``unexported`` grouped by run, each run's in attempt order."""
    by_run: dict[str, list[UnexportedAttempt]] = {}
    for attempt in unexported:
        by_run.setdefault(attempt.run_id, []).append(attempt)
    return {
        run_id: tuple(sorted(held, key=lambda each: each.attempt))
        for run_id, held in by_run.items()
    }


# --- The whole's coverage ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HarnessCoverage:
    """How much of what was intended the evaluation could grade, and what is reported apart
    from the claim measures (ruling 10 part 8), over the attempts in the evaluation's scope.

    ``intended`` is the plan's over every registered arm; ``admitted`` the runs the
    inventory lists, which the registration's roster and never the inventory is the source
    of what was intended; ``never_admitted`` the shortfall and ``admitted_beyond_intended``
    the surplus, since one does not hide the other. The attempt counts split every scoped
    attempt into exported, open and closed without export, the publication incidents among
    the last. ``failed_by_defect`` and ``failed_by_infrastructure`` are the counted runs the
    tables excluded for each, given by the caller from the accounting, so that the four
    things reported apart stand in one place. ``unexported`` lists each attempt with no
    export; none of them is placed in a cell, the inventory holding no scenario.
    """

    intended: int
    admitted: int
    never_admitted: int
    admitted_beyond_intended: int
    attempts: int
    exported: int
    open: int
    closed_without_export: int
    publication_incidents: int
    failed_by_defect: int
    failed_by_infrastructure: int
    unexported: tuple[UnexportedAttempt, ...]


def coverage_of(
    scoped: Iterable[InventoryAttempt],
    *,
    intended: int,
    failed_by_defect: int,
    failed_by_infrastructure: int,
) -> HarnessCoverage:
    """The coverage over ``scoped``, the attempts in the evaluation's scope, against the
    ``intended`` runs, with the two exclusion counts the accounting gives."""
    attempts = tuple(scoped)
    unexported = unexported_attempts(attempts)
    admitted = len({attempt.run_id for attempt in attempts})
    open_count = sum(each.status is UnexportedStatus.OPEN for each in unexported)
    return HarnessCoverage(
        intended=intended,
        admitted=admitted,
        never_admitted=max(intended - admitted, 0),
        admitted_beyond_intended=max(admitted - intended, 0),
        attempts=len(attempts),
        exported=len(attempts) - len(unexported),
        open=open_count,
        closed_without_export=len(unexported) - open_count,
        publication_incidents=sum(each.incident for each in unexported),
        failed_by_defect=failed_by_defect,
        failed_by_infrastructure=failed_by_infrastructure,
        unexported=unexported,
    )


__all__ = [
    "HarnessCoverage",
    "HarnessInventoryRead",
    "MissingPublication",
    "ObjectStanding",
    "UnexportedAttempt",
    "UnexportedStatus",
    "attempts_of_world",
    "coverage_of",
    "in_scope",
    "is_inventory_object",
    "missing_publications",
    "open_attempts",
    "read_inventory",
    "scoped_attempts",
    "standing_of",
    "unexported_attempts",
    "unexported_by_run",
]
