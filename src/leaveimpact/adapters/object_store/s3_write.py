"""The writer over one S3 bucket: the reader plus the two writes, gated by the import law.

A subclass of the reader so the generator holds one object per bucket with both
capabilities, in a module the law admits to ``adapters`` and ``generator`` alone; the
validator and the application can name the reader's module and never this one, so no
object with a write method on it is reachable from their source. The credentials are
the reader's, ambient.

Observed shapes (``probes/FINDINGS.md``, the objectstore entry, 2026-09-13): a
conditional put on an absent key returns 200 with the version id; the same put on a
present key raises ``ClientError`` with code ``PreconditionFailed`` and HTTP 412 whether
the bytes match or not, so the present-and-equal outcome is this writer's read-back and
comparison, never the SDK's; a plain put under a final prefix raises the modeled
``AccessDenied`` with the bucket policy's explicit deny in the message, which arrives as
``AccessRefused`` through the reader's translation.
"""

from __future__ import annotations

import hashlib

from botocore.exceptions import ClientError

from leaveimpact.adapters.object_store.read import ObjectStoreUnreachable
from leaveimpact.adapters.object_store.s3 import S3ObjectReader, code, translated, version_id
from leaveimpact.adapters.object_store.write import ObjectConflict, PutOutcome, PutReceipt


class S3ObjectWriter(S3ObjectReader):
    """``ObjectWriter`` over the reader's bucket."""

    def put_if_absent(self, key: str, content: bytes) -> PutReceipt:
        def seal() -> PutReceipt:
            try:
                response = self._client.put_object(
                    Bucket=self._bucket, Key=key, Body=content, IfNoneMatch="*"
                )
            except ClientError as error:
                if code(error) == "PreconditionFailed":
                    return self._present_and_equal(key, content)
                raise
            return PutReceipt(key, version_id(response, "put_if_absent", key), PutOutcome.CREATED)

        return translated("put_if_absent", key, seal)

    def overwrite(self, key: str, content: bytes) -> PutReceipt:
        def replace() -> PutReceipt:
            response = self._client.put_object(Bucket=self._bucket, Key=key, Body=content)
            return PutReceipt(key, version_id(response, "overwrite", key), PutOutcome.CREATED)

        return translated("overwrite", key, replace)

    def _present_and_equal(self, key: str, content: bytes) -> PutReceipt:
        # 412 says only "present"; the read-back decides between equal and conflicting. A
        # key that vanished between the two calls is a store no writer of this project
        # holds delete rights on, so it is reported as the fault it is.
        existing = self.get(key)
        if existing is None:
            raise ObjectStoreUnreachable("put_if_absent", key)
        if existing.content != content:
            raise ObjectConflict(key, _sha256(existing.content), _sha256(content))
        return PutReceipt(key, existing.version_id, PutOutcome.PRESENT_EQUAL)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
