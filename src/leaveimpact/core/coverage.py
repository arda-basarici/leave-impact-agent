"""Coverage: which part of a source a question needs observed before no fact means false.

Closure infers a negative from a domain fully observed (the closure module). For the
truth a world plants, fully observed is a property of a source: it is reachable or it is
not. For a run it is a property of what the run read: a source can answer every call
and the one record that would have settled the question never be asked for. An unread
record is not a negative (the investigator milestone's fourth build step, ruling 2), so
the unit a view is asked about is finer than a source.

A *slice* is where part of an answer lives: one record, every record of a kind, or the
records of a kind inside a window. Each kind of record is held by exactly one source, so
a slice names no source and has one. A view answers, for a slice, one of four statuses:
*covered*, the slice was observed whole; *failed*, its source could not be read;
*unread*, nothing stopped the read and it was not made; *unclosable*, no read of the
tool surface observes that slice whole, as with the corpus, which has a search and no
enumeration.

Where a fact lives is derivation read backwards, and the placement table states it once
per predicate and per source of the predicate's evidence domain. A team, a location or
an employment type sits on the subject's own record. Membership of a component sits on
the component's record, never on the employee's. A skill sits on the HR record, in a
comment of any work item, or in a section of any document. An absence sits on a leave
record, which the HR system finds by dates. ``closing_slices`` turns a question about one
subject into the slices that close its negative and ``closing_slices_of_any`` does it
for a subject-free question, which is the one a window narrows: who is on leave over
these days, which events fall in this span.

A negative needs every one of its slices covered, with one declared exception. Evidence
in the corpus's prose can never be enumerated, so a negative that had to wait for it
would be unreachable for every system and compare nothing; the placement marks those
slices *waivable*, and a negative may stand with one unclosable, as long as the result
says so (ruling 2: one judgment is stored, the operational one, beside the sources left
unclosed). A waivable slice that failed still blocks: a corpus that could not be read is
an outage, not a limit of the tool surface. Nothing else is waivable; an unscoped
question over leaves or events is unclosable and stays open.

``SourceCoverage`` is the coverage of a base that holds everything its reachable sources
hold: a slice is covered when its source is reachable and failed when it is not. That is
the truth a world plants, and a harness that read every source to completion.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from leaveimpact.core.enums import EntityKind, Source
from leaveimpact.core.predicates import Predicate, PredicateName
from leaveimpact.core.refs import SOURCE_BY_TARGET_KIND, EntityRef, with_article
from leaveimpact.core.values import FactValue
from leaveimpact.core.worldtime import DateSpan, InstantSpan

Scope = DateSpan | InstantSpan
"""The window a subject-free question is asked over: days for leaves, instants for events."""

WINDOWED_KINDS: Mapping[EntityKind, type[DateSpan] | type[InstantSpan]] = MappingProxyType(
    {EntityKind.LEAVE: DateSpan, EntityKind.EVENT: InstantSpan}
)
"""The kinds a read narrows by a window, and the window's shape: the two range queries of
the read ports."""

_SHAPE_NAMES: Mapping[type, str] = MappingProxyType(
    {DateSpan: "a DateSpan", InstantSpan: "an InstantSpan"}
)


# --- Slices ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RecordSlice:
    """One record: the employee's HR record, a component, a ticket, an event, a clause."""

    record: EntityRef

    @property
    def source(self) -> Source:
        """The one source that holds this kind of record."""
        return SOURCE_BY_TARGET_KIND[self.record.kind]


@dataclass(frozen=True, slots=True)
class KindSlice:
    """Every record of a kind its source holds: all work items, all documents."""

    kind: EntityKind

    @property
    def source(self) -> Source:
        """The one source that holds this kind of record."""
        return SOURCE_BY_TARGET_KIND[self.kind]


@dataclass(frozen=True, slots=True)
class WindowSlice:
    """The records of a kind inside a window: the leaves over these days, the events in this
    span.

    >>> from datetime import date
    >>> WindowSlice(EntityKind.WORK_ITEM, DateSpan(date(2026, 9, 15), date(2026, 9, 19)))
    Traceback (most recent call last):
    ...
    ValueError: no read narrows a work_item by a window; a window is over a leave or an event
    >>> WindowSlice(EntityKind.EVENT, DateSpan(date(2026, 9, 15), date(2026, 9, 19)))
    Traceback (most recent call last):
    ...
    ValueError: a window over an event is an InstantSpan, got a DateSpan
    """

    kind: EntityKind
    span: Scope

    def __post_init__(self) -> None:
        shape = WINDOWED_KINDS.get(self.kind)
        if shape is None:
            raise ValueError(
                f"no read narrows a {self.kind.value} by a window; a window is over a leave "
                "or an event"
            )
        if not isinstance(self.span, shape):
            raise ValueError(
                f"a window over {with_article(self.kind.value)} is {_SHAPE_NAMES[shape]}, got "
                f"{_SHAPE_NAMES[type(self.span)]}"
            )

    @property
    def source(self) -> Source:
        """The one source that holds this kind of record."""
        return SOURCE_BY_TARGET_KIND[self.kind]


