"""The read side: four protocols, one per system, shaped by what the rules ask.

Each method is a question the domain has — which leave is under investigation, who
could cover, what the leaver owns, what meets during the absence, which clause
applies — phrased over domain ids and answered with observed entities. Vendor ids
never cross: the adapter keeps the identity map that translates a domain id to a
vendor key, in both directions. A record that is not there is ``None`` or an empty
tuple; a source that cannot answer raises ``SourceUnreachable`` (``errors``).

Time is applied above the port, not inside it. A reader returns what the system holds;
the fact view admits a fact from the day its provenance became observable, so a
comment dated after ``now`` is filtered where every other date is, once, rather than
in four adapters. The two exceptions are the queries that are time-shaped by nature —
leaves and events over a span — because the systems answer those by range and the
rules only ever ask them by range.

These are ``Protocol`` classes: an adapter conforms by shape and inherits nothing, and
its conformance is checked by a typed assignment in its tests, so the split between
reading and writing never reads as a class hierarchy.
"""

from __future__ import annotations

from typing import Protocol

from leaveimpact.core.entities import (
    CalendarEvent,
    Component,
    Document,
    Employee,
    Leave,
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
from leaveimpact.core.ports.observed import Observed
from leaveimpact.core.worldtime import DateSpan, InstantSpan


class PeopleReader(Protocol):
    """The HR system as the domain reads it: people, teams and leaves.

    The system of record for employment, location, skills and absence — the run's
    leave under investigation is read here from the id ``RunContext`` carries, and
    its span is established from the record, never told to the run.
    """

    def employee(self, id: EmployeeId) -> Observed[Employee] | None:
        """The employee record, or ``None`` if the system holds no such person."""
        ...

    def employees(self) -> tuple[Observed[Employee], ...]:
        """Every employee on record — the candidate universe a coverage plan is judged over.

        Whole, because the organization is small by construction and a rule that
        needs "everyone in the team" or "everyone in the component" filters the
        universe by a fact it derived, not by a query it trusts.
        """
        ...

    def team(self, id: TeamId) -> Observed[Team] | None:
        """The team record, or ``None``."""
        ...

    def leave(self, id: LeaveId) -> Observed[Leave] | None:
        """The leave record, or ``None`` — the run input resolved to its record."""
        ...

    def leaves_of(self, employee_id: EmployeeId, span: DateSpan) -> tuple[Observed[Leave], ...]:
        """Every leave of the employee that shares at least one day with ``span``.

        Any status: a requested leave is a fact about the record even though it is
        not yet an absence, and the rules decide what a status means.
        """
        ...


class WorkReader(Protocol):
    """The issue tracker as the domain reads it: work items with their comments, and components."""

    def work_item(self, id: WorkItemId) -> Observed[WorkItem] | None:
        """The work item with its comments, or ``None``."""
        ...

    def work_items_owned_by(self, owner_id: EmployeeId) -> tuple[Observed[WorkItem], ...]:
        """Every work item whose current owner is ``owner_id``, any status."""
        ...

    def work_items_in(self, component_id: ComponentId) -> tuple[Observed[WorkItem], ...]:
        """Every work item filed under the component, any status."""
        ...

    def component(self, id: ComponentId) -> Observed[Component] | None:
        """The component with its named members, or ``None``."""
        ...

    def components(self) -> tuple[Observed[Component], ...]:
        """Every component the tracker holds."""
        ...


class CalendarReader(Protocol):
    """The calendar as the domain reads it: meetings as half-open instant spans with attendees."""

    def event(self, id: EventId) -> Observed[CalendarEvent] | None:
        """The event record, or ``None``."""
        ...

    def events_within(self, span: InstantSpan) -> tuple[Observed[CalendarEvent], ...]:
        """Every event that overlaps ``span`` — the meetings an absence or a window touches.

        Whoever attends: attendance is a fact derived from the record, so "Alice's
        meetings" is a filter over this answer, not a second query.
        """
        ...


class DocumentReader(Protocol):
    """The corpus as the domain reads it: documents in sections, found by id or by search.

    Returns text and derives nothing; which clause applies is the investigator's to
    establish and cite, and what a clause requires enters the fact base from the
    world's structured brief.
    """

    def document(self, id: DocumentId) -> Observed[Document] | None:
        """The document with its sections, or ``None``."""
        ...

    def search(self, query: str, *, limit: int) -> tuple[Observed[Document], ...]:
        """At most ``limit`` documents relevant to ``query``, most relevant first.

        Over the whole corpus, effective dates included: the caller keeps the ones
        effective at ``now``. Relevance is the adapter's — full text today; what the
        investigator's retrieval needs is its milestone's question.
        """
        ...
