"""The cache job over an in-memory store and a recording loader: what it hands the loader,
what it verifies first, and what it reports.

A projected world with an approving verdict is read whole and handed over with its
manifest digest, its levels and every receipted document; a world sealed before the
levels object existed reads as the base level alone; a development world is declined
under a bucket and loaded on a development root; and each clause of "verified against the
manifest" refuses by name before any load: a foreign or missing document key, an object
read back under another version id than the manifest vouches for, a levels object the
manifest vouches for that is not there.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import date

import pytest

from leaveimpact.adapters.corpus.loader import CacheWorld, LoadOutcome
from leaveimpact.adapters.manifest import DocumentReceipts, Receipts, manifest_bytes
from leaveimpact.adapters.object_store import layout
from leaveimpact.adapters.object_store.read import StoredObject
from leaveimpact.adapters.object_store.verdicts import VALIDATOR_VERSION
from leaveimpact.cache.job import CacheJobRefused, fill_cache
from leaveimpact.core.entities import Document, DocumentSection
from leaveimpact.core.enums import DocumentKind, EntityKind
from leaveimpact.core.ids import DocumentId, WorldVersion, clause_id, document_id
from leaveimpact.core.run_record import WorldProjection
from leaveimpact.validator.checks import CheckStatus, LevelsResult
from leaveimpact.validator.verdict import FidelityResult, ValidationVerdict, verdict_bytes
from leaveimpact.world.artifacts import document_bytes, levels_bytes
from leaveimpact.world.levels import BASE_CORPUS_LEVELS, CorpusLevels, SealedLevel
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.test_manifest import VERSION, manifest

POLICY = Document(
    document_id(1),
    "Leave policy",
    DocumentKind.POLICY,
    date(2026, 1, 1),
    (DocumentSection(clause_id(1), "Cover is named before leave starts."),),
)
FILLER = Document(
    document_id(2),
    "Pager etiquette",
    DocumentKind.RUNBOOK,
    date(2026, 2, 1),
    (DocumentSection(clause_id(2), "The pager is handed over each shift."),),
)
LEVELS = CorpusLevels((SealedLevel("base", 0), SealedLevel("padded", 1)), (FILLER.id,))


class RecordingLoad:
    def __init__(self, ready: frozenset[WorldVersion] = frozenset()) -> None:
        self.worlds: list[CacheWorld] = []
        self.ready = ready

    def __call__(self, world: CacheWorld) -> LoadOutcome:
        self.worlds.append(world)
        return LoadOutcome.ALREADY_READY if world.version in self.ready else LoadOutcome.LOADED


def sealed_world(
    store: InMemoryObjectStore,
    *,
    version: WorldVersion = VERSION,
    documents: tuple[Document, ...] = (POLICY, FILLER),
    levels: CorpusLevels | None = LEVELS,
    projected: bool = True,
) -> Mapping[str, StoredObject]:
    """The world's served objects in ``store``, with a manifest vouching for each and an
    approving verdict when ``projected``; the objects by key."""
    keys: dict[str, StoredObject] = {}
    for document in documents:
        key = layout.document_key(version, document.id)
        store.put_if_absent(key, document_bytes(document))
    store.put_if_absent(layout.scenario_specs_key(version), b"{}")
    if levels is not None:
        store.put_if_absent(layout.levels_key(version), levels_bytes(levels))
    for key, stored in store.objects.items():
        if key.startswith(layout.world_prefix(version)):
            keys[key] = stored
    if not projected:
        return keys
    receipts = Receipts(
        documents=DocumentReceipts(
            {document.id: layout.document_key(version, document.id) for document in documents}
        )
    )
    record = manifest(
        world_version=version,
        receipts=receipts,
        object_versions={key: stored.version_id for key, stored in keys.items()},
    )
    content = manifest_bytes(record)
    store.put_if_absent(layout.world_manifest_key(version), content)
    verdict = ValidationVerdict(
        world_version=version,
        validator_version=VALIDATOR_VERSION,
        manifest_digest=hashlib.sha256(content).hexdigest(),
        artifacts=record.artifacts,
        exactness=(),
        fidelity=(FidelityResult(EntityKind.DOCUMENT, CheckStatus.PASSED),),
        views=(),
        levels=LevelsResult(CheckStatus.PASSED, "object"),
    )
    store.put_if_absent(layout.verdict_key(version, "100", "1"), verdict_bytes(verdict))
    return keys


def test_a_projected_world_is_read_whole_and_handed_over_with_its_digest_and_levels() -> None:
    store = InMemoryObjectStore()
    sealed_world(store)
    load = RecordingLoad()
    lines: list[str] = []
    report = fill_cache(store, development=False, load=load, emit=lines.append)

    assert report.loaded == (VERSION,) and report.already_ready == () and report.declined == ()
    [world] = load.worlds
    manifest_object = store.get(layout.world_manifest_key(VERSION))
    assert manifest_object is not None
    assert world == CacheWorld(
        VERSION,
        WorldProjection.PROJECTED,
        hashlib.sha256(manifest_object.content).hexdigest(),
        LEVELS,
        (POLICY, FILLER),
    )
    assert lines == [f"loaded={VERSION} projection=projected documents=2 levels=base,padded"]


def test_a_ready_version_is_reported_as_such_and_a_declined_one_by_its_reason() -> None:
    store = InMemoryObjectStore()
    sealed_world(store)
    other = WorldVersion("b" * 64)
    sealed_world(store, version=other, projected=False)
    load = RecordingLoad(ready=frozenset({VERSION}))
    lines: list[str] = []
    report = fill_cache(store, development=False, load=load, emit=lines.append)
    assert report.already_ready == (VERSION,) and report.loaded == ()
    assert [declined.version for declined in report.declined] == [other]
    assert [world.version for world in load.worlds] == [VERSION], "a declined world is not read"
    assert lines[0].startswith(f"already_ready={VERSION} ")
    assert (
        lines[1]
        == f"declined={other} reason=no manifest under its final key: not a completed projection"
    )


def test_a_development_world_is_loaded_on_a_development_root_as_unprojected() -> None:
    store = InMemoryObjectStore()
    sealed_world(store, projected=False)
    load = RecordingLoad()
    report = fill_cache(store, development=True, load=load, emit=lambda line: None)
    assert report.loaded == (VERSION,)
    [world] = load.worlds
    assert world.projection is WorldProjection.UNPROJECTED and world.manifest_digest is None
    assert world.levels == LEVELS and world.documents == (POLICY, FILLER)


def test_a_development_sealing_that_stopped_before_its_levels_object_is_declined() -> None:
    # The external review's second finding: a root whose version holds documents and no
    # levels object was loaded as a partial world and marked ready; the levels object is the
    # last write of an unprojected sealing and the admission requires it.
    store = InMemoryObjectStore()
    sealed_world(store, levels=None, projected=False)
    load = RecordingLoad()
    report = fill_cache(store, development=True, load=load, emit=lambda line: None)
    assert load.worlds == [] and report.loaded == ()
    [declined] = report.declined
    assert declined.reason.startswith("no levels object")


def test_a_world_sealed_before_the_levels_object_reads_as_the_base_level_alone() -> None:
    store = InMemoryObjectStore()
    sealed_world(store, documents=(POLICY,), levels=None)
    load = RecordingLoad()
    fill_cache(store, development=False, load=load, emit=lambda line: None)
    [world] = load.worlds
    assert world.levels == BASE_CORPUS_LEVELS and world.documents == (POLICY,)


def refusal(store: InMemoryObjectStore, *, development: bool = False) -> str:
    load = RecordingLoad()
    with pytest.raises(CacheJobRefused) as caught:
        fill_cache(store, development=development, load=load, emit=lambda line: None)
    assert load.worlds == [], "nothing is loaded after a refusal"
    return str(caught.value)


def test_a_foreign_or_missing_document_key_refuses_by_name_before_any_load() -> None:
    store = InMemoryObjectStore()
    sealed_world(store)
    foreign = Document(document_id(9), "Stray", DocumentKind.POLICY, date(2026, 1, 1), ())
    store.put_if_absent(layout.document_key(VERSION, foreign.id), document_bytes(foreign))
    assert "foreign ['doc_009']" in refusal(store)

    store = InMemoryObjectStore()
    sealed_world(store)
    del store.objects[layout.document_key(VERSION, FILLER.id)]
    assert "missing ['doc_002']" in refusal(store)


def test_an_object_under_another_version_id_than_the_manifest_vouches_for_refuses() -> None:
    store = InMemoryObjectStore()
    sealed_world(store)
    key = layout.document_key(VERSION, POLICY.id)
    stored = store.objects[key]
    store.objects[key] = StoredObject(key, stored.content, "v9999")
    message = refusal(store)
    assert key in message and "read back as version v9999" in message

    store = InMemoryObjectStore()
    sealed_world(store)
    key = layout.levels_key(VERSION)
    stored = store.objects[key]
    store.objects[key] = StoredObject(key, stored.content, "v9999")
    assert "levels.json" in refusal(store)


def test_a_levels_object_the_manifest_vouches_for_that_is_not_there_refuses() -> None:
    store = InMemoryObjectStore()
    sealed_world(store)
    del store.objects[layout.levels_key(VERSION)]
    assert "vouches for" in refusal(store) and "not there" in refusal(store)


def test_the_pool_of_the_levels_object_must_name_held_documents() -> None:
    store = InMemoryObjectStore()
    stray = CorpusLevels((SealedLevel("base", 0),), (DocumentId("doc_077"),))
    sealed_world(store, levels=stray)
    message = refusal(store)
    assert "does not hold: ['doc_077']" in message and message.startswith(VERSION)
