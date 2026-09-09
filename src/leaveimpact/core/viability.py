"""The viability rule: whether one person could satisfy one need, and why not when not.

Viability is relational and preference is never truth (DESIGN, "Four semantic rules
travel with the vocabulary"): the rule states whether ``(need, employee)`` is viable,
never who is best. Every criterion is a question to the fact base answered through
closure, and the answers combine in one order (DESIGN, "The rules in code"): any
criterion known to fail → non-viable, with every failing reason listed; otherwise any
criterion unresolved → unknown, deriving from one unknown claim per unresolved fact;
otherwise viable. A known failure dominates an unresolved question because one certain
failure settles the candidate whatever else is unsettled, and listing every failure
rather than the first makes the verdict independent of evaluation order.

The criteria and their sources of truth. *Skill* and *hard rule* come from the
clause-backed requirements that apply to the impact — a constraint whose clause names
the artifact or its component — resolved through the clause's ``requires`` fact, so the
agent establishes which clause applies and never transcribes its content: failing a
skill criterion reads as ``skill``, failing a policy criterion (employment type) as
``hard_rule``. *Component* is a domain rule for work items: the cover belongs to the
artifact's component, a rule nobody writes down. *Availability* is a domain rule with
two halves: not on leave over the need's window — the investigated leave's span for a
deadline or a responsibility, the meeting's own day for a meeting, read in the run's
reference timezone — and, for a meeting, not attending another event that overlaps it;
the target meeting itself never disqualifies its own attendee. The leaver fails through
the ordinary on-leave check like anyone else. ``load`` is not a criterion: no first-set
class names it, and it returns when a class establishes its semantics.

A requirement's count never enters here. Criteria assess a candidate; the count judges
a plan (the plan module), so one viable person against a two-person clause is a viable
candidate and an invalid plan.

The investigated leave's span is a run input, not a fact the rule establishes: a run
whose HR system is unreachable still knows which leave it is investigating, and the
window is the premise of every assessment, not a finding of one.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from leaveimpact.core.claims import AssessmentReason, ConstraintKey, ImpactKey, Verdict
from leaveimpact.core.closure import (
    Closure,
    KnownFalse,
    KnownTrue,
    Unresolved,
    any_true,
    establish,
    establish_any,
)
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.facts import Fact, FactView
from leaveimpact.core.ids import ClauseId, EmployeeId
from leaveimpact.core.predicates import REGISTRY, Predicate, PredicateName
from leaveimpact.core.refs import EntityRef, clause_ref, employee_ref
from leaveimpact.core.values import (
    EmploymentTypeCriterion,
    Requirement,
    SkillCriterion,
)
from leaveimpact.core.worldtime import DateSpan, InstantSpan

Registry = Mapping[PredicateName, Predicate]


@dataclass(frozen=True, slots=True)
class Need:
    """What covering an impact asks for, read from the fact base: the window a cover must be free
    over, the component a work item belongs to, the span of a meeting."""

    impact: ImpactKey
    window: DateSpan
    component: EntityRef | Unresolved | None
    """A work item's component; unresolved when it could not be read in this run, so that the
    component criterion alone is unknown and every other criterion still answers."""
    event_span: InstantSpan | None
    facts: tuple[Fact, ...]
    """The facts the need was read from — the artifact's component, the meeting's schedule."""


@dataclass(frozen=True, slots=True)
class ResolvedRequirement:
    """A requirement that applies to a need, with the clause it came from and the fact stating
    it."""

    clause_id: ClauseId
    requirement: Requirement
    fact: Fact


@dataclass(frozen=True, slots=True)
class Assessment:
    """The rule's verdict on one person for one need, with what it rests on.

    ``reasons`` is non-empty exactly for a non-viable verdict; ``unresolved`` is non-empty
    exactly for an unknown one, one entry per unresolved fact and the seed of the unknown
    claims the assessment derives from; ``evidence`` is every fact any criterion read.
    """

    impact: ImpactKey
    employee_id: EmployeeId
    verdict: Verdict
    reasons: tuple[AssessmentReason, ...]
    unresolved: tuple[Unresolved, ...]
    evidence: tuple[Fact, ...]


# --- The need ------------------------------------------------------------------------


def need_of(
    view: FactView,
    impact: ImpactKey,
    leave_span: DateSpan,
    reference_timezone: str,
    *,
    registry: Registry = REGISTRY,
) -> Need | Unresolved:
    """The need behind ``impact``, or the unresolved fact that stops it from being read.

    A deadline or a responsibility needs cover over the investigated leave; a meeting
    needs cover on its own day, and its day is read from the meeting's schedule in the
    run's reference timezone — unreadable, and the need is unresolved, since no criterion
    has a window to ask about. A work item's component is read from the fact base and is
    ``None`` when the artifact is not a work item; unreadable, the need still stands with
    the component unresolved, because the leave window is a run input and the other
    criteria can answer.
    """
    artifact = impact.artifact
    if artifact.kind is EntityKind.EVENT:
        scheduled = establish(view, artifact, PredicateName.SCHEDULED_AT, registry=registry)
        match scheduled:
            case KnownTrue(facts):
                span = facts[0].value
                assert isinstance(span, InstantSpan)
                return Need(impact, span.local_dates(reference_timezone), None, span, facts)
            case Unresolved():
                return scheduled
            case KnownFalse():
                raise ValueError(f"{artifact.id} has no schedule in the fact base")
    if artifact.kind is EntityKind.WORK_ITEM:
        component = establish(view, artifact, PredicateName.IN_COMPONENT, registry=registry)
        match component:
            case KnownTrue(facts):
                ref = facts[0].value
                assert isinstance(ref, EntityRef)
                return Need(impact, leave_span, ref, None, facts)
            case Unresolved():
                return Need(impact, leave_span, component, None, ())
            case KnownFalse():
                return Need(impact, leave_span, None, None, ())
    return Need(impact, leave_span, None, None, ())


def applicable_requirements(
    view: FactView,
    need: Need,
    constraints: Iterable[ConstraintKey],
    *,
    registry: Registry = REGISTRY,
) -> tuple[ResolvedRequirement | Unresolved, ...]:
    """The requirements of the constraints that apply to ``need`` — those whose clause names the
    artifact or its component — each resolved through the clause's ``requires`` fact.

    A clause the fact base holds no requirement for is a defect in the constraints, not
    a world state, and raises; a clause whose requirement cannot be read in this run is
    returned unresolved and becomes an unknown of the assessment. With the artifact's
    component unresolved, a component-scoped constraint may or may not apply, and that
    unresolved component is returned in its place.
    """
    targets = {need.impact.artifact}
    if isinstance(need.component, EntityRef):
        targets.add(need.component)
    resolved: list[ResolvedRequirement | Unresolved] = []
    for constraint in constraints:
        if constraint.applies_to not in targets:
            if (
                isinstance(need.component, Unresolved)
                and constraint.applies_to.kind is EntityKind.COMPONENT
                and need.component not in resolved
            ):
                resolved.append(need.component)
            continue
        clause = clause_ref(constraint.clause_id)
        stated = establish(view, clause, PredicateName.REQUIRES, registry=registry)
        match stated:
            case KnownTrue(facts):
                requirement = facts[0].value
                assert isinstance(requirement, Requirement)
                resolved.append(ResolvedRequirement(constraint.clause_id, requirement, facts[0]))
            case Unresolved():
                resolved.append(stated)
            case KnownFalse():
                raise ValueError(f"{constraint.clause_id} states no requirement in the fact base")
    return tuple(resolved)


# --- The criteria ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Criterion:
    """One question asked of the candidate: the reason it fails under, and its answer."""

    reason: AssessmentReason
    answer: Closure
    fails_when_true: bool = False
    """Availability asks about an obstacle: a positive answer is the failure."""


def _criteria(
    view: FactView,
    need: Need,
    candidate: EmployeeId,
    requirements: Iterable[ResolvedRequirement],
    *,
    registry: Registry,
) -> list[_Criterion]:
    who = employee_ref(candidate)
    criteria: list[_Criterion] = []
    match need.component:
        case EntityRef():
            criteria.append(
                _Criterion(
                    AssessmentReason.COMPONENT,
                    establish(
                        view,
                        who,
                        PredicateName.MEMBER_OF_COMPONENT,
                        need.component,
                        registry=registry,
                    ),
                )
            )
        case Unresolved():
            criteria.append(_Criterion(AssessmentReason.COMPONENT, need.component))
        case None:
            pass
    on_leave = establish_any(
        view,
        PredicateName.ON_LEAVE,
        lambda fact: (
            fact.subject == who
            and isinstance(fact.value, DateSpan)
            and fact.value.overlaps(need.window)
        ),
        who,
        registry=registry,
    )
    criteria.append(_Criterion(AssessmentReason.AVAILABILITY, on_leave, fails_when_true=True))
    if need.event_span is not None:
        criteria.append(
            _Criterion(
                AssessmentReason.AVAILABILITY,
                _busy(view, need, who, registry=registry),
                fails_when_true=True,
            )
        )
    for resolved in requirements:
        for criterion in resolved.requirement.criteria:
            match criterion:
                case SkillCriterion(skill=skill):
                    criteria.append(
                        _Criterion(
                            AssessmentReason.SKILL,
                            establish(view, who, PredicateName.HAS_SKILL, skill, registry=registry),
                        )
                    )
                case EmploymentTypeCriterion(employment_type=employment_type):
                    criteria.append(
                        _Criterion(
                            AssessmentReason.HARD_RULE,
                            establish(
                                view,
                                who,
                                PredicateName.EMPLOYED_AS,
                                employment_type,
                                registry=registry,
                            ),
                        )
                    )
    return criteria


def _busy(view: FactView, need: Need, who: EntityRef, *, registry: Registry) -> Closure:
    """Whether ``who`` attends another event overlapping the meeting — the target excluded."""
    target = need.impact.artifact
    assert need.event_span is not None
    attended = establish_any(
        view,
        PredicateName.ATTENDS_EVENT,
        lambda fact: fact.value == who and fact.subject != target,
        target,
        registry=registry,
    )
    match attended:
        case KnownTrue(facts):
            return any_true(
                _overlaps(view, fact.subject, need.event_span, registry=registry) for fact in facts
            )
        case _:
            return attended


def _overlaps(
    view: FactView, event: EntityRef, span: InstantSpan, *, registry: Registry
) -> Closure:
    scheduled = establish(view, event, PredicateName.SCHEDULED_AT, registry=registry)
    match scheduled:
        case KnownTrue(facts):
            other = facts[0].value
            assert isinstance(other, InstantSpan)
            return scheduled if other.overlaps(span) else KnownFalse()
        case _:
            return scheduled


# --- The verdict -----------------------------------------------------------------------


def assess(
    view: FactView,
    need: Need,
    candidate: EmployeeId,
    constraints: Sequence[ConstraintKey],
    *,
    registry: Registry = REGISTRY,
) -> Assessment:
    """Whether ``candidate`` could cover ``need`` under ``constraints``, in the world ``view`` sees.

    Build the need with ``need_of`` first; an unresolved need is an unknown assessment for
    every candidate, which ``assess_impact`` handles.
    """
    requirements = applicable_requirements(view, need, constraints, registry=registry)
    unresolved: list[Unresolved] = [item for item in requirements if isinstance(item, Unresolved)]
    resolved = [item for item in requirements if isinstance(item, ResolvedRequirement)]
    evidence: list[Fact] = list(need.facts) + [item.fact for item in resolved]
    reasons: set[AssessmentReason] = set()
    for criterion in _criteria(view, need, candidate, resolved, registry=registry):
        match criterion.answer:
            case KnownTrue(facts):
                evidence.extend(facts)
                if criterion.fails_when_true:
                    reasons.add(criterion.reason)
            case KnownFalse():
                if not criterion.fails_when_true:
                    reasons.add(criterion.reason)
            case Unresolved():
                unresolved.append(criterion.answer)
    return _verdict(need.impact, candidate, reasons, unresolved, evidence)


def assess_impact(
    view: FactView,
    impact: ImpactKey,
    candidates: Iterable[EmployeeId],
    constraints: Sequence[ConstraintKey],
    leave_span: DateSpan,
    reference_timezone: str,
    *,
    registry: Registry = REGISTRY,
) -> tuple[Assessment, ...]:
    """Every candidate assessed for ``impact``, in the candidates' order.

    When the need itself cannot be read — a meeting whose schedule is unreachable —
    every candidate is unknown for that one reason.
    """
    need = need_of(view, impact, leave_span, reference_timezone, registry=registry)
    if isinstance(need, Unresolved):
        return tuple(_verdict(impact, candidate, set(), [need], []) for candidate in candidates)
    return tuple(
        assess(view, need, candidate, constraints, registry=registry) for candidate in candidates
    )


def _verdict(
    impact: ImpactKey,
    candidate: EmployeeId,
    reasons: set[AssessmentReason],
    unresolved: Sequence[Unresolved],
    evidence: Sequence[Fact],
) -> Assessment:
    if reasons:
        verdict, open_questions = Verdict.NON_VIABLE, ()
    elif unresolved:
        verdict, open_questions = Verdict.UNKNOWN, _unique(unresolved)
    else:
        verdict, open_questions = Verdict.VIABLE, ()
    return Assessment(
        impact,
        candidate,
        verdict,
        tuple(sorted(reasons, key=lambda reason: reason.value)),
        open_questions,
        _unique(evidence),
    )


def _unique[T](items: Iterable[T]) -> tuple[T, ...]:
    return tuple(dict.fromkeys(items))
