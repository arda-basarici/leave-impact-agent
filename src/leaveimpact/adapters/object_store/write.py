"""The write side of the object store: the generator's capability, gated by the import law.

Two operations, each named for the namespace it serves. ``put_if_absent`` is how a final
artifact is written once: the request carries the create-only condition, and the store
answers with exactly one of three outcomes. *Created* — the key was absent and now holds
these bytes, the minted version id in the receipt. *Present and equal* — the key already
held these bytes, which is a restart re-sealing what an earlier attempt sealed, accepted
with the existing version id in the receipt and no write made. *Refused* — the key holds
different bytes (``ObjectConflict``, both digests named, since a sealed artifact whose
bytes changed between attempts is the frozen-bytes rule broken and never something to
overwrite), or the store's policy refused the write (``AccessRefused``). The equality
check is the store's own read-back and comparison: S3 answers a conditional put on an
existing key with 412 whether the bytes match or not (the objectstore probe, 2026-09-13),
so the SDK cannot tell the second outcome from the third and this module does.

A fourth outcome exists for one principal: the instance, whose grant under ``runs/`` is a
put and no get. *Present and unverified* — the store refused the create as present and
refused the read-back by access, so the key holds bytes this writer cannot compare. The
receipt carries no version id. A caller that gets it decides by what it knows of the key:
the publish command adopts the object under its own pending record for that key and
digest, where nothing else could have been written (the event log step's commands group,
fork 7), and the evaluator, which can read, verifies the digest it was told.

``overwrite`` is the mutable checkpoint's operation under ``preparing/``, a plain put
that replaces whatever the key holds and receipts the new version. It is refused under a
final prefix by the bucket policy and by the in-memory test double's emulation of it,
never by this type: a caller reaching for ``overwrite`` states its intent by the name,
and the store behind it decides.

Every receipt carries the version id read back from the store, because the world
manifest, written last, records the version of every artifact written before it, and a
write whose version cannot be named is a write the manifest cannot vouch for.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from leaveimpact.adapters.object_store.read import ObjectReader


class PutOutcome(StrEnum):
    """What a ``put_if_absent`` did; ``overwrite`` always creates a version."""

    CREATED = "created"
    PRESENT_EQUAL = "present_equal"
    PRESENT_UNVERIFIED = "present_unverified"


@dataclass(frozen=True, slots=True)
class PutReceipt:
    """The version now at ``key`` and how it got there; the version id is empty exactly
    when the presence is unverified, since no read named it."""

    key: str
    version_id: str
    outcome: PutOutcome

    def __post_init__(self) -> None:
        if (self.version_id == "") != (self.outcome is PutOutcome.PRESENT_UNVERIFIED):
            raise ValueError("a receipt names a version exactly when the store let it read one")


class ObjectConflict(Exception):
    """``key`` already holds bytes other than the ones being sealed; neither is adopted."""

    def __init__(self, key: str, existing_digest: str, offered_digest: str) -> None:
        super().__init__(
            f"{key!r} already holds different bytes: stored sha256 {existing_digest}, "
            f"offered sha256 {offered_digest}"
        )
        self.key = key
        self.existing_digest = existing_digest
        self.offered_digest = offered_digest


class ObjectWriter(ObjectReader, Protocol):
    """The reader plus the two writes; importable by ``adapters`` and ``generator`` only."""

    def put_if_absent(self, key: str, content: bytes) -> PutReceipt:
        """Seal ``content`` at ``key`` once: created, or present and equal, or raises.

        Raises ``ObjectConflict`` when the key holds different bytes and ``AccessRefused``
        when the store's policy refuses the write.
        """
        ...

    def overwrite(self, key: str, content: bytes) -> PutReceipt:
        """Replace whatever ``key`` holds with ``content``; for the mutable prefix only."""
        ...
