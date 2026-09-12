"""The in-memory object store for tests above the store's seam, with the bucket policy emulated.

Test infrastructure, not an adapter, kept under ``tests`` like the in-memory ports: the
sealing sequence and the validator's composition are handed one of these where
production hands them an S3 store. What it adds over the local twin is the one thing a
directory cannot emulate and the design relies on — the bucket policy. A plain put
under any prefix other than the declared mutable ones is ``AccessRefused``, as the real
bucket refuses it with 403, so a sealing step that reached for ``overwrite`` on a final
artifact fails in a unit test and not at the first live run. A conditional put is
allowed anywhere, as it is in the bucket.

Version ids are minted per write from a counter, so a rewrite of equal bytes under
``preparing/`` is a new version as in S3, and the receipts a test collects can be
told apart. ``reachable`` turned off makes every operation ``ObjectStoreUnreachable``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from leaveimpact.adapters.object_store.read import (
    AccessRefused,
    ObjectStoreUnreachable,
    StoredObject,
)
from leaveimpact.adapters.object_store.write import ObjectConflict, PutOutcome, PutReceipt


@dataclass
class InMemoryObjectStore:
    """``ObjectWriter`` in a dict; plain puts allowed under ``mutable_prefixes`` only."""

    mutable_prefixes: tuple[str, ...] = ("preparing/",)
    reachable: bool = True
    objects: dict[str, StoredObject] = field(default_factory=dict[str, StoredObject])
    writes: list[PutReceipt] = field(default_factory=list[PutReceipt])
    _minted: int = 0

    def get(self, key: str) -> StoredObject | None:
        self._check("get", key)
        return self.objects.get(key)

    def list_keys(self, prefix: str) -> tuple[str, ...]:
        self._check("list", prefix)
        return tuple(sorted(key for key in self.objects if key.startswith(prefix)))

    def put_if_absent(self, key: str, content: bytes) -> PutReceipt:
        self._check("put_if_absent", key)
        existing = self.objects.get(key)
        if existing is not None:
            if existing.content != content:
                raise ObjectConflict(key, _sha256(existing.content), _sha256(content))
            return PutReceipt(key, existing.version_id, PutOutcome.PRESENT_EQUAL)
        return self._store(key, content)

    def overwrite(self, key: str, content: bytes) -> PutReceipt:
        self._check("overwrite", key)
        if not key.startswith(self.mutable_prefixes):
            raise AccessRefused(
                "overwrite", key, "explicit deny: a plain put outside the mutable prefixes"
            )
        return self._store(key, content)

    def _store(self, key: str, content: bytes) -> PutReceipt:
        self._minted += 1
        version = f"v{self._minted:04d}"
        self.objects[key] = StoredObject(key, content, version)
        receipt = PutReceipt(key, version, PutOutcome.CREATED)
        self.writes.append(receipt)
        return receipt

    def _check(self, operation: str, key: str) -> None:
        if not self.reachable:
            raise ObjectStoreUnreachable(operation, key)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
