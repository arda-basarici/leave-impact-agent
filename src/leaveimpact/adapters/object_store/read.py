"""The read side of the object store: what every consumer of a sealed world may do.

A reader gets one object by key or lists the keys under a prefix, and nothing else. The
object comes back with the identifier of the version that was read, because the
generator records the version id of every artifact it wrote and a reader that checks a
manifest against the bucket needs to name what it read; a listing returns keys and never
contents, so an enumeration of a world's documents is cheap and a consumer fetches the
objects it decides to.

Absence is a value, not a fault, as everywhere in the ports: a key that is not there is
``None`` and an empty prefix is an empty tuple. The two faults here are the store's, not
the vendor's — the vendor's own exception never leaves the concrete store — and they are
kept apart because a caller treats them differently: ``AccessRefused`` means the
principal is not allowed the operation, which for the validator on the truth bucket is
the boundary working as designed and for the generator on its own bucket is a
misconfiguration to fail loudly on; ``ObjectStoreUnreachable`` means the store did not
answer, a run condition and never a fact about the world.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredObject:
    """One object as read: its bytes and the identifier of the version those bytes are.

    The version id is the store's opaque identifier, distinct for distinct writes of a
    key; a versioned bucket mints it, the local twin derives it from the content.
    """

    key: str
    content: bytes
    version_id: str


class AccessRefused(Exception):
    """The store answered that the principal may not perform ``operation`` on ``key``."""

    def __init__(self, operation: str, key: str, reason: str) -> None:
        super().__init__(f"{operation} refused on {key!r}: {reason}")
        self.operation = operation
        self.key = key


class ObjectStoreUnreachable(Exception):
    """The store did not answer ``operation``; the vendor fault is the cause."""

    def __init__(self, operation: str, key: str) -> None:
        super().__init__(f"object store unreachable during {operation} on {key!r}")
        self.operation = operation
        self.key = key


class ObjectReader(Protocol):
    """Get by key, list by prefix; the capability every consumer of a world holds."""

    def get(self, key: str) -> StoredObject | None:
        """The object at ``key`` with the version read, or ``None`` when no object is there."""
        ...

    def list_keys(self, prefix: str) -> tuple[str, ...]:
        """Every key beginning with ``prefix``, sorted, contents not fetched; empty when none."""
        ...
