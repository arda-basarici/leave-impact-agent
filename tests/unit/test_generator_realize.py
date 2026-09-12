"""The composition root over fakes: a fresh run checkpoints after every calendar and every
receipt, proves the sites and the coverage, and promotes once; a run cut off during calendar
preparation resumes with the known calendars verified and none re-created; a run cut off
during projection resumes from its receipts and ends with every planted id receipted; a
checkpoint of another world, of drifted site configuration, of a tampered header or with a
foreign calendar is refused before any vendor call; debris in a site is refused before
projection; the coverage proof is exact; the file store replaces atomically."""

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

import pytest

from leaveimpact.adapters.calendar.adapter import CalendarConfig
from leaveimpact.adapters.jira.adapter import JiraConfig, JiraFields
from leaveimpact.adapters.manifest import (
    ManifestStage,
    WorldManifest,
    decode_manifest,
    with_receipt,
)
from leaveimpact.core import Source, SourceUnreachable, work_item_ref
from leaveimpact.core.entities import Employee, WorkItem
from leaveimpact.core.ids import EmployeeId, WorkItemId, WorldVersion, employee_id, work_item_id
from leaveimpact.generator.manifest_store import FileManifestStore
from leaveimpact.generator.projection import Systems, world_entities
from leaveimpact.generator.realize import (
    Prepared,
    ProjectionRefused,
    check_coverage,
    check_scope,
    frappe_company,
    jira_project_name,
    realize,
    world_key,
)
from leaveimpact.world import (
    DEFAULT_PARAMS,
    Bundle,
    GeneratorVersion,
    WorldSpec,
    assemble_world,
    bundle,
)
from tests.unit.in_memory_ports import (
    InMemoryCalendar,
    InMemoryDocuments,
    InMemoryPeople,
    InMemoryWork,
)

FIELDS = JiraFields("customfield_1", "customfield_2", "customfield_3", "customfield_4")


@pytest.fixture(scope="module")
def world() -> WorldSpec:
    return assemble_world(7, DEFAULT_PARAMS, date(2026, 1, 1))


@pytest.fixture(scope="module")
def sealed(world: WorldSpec) -> Bundle:
    return bundle(world)


def prepared(sealed: Bundle) -> Prepared:
    return Prepared(
        frappe=frappe_company(sealed.world_version),
        jira=JiraConfig(world_key(sealed.world_version), FIELDS),
        observed_sites={Source.FRAPPE: "hr.example.invalid", Source.JIRA: "jira.example.invalid"},
    )


@dataclass
class MemoryStore:
    """A manifest store that remembers every save, so a test can read the checkpoint trail."""

    current: WorldManifest | None = None
    saved: list[WorldManifest] = field(default_factory=list[WorldManifest])

    def load(self) -> WorldManifest | None:
        return self.current

    def save(self, manifest: WorldManifest) -> None:
        self.current = manifest
        self.saved.append(manifest)


@dataclass
class FakePreparation:
    """The four fakes behind the preparation seam, with switches for the failures under test."""

    people: InMemoryPeople = field(default_factory=InMemoryPeople)
    work: InMemoryWork = field(default_factory=InMemoryWork)
    calendar: InMemoryCalendar = field(default_factory=InMemoryCalendar)
    documents: InMemoryDocuments = field(default_factory=InMemoryDocuments)
    created: list[EmployeeId] = field(default_factory=list[EmployeeId])
    verified: list[EmployeeId] = field(default_factory=list[EmployeeId])
    die_after_calendars: int | None = None
    extra_numbers: frozenset[EmployeeId] = frozenset()
    extra_markers: frozenset[WorkItemId] = frozenset()
    calendars_seen: CalendarConfig | None = None

    def ensure_calendar(self, employee: Employee, known: str | None) -> str:
        if known is not None:
            self.verified.append(employee.id)
            return known
        if self.die_after_calendars is not None and len(self.created) >= self.die_after_calendars:
            raise SourceUnreachable(Source.CALENDAR, "switched off in the test")
        self.created.append(employee.id)
        return f"cal-{employee.id}@group.calendar"

    def systems(self, calendars: CalendarConfig) -> Systems:
        self.calendars_seen = calendars
        return Systems(self.people, self.work, self.calendar, self.documents)

    def held_employee_numbers(self, world_ids: Iterable[EmployeeId]) -> frozenset[EmployeeId]:
        return frozenset(self.people.people) | self.extra_numbers

    def held_markers(self) -> frozenset[WorkItemId]:
        return frozenset(self.work.tickets) | self.extra_markers


