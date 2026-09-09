"""Typed references: what a claim is about, where it was read, and the values a conflict compares.

A reference pairs an entity kind with an id and checks at construction that the id
belongs to the kind's namespace, because a union of ``NewType`` ids (``WorkItemId |
ClauseId``) is two plain strings once the type checker leaves: JSON cannot tag it and
the evaluator cannot dispatch on it. The ``NewType`` ids keep their value where
entities are built — a rule that takes an employee and a leave still cannot swap them —
and ``EntityRef`` is the run-time and serialized form a claim uses to point at any
kind of thing; the typed constructors below (``work_item_ref`` and the rest) are the
bridge from one to the other, so the checker still sees which id kind went in
(DESIGN, "The vocabulary in code").

Two lists on every claim look alike and are not: an entity reference says what the
claim is *about*; an evidence reference says where it was *read* — a source, the
record read there, and the field. The evaluator re-verifies evidence against the
world, so an evidence reference is checked at construction to name a record its source
can hold (a clause is never read from the tracker; an employee's skills are read from
the HR record, not from the employee as a Jira assignee). A conflict's observations
carry typed values rather than text, because resolution compares them and the
evaluator re-verifies the resolved one; ``FactValue`` is the union the first golden
set's conflicts need, and the fact base owns and may extend it from the rules step on.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from leaveimpact.core.enums import EntityKind, Source
from leaveimpact.core.ids import (
    ClauseId,
    CommentId,
    ComponentId,
    DocumentId,
    EmployeeId,
    EventId,
    LeaveId,
    TeamId,
    WorkItemId,
    is_numbered_id,
)

PREFIX_BY_KIND: Mapping[EntityKind, str] = MappingProxyType(
    {
        EntityKind.EMPLOYEE: "emp",
        EntityKind.TEAM: "team",
        EntityKind.COMPONENT: "comp",
        EntityKind.WORK_ITEM: "ticket",
        EntityKind.COMMENT: "comment",
        EntityKind.EVENT: "event",
        EntityKind.DOCUMENT: "doc",
        EntityKind.CLAUSE: "clause",
        EntityKind.LEAVE: "leave",
    }
)
"""The id namespace of each entity kind — the prefixes ``ids`` mints, read as a table."""

TARGET_KINDS_BY_SOURCE: Mapping[Source, frozenset[EntityKind]] = MappingProxyType(
    {
        Source.FRAPPE: frozenset({EntityKind.EMPLOYEE, EntityKind.TEAM, EntityKind.LEAVE}),
        Source.JIRA: frozenset({EntityKind.COMPONENT, EntityKind.WORK_ITEM, EntityKind.COMMENT}),
        Source.CALENDAR: frozenset({EntityKind.EVENT}),
        Source.CORPUS: frozenset({EntityKind.DOCUMENT, EntityKind.CLAUSE}),
    }
)
"""Which kinds of record each source holds — the records an evidence reference can name there."""


def with_article(noun: str) -> str:
    """``noun`` with its indefinite article, for messages that name a kind or a member."""
    return f"an {noun}" if noun[0] in "aeiou" else f"a {noun}"


def require_id(kind: EntityKind, value: str) -> str:
    """``value`` if it is an id in ``kind``'s namespace; ``ValueError`` otherwise.

    >>> require_id(EntityKind.WORK_ITEM, "ticket_042")
    'ticket_042'
    >>> require_id(EntityKind.EMPLOYEE, "ticket_042")
    Traceback (most recent call last):
    ...
    ValueError: an employee id has the form emp_NNN, got 'ticket_042'
    """
    prefix = PREFIX_BY_KIND[kind]
    if not is_numbered_id(value) or value.rsplit("_", 1)[0] != prefix:
        raise ValueError(f"{with_article(kind.value)} id has the form {prefix}_NNN, got {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class EntityRef:
    """A kind and an id, validated together — the run-time form of "which thing".

    >>> EntityRef(EntityKind.CLAUSE, "clause_011")
    EntityRef(kind=<EntityKind.CLAUSE: 'clause'>, id='clause_011')
    >>> EntityRef(EntityKind.EVENT, "LIA-42")
    Traceback (most recent call last):
    ...
    ValueError: an event id has the form event_NNN, got 'LIA-42'
    """

    kind: EntityKind
    id: str

    def __post_init__(self) -> None:
        require_id(self.kind, self.id)


def employee_ref(id: EmployeeId) -> EntityRef:
    """The reference to an employee."""
    return EntityRef(EntityKind.EMPLOYEE, id)


def team_ref(id: TeamId) -> EntityRef:
    """The reference to a team."""
    return EntityRef(EntityKind.TEAM, id)


def component_ref(id: ComponentId) -> EntityRef:
    """The reference to a component."""
    return EntityRef(EntityKind.COMPONENT, id)


def work_item_ref(id: WorkItemId) -> EntityRef:
    """The reference to a work item."""
    return EntityRef(EntityKind.WORK_ITEM, id)


def comment_ref(id: CommentId) -> EntityRef:
    """The reference to a ticket comment — an evidence target, never a subject."""
    return EntityRef(EntityKind.COMMENT, id)


def event_ref(id: EventId) -> EntityRef:
    """The reference to a calendar event."""
    return EntityRef(EntityKind.EVENT, id)


def document_ref(id: DocumentId) -> EntityRef:
    """The reference to a document."""
    return EntityRef(EntityKind.DOCUMENT, id)


def clause_ref(id: ClauseId) -> EntityRef:
    """The reference to a document section — a clause a constraint cites, or a paragraph read."""
    return EntityRef(EntityKind.CLAUSE, id)


def leave_ref(id: LeaveId) -> EntityRef:
    """The reference to a leave."""
    return EntityRef(EntityKind.LEAVE, id)


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """Where a claim was read: a source, the record read there, and the field if one was.

    ``field`` names the observation's location in the record as the adapter exposes it
    (``skills``, ``owner_id``, ``text``); it is a locator for re-verification, not a
    vocabulary of the domain, which is why it stays a string. ``None`` means the record
    as a whole is the evidence — a comment, a clause.

    >>> EvidenceRef(Source.CORPUS, clause_ref(ClauseId("clause_011"))).field is None
    True
    >>> EvidenceRef(Source.JIRA, clause_ref(ClauseId("clause_011")))
    Traceback (most recent call last):
    ...
    ValueError: jira holds no clause record; it holds comment, component, work_item
    """

    source: Source
    target: EntityRef
    field: str | None = None

    def __post_init__(self) -> None:
        held = TARGET_KINDS_BY_SOURCE[self.source]
        if self.target.kind not in held:
            raise ValueError(
                f"{self.source.value} holds no {self.target.kind.value} record; it holds "
                f"{', '.join(sorted(kind.value for kind in held))}"
            )
        if self.field is not None and not self.field:
            raise ValueError("an evidence field is a name or None, never empty")


FactValue = EntityRef | str | date
"""What an observation can say about a subject: a thing, a text (an enum member serializes
as its value), or a day. The fact base extends this union when a predicate needs more."""


@dataclass(frozen=True, slots=True)
class Observation:
    """One source's value for a fact — what a conflict compares and the authority rule ranks."""

    source: Source
    value: FactValue
