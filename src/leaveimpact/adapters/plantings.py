"""The sealed world's plantings read as the three vendor systems: people, work and calendar.

A development world is never projected (the generator step's ruling 7): its structured
records are read from the world spec's plantings through the same three read ports the
Frappe, Jira and calendar adapters implement, so a run over it goes through the one
executor path every read takes, and only the documents, which the corpus cache serves,
come from elsewhere. The readers conform to ``PeopleReader``, ``WorkReader`` and
``CalendarReader`` by shape, and the contract they keep is the fakes' that they replace in
the tests: a source, a reachability switch, enumeration to completion, and observations
dated by the caller.

Every record a planting holds is returned whatever its ``observable_from``: time is
applied above the port (``core/ports/read``), where the fact view admits a fact from the
day its provenance became observable, and the projected vendors hold every record from
the first day too. Enumeration order is the plantings' own, the organization's and then
the plan's, the order the projector writes and the fakes were filled in. The stores are
typed as read-only mappings: a reader holds what the world planted, and a test that
needs a system to have drifted from the world uses a fake, never a reader. ``reachable``
turned off makes every read raise ``SourceUnreachable``, the way an adapter does after
its retries: it is the outage condition a development run is graded under and the one
a test flips, which is why the switch is on the class and not on a wrapper for tests.
A duplicate id among the plantings is refused at construction, naming the kind and the
id, because the readers are built over a decoded file and not a vendor's answer, so the
fault is the input's and loud before any read; the port's ``MalformedRecord`` never has a
case here.

``planted_readers`` builds the three over anything that carries an organization and
scenarios whose rows hold their owned entities, a shape the decoded world spec and the
evaluator's loaded world both have, so neither is imported here; ``sealed_readers`` reads
the world spec from the truth store and builds the same. The world spec lives in the
truth bucket, so a reader built from a store holds the truth store's reader: a
development world is read by the benchmark's own principals and never by the deployed
application, which reads the vendors.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from leaveimpact.adapters.object_store.layout import world_spec_key
from leaveimpact.adapters.object_store.read import ObjectReader
from leaveimpact.core.entities import CalendarEvent, Component, Employee, Leave, Team, WorkItem
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import (
    ComponentId,
    EmployeeId,
    EventId,
    LeaveId,
    TeamId,
    WorkItemId,
    WorldVersion,
)
from leaveimpact.core.ports.errors import SourceUnreachable
from leaveimpact.core.ports.observed import Entity, Observed
from leaveimpact.core.worldtime import DateSpan, InstantSpan
from leaveimpact.world.decoders import decode_world_spec
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.scenario import OwnedEntities, Planted

__all__ = [
    "HoldsPlantings",
    "PlantedCalendar",
    "PlantedPeople",
    "PlantedReaders",
    "PlantedWork",
    "planted_readers",
    "sealed_readers",
]


class _Owning(Protocol):
    @property
    def owned(self) -> OwnedEntities: ...


class HoldsPlantings(Protocol):
    """What the readers are built from: the organization and a row per scenario with what it
    owns. The decoded world spec and the evaluator's loaded world are both one."""

    @property
    def org(self) -> OrgSpec: ...

    @property
    def scenarios(self) -> Sequence[_Owning]: ...


@dataclass
class _PlantedStore:
    """What the three readers share: a source and the reachability switch."""

    source: Source
    reachable: bool = True

    def _reach(self) -> None:
        if not self.reachable:
            raise SourceUnreachable(self.source, "switched off for this run")

    def _one[K, V: Entity](self, held: Mapping[K, V], key: K) -> Observed[V] | None:
        self._reach()
        found = held.get(key)
        return None if found is None else Observed(found, self.source)

    def _all[K, V: Entity](self, held: Mapping[K, V]) -> tuple[Observed[V], ...]:
        self._reach()
        return tuple(Observed(value, self.source) for value in held.values())


