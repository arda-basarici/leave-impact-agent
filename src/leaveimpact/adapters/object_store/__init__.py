"""The object store under the sealed world: bytes at keys, read by every shell, written by one.

The benchmark's artifacts leave the generator as objects in two buckets — the truth
bucket the application can never read, the world bucket it reads in part — and the
validator, the application's ingestion and the generator all address them by key. What
each is allowed to do differs, and the difference is the boundary the whole design rests
on: the generator writes, everyone else reads. So the store is two protocols in two
modules rather than one. ``read`` declares ``ObjectReader`` (get, list) and is imported
by whoever consumes a world; ``write`` declares ``ObjectWriter`` extending it with the
two write operations, and the import law admits that module to ``adapters`` and
``generator`` only, the way it admits ``core.ports.write`` — and admits the concrete
writers' modules the same way, since a protocol gate alone would leave a concrete class
with write methods nameable from the validator (the part-1 review's finding). A
validator that cannot name a writer cannot call one, before IAM is asked; the type
boundary, the composition wiring and the role policy are three layers, not one. This
package re-exports the read side alone, so a writer is reachable by its gated module
path and nothing else.

The two write operations are not a generic put. ``put_if_absent`` is the immutable final
artifact's operation, S3's ``If-None-Match: *`` made explicit, with three outcomes
(created, already present with equal bytes, refused) and never a fourth; ``overwrite``
is the mutable ``preparing/`` checkpoint's and says so by name. Keys carry the bucket's
prefix layout; the bucket policy, not the type, is what refuses a plain put under a
final prefix, and the in-memory test double emulates that policy so the sealing sequence
can be tested against it.

Each backend is two classes in two modules, the module boundary being the capability
boundary: ``s3`` and ``local`` hold the readers, objects with no write method on them at
runtime and not only in their type, so what the wiring hands a validator cannot write
even through a cast; ``s3_write`` and ``local_write`` hold the writers as subclasses, in
the gated modules. The in-memory double under ``tests`` emulates the bucket policy. The
byte primitive for local files stays in ``adapters.filestore``; ``local_write`` rides it.
"""

from leaveimpact.adapters.object_store.read import (
    AccessRefused,
    ObjectReader,
    ObjectStoreMisconfigured,
    ObjectStoreUnreachable,
    StoredObject,
)

__all__ = [
    "AccessRefused",
    "ObjectReader",
    "ObjectStoreMisconfigured",
    "ObjectStoreUnreachable",
    "StoredObject",
]
