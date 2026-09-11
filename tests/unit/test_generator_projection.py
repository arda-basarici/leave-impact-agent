"""Projection over the in-memory ports: a fresh world lands whole and every planted id has a
receipt; a rerun writes nothing while the calendar's receipts are complete again; a
half-projected store completes with only the missing written; an existing identity holding
other state stops projection as a conflict, nothing overwritten; teams precede employees and
managers precede reports; a dead source raises through."""

from dataclasses import dataclass, field, replace
from datetime import date

import pytest

from leaveimpact.adapters.manifest import DocumentReceipts, PeopleReceipts, WorkReceipts
from leaveimpact.core import IdentityConflict, Source, SourceUnreachable
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


def test_a_fresh_projection_writes_every_entity_and_receipts_every_id(
    entities: WorldEntities,
) -> None:
    fakes = Fakes()
    systems = fakes.systems
    receipts = project_world(entities, systems)
    assert entities.leaves and entities.work_items and entities.events, (
        "a world with something to plant"
    )
    assert set(receipts.people.teams) == {team.id for team in entities.teams}
    assert set(receipts.people.employees) == {employee.id for employee in entities.employees}
    assert set(receipts.people.leaves) == {leave.id for leave in entities.leaves}
    assert set(receipts.work.components) == {component.id for component in entities.components}
    assert set(receipts.work.work_items) == {item.id for item in entities.work_items}
    assert set(receipts.calendar.events) == {event.id for event in entities.events}
    assert set(receipts.documents.documents) == {document.id for document in entities.documents}
    assert {seen.value for seen in systems.people.employees()} == set(entities.employees)
    assert {seen.value for seen in systems.work.work_items()} == set(entities.work_items)
    assert set(fakes.calendar.events.values()) == set(entities.events)
    assert all(locator.startswith("jira-fake:") for locator in receipts.work.work_items.values())


def test_a_rerun_writes_nothing_and_the_calendar_receipts_are_complete_again(
    entities: WorldEntities,
) -> None:
    fakes = Fakes()
    systems = fakes.systems
    first = project_world(entities, systems)
    again = project_world(entities, systems)
    assert again.people == PeopleReceipts()
    assert again.work == WorkReceipts()
    assert again.documents == DocumentReceipts()
    assert again.calendar == first.calendar, (
        "the insert returns the derived id whether it created or verified"
    )
    assert len(fakes.people.people) == len(entities.employees)
    assert len(fakes.work.tickets) == len(entities.work_items)


def test_a_half_projected_store_completes_with_only_the_missing_written(
    entities: WorldEntities,
) -> None:
    fakes = Fakes()
    systems = fakes.systems
    project_world(entities, systems)
    dropped_employee = entities.employees[-1]
    dropped_item = entities.work_items[0]
    dropped_event = entities.events[0]
    del fakes.people.people[dropped_employee.id]
    del fakes.work.tickets[dropped_item.id]
    del fakes.calendar.events[dropped_event.id]
    again = project_world(entities, systems)
    assert set(again.people.employees) == {dropped_employee.id}
    assert not again.people.teams and not again.people.leaves
    assert set(again.work.work_items) == {dropped_item.id}
    assert not again.work.components
    assert set(again.calendar.events) == {event.id for event in entities.events}
    assert fakes.people.people[dropped_employee.id] == dropped_employee
    assert fakes.calendar.events[dropped_event.id] == dropped_event


def test_an_existing_identity_holding_other_state_is_a_conflict_not_an_overwrite(
    entities: WorldEntities,
) -> None:
    fakes = Fakes()
    systems = fakes.systems
    planted = entities.employees[0]
    stranger = replace(planted, name="Someone Else")
    systems.people.add_employee(stranger)
    with pytest.raises(IdentityConflict, match=f"frappe identity {planted.id}") as caught:
        project_people(entities, systems.people)
    assert caught.value.source is Source.FRAPPE
    held = systems.people.employee(planted.id)
    assert held is not None and held.value == stranger, "nothing adopted, nothing overwritten"
    assert len(fakes.people.people) == 1, "projection stopped at the conflict"


def test_teams_precede_employees_and_managers_precede_reports(entities: WorldEntities) -> None:
    order = [employee.id for employee in entities.employees]
    for employee in entities.employees:
        if employee.manager_id is not None:
            assert order.index(employee.manager_id) < order.index(employee.id)
    assert entities.employees[0].manager_id is None
    fakes = Fakes()
    systems = fakes.systems
    project_people(entities, systems.people)
    assert list(fakes.people.people) == order, "the fake received them managers first"
    with pytest.raises(ValueError, match="a manager is missing or cyclic"):
        managers_first(entities.employees[1:])


def test_a_dead_source_raises_through(entities: WorldEntities) -> None:
    fakes = Fakes()
    systems = fakes.systems
    fakes.work.reachable = False
    with pytest.raises(SourceUnreachable):
        project_world(entities, systems)
    assert len(fakes.people.people) == len(entities.employees), "the HR system was written first"