@dataclass
class PlantedPeople(_PlantedStore):
    """``PeopleReader`` over the planted teams, employees and leaves."""

    source: Source = Source.FRAPPE
    teams: Mapping[TeamId, Team] = field(default_factory=dict[TeamId, Team])
    people: Mapping[EmployeeId, Employee] = field(default_factory=dict[EmployeeId, Employee])
    leaves: Mapping[LeaveId, Leave] = field(default_factory=dict[LeaveId, Leave])

    def employee(self, id: EmployeeId) -> Observed[Employee] | None:
        return self._one(self.people, id)

    def employees(self) -> tuple[Observed[Employee], ...]:
        return self._all(self.people)

    def team(self, id: TeamId) -> Observed[Team] | None:
        return self._one(self.teams, id)

    def leave(self, id: LeaveId) -> Observed[Leave] | None:
        return self._one(self.leaves, id)

    def leaves_within(self, span: DateSpan) -> tuple[Observed[Leave], ...]:
        return tuple(
            observed for observed in self._all(self.leaves) if observed.value.span.overlaps(span)
        )


@dataclass
class PlantedWork(_PlantedStore):
    """``WorkReader`` over the planted components and work items."""

    source: Source = Source.JIRA
    components_by_id: Mapping[ComponentId, Component] = field(
        default_factory=dict[ComponentId, Component]
    )
    tickets: Mapping[WorkItemId, WorkItem] = field(default_factory=dict[WorkItemId, WorkItem])

    def work_item(self, id: WorkItemId) -> Observed[WorkItem] | None:
        return self._one(self.tickets, id)

    def work_items(self) -> tuple[Observed[WorkItem], ...]:
        return self._all(self.tickets)

    def component(self, id: ComponentId) -> Observed[Component] | None:
        return self._one(self.components_by_id, id)

    def components(self) -> tuple[Observed[Component], ...]:
        return self._all(self.components_by_id)


@dataclass
class PlantedCalendar(_PlantedStore):
    """``CalendarReader`` over the planted events."""

    source: Source = Source.CALENDAR
    events: Mapping[EventId, CalendarEvent] = field(default_factory=dict[EventId, CalendarEvent])

    def event(self, id: EventId) -> Observed[CalendarEvent] | None:
        return self._one(self.events, id)

    def events_within(self, span: InstantSpan) -> tuple[Observed[CalendarEvent], ...]:
        return tuple(
            observed for observed in self._all(self.events) if observed.value.span.overlaps(span)
        )


@dataclass(frozen=True, slots=True)
class PlantedReaders:
    """The three systems of one sealed world, as a run reads them."""

    people: PlantedPeople
    work: PlantedWork
    calendar: PlantedCalendar


def planted_readers(world: HoldsPlantings) -> PlantedReaders:
    """The three readers over ``world``'s plantings, every record held once; a duplicate id
    among the plantings is ``ValueError`` naming the kind and the id."""
    org = world.org
    owned = [scenario.owned for scenario in world.scenarios]
    people = PlantedPeople(
        teams=_by_id("team", org.teams, lambda team: team.id),
        people=_by_id("employee", org.employees, lambda employee: employee.id),
        leaves=_by_id("leave", _planted(row.leaves for row in owned), lambda leave: leave.id),
    )
    work = PlantedWork(
        components_by_id=_by_id("component", org.components, lambda component: component.id),
        tickets=_by_id(
            "work_item", _planted(row.work_items for row in owned), lambda item: item.id
        ),
    )
    calendar = PlantedCalendar(
        events=_by_id("event", _planted(row.events for row in owned), lambda event: event.id)
    )
    return PlantedReaders(people, work, calendar)


def sealed_readers(truth: ObjectReader, version: WorldVersion) -> PlantedReaders:
    """The three readers over the world spec sealed as ``version`` in ``truth``.

    Raises ``LookupError`` when the store holds no world spec for the version; a spec that
    does not decode raises the decoder's own ``ValueError``.
    """
    key = world_spec_key(version)
    stored = truth.get(key)
    if stored is None:
        raise LookupError(f"no sealed world spec at {key!r}: nothing to read")
    return planted_readers(decode_world_spec(stored.content))


def _planted[T: Entity](rows: Iterable[tuple[Planted[T], ...]]) -> list[T]:
    return [planted.entity for row in rows for planted in row]


def _by_id[K: str, V: Entity](
    kind: str, entities: Iterable[V], key_of: Callable[[V], K]
) -> dict[K, V]:
    held: dict[K, V] = {}
    for entity in entities:
        key = key_of(entity)
        if key in held:
            raise ValueError(f"the plantings hold {kind} {key!r} twice")
        held[key] = entity
    return held
