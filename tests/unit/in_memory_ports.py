"""In-memory implementations of the four ports, both sides, for tests above the seam.

Test infrastructure, not an adapter: a projector or an investigator under test is
handed one of these where production hands it a Frappe or a Jira adapter, so the
code above the ports is exercised against the ports' contract and never against a
sandbox. Kept under ``tests`` on purpose — an ``adapters/memory`` package would say
that memory is an external system.

Each store is a mapping from domain id to record; ``add_*`` refuses a duplicate id,
because find-or-create is the projector's and a second add for the same id is a
projector bug the fake should expose, not absorb. The calendar is the one exception,
as in production: its insert is the ensure, so an equal event is verified and a
different one under the same id is ``IdentityConflict``. ``reachable`` turned off makes
every read and write raise ``SourceUnreachable``, the way an adapter does after its
retries, so a harness's handling of a dead source is testable without a network.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from leaveimpact.core import (
    CalendarEvent,
    Component,
    DateSpan,
    Document,
    Employee,
    Entity,
    IdentityConflict,
    InstantSpan,
    Leave,
    Observed,
    Source,
    SourceUnreachable,
    Team,
    WorkItem,
)
from leaveimpact.core.ids import (
    ComponentId,
    DocumentId,
    EmployeeId,
    EventId,
    LeaveId,
    TeamId,
    WorkItemId,
)


@dataclass
class _Store:
    """What every fake shares: a source, a reachability switch, and the two guards."""

    source: Source
    reachable: bool = True

    def _reach(self) -> None:
        if not self.reachable:
            raise SourceUnreachable(self.source, "switched off in the test")

    def _observe[T: Entity](self, value: T) -> Observed[T]:
        return Observed(value, self.source)

    def _add[K, V](self, store: dict[K, V], key: K, value: V, what: str) -> str:
        self._reach()
        if key in store:
            raise ValueError(f"{what} {key!r} already exists in the {self.source.value} fake")
        store[key] = value
        return f"{self.source.value}-fake:{what}:{key}"

    def _one[K, V: Entity](self, store: Mapping[K, V], key: K) -> Observed[V] | None:
        self._reach()
        found = store.get(key)
        return None if found is None else self._observe(found)

    def _all[K, V: Entity](
        self, store: Mapping[K, V], keep: Callable[[V], bool] = lambda _: True
    ) -> tuple[Observed[V], ...]:
        self._reach()
        return tuple(self._observe(value) for value in store.values() if keep(value))


@dataclass
class InMemoryPeople(_Store):
    """``PeopleReader`` and ``PeopleWriter`` over dictionaries."""

    source: Source = Source.FRAPPE
    teams: dict[TeamId, Team] = field(default_factory=dict[TeamId, Team])
    people: dict[EmployeeId, Employee] = field(default_factory=dict[EmployeeId, Employee])
    leaves: dict[LeaveId, Leave] = field(default_factory=dict[LeaveId, Leave])

    def employee(self, id: EmployeeId) -> Observed[Employee] | None:
        return self._one(self.people, id)

    def employees(self) -> tuple[Observed[Employee], ...]:
        return self._all(self.people)

    def team(self, id: TeamId) -> Observed[Team] | None:
        return self._one(self.teams, id)

    def leave(self, id: LeaveId) -> Observed[Leave] | None:
        return self._one(self.leaves, id)

    def leaves_within(self, span: DateSpan) -> tuple[Observed[Leave], ...]:
        return self._all(self.leaves, lambda leave: leave.span.overlaps(span))

    def add_team(self, team: Team) -> str:
        return self._add(self.teams, team.id, team, "team")

    def add_employee(self, employee: Employee) -> str:
        return self._add(self.people, employee.id, employee, "employee")

    def add_leave(self, leave: Leave) -> str:
        return self._add(self.leaves, leave.id, leave, "leave")


@dataclass
class InMemoryWork(_Store):
    """``WorkReader`` and ``WorkWriter`` over dictionaries."""

    source: Source = Source.JIRA
    components_by_id: dict[ComponentId, Component] = field(
        default_factory=dict[ComponentId, Component]
    )
    tickets: dict[WorkItemId, WorkItem] = field(default_factory=dict[WorkItemId, WorkItem])

    def work_item(self, id: WorkItemId) -> Observed[WorkItem] | None:
        return self._one(self.tickets, id)

    def work_items(self) -> tuple[Observed[WorkItem], ...]:
        return self._all(self.tickets)

    def component(self, id: ComponentId) -> Observed[Component] | None:
        return self._one(self.components_by_id, id)

    def components(self) -> tuple[Observed[Component], ...]:
        return self._all(self.components_by_id)

    def add_component(self, component: Component) -> str:
        return self._add(self.components_by_id, component.id, component, "component")

    def add_work_item(self, work_item: WorkItem) -> str:
        return self._add(self.tickets, work_item.id, work_item, "work_item")


@dataclass
class InMemoryCalendar(_Store):
    """``CalendarReader`` and ``CalendarWriter`` over a dictionary."""

    source: Source = Source.CALENDAR
    events: dict[EventId, CalendarEvent] = field(default_factory=dict[EventId, CalendarEvent])

    def event(self, id: EventId) -> Observed[CalendarEvent] | None:
        return self._one(self.events, id)

    def events_within(self, span: InstantSpan) -> tuple[Observed[CalendarEvent], ...]:
        return self._all(self.events, lambda event: event.span.overlaps(span))

    def add_event(self, event: CalendarEvent) -> str:
        self._reach()
        existing = self.events.get(event.id)
        if existing is None:
            self.events[event.id] = event
        elif existing != event:
            raise IdentityConflict(
                self.source,
                f"event:{event.id}",
                f"an existing event differs: {existing} is not {event}",
            )
        return f"{self.source.value}-fake:event:{event.id}"


@dataclass
class InMemoryDocuments(_Store):
    """``DocumentReader`` and ``DocumentWriter`` over a dictionary; search is substring match.

    Relevance is the count of sections containing the query, case-insensitive — enough
    for a test to see ordering, and no claim about what the corpus adapter's full-text
    search returns.
    """

    source: Source = Source.CORPUS
    documents: dict[DocumentId, Document] = field(default_factory=dict[DocumentId, Document])

    def document(self, id: DocumentId) -> Observed[Document] | None:
        return self._one(self.documents, id)

    def search(self, query: str, *, limit: int) -> tuple[Observed[Document], ...]:
        self._reach()
        needle = query.casefold()

        def hits(document: Document) -> int:
            return sum(needle in section.text.casefold() for section in document.sections)

        ranked = sorted(
            (document for document in self.documents.values() if hits(document)),
            key=lambda document: (-hits(document), document.id),
        )
        return tuple(self._observe(document) for document in ranked[:limit])

    def add_document(self, document: Document) -> str:
        return self._add(self.documents, document.id, document, "document")

    def held_document_ids(self) -> frozenset[DocumentId]:
        """The inspection outside the port, as the corpus adapter offers it to a validator."""
        self._reach()
        return frozenset(self.documents)
