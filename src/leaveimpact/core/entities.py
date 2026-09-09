"""The domain entities: what the systems believe about people, work, meetings, documents, leaves.

Every record is a frozen, slotted dataclass built by code the project controls — the
world generator or an adapter translating a vendor's shape — and trusted by
construction; raw external data is validated into these at the adapters, never here
(the SteamLens contracts precedent). A record carries exactly the fields the generator
controls and the investigator may see (DESIGN, "Time is world state"): a vendor's own
timestamps and ids stay out, because they are vendor operational time and the world
manifest's business respectively. Collections are tuples, so a record hashes and never
changes under a reader.

Two relationships look alike and are not: an employee's ``team_id`` is organizational
membership, a component's ``member_ids`` is work-domain association, and a scenario can
make the two disagree ("same team" against "relevant component"). Two absences look
alike and are not: ``skills`` is ``None`` when the world has no skills record for the
person — the missing-information case, which grades as unknown — and an empty tuple
when the record exists and lists nothing, which grades as non-viable (DESIGN, the
closed-world rule in "The answer-key contract"). ``None`` means absent in the world;
an adapter that could not read a field raises, and that failure is a run condition,
never a ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from leaveimpact.core.enums import (
    DocumentKind,
    EmploymentType,
    Grade,
    LeaveKind,
    LeaveStatus,
    WorkItemStatus,
)
from leaveimpact.core.ids import (
    ClauseId,
    CommentId,
    ComponentId,
    DocumentId,
    EmployeeId,
    EventId,
    LeaveId,
    SkillId,
    TeamId,
    WorkItemId,
)
from leaveimpact.core.worldtime import DateSpan, InstantSpan


@dataclass(frozen=True, slots=True)
class Employee:
    """A person in the organization, as the HR system records them.

    ``location`` is the office city, ``country`` its ISO 3166 alpha-2 code and
    ``timezone`` the IANA zone the person's working day is read in; the three are
    separate facts and none is derived from another, so a planted disagreement between
    the HR record and a calendar stays visible. ``manager_id`` is ``None`` only at the
    top of the organization. ``grade`` and ``employment_type`` exist because policy
    clauses scope by them.
    """

    id: EmployeeId
    name: str
    team_id: TeamId
    manager_id: EmployeeId | None
    skills: tuple[SkillId, ...] | None
    location: str
    country: str
    timezone: str
    grade: Grade
    employment_type: EmploymentType


@dataclass(frozen=True, slots=True)
class Team:
    """An organizational unit; membership lives on the employee, so a team is a name."""

    id: TeamId
    name: str


@dataclass(frozen=True, slots=True)
class Component:
    """A work-domain grouping in the tracker with its named members — a qualification fact.

    Component membership is the structured half of "has experience with": a coverage
    clause may require it, and it deliberately does not follow team membership.
    """

    id: ComponentId
    name: str
    member_ids: tuple[EmployeeId, ...]


@dataclass(frozen=True, slots=True)
class Comment:
    """A dated remark on a work item; its text and world date are facts, its author too.

    A comment carries its own id because an answer-changing fact may live only here (a
    qualification mentioned in passing, a blockage the status does not show) and an
    evidence reference needs a stable target that does not depend on list order.
    ``world_date`` and ``author_id`` physically live in a fixed bracketed prefix of the
    text (``[2026-09-12, emp_023 — Bob Kaya] …``), because the tracker's own author is
    the service account and its timestamp is vendor time; the adapter reads the prefix
    the way it reads a custom field and ``text`` keeps the comment whole, prefix
    included (DESIGN, "History is planted only where it can be planted honestly").
    """

    id: CommentId
    world_date: date
    author_id: EmployeeId
    text: str


@dataclass(frozen=True, slots=True)
class WorkItem:
    """A ticket: who owns it, where it stands, when it opened, resolved and is due.

    The dates are world facts the generator sets through custom fields, day-level
    because a deadline is a calendar-day fact; the tracker's own timestamps are vendor
    time and absent. ``resolved_on`` is ``None`` while the item is open and ``due_on``
    ``None`` when nothing is due. Every item has an owner: the world plants none
    unassigned, so an optional owner would be optionality for the vendor's sake.
    """

    id: WorkItemId
    title: str
    owner_id: EmployeeId
    status: WorkItemStatus
    component_id: ComponentId
    opened_on: date
    resolved_on: date | None
    due_on: date | None
    comments: tuple[Comment, ...]


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    """A meeting: an aware, half-open instant span and who attends.

    Instants, not dates, because a timezone-boundary distractor turns on a clock time;
    the organizer is not a world fact (every write comes from one service account).
    """

    id: EventId
    title: str
    start: datetime
    end: datetime
    attendee_ids: tuple[EmployeeId, ...]

    def __post_init__(self) -> None:
        # A naive or reversed pair is a construction bug, so it fails here, not at first read.
        InstantSpan(self.start, self.end)

    @property
    def span(self) -> InstantSpan:
        """The event's time as a half-open span, ``[start, end)``."""
        return InstantSpan(self.start, self.end)


@dataclass(frozen=True, slots=True)
class DocumentSection:
    """One clause of a document — the unit an evidence reference or a constraint cites.

    A section has its own id because a constraint is cited from its clause, not from a
    whole document, and because the materializer's containment gate checks a clause's
    text against a clause's brief.
    """

    id: ClauseId
    text: str


@dataclass(frozen=True, slots=True)
class Document:
    """A corpus document: a runbook, a client note, a procedure or a policy, in sections.

    ``effective_from`` is the world date the document became observable, which is what
    time-filtering by ``now`` reads. A runbook or a client note usually has one section;
    a policy has one per clause.
    """

    id: DocumentId
    title: str
    kind: DocumentKind
    effective_from: date
    sections: tuple[DocumentSection, ...]


@dataclass(frozen=True, slots=True)
class Leave:
    """An absence as the HR system records it: inclusive calendar days, kind and status.

    ``start`` and ``end`` are both absent days, the way HR reads "10 to 12 September";
    ``span`` states that convention once. A ``requested`` leave is not yet an absence.
    """

    id: LeaveId
    employee_id: EmployeeId
    start: date
    end: date
    kind: LeaveKind
    status: LeaveStatus

    def __post_init__(self) -> None:
        # A reversed pair is a construction bug, so it fails here, not at first read.
        DateSpan(self.start, self.end)

    @property
    def span(self) -> DateSpan:
        """The absent days, inclusive at both ends."""
        return DateSpan(self.start, self.end)