def test_a_fresh_run_checkpoints_after_every_calendar_and_receipt_then_promotes_once(
    world: WorldSpec, sealed: Bundle
) -> None:
    preparation = FakePreparation()
    store = MemoryStore()
    final = realize(world, sealed, prepared(sealed), preparation, store)
    employees = len(world.org.employees)
    receipts = len(store.saved[-1].receipts.people.teams) + employees
    receipts += len(store.saved[-1].receipts.people.leaves)
    receipts += len(store.saved[-1].receipts.work.components)
    receipts += len(store.saved[-1].receipts.work.work_items)
    receipts += len(store.saved[-1].receipts.calendar.events)
    receipts += len(store.saved[-1].receipts.documents.documents)
    assert len(store.saved) == 1 + employees + receipts + 1, (
        "one save at the start, one per calendar, one per receipt, one promotion"
    )
    assert [m.stage for m in store.saved[:-1]] == [ManifestStage.PREPARING] * (len(store.saved) - 1)
    assert final.stage is ManifestStage.PROJECTED and store.current == final
    assert set(final.systems.calendar.calendar_by_employee) == {e.id for e in world.org.employees}
    assert preparation.calendars_seen == final.systems.calendar
    assert preparation.created == list(store.saved[-1].systems.calendar.calendar_by_employee)
    assert final.world_version == sealed.world_version
    assert final.digest_of(final.artifacts[2].role) == sealed.truth_manifest.digest
    assert (
        final.org_params == world.org.params and final.generator_version == world.generator_version
    )
    assert len(preparation.people.people) == employees
    check_coverage(final.receipts, world_entities(world))


def test_a_run_cut_off_during_calendar_preparation_resumes_without_recreating(
    world: WorldSpec, sealed: Bundle
) -> None:
    first = FakePreparation(die_after_calendars=3)
    store = MemoryStore()
    with pytest.raises(SourceUnreachable):
        realize(world, sealed, prepared(sealed), first, store)
    assert store.current is not None and store.current.stage is ManifestStage.PREPARING
    assert len(store.current.systems.calendar.calendar_by_employee) == 3, (
        "three calendars checkpointed"
    )
    assert not first.people.people, "nothing projected before preparation completed"
    second = FakePreparation()
    final = realize(world, sealed, prepared(sealed), second, store)
    assert second.verified == first.created, "the known three were verified, in order"
    assert len(second.created) == len(world.org.employees) - 3
    assert final.stage is ManifestStage.PROJECTED
    assert dict(final.systems.calendar.calendar_by_employee) | {} == {
        **{e: f"cal-{e}@group.calendar" for e in first.created},
        **{e: f"cal-{e}@group.calendar" for e in second.created},
    }


def test_a_run_cut_off_during_projection_resumes_from_its_receipts_and_covers_every_id(
    world: WorldSpec, sealed: Bundle
) -> None:
    class DiesAfterTwoAdds(InMemoryWork):
        def add_work_item(self, work_item: WorkItem) -> str:
            locator = super().add_work_item(work_item)
            if len(self.tickets) == 2:
                self.reachable = False
            return locator

    dying = DiesAfterTwoAdds()
    first = FakePreparation(work=dying)
    store = MemoryStore()
    with pytest.raises(SourceUnreachable):
        realize(world, sealed, prepared(sealed), first, store)
    checkpoint = store.current
    assert checkpoint is not None and checkpoint.stage is ManifestStage.PREPARING
    assert len(checkpoint.receipts.work.work_items) == 2, "both writes reached the checkpoint"
    assert len(checkpoint.receipts.people.employees) == len(world.org.employees)
    dying.reachable = True
    second = FakePreparation(
        people=first.people, work=dying, calendar=first.calendar, documents=first.documents
    )
    final = realize(world, sealed, prepared(sealed), second, store)
    assert final.stage is ManifestStage.PROJECTED
    assert second.verified and not second.created, "every calendar was known"
    first_two = dict(checkpoint.receipts.work.work_items)
    assert all(final.receipts.work.work_items[id] == locator for id, locator in first_two.items())
    assert len(final.receipts.work.work_items) == len(dying.tickets)


def test_a_checkpoint_of_another_world_or_of_drifted_configuration_is_refused_before_any_call(
    world: WorldSpec, sealed: Bundle
) -> None:
    store = MemoryStore()
    realize(world, sealed, prepared(sealed), FakePreparation(), store)
    accepted = store.current
    assert accepted is not None
    other_version = WorldVersion("b" * 64)
    store.current = replace(
        accepted,
        world_version=other_version,
        systems=replace(
            accepted.systems, corpus=replace(accepted.systems.corpus, world_version=other_version)
        ),
    )
    preparation = FakePreparation()
    with pytest.raises(ProjectionRefused, match="realizes world bbbb"):
        realize(world, sealed, prepared(sealed), preparation, store)
    assert not preparation.created and not preparation.verified and not preparation.people.people
    store.current = accepted
    drifted = replace(
        prepared(sealed),
        jira=JiraConfig(world_key(sealed.world_version), replace(FIELDS, owner="customfield_9")),
    )
    with pytest.raises(ProjectionRefused, match=r"disagrees with this run on \['jira'\]"):
        realize(world, sealed, drifted, preparation, store)
    assert not preparation.created and not preparation.verified


