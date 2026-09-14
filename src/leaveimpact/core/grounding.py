"""Impact grounding: whether the leaver holds the obligation an impact names, and which
obligations a leaver holds — one derivation for both questions.

Impacts were authored and never derived (DESIGN, "Impact grounding is a conclusion" under
the step 15 rulings): the rules concluded verdicts and outcomes *for* an expected impact
and nothing asked whether the fact base entailed the impact itself, so a fact whose only
role is to make an impact exist — a section naming the leaver as a client's contact —
was invisible to the role derivation by ablation and to the required-sources derivation
by outage. ``ground_impact`` asks, for one exact key, whether the leaver holds that
obligation; ``derive_impacts`` enumerates the leaver's obligations by applying the same
predicate to every artifact the view connects to the leaver. Discovery — the harness's
deterministic impact detection over live-derived facts — and truth-side grounding are
therefore one function and cannot drift apart. The exact key matters: a missing fact for
one section is never masked by an obligation elsewhere.

The subtype conditions mirror what the classes plant. A *deadline* is an open work item
the leaver owns whose due date lies inside the leave. A *meeting* is an event the leaver
attends whose schedule, read in the run's reference timezone, has a day inside the leave.
A *responsibility* is a section that names the leaver, or an open work item the leaver
owns that carries no due date at all: a dated ticket is a deadline or nothing, so the
wrong-window distractor — due the day before or after the leave — grounds no impact of
either subtype, and the already-resolved distractor fails on status. Open means a status
other than done. Every question goes through closure, so ownership resolves through the
authority table and a stale document never grounds an obligation the tracker
contradicts; an unreachable source makes the grounding unknown with closure's reason
rather than false, and any known failure settles the grounding whatever else is
unsettled, the same order the viability rule uses.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from leaveimpact.core.claims import ImpactKey, ImpactSubtype
from leaveimpact.core.closure import Closure, KnownFalse, KnownTrue, Unresolved, establish
from leaveimpact.core.enums import EntityKind, WorkItemStatus
from leaveimpact.core.facts import Fact, FactView
from leaveimpact.core.ids import EmployeeId, LeaveId
from leaveimpact.core.predicates import REGISTRY, Predicate, PredicateName
from leaveimpact.core.refs import EntityRef, employee_ref
from leaveimpact.core.worldtime import DateSpan, InstantSpan

Registry = Mapping[PredicateName, Predicate]


@dataclass(frozen=True, slots=True)
class Grounded:
    """The leaver holds the obligation; ``facts`` are what established it, in question order."""

    facts: tuple[Fact, ...]


@dataclass(frozen=True, slots=True)
class Ungrounded:
    """The fact base was fully observed on the question that failed, and the obligation is not
    the leaver's — or not of this subtype."""


Grounding = Grounded | Ungrounded | Unresolved


@dataclass(frozen=True, slots=True)
class DerivedImpacts:
    """What a leaver holds in one view: the grounded keys, and the keys a source outage or a gap
    left open, each with the question it stopped on. Both in key order."""

    grounded: tuple[ImpactKey, ...]
    unresolved: tuple[tuple[ImpactKey, Unresolved], ...]


def ground_impact(
    view: FactView,
    impact: ImpactKey,
    leaver: EmployeeId,
    leave_span: DateSpan,
    reference_timezone: str,
    *,
    registry: Registry = REGISTRY,
) -> Grounding:
    """Whether ``leaver`` holds the obligation ``impact`` names, in the world ``view`` sees.

    The key's subtype chooses the questions; the artifact's kind chooses the responsibility
    shape. Unlike the viability rule, an event without a schedule is ungrounded rather
    than an error: the enumerator may ask about an artifact the view only half sees.
    """
    who = employee_ref(leaver)
    artifact = impact.artifact
    match impact.subtype:
        case ImpactSubtype.DEADLINE:
            answers = [
                establish(view, artifact, PredicateName.OWNS_WORK_ITEM, who, registry=registry),
                _open(view, artifact, registry),
                _due(view, artifact, registry, inside=leave_span),
            ]
        case ImpactSubtype.MEETING:
            answers = [
                establish(view, artifact, PredicateName.ATTENDS_EVENT, who, registry=registry),
                _on_a_leave_day(view, artifact, registry, leave_span, reference_timezone),
            ]
        case ImpactSubtype.RESPONSIBILITY if artifact.kind is EntityKind.CLAUSE:
            answers = [
                establish(view, artifact, PredicateName.NAMES_RESPONSIBLE, who, registry=registry)
            ]
        case ImpactSubtype.RESPONSIBILITY:
            answers = [
                establish(view, artifact, PredicateName.OWNS_WORK_ITEM, who, registry=registry),
                _open(view, artifact, registry),
                _due(view, artifact, registry, inside=None),
            ]
    return _combine(answers)


