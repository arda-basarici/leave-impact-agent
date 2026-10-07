"""Hand-built harness inventories for the evaluator's tests: a published attempt over an
export's bytes, an open one, a closed one with no export, and an inventory listing each
export a test stored. Built from ``core.inventory`` alone, as the evaluator reads them, with
nothing of the agent's store."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime

from leaveimpact.adapters.object_store.layout import run_export_key
from leaveimpact.core import (
    AccountFigures,
    AttemptEnding,
    AttemptStatus,
    Inventory,
    InventoryAttempt,
    InventoryScope,
    InventorySnapshot,
    PublicationObserved,
    PublicationStatus,
    SupersededObject,
    TerminalStatus,
    decode_export_bytes,
    inventory_bytes,
    inventory_digest,
)
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.run_ending import ApprovalState, SegmentStatus
from leaveimpact.evaluator.harness_inventory import HarnessInventoryRead, read_inventory

COMMIT = "b" * 40
"""The registration commit the evaluator's fixtures cite (``export_fixture.COMMIT``)."""
READER = "d" * 40
BUILDER = "e" * 40
LEDGER = "ledger-1"
INSTANT = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
PREFIX_DIGEST = "f" * 64
LOG_DIGEST = "0" * 64
FIGURES = AccountFigures(297_000_000, 0, 297_000_000)
COMPLETED = AttemptEnding(TerminalStatus.COMPLETED, None, None, None)
STOPPED = AttemptStatus(COMPLETED, SegmentStatus.STOPPED, ApprovalState.NOT_REQUESTED)
OPEN = AttemptStatus(None, SegmentStatus.OPEN, ApprovalState.NOT_REQUESTED)


def digest_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def listed(
    version: WorldVersion,
    *attempts: InventoryAttempt,
    registration_commit: str = COMMIT,
    taken_at: datetime = INSTANT,
) -> Inventory:
    """An inventory of ``attempts`` for ``version``, sorted as the type requires."""
    return Inventory(
        format_version=1,
        scope=InventoryScope(version, registration_commit, LEDGER),
        snapshot=InventorySnapshot(4, BUILDER, taken_at),
        ledger=None,
        attempts=tuple(sorted(attempts, key=lambda each: (each.run_id, each.attempt))),
        refused=(),
    )


def published(
    version: WorldVersion,
    run_id: str,
    attempt: int,
    content: bytes,
    *,
    key: str | None = None,
    reader_commit: str = READER,
    registration_commit: str = COMMIT,
    superseded: tuple[SupersededObject, ...] = (),
    status: PublicationStatus = PublicationStatus.PUBLISHED,
) -> InventoryAttempt:
    """A closed, completed attempt whose publication record names ``content`` at ``key``,
    the layout's export key for ``reader_commit`` unless given; ``status`` other than
    published makes it an unfinished publication naming the same object."""
    identity = run_export_key(version, run_id, attempt, reader_commit) if key is None else key
    return InventoryAttempt(
        run_id=run_id,
        attempt=attempt,
        world_version=version,
        registration_commit=registration_commit,
        ledger_id=LEDGER,
        closed=True,
        status=STOPPED,
        position=15,
        prefix_digest=PREFIX_DIGEST,
        figures=FIGURES,
        publication=PublicationObserved(
            status,
            reader_commit,
            3,
            LOG_DIGEST,
            identity,
            digest_of(content),
            None,
            None,
            INSTANT,
        ),
        superseded=superseded,
    )


def superseded_object(
    version: WorldVersion, run_id: str, attempt: int, content: bytes, *, reader_commit: str
) -> SupersededObject:
    key = run_export_key(version, run_id, attempt, reader_commit)
    return SupersededObject(reader_commit, key, digest_of(content), INSTANT)


def open_attempt(
    version: WorldVersion, run_id: str, attempt: int, *, registration_commit: str = COMMIT
) -> InventoryAttempt:
    """An attempt still open: a segment running, no publication."""
    return InventoryAttempt(
        run_id=run_id,
        attempt=attempt,
        world_version=version,
        registration_commit=registration_commit,
        ledger_id=LEDGER,
        closed=False,
        status=OPEN,
        position=7,
        prefix_digest=PREFIX_DIGEST,
        figures=FIGURES,
        publication=None,
        superseded=(),
    )


def closed_without_export(
    version: WorldVersion,
    run_id: str,
    attempt: int,
    *,
    incident: bool = False,
    folded: bool = True,
    registration_commit: str = COMMIT,
) -> InventoryAttempt:
    """A closed attempt with no published export: no record begun, or with ``incident`` a
    failed record naming no object (a reader that raised); with ``folded`` false the attempt
    was admitted under other rules and carries no status and no figures."""
    publication = None
    if incident:
        publication = PublicationObserved(
            PublicationStatus.FAILED, READER, 3, LOG_DIGEST, None, None, "ValueError", None, INSTANT
        )
    return InventoryAttempt(
        run_id=run_id,
        attempt=attempt,
        world_version=version,
        registration_commit=registration_commit,
        ledger_id=LEDGER,
        closed=True,
        status=STOPPED if folded else None,
        position=15,
        prefix_digest=PREFIX_DIGEST,
        figures=FIGURES if folded else None,
        publication=publication,
        superseded=(),
    )


def inventory_over(
    version: WorldVersion,
    objects: Mapping[str, bytes],
    *,
    registration_commit: str = COMMIT,
    extra: tuple[InventoryAttempt, ...] = (),
    undecodable: Mapping[str, tuple[str, int]] | None = None,
) -> Inventory:
    """An inventory listing every export among ``objects`` (key to bytes) as a published
    attempt of the run and attempt its header names, admitted under the registration commit
    its record cites, with ``extra`` attempts beside them. Bytes that are no export are not
    listed, as a harness never publishes them, unless ``undecodable`` names the run and
    attempt to list the key under."""
    attempts: list[InventoryAttempt] = []
    for key, content in objects.items():
        try:
            export = decode_export_bytes(content)
        except ValueError:
            if undecodable is not None and key in undecodable:
                run_id, attempt = undecodable[key]
                attempts.append(published(version, run_id, attempt, content, key=key))
            continue
        attempts.append(
            published(
                version,
                export.run_id,
                export.attempt,
                content,
                key=key,
                registration_commit=export.record.preregistration_commit,
            )
        )
    return listed(version, *attempts, *extra, registration_commit=registration_commit)


def as_read(inventory: Inventory) -> tuple[Inventory, HarnessInventoryRead]:
    """``inventory`` as the evaluator reads it: encoded, named by its digest, read back."""
    content = inventory_bytes(inventory)
    return read_inventory(inventory.scope.world_version, inventory_digest(content), content)


__all__ = [
    "BUILDER",
    "COMMIT",
    "FIGURES",
    "INSTANT",
    "LEDGER",
    "READER",
    "closed_without_export",
    "digest_of",
    "inventory_over",
    "listed",
    "open_attempt",
    "published",
    "superseded_object",
]
