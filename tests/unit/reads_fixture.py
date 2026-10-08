"""A run's reads, made through the ports over a sealed world and recorded as a trace's operations.

Test infrastructure. The evaluator replays what a run read, so its tests need reads: real
calls of the declared tools, with the arguments the tools accept, answered by systems that
hold a sealed world. ``systems_holding`` is the three planted readers over the world (the
adapters' own, what a development run reads) beside the in-memory documents port filled
with every document the scenarios plant, since the readers have no document side and the
tests need a search; ``fakes_holding`` fills the four in-memory ports the same way, for a
test that wants a system to have drifted from the world since it was sealed and changes a
store directly, which a reader over sealed plantings cannot be made to do (the generator
step's ruling 7: the fakes retire where a test reads a sealed world and stay where a test
needs a controlled fault). Both expose the ports and the outage switch. ``Recorder`` makes
a call through the harness's own executor, the one path every system's reads take:
the specification's validation, the port method the specification names, the operation
recorded with its outcome. One liberty is the fixture's: the executor stops a source at
its first unreachable answer and refuses a further call against it, while the evaluator
must grade traces no conforming harness makes, a full read under an outage among them,
so the recorder clears the stop state before each read and asks whatever the test asks.
``full_read`` is the reads of a run that looked at everything a scenario can show it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from leaveimpact.adapters.plantings import (
    PlantedCalendar,
    PlantedPeople,
    PlantedWork,
    planted_readers,
)
from leaveimpact.agent.execution import Executor, ReadPorts
from leaveimpact.core import Operation, Outcome, PortFamily, PrefetchOrigin, Source
from leaveimpact.core.timeshape import encode_date_span, encode_instant
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.in_memory_ports import (
    InMemoryCalendar,
    InMemoryDocuments,
    InMemoryPeople,
    InMemoryWork,
)


class HoldsPorts(Protocol):
    """What the recorder reads through: the four ports as the executor takes them."""

    @property
    def ports(self) -> ReadPorts: ...


@dataclass
class Systems:
    """The four systems a run reads: the three planted readers and the in-memory documents."""

    people: PlantedPeople
    work: PlantedWork
    calendar: PlantedCalendar
    documents: InMemoryDocuments

    def port(self, family: PortFamily) -> object:
        """The port a tool of ``family`` reads."""
        return self.ports.port(family)

    @property
    def ports(self) -> ReadPorts:
        """The four as the executor takes them."""
        return ReadPorts(self.people, self.work, self.calendar, self.documents)


@dataclass
class FakeSystems:
    """The four systems a run reads, as in-memory ports a test may drift."""

    people: InMemoryPeople = field(default_factory=InMemoryPeople)
    work: InMemoryWork = field(default_factory=InMemoryWork)
    calendar: InMemoryCalendar = field(default_factory=InMemoryCalendar)
    documents: InMemoryDocuments = field(default_factory=InMemoryDocuments)

    def port(self, family: PortFamily) -> object:
        """The port a tool of ``family`` reads."""
        return self.ports.port(family)

    @property
    def ports(self) -> ReadPorts:
        """The four as the executor takes them."""
        return ReadPorts(self.people, self.work, self.calendar, self.documents)


def systems_holding(world: SealedWorld) -> Systems:
    """The planted readers over ``world`` and a documents port holding every document its
    scenarios plant."""
    readers = planted_readers(world)
    return Systems(readers.people, readers.work, readers.calendar, _documents_of(world))


def fakes_holding(world: SealedWorld) -> FakeSystems:
    """Fakes that hold every record ``world`` plants: the organization and each scenario's
    leaves, work items, events and documents; for a test that drifts a store afterwards."""
    systems = FakeSystems(documents=_documents_of(world))
    for team in world.org.teams:
        systems.people.add_team(team)
    for employee in world.org.employees:
        systems.people.add_employee(employee)
    for component in world.org.components:
        systems.work.add_component(component)
    for scenario in world.scenarios:
        owned = scenario.owned
        for leave in owned.leaves:
            systems.people.add_leave(leave.entity)
        for item in owned.work_items:
            systems.work.add_work_item(item.entity)
        for event in owned.events:
            systems.calendar.add_event(event.entity)
    return systems


def _documents_of(world: SealedWorld) -> InMemoryDocuments:
    documents = InMemoryDocuments()
    for scenario in world.scenarios:
        for document in scenario.owned.documents:
            documents.add_document(document.entity)
    return documents


@dataclass
class Recorder:
    """Calls of the declared tools against ``systems`` through the executor, kept as operations
    in call order."""

    systems: HoldsPorts
    executor: Executor = field(init=False)

    def __post_init__(self) -> None:
        self.executor = Executor(self.systems.ports)

    @property
    def operations(self) -> list[Operation]:
        """Every call made, in the order made."""
        return self.executor.operations

    def read(self, tool: str, arguments: Mapping[str, object] | None = None) -> Outcome:
        """Call ``tool`` with ``arguments`` as a model would spell them, and record it; a source
        that has stopped is asked all the same (the module docstring says why)."""
        self.executor.stopped.clear()
        return self.executor.call(PrefetchOrigin(), tool, dict(arguments or {}))


def full_read(reads: Recorder, world: SealedWorld, scenario: Scenario) -> None:
    """Every read a complete investigation of ``scenario`` makes, through ``reads``.

    The leave under investigation by its id; the organization, the components and the work
    items enumerated; the leaves and the events of the scenario's window, the events as
    the reference zone reads its days; and every document of the world by its id. The
    document ids are the fixture's knowledge, where a harness has a search: the corpus
    has no enumeration, which is the point the tests that use this make.
    """
    spec = scenario.spec
    instants = spec.window.instants_in(spec.reference_timezone)
    reads.read("leave", {"id": spec.leave_id})
    reads.read("employees")
    reads.read("components")
    reads.read("work_items")
    reads.read("leaves_within", {"span": encode_date_span(spec.window)})
    reads.read(
        "events_within",
        {"span": {"start": encode_instant(instants.start), "end": encode_instant(instants.end)}},
    )
    for owner in world.scenarios:
        for planted in owner.owned.documents:
            reads.read("document", {"id": planted.entity.id})


def reads_of_everything(
    world: SealedWorld, scenario: Scenario, *down: Source
) -> list[Operation]:
    """The operations of a run of ``scenario`` that read everything, with the sources in
    ``down`` unreachable for the whole run."""
    systems = systems_holding(world)
    for port in (systems.people, systems.work, systems.calendar, systems.documents):
        port.reachable = port.source not in down
    reads = Recorder(systems)
    full_read(reads, world, scenario)
    return reads.operations


__all__ = [
    "FakeSystems",
    "HoldsPorts",
    "Recorder",
    "Systems",
    "fakes_holding",
    "full_read",
    "reads_of_everything",
    "systems_holding",
]
