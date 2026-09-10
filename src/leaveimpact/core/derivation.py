"""Fact derivation: an observed entity becomes the facts and gaps the rules read, in one place.

A port returns records and never facts (the ports ruling in DESIGN); this module is
where a record's fields become atomic facts against the registry, so an adapter
translates shape and identity and the domain alone decides what is true. One
derivation serves every consumer: the investigator's harness derives from live reads,
and the world builds its truth base by deriving from the entities it generated and
then adding the facts only a world can plant — a skill evidenced in a ticket comment,
an owner a runbook asserts, what a clause requires — so the two bases agree on what
every field means by construction rather than by a table kept in step.

The per-field meaning of absence lives here and nowhere else. ``skills`` ``None`` is
a ``Gap`` — the record was observed and held no skills field, the missing-information
case — and an empty tuple is zero facts, which grades as non-viable through the
closed-world rule; a ticket without a due date and an employee without a manager are
observed negatives, zero facts and no gap, because both are real states of the world
rather than information withheld. A requested leave derives no absence: it is not yet
one, and no rule reads the request itself. A work item's comments derive nothing —
a skill shown in a comment is extracted from prose, which is the world's to plant with
the comment as provenance, never a deterministic read. Documents and teams derive
nothing: what a clause requires enters the fact base from the world's structured
brief, and no predicate is about a team.

When a fact became observable is the caller's knowledge, not the record's — the
entity types keep vendor timestamps out on purpose — so every derivation takes the
date and stamps it on each fact it emits: the world passes the date it planted the
record, a live harness passes the run's day. Completeness is the caller's too: the
registry declares a domain closed and closure infers false from zero facts, which is
sound only when the caller derived from every record an enumerating read returned,
to completion, before the rules ran; reachability is not completeness (the read ports).
"""

# No deferred annotations here: pdoc resolves a PEP 695 type parameter only when the
# signature evaluates it, and nothing in this module needs a forward reference.
from datetime import date

from leaveimpact.core.entities import CalendarEvent, Component, Employee, Leave, WorkItem
from leaveimpact.core.enums import LeaveStatus
from leaveimpact.core.facts import Fact, Gap
from leaveimpact.core.ports.observed import Entity, Observed
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import EvidenceRef, component_ref, employee_ref, team_ref
from leaveimpact.core.values import FactValue

Derived = Fact | Gap
"""What derivation emits: facts, and gaps where a field held no value."""


def derive[T: Entity](observed: Observed[T], observable_from: date) -> tuple[Derived, ...]:
    """Every fact and gap the observed record carries, dated ``observable_from``.

    Dispatches on the record's type; a document or a team yields an empty tuple, as
    the module docstring says why.

    >>> from leaveimpact.core.enums import Source, WorkItemStatus
    >>> from leaveimpact.core.ids import component_id, employee_id, work_item_id
    >>> ticket = WorkItem(work_item_id(42), "Kafka upgrade", employee_id(17),
    ...                   WorkItemStatus.IN_PROGRESS, component_id(1), date(2026, 9, 1),
    ...                   None, None, ())
    >>> seen = Observed(ticket, Source.JIRA)
    >>> [fact.predicate.value for fact in derive(seen, date(2026, 9, 1))]
    ['owns_work_item', 'work_item_status', 'in_component']
    """
    value = observed.value
    if isinstance(value, Employee):
        return derive_employee(Observed(value, observed.source), observable_from)
    if isinstance(value, Component):
        return derive_component(Observed(value, observed.source), observable_from)
    if isinstance(value, WorkItem):
        return derive_work_item(Observed(value, observed.source), observable_from)
    if isinstance(value, CalendarEvent):
        return derive_event(Observed(value, observed.source), observable_from)
    if isinstance(value, Leave):
        return derive_leave(Observed(value, observed.source), observable_from)
    return ()


