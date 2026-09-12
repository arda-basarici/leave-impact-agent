"""The object store under the sealed world: bytes at keys, read by every shell, written by one.

The benchmark's artifacts leave the generator as objects in two buckets — the truth
bucket the application can never read, the world bucket it reads in part — and the
validator, the application's ingestion and the generator all address them by key. What
each is allowed to do differs, and the difference is the boundary the whole design rests
on: the generator writes, everyone else reads. So the store is two protocols in two
modules rather than one. ``read`` declares ``ObjectReader`` (get, list) and is imported
by whoever consumes a world; ``write`` declares ``ObjectWriter`` extending it with the
two write operations, and the import law admits that module to ``adapters`` and
``generator`` only, the way it admits ``core.ports.write``. A validator that cannot name
the writer cannot call it, before IAM is asked; the type boundary, the composition
wiring and the role policy are three layers, not one. This package re-exports the read
side alone, so the writer is reachable by its module path and nothing else.

The two write operations are not a generic put. ``put_if_absent`` is the immutable final
artifact's operation, S3's ``If-None-Match: *`` made explicit, with three outcomes
(created, already present with equal bytes, refused) and never a fourth; ``overwrite``
is the mutable ``preparing/`` checkpoint's and says so by name. Keys carry the bucket's
prefix layout; the bucket policy, not the type, is what refuses a plain put under a
final prefix, and the in-memory test double emulates that policy so the sealing sequence
can be tested against it.

One concrete store per backend implements the writer, and a consumer is typed against
the narrower capability it is allowed: ``s3`` for the buckets, ``local`` as the
development twin over a directory, the in-memory one under ``tests``. The byte
primitive for local files stays in ``adapters.filestore``; ``local`` rides it.
"""

from leaveimpact.adapters.object_store.read import (
    AccessRefused,
    ObjectReader,
    ObjectStoreUnreachable,
    StoredObject,
)

__all__ = ["AccessRefused", "ObjectReader", "ObjectStoreUnreachable", "StoredObject"]
