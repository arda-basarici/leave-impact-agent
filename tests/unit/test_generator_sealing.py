"""The sealing sequence over two in-memory buckets: the truth objects land before any vendor
call, the checkpoint lives under the mutable prefix and every document under the final one,
the documents seal only after the postflight so a refused site leaves none, the manifest is
the last object written and vouches for exactly the sealed keys with the version ids read
back, and a rerun of a sealed world writes nothing and yields the same bytes; a truth object
whose bytes changed between attempts is refused before any vendor call, and a sealed object
read back with other bytes is refused before the manifest.

No Tier 1 class plants a document — prose arrives with the materializer — so the seed world
seals none; the document-order claims are proven on the same world with one document added
to its entities at the root's seam, to be replaced by a planting class when one exists.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import date

import pytest

import leaveimpact.generator.realize as realize_module
import leaveimpact.generator.sealing as sealing_module
from leaveimpact.adapters.calendar.adapter import CalendarConfig
from leaveimpact.adapters.jira.adapter import JiraConfig, JiraFields
from leaveimpact.adapters.manifest import ManifestStage, decode_manifest
from leaveimpact.adapters.object_store import layout
from leaveimpact.adapters.object_store.documents_write import SealedDocumentWriter
from leaveimpact.adapters.object_store.read import StoredObject
from leaveimpact.adapters.object_store.write import ObjectConflict, PutOutcome, PutReceipt
from leaveimpact.core.entities import Document, DocumentSection, Employee
from leaveimpact.core.enums import DocumentKind, Source
from leaveimpact.core.ids import EmployeeId, WorkItemId, clause_id, document_id
from leaveimpact.generator.projection import Systems, WorldEntities, world_entities
from leaveimpact.generator.realize import Prepared, ProjectionRefused, frappe_company, world_key
from leaveimpact.generator.sealing import SealedWorld, SealingRefused, seal_world
from leaveimpact.world import DEFAULT_PARAMS, WorldSpec, assemble_world, bundle
from leaveimpact.world.artifacts import Bundle
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.in_memory_ports import InMemoryCalendar, InMemoryPeople, InMemoryWork

FIELDS = JiraFields("customfield_1", "customfield_2", "customfield_3", "customfield_4")
POLICY = Document(
    document_id(901),
    "Leave policy",
    DocumentKind.POLICY,
    date(2026, 1, 1),
    (DocumentSection(clause_id(901), "Cover is named before leave starts."),),
)


@pytest.fixture(scope="module")
def world() -> WorldSpec:
    return assemble_world(7, DEFAULT_PARAMS, date(2026, 1, 1))


@pytest.fixture(scope="module")
def sealed(world: WorldSpec) -> Bundle:
    return bundle(world)


@pytest.fixture
def with_a_document(monkeypatch: pytest.MonkeyPatch) -> Document:
    """One document in the world's entities, at the seam the root and the sealing read them."""

    def entities_with_policy(world: WorldSpec) -> WorldEntities:
        entities = world_entities(world)
        return replace(entities, documents=(*entities.documents, POLICY))

    monkeypatch.setattr(realize_module, "world_entities", entities_with_policy)
    monkeypatch.setattr(sealing_module, "world_entities", entities_with_policy)
    return POLICY


def prepared(sealed: Bundle) -> Prepared:
    return Prepared(
        frappe=frappe_company(sealed.world_version),
        jira=JiraConfig(world_key(sealed.world_version), FIELDS),
        observed_sites={Source.FRAPPE: "hr.example.invalid", Source.JIRA: "jira.example.invalid"},
    )


@dataclass
class Buckets:
    """The two stores of one sealing run, the world store's write trail readable."""

    truth: InMemoryObjectStore = field(default_factory=InMemoryObjectStore)
    world: InMemoryObjectStore = field(default_factory=InMemoryObjectStore)


@dataclass
class SealingPreparation:
    """Three in-memory vendors and the real sealed-document writer over the world store."""

    documents: SealedDocumentWriter
    truth: InMemoryObjectStore
    debris_markers: frozenset[WorkItemId] = frozenset()
    people: InMemoryPeople = field(default_factory=InMemoryPeople)
    work: InMemoryWork = field(default_factory=InMemoryWork)
    calendar: InMemoryCalendar = field(default_factory=InMemoryCalendar)
    truth_objects_at_prepare: int | None = None
    sealed: Bundle | None = None

    def prepare(self) -> Prepared:
        # The first vendor calls of a production run happen here, before the root runs.
        self.truth_objects_at_prepare = len(self.truth.objects)
        assert self.sealed is not None
        return prepared(self.sealed)

    def ensure_calendar(self, employee: Employee, known: str | None) -> str:
        return known or f"cal-{employee.id}@group.calendar"

    def systems(self, calendars: CalendarConfig) -> Systems:
        return Systems(self.people, self.work, self.calendar, self.documents)

    def held_employee_numbers(self, world_ids: Iterable[EmployeeId]) -> frozenset[EmployeeId]:
        return frozenset(self.people.people)

    def held_markers(self) -> frozenset[WorkItemId]:
        return frozenset(self.work.tickets) | self.debris_markers


def run(
    world: WorldSpec,
    sealed: Bundle,
    buckets: Buckets,
    debris_markers: frozenset[WorkItemId] = frozenset(),
) -> tuple[SealedWorld, SealingPreparation]:
    preparation = SealingPreparation(
        SealedDocumentWriter(buckets.world, sealed.world_version),
        buckets.truth,
        debris_markers,
        sealed=sealed,
    )
    result = seal_world(world, sealed, preparation, buckets.truth, buckets.world)
    return result, preparation


