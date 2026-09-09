"""The predicate registry: each normalized fact kind, its value, its system of record, its evidence
domain.

A predicate names one kind of fact about one kind of subject — ``has_skill`` about an
employee, ``owns_work_item`` about a work item — and the registry declares four things
about it that the rules read as data rather than hold as their own copies (DESIGN, "The
answer-key contract" and "The rules in code"). The *value spec* is the shape of what
the fact says — a team reference, a date, a requirement — which a fact validates
against at construction and the codec writes as the value's JSON tag; whether the
predicate is *multi-valued* (one fact per skill, per attendee, per leave) or holds one
value per subject, which is what makes two differing values a conflict rather than a
set. The *system of record* is the one source whose value wins when observations
conflict: ``system_of_record_wins`` is the authority rule, and a document is never the
record for an operational fact about a person or a work item (the corpus is the record
only for what a procedure requires), so a runbook naming an outdated owner loses to the
tracker by this table and not by intuition. The *evidence domain* is the set of sources
that collectively hold every admissible piece of evidence for the predicate in this
synthetic world, and whether that set is closed: with a closed domain, no positive
evidence and every source readable is *known false*, while a source unreachable in this
run turns the same absence into *unknown* — which is why an expected verdict is derived
per run condition rather than stored.

The registry is a plain frozen table: predicates are data the world milestone
enumerates, not plugins that register themselves, and the tests check the table's
invariants (every predicate name has an entry, the record sits inside its own
domain). A predicate is added when a scenario class needs it and its domain is then
declared with it; a fact kind with no entry cannot be graded, on purpose. Two rows
exist because a rule reads them and nothing else does — ``scheduled_at`` for the
meeting-overlap check, ``in_component`` for the component rule — since a rule that
reaches back into an entity for a field is not reading the fact base. Country,
timezone and grade have no row until a rule reads one.

Deliberately not registered yet: a ``responsible_for`` predicate for an obligation
that exists only in a document (a named client contact in a runbook). DESIGN grades
that as a responsibility impact, but a document is never a system of record, so which
source holds that predicate's authority is the fragmented tier's first design question
(build plan, Tier 2 classes).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from leaveimpact.core.enums import EmploymentType, EntityKind, Source, WorkItemStatus
from leaveimpact.core.values import (
    DATE_SPAN_VALUE,
    DATE_VALUE,
    INSTANT_SPAN_VALUE,
    REQUIREMENT_VALUE,
    SKILL_VALUE,
    TEXT_VALUE,
    ValueSpec,
    entity_value,
    enum_value,
)


class PredicateName(StrEnum):
    """The fact kinds the world plants and the rules read; a member is the wire format."""

    MEMBER_OF_TEAM = "member_of_team"
    REPORTS_TO = "reports_to"
    LOCATED_IN = "located_in"
    HAS_SKILL = "has_skill"
    MEMBER_OF_COMPONENT = "member_of_component"
    EMPLOYED_AS = "employed_as"
    ON_LEAVE = "on_leave"
    OWNS_WORK_ITEM = "owns_work_item"
    WORK_ITEM_STATUS = "work_item_status"
    DUE_ON = "due_on"
    IN_COMPONENT = "in_component"
    ATTENDS_EVENT = "attends_event"
    SCHEDULED_AT = "scheduled_at"
    REQUIRES = "requires"


@dataclass(frozen=True, slots=True)
class Predicate:
    """One registry row: what the fact is about and says, which source is its record, where
    evidence lives.

    ``evidence_domain`` always contains ``system_of_record``: the record is evidence
    before it is authority. ``closed`` says whether the domain is complete for this
    world — every predicate is closed in the first golden set, and the field exists so
    an open domain is a declaration rather than an accident. ``multi_valued`` says the
    subject may hold several values at once, each its own fact; a single-valued
    predicate with two differing values across sources is a conflict.
    """

    name: PredicateName
    subject: EntityKind
    """The kind of entity the fact is about; a predicate accepts one kind of subject."""
    value_spec: ValueSpec
    system_of_record: Source
    evidence_domain: frozenset[Source]
    closed: bool
    multi_valued: bool

    def __post_init__(self) -> None:
        if self.system_of_record not in self.evidence_domain:
            raise ValueError(
                f"{self.name}: the system of record {self.system_of_record} must be in the "
                f"evidence domain {sorted(self.evidence_domain)}"
            )


def _row(
    name: PredicateName,
    subject: EntityKind,
    value_spec: ValueSpec,
    system_of_record: Source,
    *evidence: Source,
    multi_valued: bool = False,
) -> Predicate:
    domain = frozenset((system_of_record, *evidence))
    return Predicate(name, subject, value_spec, system_of_record, domain, True, multi_valued)


ROWS: tuple[Predicate, ...] = (
    # Employment and location facts: the HR system is the record and the only evidence.
    _row(
        PredicateName.MEMBER_OF_TEAM,
        EntityKind.EMPLOYEE,
        entity_value(EntityKind.TEAM),
        Source.FRAPPE,
    ),
    _row(
        PredicateName.REPORTS_TO,
        EntityKind.EMPLOYEE,
        entity_value(EntityKind.EMPLOYEE),
        Source.FRAPPE,
    ),
    _row(PredicateName.LOCATED_IN, EntityKind.EMPLOYEE, TEXT_VALUE, Source.FRAPPE),
    _row(
        PredicateName.EMPLOYED_AS,
        EntityKind.EMPLOYEE,
        enum_value(EmploymentType),
        Source.FRAPPE,
    ),
    # A person may hold several leaves over the world's span; the leave record is the
    # fact's provenance, the inclusive span is what the availability rule reads.
    _row(
        PredicateName.ON_LEAVE,
        EntityKind.EMPLOYEE,
        DATE_SPAN_VALUE,
        Source.FRAPPE,
        multi_valued=True,
    ),
    # A qualification may be evidenced in a ticket comment as well as the HR record — the
    # fragmented tier's case — so the tracker is in the domain and the HR system stays
    # the record.
    _row(
        PredicateName.HAS_SKILL,
        EntityKind.EMPLOYEE,
        SKILL_VALUE,
        Source.FRAPPE,
        Source.JIRA,
        multi_valued=True,
    ),
    # Component membership is the other atomic qualification fact ("component experience
    # and the required skill"); the tracker holds it and nothing else does.
    _row(
        PredicateName.MEMBER_OF_COMPONENT,
        EntityKind.EMPLOYEE,
        entity_value(EntityKind.COMPONENT),
        Source.JIRA,
        multi_valued=True,
    ),
    # Ownership may also be asserted by a runbook, which the stale-source scenario plants
    # against the tracker; the tracker is the record.
    _row(
        PredicateName.OWNS_WORK_ITEM,
        EntityKind.WORK_ITEM,
        entity_value(EntityKind.EMPLOYEE),
        Source.JIRA,
        Source.CORPUS,
    ),
    _row(
        PredicateName.WORK_ITEM_STATUS,
        EntityKind.WORK_ITEM,
        enum_value(WorkItemStatus),
        Source.JIRA,
    ),
    _row(PredicateName.DUE_ON, EntityKind.WORK_ITEM, DATE_VALUE, Source.JIRA),
    _row(
        PredicateName.IN_COMPONENT,
        EntityKind.WORK_ITEM,
        entity_value(EntityKind.COMPONENT),
        Source.JIRA,
    ),
    _row(
        PredicateName.ATTENDS_EVENT,
        EntityKind.EVENT,
        entity_value(EntityKind.EMPLOYEE),
        Source.CALENDAR,
        multi_valued=True,
    ),
    _row(PredicateName.SCHEDULED_AT, EntityKind.EVENT, INSTANT_SPAN_VALUE, Source.CALENDAR),
    # What a procedure requires is stated by its clause; the corpus is the record here
    # because the fact is normative, not a fact about a person or a ticket.
    _row(PredicateName.REQUIRES, EntityKind.CLAUSE, REQUIREMENT_VALUE, Source.CORPUS),
)
"""The rows in declaration order — the table as authored; ``REGISTRY`` is its index."""


def index_by_name(rows: tuple[Predicate, ...]) -> Mapping[PredicateName, Predicate]:
    """The rows by name; a name declared twice fails at import, never by silent overwrite."""
    by_name: dict[PredicateName, Predicate] = {}
    for row in rows:
        if row.name in by_name:
            raise ValueError(f"predicate {row.name} is declared twice in the registry")
        by_name[row.name] = row
    return MappingProxyType(by_name)


REGISTRY: Mapping[PredicateName, Predicate] = index_by_name(ROWS)
"""Every registered predicate by name; read-only."""


def predicate(name: PredicateName) -> Predicate:
    """The registry row for ``name``.

    >>> predicate(PredicateName.HAS_SKILL).system_of_record
    <Source.FRAPPE: 'frappe'>
    >>> sorted(predicate(PredicateName.HAS_SKILL).evidence_domain)
    [<Source.FRAPPE: 'frappe'>, <Source.JIRA: 'jira'>]
    >>> predicate(PredicateName.DUE_ON).value_spec.kind
    <ValueKind.DATE: 'date'>
    """
    return REGISTRY[name]
