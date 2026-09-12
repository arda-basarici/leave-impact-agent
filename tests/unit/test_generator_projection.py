"""Projection over the in-memory ports: a fresh world lands whole and every planted id reaches
the sink; a rerun reports nothing but the calendar's derived ids; a half-projected store
completes with only the missing written; a failure after two checkpointed writes loses no
receipt, the rerun completes the set; an existing identity holding other state stops projection
as a conflict, nothing overwritten; teams precede employees and managers precede reports; a dead
source raises through."""

from dataclasses import dataclass, field, replace
from datetime import date

import pytest

from leaveimpact.adapters.manifest import (
    DocumentReceipts,
    PeopleReceipts,
    Receipts,
    WorkReceipts,
    with_receipt,
)
from leaveimpact.core import EntityRef, IdentityConflict, Source, SourceUnreachable
from leaveimpact.generator.projection import (
    Systems,
    WorldEntities,
    managers_first,
    project_people,
    project_world,
    world_entities,
)
from leaveimpact.world import DEFAULT_PARAMS, assemble_world
from tests.unit.in_memory_ports import (
    InMemoryCalendar,
    InMemoryDocuments,
    InMemoryPeople,
    InMemoryWork,
)


@pytest.fixture(scope="module")
def entities() -> WorldEntities:
    return world_entities(assemble_world(7, DEFAULT_PARAMS, date(2026, 1, 1)))


@dataclass
class Fakes:
    """The four in-memory stores, kept by name so a test can inspect and damage them."""

    people: InMemoryPeople = field(default_factory=InMemoryPeople)
    work: InMemoryWork = field(default_factory=InMemoryWork)
    calendar: InMemoryCalendar = field(default_factory=InMemoryCalendar)
    documents: InMemoryDocuments = field(default_factory=InMemoryDocuments)

    @property
    def systems(self) -> Systems:
        return Systems(self.people, self.work, self.calendar, self.documents)


@dataclass
class Checkpoint:
    """A receipt sink that folds like the composition root and remembers every call in order."""

    receipts: Receipts = field(default_factory=Receipts)
    calls: list[tuple[EntityRef, str]] = field(default_factory=list[tuple[EntityRef, str]])

    def __call__(self, ref: EntityRef, locator: str) -> None:
        self.receipts = with_receipt(self.receipts, ref, locator)
        self.calls.append((ref, locator))


def ids(receipts: Receipts) -> set[str]:
    return {
        str(id)
        for held in (
            receipts.people.teams,
            receipts.people.employees,
            receipts.people.leaves,
            receipts.work.components,
            receipts.work.work_items,
            receipts.calendar.events,
            receipts.documents.documents,
        )
        for id in held
    }


def planted_ids(entities: WorldEntities) -> set[str]:
    return {
        str(entity.id)
        for kind in (
            entities.teams,
            entities.employees,
            entities.leaves,
            entities.components,
            entities.work_items,
            entities.events,
            entities.documents,
        )
        for entity in kind
    }


def test_a_fresh_projection_writes_every_entity_and_reports_every_id(
    entities: WorldEntities,
) -> None:
    fakes = Fakes()
    sink = Checkpoint()
    project_world(entities, fakes.systems, sink)
    assert entities.leaves and entities.work_items and entities.events, "something to plant"
    assert ids(sink.receipts) == planted_ids(entities)
    assert len(sink.calls) == len(planted_ids(entities)), "one report per write, in order"
    assert {seen.value for seen in fakes.people.employees()} == set(entities.employees)
    assert {seen.value for seen in fakes.work.work_items()} == set(entities.work_items)
    assert set(fakes.calendar.events.values()) == set(entities.events)
    assert all(
        locator.startswith("jira-fake:") for locator in sink.receipts.work.work_items.values()
    )


def test_a_rerun_reports_nothing_but_the_calendar_s_derived_ids(entities: WorldEntities) -> None:
    fakes = Fakes()
    first = Checkpoint()
    project_world(entities, fakes.systems, first)
    again = Checkpoint()
    project_world(entities, fakes.systems, again)
    assert again.receipts.people == PeopleReceipts()
    assert again.receipts.work == WorkReceipts()
    assert again.receipts.documents == DocumentReceipts()
    assert again.receipts.calendar == first.receipts.calendar, (
        "the insert re-reports the derived id"
    )
    assert len(fakes.people.people) == len(entities.employees)
    assert len(fakes.work.tickets) == len(entities.work_items)


