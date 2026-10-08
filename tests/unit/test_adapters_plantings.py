"""The planted readers conform to the three read ports and answer what the fakes filled from
the same world answer, record for record and in order, for every enumeration, every by-id
read and every windowed read; every planting is returned whatever the day it became
observable; the switch makes every read raise with the source; a duplicate planting refuses
at construction naming the kind and the id; the readers built from the sealed truth store
equal the ones built from the loaded world; and the triple survives a pickle."""

from __future__ import annotations

import pickle
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

import pytest

from leaveimpact.adapters.object_store.layout import world_spec_key
from leaveimpact.adapters.plantings import (
    PlantedCalendar,
    PlantedPeople,
    PlantedReaders,
    PlantedWork,
    planted_readers,
    sealed_readers,
)
from leaveimpact.core import CalendarReader, PeopleReader, Source, SourceUnreachable, WorkReader
from leaveimpact.core.ids import ComponentId, EmployeeId, EventId, LeaveId, TeamId, WorkItemId
from leaveimpact.core.worldtime import DateSpan, InstantSpan
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import bundle
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.in_memory_ports import InMemoryCalendar, InMemoryPeople, InMemoryWork
from tests.unit.throwaway_world import composed_world, loaded_world, sealed_stores


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def readers(world: SealedWorld) -> PlantedReaders:
    return planted_readers(world)


@dataclass(frozen=True)
class Fakes:
    """The fakes filled from a sealed world the way the reads fixture filled them: the
    contract the readers replace."""

    people: InMemoryPeople
    work: InMemoryWork
    calendar: InMemoryCalendar


@pytest.fixture(scope="module")
def fakes(world: SealedWorld) -> Fakes:
    people, work, calendar = InMemoryPeople(), InMemoryWork(), InMemoryCalendar()
    for team in world.org.teams:
        people.add_team(team)
    for employee in world.org.employees:
        people.add_employee(employee)
    for component in world.org.components:
        work.add_component(component)
    for scenario in world.scenarios:
        for leave in scenario.owned.leaves:
            people.add_leave(leave.entity)
        for item in scenario.owned.work_items:
            work.add_work_item(item.entity)
        for event in scenario.owned.events:
            calendar.add_event(event.entity)
    return Fakes(people, work, calendar)


def test_the_readers_conform_to_the_three_read_ports() -> None:
    people: PeopleReader = PlantedPeople()
    work: WorkReader = PlantedWork()
    calendar: CalendarReader = PlantedCalendar()
    assert (people.source, work.source, calendar.source) == (
        Source.FRAPPE,
        Source.JIRA,
        Source.CALENDAR,
    )


def test_every_enumeration_equals_the_fakes_answer_in_order(
    readers: PlantedReaders, fakes: Fakes
) -> None:
    assert readers.people.employees() == fakes.people.employees()
    assert readers.work.work_items() == fakes.work.work_items()
    assert readers.work.components() == fakes.work.components()
    assert len(readers.people.employees()) == 28 and len(readers.work.work_items()) == 36


def test_every_by_id_read_equals_the_fakes_answer(readers: PlantedReaders, fakes: Fakes) -> None:
    for team in fakes.people.teams:
        assert readers.people.team(team) == fakes.people.team(team)
    for employee in fakes.people.people:
        assert readers.people.employee(employee) == fakes.people.employee(employee)
    for leave in fakes.people.leaves:
        assert readers.people.leave(leave) == fakes.people.leave(leave)
    for component in fakes.work.components_by_id:
        assert readers.work.component(component) == fakes.work.component(component)
    for ticket in fakes.work.tickets:
        assert readers.work.work_item(ticket) == fakes.work.work_item(ticket)
    for event in fakes.calendar.events:
        assert readers.calendar.event(event) == fakes.calendar.event(event)
    assert readers.people.employee(EmployeeId("emp_999")) is None
    assert readers.people.team(TeamId("team_999")) is None
    assert readers.people.leave(LeaveId("leave_999")) is None
    assert readers.work.work_item(WorkItemId("ticket_999")) is None


def test_every_windowed_read_equals_the_fakes_answer(
    world: SealedWorld, readers: PlantedReaders, fakes: Fakes
) -> None:
    seen_leaves = seen_events = 0
    for scenario in world.scenarios:
        window = scenario.spec.window
        instants = window.instants_in(scenario.spec.reference_timezone)
        leaves = readers.people.leaves_within(window)
        events = readers.calendar.events_within(instants)
        assert leaves == fakes.people.leaves_within(window)
        assert events == fakes.calendar.events_within(instants)
        seen_leaves += len(leaves)
        seen_events += len(events)
    assert seen_leaves > 0 and seen_events > 0