def derive_employee(observed: Observed[Employee], observable_from: date) -> tuple[Derived, ...]:
    """Team, manager, location, skills and employment type as facts; no skills field, a gap.

    Grade, country and timezone have no predicate until a rule reads one, and derive
    nothing.
    """
    person = observed.value
    who = observed.ref

    def fact(name: PredicateName, value: FactValue, field: str) -> Fact:
        return Fact(who, name, value, EvidenceRef(observed.source, who, field), observable_from)

    derived: list[Derived] = [
        fact(PredicateName.MEMBER_OF_TEAM, team_ref(person.team_id), "team_id"),
        fact(PredicateName.LOCATED_IN, person.location, "location"),
        fact(PredicateName.EMPLOYED_AS, person.employment_type, "employment_type"),
    ]
    if person.manager_id is not None:
        derived.append(
            fact(PredicateName.REPORTS_TO, employee_ref(person.manager_id), "manager_id")
        )
    if person.skills is None:
        derived.append(
            Gap(
                who,
                PredicateName.HAS_SKILL,
                EvidenceRef(observed.source, who, "skills"),
                observable_from,
            )
        )
    else:
        derived.extend(fact(PredicateName.HAS_SKILL, skill, "skills") for skill in person.skills)
    return tuple(derived)


def derive_component(
    observed: Observed[Component], observable_from: date
) -> tuple[Derived, ...]:
    """One membership fact per named member, about the member, evidenced by the component."""
    component = observed.value
    evidence = EvidenceRef(observed.source, observed.ref, "member_ids")
    return tuple(
        Fact(
            employee_ref(member),
            PredicateName.MEMBER_OF_COMPONENT,
            component_ref(component.id),
            evidence,
            observable_from,
        )
        for member in component.member_ids
    )


def derive_work_item(
    observed: Observed[WorkItem], observable_from: date
) -> tuple[Derived, ...]:
    """Owner, status, due date and component as facts about the work item; comments derive none."""
    item = observed.value
    subject = observed.ref

    def fact(name: PredicateName, value: FactValue, field: str) -> Fact:
        evidence = EvidenceRef(observed.source, subject, field)
        return Fact(subject, name, value, evidence, observable_from)

    derived: list[Derived] = [
        fact(PredicateName.OWNS_WORK_ITEM, employee_ref(item.owner_id), "owner_id"),
        fact(PredicateName.WORK_ITEM_STATUS, item.status, "status"),
    ]
    if item.due_on is not None:
        derived.append(fact(PredicateName.DUE_ON, item.due_on, "due_on"))
    derived.append(
        fact(PredicateName.IN_COMPONENT, component_ref(item.component_id), "component_id")
    )
    return tuple(derived)


def derive_event(observed: Observed[CalendarEvent], observable_from: date) -> tuple[Derived, ...]:
    """The schedule as one fact and attendance as one fact per attendee, about the event.

    The schedule cites the whole event record, not a field: the span is synthesized
    from ``start`` and ``end`` together, and an evidence reference is a locator for
    re-verification, so naming one field could not re-establish the value (found at
    the step-5 review). Same shape as a leave's absence citing the leave record.
    """
    event = observed.value
    subject = observed.ref
    return (
        Fact(
            subject,
            PredicateName.SCHEDULED_AT,
            event.span,
            EvidenceRef(observed.source, subject),
            observable_from,
        ),
        *(
            Fact(
                subject,
                PredicateName.ATTENDS_EVENT,
                employee_ref(attendee),
                EvidenceRef(observed.source, subject, "attendee_ids"),
                observable_from,
            )
            for attendee in event.attendee_ids
        ),
    )


def derive_leave(observed: Observed[Leave], observable_from: date) -> tuple[Derived, ...]:
    """An approved leave as the employee's absence over its span, the leave record as provenance.

    A requested leave derives nothing — it is not yet an absence.
    """
    leave = observed.value
    if leave.status is not LeaveStatus.APPROVED:
        return ()
    return (
        Fact(
            employee_ref(leave.employee_id),
            PredicateName.ON_LEAVE,
            leave.span,
            EvidenceRef(observed.source, observed.ref),
            observable_from,
        ),
    )
