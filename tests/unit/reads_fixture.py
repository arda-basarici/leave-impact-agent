"""A run's reads, made through the in-memory ports and recorded as a trace's operations.

Test infrastructure. The evaluator replays what a run read, so its tests need reads: real
calls of the declared tools, with the arguments the tools accept, answered by systems that
hold a sealed world. ``systems_holding`` fills the four in-memory ports with every record a
sealed world plants, which is what the projector does to the real systems; a test that
wants the systems to have drifted since then changes a store directly. ``Recorder`` makes
a call the way the harness's tool wrapper will, through the specification's own validation
and the port method the specification names, and records the operation with its outcome:
a record, no record, a sequence, or the source unreachable when the port is switched off.
``full_read`` is the reads of a run that looked at everything a scenario can show it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from leaveimpact.core import (
    AbsentOutcome,
    Entity,
    Observed,
    Operation,
    OperationId,
    Outcome,
    PortFamily,
    PrefetchOrigin,
    RecordOutcome,
    RecordsOutcome,
    Source,
    SourceUnreachable,
    UnreachableOutcome,
    specification_named,
    validate_arguments,
)
from leaveimpact.core.timeshape import encode_date_span, encode_instant
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from leaveimpact.world.runtime_view import window_instants
from tests.unit.in_memory_ports import (
    InMemoryCalendar,
    InMemoryDocuments,
    InMemoryPeople,
    InMemoryWork,
)


@dataclass
class Systems:
    """The four systems a run reads, as in-memory ports."""

    people: InMemoryPeople = field(default_factory=InMemoryPeople)
    work: InMemoryWork = field(default_factory=InMemoryWork)
    calendar: InMemoryCalendar = field(default_factory=InMemoryCalendar)
    documents: InMemoryDocuments = field(default_factory=InMemoryDocuments)

    def port(self, family: PortFamily) -> object:
        """The port a tool of ``family`` reads."""
        return {
            PortFamily.PEOPLE: self.people,
            PortFamily.WORK: self.work,
            PortFamily.CALENDAR: self.calendar,
            PortFamily.DOCUMENT: self.documents,
        }[family]


def systems_holding(world: SealedWorld) -> Systems:
    """Systems that hold every record ``world`` plants: the organization and each scenario's
    leaves, work items, events and documents."""
    systems = Systems()
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
        for document in owned.documents:
            systems.documents.add_document(document.entity)
    return systems


@dataclass
class Recorder:
    """Calls of the declared tools against ``systems``, kept as operations in call order."""

    systems: Systems
    operations: list[Operation] = field(default_factory=list[Operation])

    def read(self, tool: str, arguments: Mapping[str, object] | None = None) -> Outcome:
        """Call ``tool`` with ``arguments`` as a model would spell them, and record it."""
        given = dict(arguments or {})
        specification = specification_named(tool)
        assert specification is not None, tool
        accepted = validate_arguments(specification, given)
        method = getattr(self.systems.port(specification.facts.family), specification.method.value)
        try:
            answer: object = method(**accepted)
        except SourceUnreachable as unreachable:
            outcome: Outcome = UnreachableOutcome(unreachable.source, unreachable.reason)
        else:
            if answer is None:
                outcome = AbsentOutcome()
            elif isinstance(answer, tuple):
                records = cast("tuple[Observed[Entity], ...]", answer)
                outcome = RecordsOutcome(tuple(_as_returned(record) for record in records))
            else:
                outcome = RecordOutcome(_as_returned(cast("Observed[Entity]", answer)))
        self.operations.append(
            Operation(
                OperationId(f"op-{len(self.operations) + 1}"),
                PrefetchOrigin(),
                tool,
                specification.facts.source,
                given,
                outcome,
            )
        )
        return outcome


def _as_returned(record: Observed[Entity]) -> Observed[Entity]:
    """``record`` typed as an operation's outcome holds it: any entity, from its source."""
    return Observed[Entity](record.value, record.source)




def full_read(reads: Recorder, world: SealedWorld, scenario: Scenario) -> None:
    """Every read a complete investigation of ``scenario`` makes, through ``reads``.

    The leave under investigation by its id; the organization, the components and the work
    items enumerated; the leaves and the events of the scenario's window, the events as
    the reference zone reads its days; and every document of the world by its id. The
    document ids are the fixture's knowledge, where a harness has a search: the corpus
    has no enumeration, which is the point the tests that use this make.
    """
    spec = scenario.spec
    instants = window_instants(spec.window, spec.reference_timezone)
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


__all__ = ["Recorder", "Systems", "full_read", "reads_of_everything", "systems_holding"]
