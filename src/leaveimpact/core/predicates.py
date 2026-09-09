"""The predicate registry: each normalized fact kind, its system of record, its evidence domain.

A predicate names one kind of fact about one kind of subject — ``has_skill`` about an
employee, ``owns_work_item`` about a work item — and the registry declares two things
about it that the rules read as data rather than hold as their own copies (DESIGN,
"The answer-key contract"). The *system of record* is the one source whose value wins
when observations conflict: ``system_of_record_wins`` is the authority rule, and a
document is never the record for an operational fact about a person or a work item
(the corpus is the record only for what a procedure requires), so a runbook naming an
outdated owner loses to the tracker by this table and not by intuition. The *evidence
domain* is the set of sources that collectively hold every admissible piece of evidence
for the predicate in this synthetic world, and whether that set is closed: with a
closed domain, no positive evidence and every source readable is *known false*, while
a source unreachable in this run turns the same absence into *unknown* — which is why
an expected verdict is derived per run condition rather than stored.

The registry is a plain frozen table: predicates are data the world milestone
enumerates, not plugins that register themselves, and the tests check the table's
invariants (every predicate name has an entry, the record sits inside its own
domain). A predicate is added when a scenario class needs it and its domain is then
declared with it; a fact kind with no entry cannot be graded, on purpose.

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

from leaveimpact.core.enums import Source, SubjectKind


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
    ATTENDS_EVENT = "attends_event"
    REQUIRES = "requires"


@dataclass(frozen=True, slots=True)
class Predicate:
    """One registry row: what the fact is about, which source is its record, where evidence lives.

    ``evidence_domain`` always contains ``system_of_record``: the record is evidence
    before it is authority. ``closed`` says whether the domain is complete for this
    world — every predicate is closed in the first golden set, and the field exists so
    an open domain is a declaration rather than an accident.
    """

    name: PredicateName
    subject: SubjectKind
    system_of_record: Source
    evidence_domain: frozenset[Source]
    closed: bool

    def __post_init__(self) -> None:
        if self.system_of_record not in self.evidence_domain:
            raise ValueError(
                f"{self.name}: the system of record {self.system_of_record} must be in the "
                f"evidence domain {sorted(self.evidence_domain)}"
            )


def _row(
    name: PredicateName,
    subject: SubjectKind,
    system_of_record: Source,
    *evidence: Source,
) -> Predicate:
    domain = frozenset((system_of_record, *evidence))
    return Predicate(name, subject, system_of_record, domain, True)


ROWS: tuple[Predicate, ...] = (
    # Employment and location facts: the HR system is the record and the only evidence.
    _row(PredicateName.MEMBER_OF_TEAM, SubjectKind.EMPLOYEE, Source.FRAPPE),
    _row(PredicateName.REPORTS_TO, SubjectKind.EMPLOYEE, Source.FRAPPE),
    _row(PredicateName.LOCATED_IN, SubjectKind.EMPLOYEE, Source.FRAPPE),
    _row(PredicateName.EMPLOYED_AS, SubjectKind.EMPLOYEE, Source.FRAPPE),
    _row(PredicateName.ON_LEAVE, SubjectKind.EMPLOYEE, Source.FRAPPE),
    # A qualification may be evidenced in a ticket comment as well as the HR record — the
    # fragmented tier's case — so the tracker is in the domain and the HR system stays
    # the record.
    _row(PredicateName.HAS_SKILL, SubjectKind.EMPLOYEE, Source.FRAPPE, Source.JIRA),
    # Component membership is the other atomic qualification fact ("component experience
    # and the required skill"); the tracker holds it and nothing else does.
    _row(PredicateName.MEMBER_OF_COMPONENT, SubjectKind.EMPLOYEE, Source.JIRA),
    # Ownership may also be asserted by a runbook, which the stale-source scenario plants
    # against the tracker; the tracker is the record.
    _row(PredicateName.OWNS_WORK_ITEM, SubjectKind.WORK_ITEM, Source.JIRA, Source.CORPUS),
    _row(PredicateName.WORK_ITEM_STATUS, SubjectKind.WORK_ITEM, Source.JIRA),
    _row(PredicateName.DUE_ON, SubjectKind.WORK_ITEM, Source.JIRA),
    _row(PredicateName.ATTENDS_EVENT, SubjectKind.EVENT, Source.CALENDAR),
    # What a procedure requires is stated by its clause; the corpus is the record here
    # because the fact is normative, not a fact about a person or a ticket.
    _row(PredicateName.REQUIRES, SubjectKind.CLAUSE, Source.CORPUS),
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
    """
    return REGISTRY[name]
