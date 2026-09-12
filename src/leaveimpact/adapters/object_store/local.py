"""The object store over a directory: the development twin of the bucket, both capabilities.

A world sealed on a laptop lands under one root, a key becoming the path below it, so the
sealing sequence and the validator's reads run end to end with no AWS in reach and no
credential in the environment. The twin keeps the contract that matters — absent versus
present, created versus present-and-equal versus conflicting, a listing by string prefix
and not by directory — and drops what a directory cannot give: there is no bucket
policy, so ``overwrite`` under a final prefix is not refused here, and there is no
version history, so the version id is derived from the content (its SHA-256), distinct
for distinct bytes and equal for a rewrite of the same bytes. A test that needs the
policy uses the in-memory store under ``tests``, which emulates it.

Each write rides ``adapters.filestore`` for the whole-or-nothing replacement, so a
checkpoint under ``preparing/`` here has the same visibility guarantee the step-10 file
store gave it. Keys use ``/`` as S3 does; the path below the root is built from the
segments, and a listing returns keys in S3's form regardless of the host's separator.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from leaveimpact.adapters.filestore import read_if_present, replace_atomically
from leaveimpact.adapters.object_store.read import StoredObject
from leaveimpact.adapters.object_store.write import ObjectConflict, PutOutcome, PutReceipt


class LocalObjectStore:
    """``ObjectWriter`` over the directory at ``root``, created on first write."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def get(self, key: str) -> StoredObject | None:
        content = read_if_present(self._path(key))
        if content is None:
            return None
        return StoredObject(key, content, _sha256(content))

    def list_keys(self, prefix: str) -> tuple[str, ...]:
        if not self._root.exists():
            return ()
        found = (
            path.relative_to(self._root).as_posix()
            for path in self._root.rglob("*")
            if path.is_file() and not path.name.endswith(".tmp")
        )
        return tuple(sorted(key for key in found if key.startswith(prefix)))

    def put_if_absent(self, key: str, content: bytes) -> PutReceipt:
        existing = self.get(key)
        if existing is not None:
            if existing.content != content:
                raise ObjectConflict(key, existing.version_id, _sha256(content))
            return PutReceipt(key, existing.version_id, PutOutcome.PRESENT_EQUAL)
        return self._write(key, content)

    def overwrite(self, key: str, content: bytes) -> PutReceipt:
        return self._write(key, content)

    def _write(self, key: str, content: bytes) -> PutReceipt:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        replace_atomically(path, content)
        return PutReceipt(key, _sha256(content), PutOutcome.CREATED)

    def _path(self, key: str) -> Path:
        segments = key.split("/")
        if not key or "" in segments or ".." in segments:
            raise ValueError(f"not an object key: {key!r}")
        return self._root.joinpath(*segments)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