def test_every_planting_is_returned_whatever_the_day_it_became_observable(
    world: SealedWorld, readers: PlantedReaders
) -> None:
    """Time is applied above the port: the readers hold what the systems hold, and the fact
    view dates it. The world has plantings observable only after its earliest ``now``, and
    the readers return them to a run asked at that ``now``."""
    earliest = min(scenario.spec.now.date() for scenario in world.scenarios)
    late = [
        planted.entity
        for scenario in world.scenarios
        for planted in (*scenario.owned.leaves, *scenario.owned.work_items, *scenario.owned.events)
        if planted.observable_from > earliest
    ]
    assert late, "the fixture world must plant something after its earliest now"
    held = {
        observed.value
        for observed in (
            *readers.people.leaves_within(_whole_span(world)),
            *readers.work.work_items(),
            *readers.calendar.events_within(_whole_instants(world)),
        )
    }
    assert all(entity in held for entity in late)


def _whole_span(world: SealedWorld) -> DateSpan:
    spans = [scenario.spec.window for scenario in world.scenarios]
    return DateSpan(min(span.start for span in spans), max(span.end for span in spans))


def _whole_instants(world: SealedWorld) -> InstantSpan:
    return _whole_span(world).instants_in(world.scenarios[0].spec.reference_timezone)


def test_the_switch_makes_every_read_raise_with_the_source(world: SealedWorld) -> None:
    readers = planted_readers(world)
    scenario = world.scenarios[0]
    window = scenario.spec.window
    instants = window.instants_in(scenario.spec.reference_timezone)
    people, work, calendar = readers.people, readers.work, readers.calendar
    reads: list[tuple[PlantedPeople | PlantedWork | PlantedCalendar, Callable[[], object]]] = [
        (people, lambda: people.employee(EmployeeId("emp_001"))),
        (people, lambda: people.employees()),
        (people, lambda: people.team(TeamId("team_001"))),
        (people, lambda: people.leave(LeaveId(scenario.spec.leave_id))),
        (people, lambda: people.leaves_within(window)),
        (work, lambda: work.work_item(WorkItemId("ticket_001"))),
        (work, lambda: work.work_items()),
        (work, lambda: work.component(ComponentId("component_001"))),
        (work, lambda: work.components()),
        (calendar, lambda: calendar.event(EventId("event_001"))),
        (calendar, lambda: calendar.events_within(instants)),
    ]
    for port, read in reads:
        port.reachable = False
        with pytest.raises(SourceUnreachable) as raised:
            read()
        assert raised.value.source is port.source
        port.reachable = True
        read()


@dataclass(frozen=True)
class _Org:
    teams: tuple[Any, ...]
    employees: tuple[Any, ...]
    components: tuple[Any, ...]


@dataclass(frozen=True)
class _World:
    org: Any
    scenarios: tuple[Any, ...]


def test_a_duplicate_planting_refuses_at_construction_naming_the_kind_and_the_id(
    world: SealedWorld,
) -> None:
    org = world.org
    twice = _World(_Org(org.teams, (*org.employees, org.employees[0]), org.components), ())
    with pytest.raises(ValueError, match=f"employee '{org.employees[0].id}' twice"):
        planted_readers(twice)
    one_leave = world.scenarios[0].owned.leaves[0]
    doubled = replace(world.scenarios[0], owned=replace(world.scenarios[0].owned))
    with pytest.raises(ValueError, match=f"leave '{one_leave.entity.id}' twice"):
        planted_readers(_World(org, (doubled, doubled)))


def test_the_readers_from_the_sealed_truth_store_equal_the_ones_from_the_loaded_world(
    world: SealedWorld, readers: PlantedReaders
) -> None:
    sealed = bundle(composed_world("golden"))
    stores = sealed_stores(sealed)
    assert sealed_readers(stores.truth, sealed.world_version) == readers
    with pytest.raises(LookupError, match=world_spec_key(sealed.world_version)):
        sealed_readers(InMemoryObjectStore(), sealed.world_version)


def test_the_triple_survives_a_pickle(readers: PlantedReaders) -> None:
    copied: PlantedReaders = pickle.loads(pickle.dumps(readers))
    assert copied == readers
    assert copied.people.employees() == readers.people.employees()
