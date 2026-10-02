"""Reading a plan off a report: the requirements of the clauses it cites for an impact, and what
the plan rule makes of one coverage action over the report's own assessments.

Two checks ask this and must not ask it two ways. *Coherence* (the plan checks) asks
whether a report hangs together with itself: its action against its own assessments and
the clauses it cites. The *grounding replay* asks the same of an action claim, with the
leave's span as the run read it and the candidate universe the run enumerated, and wants
one thing more, the action the rule expects over that universe (the investigator
milestone's fourth build step, ruling 3: shared plan primitives). So the reading is one
function over what both supply: the view a cited clause's content is read from, the
leave's span and the reference timezone the need behind the impact is read with, the cited
constraints, the assessments, and the universe when the caller has one.

A report states which clause applies and never transcribes it, so a clause's content is
read from the view. A cited clause whose content cannot be read makes the plan unreadable
for that impact, whatever the action: the clauses are resolved before the plan rule is
asked anything, and an unreadable clause is never read as imposing no requirement. The
same holds when the impact's artifact, or its component, cannot be read and a cited clause
could apply through it. That is also why nothing here raises for what a report cites: a
clause that states no requirement, or an event with no schedule, is an unreadable plan
and not an error.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.claims import (
    CandidateAssessment,
    ConstraintKey,
    CoverageAction,
    CoverageActionKind,
    ImpactKey,
)
from leaveimpact.core.closure import KnownTrue, Unresolved, establish
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.facts import FactView
from leaveimpact.core.ids import ClauseId, EmployeeId
from leaveimpact.core.plans import (
    Violation,
    expected_action,
    plan_violations,
    required_count,
    verdicts_by_employee,
)
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import EntityRef, clause_ref
from leaveimpact.core.viability import ResolvedRequirement, applicable_requirements, need_of
from leaveimpact.core.worldtime import DateSpan


class Unreadable(StrEnum):
    """What stood between a report's cited clauses and their requirements."""

    ARTIFACT = "artifact"
    COMPONENT = "component"
    CLAUSE = "clause"


@dataclass(frozen=True, slots=True)
class PlanUnreadable:
    """The clauses a report cites for an impact cannot be resolved, and why. ``clauses`` are
    the cited ones whose requirement cannot be read, when that is the reason."""

    what: Unreadable
    message: str
    clauses: tuple[ClauseId, ...] = ()


@dataclass(frozen=True, slots=True)
class PlanReading:
    """What the plan rule makes of one action over a report's own assessments.

    ``applied`` are the cited constraints that apply to the impact, ``requirements`` what
    they ask, in the same order. ``violations`` is the plan rule's answer. With a
    universe, ``unassessed`` are its members the report holds no assessment of for the
    impact, and ``expected`` is the action the rule expects over the universe, ``None``
    while someone is unassessed: a missing assessment is not a non-viable candidate.
    Without one, both are empty.
    """

    applied: tuple[ConstraintKey, ...]
    requirements: tuple[ResolvedRequirement, ...]
    violations: tuple[Violation, ...]
    unassessed: tuple[EmployeeId, ...] = ()
    expected: CoverageActionKind | None = None


def read_plan(
    action: CoverageAction,
    cited: Sequence[ConstraintKey],
    assessments: Sequence[CandidateAssessment],
    view: FactView,
    leave_span: DateSpan,
    reference_timezone: str,
    universe: Sequence[EmployeeId] | None = None,
) -> PlanReading | PlanUnreadable:
    """The plan ``action`` states, read against ``assessments`` and the clauses ``cited``.

    ``universe`` is everyone a conclusion of uncovered or unknown is about; a caller that
    judges only the people an action names passes none.
    """
    impact = action.impact_key
    cited_for = cited_requirements(cited, impact, view, leave_span, reference_timezone)
    if isinstance(cited_for, PlanUnreadable):
        return cited_for
    applied, requirements = cited_for
    verdicts = verdicts_by_employee(impact, assessments)
    unassessed: tuple[EmployeeId, ...] = ()
    expected: CoverageActionKind | None = None
    if universe is not None:
        unassessed = tuple(employee for employee in universe if employee not in verdicts)
        if not unassessed:
            expected = expected_action(
                (verdicts[employee] for employee in universe), required_count(requirements)
            )
    return PlanReading(
        applied=applied,
        requirements=requirements,
        violations=plan_violations(action, requirements, verdicts),
        unassessed=unassessed,
        expected=expected,
    )


def cited_requirements(
    cited: Sequence[ConstraintKey],
    impact: ImpactKey,
    view: FactView,
    leave_span: DateSpan,
    reference_timezone: str,
) -> tuple[tuple[ConstraintKey, ...], tuple[ResolvedRequirement, ...]] | PlanUnreadable:
    """The cited constraints that apply to ``impact`` and their requirements, or why they
    cannot be read: a reason, never an empty answer, since an unreadable clause imposes an
    unknown requirement and not none."""
    # What the report's own citations could be about for this impact, read off the report:
    # the artifact itself, or a component when the artifact is a work item.
    by_component = [
        constraint
        for constraint in cited
        if impact.artifact.kind is EntityKind.WORK_ITEM
        and constraint.applies_to.kind is EntityKind.COMPONENT
    ]
    could_apply = [c for c in cited if c.applies_to == impact.artifact] + by_component
    try:
        need = need_of(view, impact, leave_span, reference_timezone)
    except ValueError:
        need = None  # an artifact the fact base knows nothing of
    if need is None or isinstance(need, Unresolved):
        if could_apply:
            return PlanUnreadable(
                Unreadable.ARTIFACT,
                "the impact's artifact cannot be read, so which cited clause applies is open",
            )
        return (), ()
    component = need.component
    if isinstance(component, Unresolved) and by_component:
        return PlanUnreadable(
            Unreadable.COMPONENT,
            "the artifact's component cannot be read, so whether a cited component clause "
            "applies is open",
        )
    scope = {impact.artifact, component} if isinstance(component, EntityRef) else {impact.artifact}
    applying = tuple(constraint for constraint in cited if constraint.applies_to in scope)
    unreadable = tuple(
        sorted(
            constraint.clause_id
            for constraint in applying
            if not isinstance(
                establish(view, clause_ref(constraint.clause_id), PredicateName.REQUIRES),
                KnownTrue,
            )
        )
    )
    if unreadable:
        return PlanUnreadable(
            Unreadable.CLAUSE,
            "a clause the report cites for this impact states no requirement that can be "
            f"read: {', '.join(unreadable)}",
            unreadable,
        )
    requirements = tuple(
        requirement
        for requirement in applicable_requirements(view, need, applying)
        if isinstance(requirement, ResolvedRequirement)
    )
    return applying, requirements


__all__ = ["PlanReading", "PlanUnreadable", "Unreadable", "cited_requirements", "read_plan"]
