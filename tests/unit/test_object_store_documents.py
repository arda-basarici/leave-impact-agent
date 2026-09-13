"""The sealed documents over the object store: a document seals once at its content-addressed
key and reads back equal as a corpus observation; a second add of the same document is the
equal case and a changed one the conflict; the held ids are exactly the keys under the
prefix, a foreign key there refused; an object naming another id than its key, or bytes that
do not decode, are malformed with the key as locator; the reader has no add; the version
of every object read or written is remembered by id. Beside it, the key layout's
invariants and the object-backed checkpoint store's round trip."""

from __future__ import annotations

from datetime import date

import pytest

from leaveimpact.adapters.manifest import ManifestStage
from leaveimpact.adapters.object_store import layout
from leaveimpact.adapters.object_store.documents import SealedDocumentReader
from leaveimpact.adapters.object_store.documents_write import SealedDocumentWriter
from leaveimpact.adapters.object_store.write import ObjectConflict
from leaveimpact.core.entities import Document, DocumentSection
from leaveimpact.core.enums import DocumentKind, Source
from leaveimpact.core.ids import WorldVersion, clause_id, document_id
from leaveimpact.core.ports.errors import MalformedRecord
from leaveimpact.generator.manifest_store import ObjectManifestStore
from leaveimpact.generator.projection import DocumentSystem
from leaveimpact.world.artifacts import document_bytes
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.test_manifest import manifest

VERSION = WorldVersion("ab" * 32)
POLICY = Document(
    document_id(3),
    "Leave policy",
    DocumentKind.POLICY,
    date(2026, 1, 1),
    (
        DocumentSection(clause_id(7), "Cover is named before leave starts."),
        DocumentSection(clause_id(8), "A handover precedes any leave over five days."),
    ),
)


def test_a_document_seals_once_and_reads_back_as_a_corpus_observation() -> None:
    store = InMemoryObjectStore()
    writer = SealedDocumentWriter(store, VERSION)
    key = writer.add_document(POLICY)
    assert key == layout.document_key(VERSION, POLICY.id)
    observed = SealedDocumentReader(store, VERSION).document(POLICY.id)
    assert observed is not None
    assert observed.value == POLICY and observed.source is Source.CORPUS
    assert writer.add_document(POLICY) == key, "the equal case, no second write"
    assert len(store.writes) == 1
    with pytest.raises(ObjectConflict):
        writer.add_document(
            Document(
                POLICY.id,
                "Leave policy, revised",
                POLICY.kind,
                POLICY.effective_from,
                POLICY.sections,
            )
        )


def test_the_held_ids_are_the_keys_under_the_prefix_and_a_foreign_key_is_refused() -> None:
    store = InMemoryObjectStore()
    writer = SealedDocumentWriter(store, VERSION)
    assert writer.held_document_ids() == frozenset()
    writer.add_document(POLICY)
    store.put_if_absent(layout.document_key(WorldVersion("cd" * 32), POLICY.id), b"{}")
    assert writer.held_document_ids() == frozenset({POLICY.id})
    for stray in ("notes.txt", "emp_001.json", "foo.json"):
        store.put_if_absent(layout.documents_prefix(VERSION) + stray, b"stray")
        with pytest.raises(MalformedRecord, match="not a document key"):
            writer.held_document_ids()
        del store.objects[layout.documents_prefix(VERSION) + stray]


def test_an_object_that_is_not_this_document_is_malformed_with_the_key_as_locator() -> None:
    store = InMemoryObjectStore()
    other = document_id(4)
    store.put_if_absent(layout.document_key(VERSION, other), document_bytes(POLICY))
    store.put_if_absent(layout.document_key(VERSION, document_id(5)), b'{"id": "doc_005"}')
    reader = SealedDocumentReader(store, VERSION)
    with pytest.raises(MalformedRecord, match="names document doc_003, the key says doc_004"):
        reader.document(other)
    with pytest.raises(MalformedRecord, match=layout.document_key(VERSION, document_id(5))):
        reader.document(document_id(5))
    assert reader.document(document_id(6)) is None


def test_the_reader_has_no_add_and_versions_are_remembered_by_id() -> None:
    store = InMemoryObjectStore()
    writer = SealedDocumentWriter(store, VERSION)
    receipt_version = store.get(writer.add_document(POLICY))
    assert receipt_version is not None
    assert dict(writer.object_versions) == {POLICY.id: receipt_version.version_id}
    reader = SealedDocumentReader(store, VERSION)
    assert not hasattr(reader, "add_document")
    assert dict(reader.object_versions) == {}
    reader.document(POLICY.id)
    assert dict(reader.object_versions) == {POLICY.id: receipt_version.version_id}
    system: DocumentSystem = writer
    assert system.document(POLICY.id) is not None


def test_the_layout_keeps_final_and_mutable_apart_and_every_key_names_the_version() -> None:
    final = (
        layout.scenario_specs_key(VERSION),
        layout.world_manifest_key(VERSION),
        layout.document_key(VERSION, POLICY.id),
        layout.verdict_key(VERSION, "1", "1"),
    )
    assert all(key.startswith(layout.world_prefix(VERSION)) for key in final)
    assert layout.checkpoint_key(VERSION).startswith("preparing/")
    assert layout.world_spec_key(VERSION).startswith("world-spec/")
    assert layout.truth_manifest_key(VERSION).startswith("truth-manifest/")
    assert all(VERSION in key for key in (*final, layout.checkpoint_key(VERSION)))
    assert layout.document_id_of(VERSION, layout.document_key(VERSION, POLICY.id)) == POLICY.id
    assert layout.document_id_of(VERSION, layout.documents_prefix(VERSION) + "a/b.json") is None


def test_the_object_checkpoint_store_round_trips_at_the_preparing_key_of_its_own_world() -> None:
    first = manifest(ManifestStage.PREPARING)
    store = InMemoryObjectStore()
    checkpoint = ObjectManifestStore(store, first.world_version)
    assert checkpoint.load() is None
    checkpoint.save(first)
    checkpoint.save(first)
    assert checkpoint.load() == first
    assert checkpoint.key == layout.checkpoint_key(first.world_version)
    assert store.list_keys("preparing/") == (checkpoint.key,)
    assert len(store.writes) == 2, "each save is a new version of the one mutable key"
    foreign = ObjectManifestStore(store, VERSION)
    with pytest.raises(ValueError, match="was given a manifest of world"):
        foreign.save(first)
    assert store.get(foreign.key) is None, "nothing was written under the other world's key"
    held = store.get(checkpoint.key)
    assert held is not None
    store.overwrite(foreign.key, held.content)
    with pytest.raises(ValueError, match="holds a manifest of world"):
        foreign.load()