Slice = RecordSlice | KindSlice | WindowSlice
"""Where part of an answer lives."""


# --- What a view answers -----------------------------------------------------------------


class SliceStatus(StrEnum):
    """What a view knows about a slice, the four cases the module docstring separates."""

    COVERED = "covered"
    UNCLOSABLE = "unclosable"
    UNREAD = "unread"
    FAILED = "failed"


class Coverage(Protocol):
    """What was observed, asked slice by slice."""

    def status(self, where: Slice) -> SliceStatus:
        """Whether ``where`` was observed whole, and why not when it was not."""
        ...


@dataclass(frozen=True, slots=True)
class SourceCoverage:
    """The coverage of a base that holds everything its reachable sources hold.

    >>> everything_but_the_tracker = SourceCoverage(frozenset(Source) - {Source.JIRA})
    >>> everything_but_the_tracker.status(KindSlice(EntityKind.WORK_ITEM)).value
    'failed'
    >>> everything_but_the_tracker.status(KindSlice(EntityKind.DOCUMENT)).value
    'covered'
    """

    reachable: frozenset[Source]

    def status(self, where: Slice) -> SliceStatus:
        """Covered when the slice's source is reachable, failed when it is not."""
        return SliceStatus.COVERED if where.source in self.reachable else SliceStatus.FAILED


# --- Where a fact lives ------------------------------------------------------------------


class Placement(StrEnum):
    """Where one source keeps the facts of one predicate.

    ``SUBJECT_RECORD``: on the record of the fact's own subject. ``VALUE_RECORD``: on the
    record the fact's value names, as a membership sits in the component's member list.
    ``COMMENTS``: in a comment of any work item. ``SECTIONS``: in a section of any
    document, the one placement no read enumerates. ``LEAVES``: on a leave record, which
    is about an employee and found by its dates.
    """

    SUBJECT_RECORD = "subject_record"
    VALUE_RECORD = "value_record"
    COMMENTS = "comments"
    SECTIONS = "sections"
    LEAVES = "leaves"


_ON_THE_SUBJECT: tuple[tuple[PredicateName, Source], ...] = (
    (PredicateName.MEMBER_OF_TEAM, Source.FRAPPE),
    (PredicateName.REPORTS_TO, Source.FRAPPE),
    (PredicateName.LOCATED_IN, Source.FRAPPE),
    (PredicateName.EMPLOYED_AS, Source.FRAPPE),
    (PredicateName.HAS_SKILL, Source.FRAPPE),
    (PredicateName.OWNS_WORK_ITEM, Source.JIRA),
    (PredicateName.WORK_ITEM_STATUS, Source.JIRA),
    (PredicateName.DUE_ON, Source.JIRA),
    (PredicateName.IN_COMPONENT, Source.JIRA),
    (PredicateName.ATTENDS_EVENT, Source.CALENDAR),
    (PredicateName.SCHEDULED_AT, Source.CALENDAR),
    (PredicateName.REQUIRES, Source.CORPUS),
    (PredicateName.NAMES_RESPONSIBLE, Source.CORPUS),
)

PLACEMENTS: Mapping[tuple[PredicateName, Source], Placement] = MappingProxyType(
    {
        **dict.fromkeys(_ON_THE_SUBJECT, Placement.SUBJECT_RECORD),
        (PredicateName.MEMBER_OF_COMPONENT, Source.JIRA): Placement.VALUE_RECORD,
        (PredicateName.ON_LEAVE, Source.FRAPPE): Placement.LEAVES,
        # A skill shown in a ticket comment or stated by a client note, an owner a runbook
        # still names: prose the world plants, with the comment or the section as provenance.
        (PredicateName.HAS_SKILL, Source.JIRA): Placement.COMMENTS,
        (PredicateName.HAS_SKILL, Source.CORPUS): Placement.SECTIONS,
        (PredicateName.OWNS_WORK_ITEM, Source.CORPUS): Placement.SECTIONS,
    }
)
"""Where each predicate's facts live, per source of its evidence domain: derivation and the
world's plantings read backwards. The tests hold it to the registry, one entry per
predicate and source and no other."""


@dataclass(frozen=True, slots=True)
class Needed:
    """One slice a negative needs covered, and whether the negative may stand without it when
    no read can observe it whole."""

    where: Slice
    waivable: bool


