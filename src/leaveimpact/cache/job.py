"""The cache job over a store reader and a loading callable: discover, admit, read, verify,
load, report.

One version at a time, in the listing's order. The serving rule (``adapters.object_store
.serving``) says whether a version is served and why not; a version it declines is
reported by name and never read further. For a served version the job reads the levels
object, every document the manifest receipts (or, for a development world, every document
under the prefix), and compares what it read with what the manifest vouches for before
anything is loaded: the set of document keys under the prefix equals the receipts' set
exactly, missing and foreign both named; each object read came back under the version id
the manifest recorded for it, the levels object included; each decoded document names its
key's id (the sealed-document reader refuses otherwise); and no object the manifest never
recorded shapes the world, a levels object included, since a final prefix is create-only
and a key the manifest lacks is exactly what a later put could add (the review's first
finding). That is what "verified against the manifest" means here (the M2 step 9 design,
fork 2): the manifest holds version ids, not content digests, and on the local twin a
version id is the content's digest, so the same comparison is a byte check there. A world
sealed before the levels object existed, whose manifest records no such key and whose
prefix holds none, reads as the base level over an empty pool.

Every mismatch, and a world that cannot be one world (a pool naming a document the prefix
does not hold), is ``CacheJobRefused`` naming the version and what differed, raised before
the load, and the job stops there: a world the cache cannot state the provenance of is
not served around. The loading callable is the loader's ``load_world`` bound to the
database in production and a recording fake in the tests; the report goes through
``emit`` one line per version, the key=value lines the other jobs print.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from leaveimpact.adapters.corpus.loader import CacheWorld, LoadOutcome
from leaveimpact.adapters.manifest import WorldManifest
from leaveimpact.adapters.object_store.documents import SealedDocumentReader
from leaveimpact.adapters.object_store.layout import levels_key
from leaveimpact.adapters.object_store.read import ObjectReader
from leaveimpact.adapters.object_store.serving import (
    NotServed,
    ServedWorld,
    admit,
    discover_versions,
)
from leaveimpact.core.entities import Document
from leaveimpact.core.ids import DocumentId, WorldVersion
from leaveimpact.world.decoders import decode_levels
from leaveimpact.world.levels import BASE_CORPUS_LEVELS, CorpusLevels

Load = Callable[[CacheWorld], LoadOutcome]
Emit = Callable[[str], None]


class CacheJobRefused(Exception):
    """What the store holds does not agree with its manifest, or cannot be read as a world;
    the message names the version and what differed."""


@dataclass(frozen=True, slots=True)
class CacheReport:
    """What one run of the job did: the versions loaded, found ready, and declined."""

    loaded: tuple[WorldVersion, ...]
    already_ready: tuple[WorldVersion, ...]
    declined: tuple[NotServed, ...]


def fill_cache(store: ObjectReader, *, development: bool, load: Load, emit: Emit) -> CacheReport:
    """Every version under ``worlds/`` admitted by the serving rule, verified and loaded through
    ``load``; one report line per version through ``emit``."""
    loaded: list[WorldVersion] = []
    ready: list[WorldVersion] = []
    declined: list[NotServed] = []
    for version in discover_versions(store):
        served = admit(store, version, development=development)
        if isinstance(served, NotServed):
            declined.append(served)
            emit(f"declined={version} reason={served.reason}")
            continue
        world = cache_world_of(store, served)
        outcome = load(world)
        (loaded if outcome is LoadOutcome.LOADED else ready).append(version)
        emit(
            f"{outcome.value}={version} projection={world.projection.value} "
            f"documents={len(world.documents)} "
            f"levels={','.join(level.name for level in world.levels.levels)}"
        )
    return CacheReport(tuple(loaded), tuple(ready), tuple(declined))


def cache_world_of(store: ObjectReader, served: ServedWorld) -> CacheWorld:
    """The served world read whole from ``store`` and verified against its manifest where it
    has one: the levels, every document, the version ids."""
    version = served.version
    manifest = served.manifest
    levels = _levels(store, version, manifest)
    reader = SealedDocumentReader(store, version)
    held = reader.held_document_ids()
    if manifest is not None:
        _check_receipts(version, held, manifest)
    documents = tuple(_documents(reader, version, sorted(held)))
    if manifest is not None:
        _check_versions(version, reader, manifest)
    try:
        return CacheWorld(version, served.projection, served.manifest_digest, levels, documents)
    except ValueError as error:
        raise CacheJobRefused(f"{version}: {error}") from error


def _levels(
    store: ObjectReader, version: WorldVersion, manifest: WorldManifest | None
) -> CorpusLevels:
    key = levels_key(version)
    stored = store.get(key)
    vouched = manifest.object_versions.get(key) if manifest is not None else None
    if stored is None:
        if vouched is not None:
            raise CacheJobRefused(
                f"{version}: the manifest vouches for {key!r} and it is not there"
            )
        return BASE_CORPUS_LEVELS
    if manifest is not None and vouched is None:
        # A final prefix is create-only, so a key the manifest never recorded is exactly what
        # the bucket policy lets anyone with a put add later; it shapes no level here.
        raise CacheJobRefused(
            f"{version}: {key!r} is under the prefix and the manifest vouches for no such object"
        )
    if vouched is not None and stored.version_id != vouched:
        raise CacheJobRefused(
            f"{version}: {key!r} read back as version {stored.version_id}, the manifest "
            f"vouches for {vouched}"
        )
    try:
        return decode_levels(stored.content)
    except ValueError as error:
        raise CacheJobRefused(
            f"{version}: {key!r} does not decode as the levels: {error}"
        ) from error


def _check_receipts(
    version: WorldVersion, held: frozenset[DocumentId], manifest: WorldManifest
) -> None:
    receipted = frozenset(manifest.receipts.documents.documents)
    if held != receipted:
        raise CacheJobRefused(
            f"{version}: the documents under the prefix are not the receipted ones; missing "
            f"{sorted(receipted - held)}, foreign {sorted(held - receipted)}"
        )


def _documents(
    reader: SealedDocumentReader, version: WorldVersion, ids: Iterable[DocumentId]
) -> Iterable[Document]:
    for id in ids:
        observed = reader.document(id)
        if observed is None:
            raise CacheJobRefused(f"{version}: document {id} was listed and is not there to read")
        yield observed.value


def _check_versions(
    version: WorldVersion, reader: SealedDocumentReader, manifest: WorldManifest
) -> None:
    for id, key in manifest.receipts.documents.documents.items():
        read = reader.object_versions[id]
        vouched = manifest.object_versions.get(key)
        if vouched is None:
            raise CacheJobRefused(
                f"{version}: the manifest receipts {id} and vouches for no version of {key!r}"
            )
        if read != vouched:
            raise CacheJobRefused(
                f"{version}: {key!r} read back as version {read}, the manifest vouches "
                f"for {vouched}"
            )
