"""The writer over a directory: the local reader plus the two writes, gated by the import law.

An overwrite rides ``adapters.filestore`` for the whole-or-nothing replacement, so a
checkpoint under ``preparing/`` here has the same visibility guarantee the step-10 file
store gave it. A conditional put is exclusive by the filesystem and not by a read that
preceded it: the content is staged under a name of this process's own and hard-linked
into place, which the filesystem refuses when the key already holds a file, so two
concurrent puts of one key give one creation and one comparison, never a second write
(the event log step's review named the read-then-write race). There is no bucket policy
on a directory, so ``overwrite`` under a final prefix is not refused here; a test that
needs the policy uses the in-memory store under ``tests``, which emulates it.
"""

from __future__ import annotations

import os
from uuid import uuid4

from leaveimpact.adapters.filestore import replace_atomically
from leaveimpact.adapters.object_store.local import LocalObjectReader, content_version, key_path
from leaveimpact.adapters.object_store.write import ObjectConflict, PutOutcome, PutReceipt


class LocalObjectWriter(LocalObjectReader):
    """``ObjectWriter`` over the reader's root, created on first write."""

    def put_if_absent(self, key: str, content: bytes) -> PutReceipt:
        path = key_path(self._root, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        staged = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
        try:
            with staged.open("wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(staged, path)
            except FileExistsError:
                existing = self.get(key)
                assert existing is not None, f"{key} exists and could not be read"
                if existing.content != content:
                    raise ObjectConflict(
                        key, existing.version_id, content_version(content)
                    ) from None
                return PutReceipt(key, existing.version_id, PutOutcome.PRESENT_EQUAL)
            return PutReceipt(key, content_version(content), PutOutcome.CREATED)
        finally:
            staged.unlink(missing_ok=True)

    def overwrite(self, key: str, content: bytes) -> PutReceipt:
        return self._write(key, content)

    def _write(self, key: str, content: bytes) -> PutReceipt:
        path = key_path(self._root, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        replace_atomically(path, content)
        return PutReceipt(key, content_version(content), PutOutcome.CREATED)