def derive_impacts(
    view: FactView,
    leave_id: LeaveId,
    leaver: EmployeeId,
    leave_span: DateSpan,
    reference_timezone: str,
    *,
    registry: Registry = REGISTRY,
) -> DerivedImpacts:
    """Every obligation ``leaver`` holds over the leave: candidates times ``ground_impact``.

    A candidate is any artifact a visible fact connects to the leaver — a work item some
    source says they own, an event some source says they attend, a section some source
    says names them — read raw on purpose: the grounding of each candidate is where
    authority resolves, so a stale document proposes a candidate and the tracker's answer
    decides it. A work item is tried as a deadline and as a responsibility; at most one
    grounds.
    """
    who = employee_ref(leaver)
    candidates: list[ImpactKey] = []
    for fact in view.facts_of(PredicateName.OWNS_WORK_ITEM):
        if fact.value == who:
            candidates.append(ImpactKey(leave_id, ImpactSubtype.DEADLINE, fact.subject))
            candidates.append(ImpactKey(leave_id, ImpactSubtype.RESPONSIBILITY, fact.subject))
    for fact in view.facts_of(PredicateName.ATTENDS_EVENT):
        if fact.value == who:
            candidates.append(ImpactKey(leave_id, ImpactSubtype.MEETING, fact.subject))
    for fact in view.facts_of(PredicateName.NAMES_RESPONSIBLE):
        if fact.value == who:
            candidates.append(ImpactKey(leave_id, ImpactSubtype.RESPONSIBILITY, fact.subject))
    grounded: list[ImpactKey] = []
    unresolved: list[tuple[ImpactKey, Unresolved]] = []
    for key in sorted(set(candidates), key=_key_order):
        match ground_impact(view, key, leaver, leave_span, reference_timezone, registry=registry):
            case Grounded():
                grounded.append(key)
            case Unresolved() as open_question:
                unresolved.append((key, open_question))
            case Ungrounded():
                pass
    return DerivedImpacts(tuple(grounded), tuple(unresolved))


def _key_order(key: ImpactKey) -> tuple[str, str, str]:
    return (key.subtype.value, key.artifact.kind.value, key.artifact.id)


# --- The questions ----------------------------------------------------------------------


def _open(view: FactView, artifact: EntityRef, registry: Registry) -> Closure:
    """Whether the work item's status is anything but done; no status at all is not open."""
    status = establish(view, artifact, PredicateName.WORK_ITEM_STATUS, registry=registry)
    match status:
        case KnownTrue(facts):
            return status if facts[0].value is not WorkItemStatus.DONE else KnownFalse()
        case _:
            return status


def _due(
    view: FactView, artifact: EntityRef, registry: Registry, *, inside: DateSpan | None
) -> Closure:
    """A deadline wants a due date inside ``inside``; a responsibility (``None``) wants none."""
    due = establish(view, artifact, PredicateName.DUE_ON, registry=registry)
    match due:
        case KnownTrue(facts):
            if inside is None:
                return KnownFalse()
            day = facts[0].value
            assert isinstance(day, date)
            return due if inside.contains(day) else KnownFalse()
        case KnownFalse():
            return KnownTrue(()) if inside is None else due
        case _:
            return due


def _on_a_leave_day(
    view: FactView,
    artifact: EntityRef,
    registry: Registry,
    leave_span: DateSpan,
    reference_timezone: str,
) -> Closure:
    scheduled = establish(view, artifact, PredicateName.SCHEDULED_AT, registry=registry)
    match scheduled:
        case KnownTrue(facts):
            span = facts[0].value
            assert isinstance(span, InstantSpan)
            days = span.local_dates(reference_timezone)
            return scheduled if days.overlaps(leave_span) else KnownFalse()
        case _:
            return scheduled


def _combine(answers: list[Closure]) -> Grounding:
    """Known failure first, then any open question, else grounded on every answer's facts."""
    if any(isinstance(answer, KnownFalse) for answer in answers):
        return Ungrounded()
    for answer in answers:
        if isinstance(answer, Unresolved):
            return answer
    facts: list[Fact] = []
    for answer in answers:
        assert isinstance(answer, KnownTrue)
        facts.extend(answer.facts)
    return Grounded(tuple(facts))


__all__ = [
    "DerivedImpacts",
    "Grounded",
    "Grounding",
    "Ungrounded",
    "derive_impacts",
    "ground_impact",
]
