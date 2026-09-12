"""The writer over a directory: the local reader plus the two writes, gated by the import law.

Each write rides ``adapters.filestore`` for the whole-or-nothing replacement, so a
checkpoint under ``preparing/`` here has the same visibility guarantee the step-10 file
store gave it. There is no bucket policy on a directory, so ``overwrite`` under a final
prefix is not refused here; a test that needs the policy uses the in-memory store under
``tests``, which emulates it.
"""

from __future__ import annotations

from leaveimpact.adapters.filestore import replace_atomically
from leaveimpact.adapters.object_store.local import LocalObjectReader, content_version, key_path
from leaveimpact.adapters.object_store.write import ObjectConflict, PutOutcome, PutReceipt


class LocalObjectWriter(LocalObjectReader):
    """``ObjectWriter`` over the reader's root, created on first write."""

    def put_if_absent(self, key: str, content: bytes) -> PutReceipt:
        existing = self.get(key)
        if existing is not None:
            if existing.content != content:
                raise ObjectConflict(key, existing.version_id, content_version(content))
            return PutReceipt(key, existing.version_id, PutOutcome.PRESENT_EQUAL)
        return self._write(key, content)

    def overwrite(self, key: str, content: bytes) -> PutReceipt:
        return self._write(key, content)

    def _write(self, key: str, content: bytes) -> PutReceipt:
        path = key_path(self._root, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        replace_atomically(path, content)
        return PutReceipt(key, content_version(content), PutOutcome.CREATED)