def test_debris_in_a_site_is_refused_before_projection_and_an_incomplete_site_after(
    world: WorldSpec, sealed: Bundle
) -> None:
    preparation = FakePreparation(extra_markers=frozenset({work_item_id(999)}))
    store = MemoryStore()
    with pytest.raises(
        ProjectionRefused, match="the Jira project holds ids outside this world: \\['ticket_999'\\]"
    ):
        realize(world, sealed, prepared(sealed), preparation, store)
    assert not preparation.people.people, "nothing projected into a site holding debris"
    assert store.current is not None and store.current.stage is ManifestStage.PREPARING
    assert len(store.current.systems.calendar.calendar_by_employee) == len(world.org.employees), (
        "the calendars prepared before the preflight stay checkpointed"
    )
    with pytest.raises(ProjectionRefused, match="the site lacks \\['b'\\] after projection"):
        check_scope({"a"}, {"a", "b"}, complete=True, what="the site")
    check_scope({"a", "b"}, {"a", "b"}, complete=True, what="the site")


def test_a_rerun_of_an_accepted_world_re_proves_it_and_writes_nothing(
    world: WorldSpec, sealed: Bundle
) -> None:
    preparation = FakePreparation()
    store = MemoryStore()
    first = realize(world, sealed, prepared(sealed), preparation, store)
    saves_before = len(store.saved)
    again = realize(world, sealed, prepared(sealed), preparation, store)
    assert again == first
    assert not preparation.created[len(world.org.employees) :], "no calendar re-created"
    assert len(store.saved) == saves_before + 2, (
        "the start and the promotion only: the calendar's re-reported ids fold to no change"
    )


def test_the_names_a_world_takes_are_derived_from_its_version(sealed: Bundle) -> None:
    key = world_key(sealed.world_version)
    assert len(key) == 10 and key[0] == "W" and key[1:] == sealed.world_version[:9].upper()
    assert frappe_company(sealed.world_version).company_abbr == key[:5]
    assert jira_project_name(sealed.world_version).endswith(sealed.world_version[:8])


def test_the_file_store_replaces_atomically_and_loads_any_stage(
    world: WorldSpec, sealed: Bundle, tmp_path: Path
) -> None:
    store = FileManifestStore(tmp_path / "world-manifest.json")
    assert store.load() is None
    final = realize(world, sealed, prepared(sealed), FakePreparation(), store)
    assert store.load() == final
    assert decode_manifest(store.path.read_bytes(), stage=ManifestStage.PROJECTED) == final
    assert sorted(p.name for p in tmp_path.iterdir()) == ["world-manifest.json"], (
        "no temporary left"
    )
    store.path.write_bytes(b"{not json")
    with pytest.raises(ValueError):
        store.load()


def test_a_checkpoint_with_a_foreign_calendar_or_a_tampered_header_is_refused_before_any_call(
    world: WorldSpec, sealed: Bundle
) -> None:
    store = MemoryStore()
    realize(world, sealed, prepared(sealed), FakePreparation(), store)
    accepted = store.current
    assert accepted is not None
    foreign = {**accepted.systems.calendar.calendar_by_employee, employee_id(999): "foreign@cal"}
    store.current = replace(
        accepted, systems=replace(accepted.systems, calendar=CalendarConfig(foreign))
    )
    preparation = FakePreparation()
    with pytest.raises(
        ProjectionRefused, match="the calendar map holds ids outside this world: \\['emp_999'\\]"
    ):
        realize(world, sealed, prepared(sealed), preparation, store)
    assert not preparation.created and not preparation.verified, "refused before any calendar call"
    store.current = replace(accepted, generator_version=GeneratorVersion("99"))
    with pytest.raises(
        ProjectionRefused, match="disagrees with this run on \\['generator_version'\\]"
    ):
        realize(world, sealed, prepared(sealed), preparation, store)
    tampered = (
        accepted.artifacts[0],
        accepted.artifacts[1],
        replace(accepted.artifacts[2], digest="f" * 64),
    )
    store.current = replace(
        accepted, artifacts=tampered, org_params=replace(accepted.org_params, org_size=30)
    )
    with pytest.raises(ProjectionRefused, match="on \\['artifacts', 'org_params'\\]"):
        realize(world, sealed, prepared(sealed), preparation, store)
    assert not preparation.created and not preparation.verified


def test_the_coverage_proof_is_exact_in_both_directions(world: WorldSpec, sealed: Bundle) -> None:
    store = MemoryStore()
    final = realize(world, sealed, prepared(sealed), FakePreparation(), store)
    entities = world_entities(world)
    check_coverage(final.receipts, entities)
    with pytest.raises(
        ProjectionRefused, match="receipts for ids this world never planted: \\['ticket_999'\\]"
    ):
        check_coverage(
            with_receipt(final.receipts, work_item_ref(work_item_id(999)), "X-999"), entities
        )
    with pytest.raises(ProjectionRefused, match="no receipt for"):
        check_coverage(
            replace(final.receipts, work=replace(final.receipts.work, work_items={})), entities
        )