def test_a_half_projected_store_completes_with_only_the_missing_written(
    entities: WorldEntities,
) -> None:
    fakes = Fakes()
    project_world(entities, fakes.systems, Checkpoint())
    dropped_employee = entities.employees[-1]
    dropped_item = entities.work_items[0]
    dropped_event = entities.events[0]
    del fakes.people.people[dropped_employee.id]
    del fakes.work.tickets[dropped_item.id]
    del fakes.calendar.events[dropped_event.id]
    again = Checkpoint()
    project_world(entities, fakes.systems, again)
    assert set(again.receipts.people.employees) == {dropped_employee.id}
    assert not again.receipts.people.teams and not again.receipts.people.leaves
    assert set(again.receipts.work.work_items) == {dropped_item.id}
    assert not again.receipts.work.components
    assert set(again.receipts.calendar.events) == {event.id for event in entities.events}
    assert fakes.people.people[dropped_employee.id] == dropped_employee
    assert fakes.calendar.events[dropped_event.id] == dropped_event


def test_a_failure_after_checkpointed_writes_loses_no_receipt_and_the_rerun_completes_the_set(
    entities: WorldEntities,
) -> None:
    """Two writes land and are checkpointed; the source dies before the third entity is touched;
    the restart finds the two, receipts nothing for them, writes the rest — and the checkpoint,
    kept across both runs the way the manifest is, covers every planted id."""
    fakes = Fakes()

    @dataclass
    class DiesAfterTwo(Checkpoint):
        def __call__(self, ref: EntityRef, locator: str) -> None:
            super().__call__(ref, locator)
            if len(self.calls) == 2:
                fakes.people.reachable = False

    checkpoint = DiesAfterTwo()
    with pytest.raises(SourceUnreachable):
        project_world(entities, fakes.systems, checkpoint)
    assert len(checkpoint.calls) == 2 and len(fakes.people.teams) == 2, "died after the second team"
    survived = checkpoint.receipts
    fakes.people.reachable = True
    resumed = Checkpoint(receipts=survived)
    project_world(entities, fakes.systems, resumed)
    assert ids(survived) & {ref.id for ref, _ in resumed.calls} == set(), (
        "the found two are not re-reported"
    )
    assert ids(resumed.receipts) == planted_ids(entities)
    assert all(
        resumed.receipts.people.teams[team.id] == survived.people.teams[team.id]
        for team in entities.teams[:2]
    )


def test_an_existing_identity_holding_other_state_is_a_conflict_not_an_overwrite(
    entities: WorldEntities,
) -> None:
    fakes = Fakes()
    planted = entities.employees[0]
    stranger = replace(planted, name="Someone Else")
    fakes.people.add_employee(stranger)
    sink = Checkpoint()
    with pytest.raises(IdentityConflict, match=f"frappe identity {planted.id}") as caught:
        project_people(entities, fakes.people, sink)
    assert caught.value.source is Source.FRAPPE
    held = fakes.people.employee(planted.id)
    assert held is not None and held.value == stranger, "nothing adopted, nothing overwritten"
    assert len(fakes.people.people) == 1, "projection stopped at the conflict"
    assert set(sink.receipts.people.teams) == {team.id for team in entities.teams}, (
        "teams landed first"
    )


def test_teams_precede_employees_and_managers_precede_reports(entities: WorldEntities) -> None:
    order = [employee.id for employee in entities.employees]
    for employee in entities.employees:
        if employee.manager_id is not None:
            assert order.index(employee.manager_id) < order.index(employee.id)
    assert entities.employees[0].manager_id is None
    fakes = Fakes()
    sink = Checkpoint()
    project_people(entities, fakes.people, sink)
    assert list(fakes.people.people) == order, "the fake received them managers first"
    kinds = [ref.kind.value for ref, _ in sink.calls]
    assert (
        kinds.index("employee") > kinds.index("team")
        and "team" not in kinds[kinds.index("employee") :]
    )
    with pytest.raises(ValueError, match="a manager is missing or cyclic"):
        managers_first(entities.employees[1:])


def test_a_dead_source_raises_through(entities: WorldEntities) -> None:
    fakes = Fakes()
    fakes.work.reachable = False
    with pytest.raises(SourceUnreachable):
        project_world(entities, fakes.systems, Checkpoint())
    assert len(fakes.people.people) == len(entities.employees), "the HR system was written first"