def test_a_fresh_run_seals_in_the_ruled_order_and_the_manifest_vouches_for_every_key(
    world: WorldSpec, sealed: Bundle, with_a_document: Document
) -> None:
    buckets = Buckets()
    result, preparation = run(world, sealed, buckets)
    version = sealed.world_version

    assert preparation.truth_objects_at_prepare == 2, "both truth objects before prepare()"
    assert buckets.truth.list_keys("") == (
        layout.truth_manifest_key(version),
        layout.world_spec_key(version),
    )

    trail = [receipt.key for receipt in buckets.world.writes]
    checkpoint, document = layout.checkpoint_key(version), layout.document_key(version, POLICY.id)
    assert trail[0] == checkpoint, "the checkpoint is the first world write"
    assert trail[-1] == layout.world_manifest_key(version), "the manifest is the last"
    assert all(key == checkpoint for key in trail[: trail.index(document)]), (
        "no final object before the vendor projection's checkpoints"
    )
    assert trail.index(layout.scenario_specs_key(version)) > trail.index(document)

    expected = {
        layout.world_spec_key(version),
        layout.truth_manifest_key(version),
        layout.scenario_specs_key(version),
        document,
    }
    assert set(result.manifest.object_versions) == expected
    for key, version_id in result.manifest.object_versions.items():
        store = (
            buckets.truth if key.startswith(("world-spec/", "truth-manifest/")) else buckets.world
        )
        stored = store.get(key)
        assert stored is not None and stored.version_id == version_id
    assert result.manifest.stage is ManifestStage.PROJECTED
    published = buckets.world.get(result.manifest_key)
    assert published is not None and published.version_id == result.manifest_version_id
    assert decode_manifest(published.content, stage=ManifestStage.PROJECTED) == result.manifest


def test_a_world_without_documents_seals_with_no_document_key_and_the_specs_before_the_manifest(
    world: WorldSpec, sealed: Bundle
) -> None:
    buckets = Buckets()
    result, _ = run(world, sealed, buckets)
    version = sealed.world_version
    assert set(result.manifest.object_versions) == {
        layout.world_spec_key(version),
        layout.truth_manifest_key(version),
        layout.scenario_specs_key(version),
    }
    trail = [receipt.key for receipt in buckets.world.writes]
    assert trail[-2:] == [layout.scenario_specs_key(version), layout.world_manifest_key(version)]


def test_a_rerun_of_a_sealed_world_writes_nothing_and_yields_the_same_bytes(
    world: WorldSpec, sealed: Bundle, with_a_document: Document
) -> None:
    buckets = Buckets()
    first, _ = run(world, sealed, buckets)
    writes_before = (len(buckets.truth.writes), len(buckets.world.writes))
    again, _ = run(world, sealed, buckets)
    assert again.manifest == first.manifest
    assert again.manifest_version_id == first.manifest_version_id
    assert len(buckets.truth.writes) == writes_before[0]
    final_writes = [
        r
        for r in buckets.world.writes[writes_before[1] :]
        if r.key != layout.checkpoint_key(sealed.world_version)
    ]
    assert final_writes == [], "only the mutable checkpoint is rewritten on a rerun"


def test_a_refused_postflight_leaves_no_document_under_the_final_prefix(
    world: WorldSpec, sealed: Bundle, with_a_document: Document
) -> None:
    buckets = Buckets()
    with pytest.raises(ProjectionRefused):
        run(world, sealed, buckets, debris_markers=frozenset({WorkItemId("ticket_999")}))
    version = sealed.world_version
    assert buckets.world.list_keys(layout.world_prefix(version)) == ()
    assert buckets.world.list_keys("preparing/") == (layout.checkpoint_key(version),)
    assert len(buckets.truth.objects) == 2, "truth stays sealed for the retry"


def test_truth_that_changed_between_attempts_is_refused_before_any_vendor_call(
    world: WorldSpec, sealed: Bundle
) -> None:
    buckets = Buckets()
    buckets.truth.put_if_absent(layout.world_spec_key(sealed.world_version), b"other bytes")
    with pytest.raises(ObjectConflict):
        run(world, sealed, buckets)
    assert buckets.world.objects == {}, "no vendor call and no world write"


def test_a_bundle_that_is_not_the_world_s_is_refused_before_any_write(
    world: WorldSpec, sealed: Bundle
) -> None:
    other = bundle(assemble_world(8, DEFAULT_PARAMS, date(2026, 1, 1)))
    buckets = Buckets()
    with pytest.raises(SealingRefused, match="not the bundle of the world"):
        run(world, other, buckets)
    assert buckets.truth.objects == {} and buckets.world.objects == {}


def test_an_object_read_back_with_other_bytes_is_refused_before_the_manifest(
    world: WorldSpec, sealed: Bundle
) -> None:
    class Tampering(InMemoryObjectStore):
        def put_if_absent(self, key: str, content: bytes) -> PutReceipt:
            receipt = super().put_if_absent(key, content)
            if key.endswith("scenario-specs.json") and receipt.outcome is PutOutcome.CREATED:
                self.objects[key] = StoredObject(key, b"swapped", "v-x")
            return receipt

    buckets = Buckets(world=Tampering())
    with pytest.raises(SealingRefused, match="read back with other bytes"):
        run(world, sealed, buckets)
    assert buckets.world.get(layout.world_manifest_key(sealed.world_version)) is None