def closing_slices(
    row: Predicate, subject: EntityRef, value: FactValue | None = None
) -> tuple[Needed, ...]:
    """The slices that must be covered before "no fact states ``row`` of ``subject``" is false:
    one per source of the evidence domain, the system of record's first.

    ``value`` narrows the one placement it can: asked whether someone is a member of a
    named component, that component's record closes the question; asked whether they are
    a member of any, every component does.

    >>> from leaveimpact.core.ids import component_id, employee_id
    >>> from leaveimpact.core.predicates import predicate
    >>> from leaveimpact.core.refs import component_ref, employee_ref
    >>> who = employee_ref(employee_id(17))
    >>> membership = predicate(PredicateName.MEMBER_OF_COMPONENT)
    >>> [needed.where for needed in closing_slices(membership, who, component_ref(component_id(1)))]
    [RecordSlice(record=EntityRef(kind=<EntityKind.COMPONENT: 'component'>, id='comp_001'))]
    >>> skill = closing_slices(predicate(PredicateName.HAS_SKILL), who)
    >>> [(needed.where.source.value, needed.waivable) for needed in skill]
    [('frappe', False), ('corpus', True), ('jira', False)]
    """
    needed: list[Needed] = []
    for source in _record_first(row):
        match _placement(row, source):
            case Placement.SUBJECT_RECORD:
                needed.append(Needed(RecordSlice(subject), False))
            case Placement.VALUE_RECORD:
                if isinstance(value, EntityRef):
                    needed.append(Needed(RecordSlice(value), False))
                else:
                    needed.append(Needed(KindSlice(_value_kind(row)), False))
            case Placement.COMMENTS:
                needed.append(Needed(KindSlice(EntityKind.WORK_ITEM), False))
            case Placement.SECTIONS:
                needed.append(Needed(KindSlice(EntityKind.DOCUMENT), True))
            case Placement.LEAVES:
                needed.append(Needed(KindSlice(EntityKind.LEAVE), False))
    return tuple(needed)


def closing_slices_of_any(row: Predicate, scope: Scope | None) -> tuple[Needed, ...]:
    """The slices that must be covered before "no fact of ``row`` matches" is false, for a
    question about no one subject: the window ``scope`` over the records that hold the
    fact, or every such record when the question has no window.

    A window is refused for a predicate whose records no read narrows by one.

    >>> from datetime import date
    >>> from leaveimpact.core.predicates import predicate
    >>> week = DateSpan(date(2026, 9, 15), date(2026, 9, 19))
    >>> closing_slices_of_any(predicate(PredicateName.ON_LEAVE), week)[0].where == WindowSlice(
    ...     EntityKind.LEAVE, week
    ... )
    True
    >>> closing_slices_of_any(predicate(PredicateName.ON_LEAVE), None)[0].where
    KindSlice(kind=<EntityKind.LEAVE: 'leave'>)
    """
    needed: list[Needed] = []
    for source in _record_first(row):
        match _placement(row, source):
            case Placement.SUBJECT_RECORD:
                needed.append(Needed(_over(row.subject, scope), False))
            case Placement.VALUE_RECORD:
                needed.append(Needed(_over(_value_kind(row), scope), False))
            case Placement.COMMENTS:
                needed.append(Needed(_over(EntityKind.WORK_ITEM, scope), False))
            case Placement.SECTIONS:
                needed.append(Needed(_over(EntityKind.DOCUMENT, scope), True))
            case Placement.LEAVES:
                needed.append(Needed(_over(EntityKind.LEAVE, scope), False))
    return tuple(needed)


def _over(kind: EntityKind, scope: Scope | None) -> Slice:
    return KindSlice(kind) if scope is None else WindowSlice(kind, scope)


def _record_first(row: Predicate) -> tuple[Source, ...]:
    """The evidence domain in one order: the system of record, then the rest by name."""
    rest = sorted(row.evidence_domain - {row.system_of_record}, key=lambda source: source.value)
    return (row.system_of_record, *rest)


def _placement(row: Predicate, source: Source) -> Placement:
    placement = PLACEMENTS.get((row.name, source))
    if placement is None:
        raise ValueError(
            f"no placement says where {source.value} keeps {row.name.value}; a source added "
            "to an evidence domain is declared in the placement table with it"
        )
    return placement


def _value_kind(row: Predicate) -> EntityKind:
    """The kind of record a value-placed predicate's value names."""
    kind = row.value_spec.entity_kind
    if kind is None:
        raise ValueError(
            f"{row.name.value} is placed on the record its value names, and its value names "
            "no record"
        )
    return kind


__all__ = [
    "PLACEMENTS",
    "WINDOWED_KINDS",
    "Coverage",
    "KindSlice",
    "Needed",
    "Placement",
    "RecordSlice",
    "Scope",
    "Slice",
    "SliceStatus",
    "SourceCoverage",
    "WindowSlice",
    "closing_slices",
    "closing_slices_of_any",
]
