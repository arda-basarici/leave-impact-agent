"""The cache job over a store reader and the cache's three operations: discover, admit,
read, verify, load, demote what the rule no longer serves, report.

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
not served around.

After the listing, the flip (the first live run's step, fork 11): every version the cache
serves that the listing holds and the rule declined this run is demoted to not ready and
reported with the clause that declined it, so the serving check every attempt makes refuses
it; no row is deleted, and a later approval under the current rule readmits it through the
load. A version the cache serves and the listing no longer holds is reported as unlisted
and left as it is: under a create-only prefix a version vanishes only by an operator's hand,
which the operator finishes by hand, and on a laptop where several local roots share one
database a flip here would unserve every other root's world at each run (the step's build
notes). The cache is the protocol below, the loader's three functions bound to the database
in production and a recording fake in the tests; the report goes through ``emit`` one line
per version, the key=value lines the other jobs print.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

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


class Cache(Protocol):
    """The cache as the job drives it: a load, the versions served now, and the flip."""

    def load(self, world: CacheWorld) -> LoadOutcome: ...

    def ready_versions(self) -> frozenset[WorldVersion]: ...

    def demote(self, version: WorldVersion) -> bool: ...


Emit = Callable[[str], None]


class CacheJobRefused(Exception):
    """What the store holds does not agree with its manifest, or cannot be read as a world;
    the message names the version and what differed."""


@dataclass(frozen=True, slots=True)
class CacheReport:
    """What one run of the job did: the versions loaded, found ready, readmitted, declined,
    demoted (served before this run and declined by the rule now) and unlisted (served
    before this run and no longer under the prefix, left as they are)."""

    loaded: tuple[WorldVersion, ...]
    already_ready: tuple[WorldVersion, ...]
    readmitted: tuple[WorldVersion, ...]
    declined: tuple[NotServed, ...]
    demoted: tuple[WorldVersion, ...]
    unlisted: tuple[WorldVersion, ...]


def fill_cache(store: ObjectReader, *, development: bool, cache: Cache, emit: Emit) -> CacheReport:
    """Every version under ``worlds/`` admitted by the serving rule, verified and loaded into
    ``cache``; every version the cache serves and the rule declined demoted, one it no longer
    lists reported; one report line per version through ``emit``."""
    loaded: list[WorldVersion] = []
    ready: list[WorldVersion] = []
    readmitted: list[WorldVersion] = []
    declined: list[NotServed] = []
    served: set[WorldVersion] = set()
    for version in discover_versions(store):
        admitted = admit(store, version, development=development)
        if isinstance(admitted, NotServed):
            declined.append(admitted)
            emit(f"declined={version} reason={admitted.reason}")
            continue
        world = cache_world_of(store, admitted)
        outcome = cache.load(world)
        served.add(version)
        match outcome:
            case LoadOutcome.LOADED:
                loaded.append(version)
            case LoadOutcome.ALREADY_READY:
                ready.append(version)
            case LoadOutcome.READMITTED:
                readmitted.append(version)
        emit(
            f"{outcome.value}={version} projection={world.projection.value} "
            f"documents={len(world.documents)} "
            f"levels={','.join(level.name for level in world.levels.levels)}"
        )
    reasons = {declined_world.version: declined_world.reason for declined_world in declined}
    demoted: list[WorldVersion] = []
    unlisted: list[WorldVersion] = []
    for version in sorted(cache.ready_versions() - served):
        if version not in reasons:
            unlisted.append(version)
            emit(f"unlisted={version} note=served and no longer under the prefix; left as it is")
        elif cache.demote(version):
            demoted.append(version)
            emit(f"demoted={version} reason={reasons[version]}")
    return CacheReport(
        tuple(loaded),
        tuple(ready),
        tuple(readmitted),
        tuple(declined),
        tuple(demoted),
        tuple(unlisted),
    )


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
        if manifest is None:
            raise CacheJobRefused(
                f"{version}: a development world is admitted on its levels object and {key!r} "
                "is not there"
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
