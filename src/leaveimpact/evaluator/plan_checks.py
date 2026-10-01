"""The plan checks: whether a report's plan is valid against the truth, whether the report
hangs together with itself, and whether it looked at everyone where a conclusion calls for it.
Three questions, kept apart.

*Plan validity, against the oracle* (the plan ruling of the investigator milestone's third
build step). For every coverage action the report makes on an expected impact, the plan
rule is fed the oracle's requirements and the oracle's verdicts. An assign is valid only
when every assignee belongs to the organization, is viable in the oracle for that impact,
and the viable assignees meet the count each applicable clause asks for. The action's kind
is judged apart, as outcome match on its row; here the question is whom the plan names. No
assignee set is truth, so nothing is compared with an expected set.

*Coherence, within the report.*

- *The chain.* ``core``'s chain checks over the whole report: an unknown assessment rests
  on an unknown claim, an assign on viable assessments, a conflict resolves to the system
  of record, every impact has one action.
- *Declared-constraint consistency.* The plan rule again, fed the report's own assessments
  and the clauses the report itself cites for that impact. A clause's content is read
  from the fact base, since a report states which clause applies and never transcribes
  it, which is why the name does not say "internal". A report that missed a constraint
  fails validity and stays consistent; one that contradicts a clause it cited fails here.
  A cited clause whose content cannot be read (the fact base holds no requirement for it,
  or its source is unreachable) makes the check *uncheckable* for that action, whatever
  kind of action it is: the clauses are resolved before the plan rule is asked anything,
  so an uncovered action that cites a clause nobody can read is recorded too. It is never
  read as imposing no requirement.

*Coverage.* A conclusion of uncovered or unknown is about everyone, so it calls for an
assessment of every organization member. Two things can call for it for an impact: the
oracle expects such a conclusion there, whatever action the report made, which fixes the
count's denominator by truth and makes it the same for every system graded; or the report
itself made such a conclusion, which it is not entitled to from a report that stopped
assessing. One omission is one record. A gap names the impact, the colleagues left
unassessed and which of the two called for them, both when both did, so a colleague
missing where the oracle and the report agree is not counted twice. Where the oracle
expects the impact, its sealed probe set is left out of the gap: a probed candidate with no
assessment there is a recall miss on its own row. Where no such row exists (an impact the
oracle does not expect under the condition, or a run with no claim-level answer at all)
nobody is left out, since the gap is then the omission's only record.

So each omission has one home: a probed candidate of an expected impact unassessed is a
recall miss; anyone else unassessed where everyone is called for is a coverage gap; an
assignee with no reported assessment is a consistency finding; an unknown assessment with
no unknown claim behind it is a chain finding.

A finding is a small envelope: the check family, the impact it concerns when it concerns
one, the people it names, and the result itself, the plan rule's typed violation where it
produced one and the returned message otherwise. Every function takes a structurally valid
claim set, the checks' own precondition; a caller holding an invalid one records the
checks as not evaluated and does not call them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.checks import chain_problems
from leaveimpact.core.claims import (
    CandidateAssessment,
    Claim,
    Constraint,
    ConstraintKey,
    CoverageAction,
    CoverageActionKind,
    ImpactKey,
    require_well_formed,
)
from leaveimpact.core.closure import KnownTrue, Unresolved, establish
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.facts import FactView
from leaveimpact.core.ids import EmployeeId
from leaveimpact.core.plans import Violation, ViolationKind, plan_violations, verdicts_by_employee
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import EntityRef, clause_ref
from leaveimpact.core.viability import ResolvedRequirement, applicable_requirements, need_of
from leaveimpact.evaluator.oracle import Answerable
from leaveimpact.world.scenario import Scenario

UNIVERSAL = (CoverageActionKind.UNCOVERED, CoverageActionKind.UNKNOWN)
"""The outcomes that conclude something about every candidate."""


class CheckFamily(StrEnum):
    """Which check produced a finding; a member is the wire format."""

    ORACLE_PLAN = "oracle_plan"
    CHAIN = "chain"
    DECLARED_CONSTRAINT = "declared_constraint"


@dataclass(frozen=True, slots=True)
class CheckFinding:
    """One thing a check found.

    ``result`` is the plan rule's violation record for the two families it feeds and the
    check's own message otherwise. ``people`` are the employees the finding names.
    ``uncheckable`` marks a check that could not run for this action, which is a finding
    about the report (it cited a clause nobody can read) and never a pass.
    """

    family: CheckFamily
    impact: ImpactKey | None
    result: Violation | str
    people: tuple[EmployeeId, ...] = ()
    uncheckable: bool = False


@dataclass(frozen=True, slots=True)
class CoverageGap:
    """Colleagues left unassessed for an impact whose conclusion is about everyone.

    ``missing`` are the organization members with no assessment in the report, less the
    probe set of an impact the oracle expects, whose omissions are recall misses on their
    own rows. ``required_by_oracle`` says the oracle expects uncovered or
    unknown there, ``required_by_report`` that the report itself concluded so; at least one
    holds, and both hold when the two agree, which is one gap and not two.
    """

    impact: ImpactKey
    missing: tuple[EmployeeId, ...]
    required_by_oracle: bool
    required_by_report: bool

    def __post_init__(self) -> None:
        if not self.missing:
            raise ValueError("a coverage gap names at least one unassessed colleague")
        if not (self.required_by_oracle or self.required_by_report):
            raise ValueError("a coverage gap is called for by the oracle, the report or both")


def oracle_checks(oracle: Answerable, claims: Sequence[Claim]) -> tuple[CheckFinding, ...]:
    """The plan validity of ``claims`` against ``oracle``; empty when every plan is valid."""
    require_well_formed(claims)
    return tuple(_plan_validity(oracle, claims))


def report_checks(
    claims: Sequence[Claim], scenario: Scenario, view: FactView
) -> tuple[CheckFinding, ...]:
    """The chain and the declared-constraint consistency of ``claims``.

    ``view`` is the fact base a cited clause's content is read from; ``scenario`` supplies
    the leave's span and the reference timezone the need behind an impact is read with.
    Nothing here needs an answerable oracle, so these run on whatever a system emitted, a
    degraded run's report included.
    """
    require_well_formed(claims)
    return (
        *(CheckFinding(CheckFamily.CHAIN, None, problem) for problem in chain_problems(claims)),
        *_declared_constraints(claims, scenario, view),
    )


def coverage_gaps(
    claims: Sequence[Claim],
    universe: Sequence[EmployeeId],
    oracle: Answerable | None = None,
) -> tuple[CoverageGap, ...]:
    """One gap per impact that calls for everyone and was not given everyone.

    An impact calls for everyone when ``oracle`` expects uncovered or unknown for it, or
    when the report's own action for it is one of those. Without an oracle (a run with no
    claim-level answer) only the report's own conclusions call for it. The probe set is
    left out only for an impact ``oracle`` expects, where claim matching records a probed
    candidate's omission as a missed row; for any other impact, and for every impact when
    there is no oracle, a gap is over the whole of ``universe``. The oracle's impacts come
    first, in its order, then the report's others in claim order.
    """
    require_well_formed(claims)
    expected = oracle.impacts if oracle else ()
    probes = {truth.key: frozenset(truth.probe) for truth in expected}
    by_oracle = [truth.key for truth in expected if truth.outcome in UNIVERSAL]
    by_report = [action.impact_key for action in _actions(claims) if action.action in UNIVERSAL]
    gaps: list[CoverageGap] = []
    for impact in dict.fromkeys((*by_oracle, *by_report)):
        assessed = _assessed(claims, impact)
        probe = probes.get(impact, frozenset())
        missing = tuple(
            employee for employee in universe if employee not in probe and employee not in assessed
        )
        if missing:
            gaps.append(CoverageGap(impact, missing, impact in by_oracle, impact in by_report))
    return tuple(gaps)


# --- Against the oracle ---------------------------------------------------------------------


def _plan_validity(oracle: Answerable, claims: Sequence[Claim]) -> list[CheckFinding]:
    findings: list[CheckFinding] = []
    for action in _actions(claims):
        truth = oracle.impact(action.impact_key)
        if truth is None:
            continue
        # Membership first: the oracle holds a verdict for everyone in the organization, so
        # a name it has none for is a stranger and is said to be one.
        strangers = tuple(a for a in action.assignee_ids if a not in oracle.universe)
        findings.extend(
            CheckFinding(
                CheckFamily.ORACLE_PLAN,
                truth.key,
                f"{stranger} is assigned and is not in the organization",
                (stranger,),
            )
            for stranger in strangers
        )
        verdicts = {a.employee_id: a.verdict for a in truth.assessments}
        findings.extend(
            CheckFinding(CheckFamily.ORACLE_PLAN, truth.key, violation)
            for violation in plan_violations(action, truth.requirements, verdicts)
            if violation.kind is not ViolationKind.MISSING_ASSESSMENT
        )
    return findings


# --- Within the report ----------------------------------------------------------------------


def _declared_constraints(
    claims: Sequence[Claim], scenario: Scenario, view: FactView
) -> list[CheckFinding]:
    cited = [claim.key for claim in claims if isinstance(claim, Constraint)]
    assessments = [claim for claim in claims if isinstance(claim, CandidateAssessment)]
    findings: list[CheckFinding] = []
    for action in _actions(claims):
        impact = action.impact_key
        # Resolved before the plan rule is asked: an action of any kind that cites a clause
        # nobody can read is uncheckable, and the rule itself has nothing to say of an
        # action that names nobody.
        cited_requirements = _cited_requirements(cited, impact, scenario, view)
        if isinstance(cited_requirements, str):
            findings.append(
                CheckFinding(
                    CheckFamily.DECLARED_CONSTRAINT, impact, cited_requirements, uncheckable=True
                )
            )
            continue
        findings.extend(
            CheckFinding(CheckFamily.DECLARED_CONSTRAINT, impact, violation)
            for violation in plan_violations(
                action, cited_requirements, verdicts_by_employee(impact, assessments)
            )
        )
    return findings


def _cited_requirements(
    cited: Sequence[ConstraintKey], impact: ImpactKey, scenario: Scenario, view: FactView
) -> list[ResolvedRequirement] | str:
    """The requirements of the clauses the report cites for ``impact``, or why they cannot be
    read: a reason, never an empty list, since an unreadable clause imposes an unknown
    requirement and not none."""
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
        need = need_of(
            view, impact, scenario.investigated_leave.span, scenario.spec.reference_timezone
        )
    except ValueError:
        need = None  # an artifact the fact base knows nothing of
    if need is None or isinstance(need, Unresolved):
        if could_apply:
            return "the impact's artifact cannot be read, so which cited clause applies is open"
        return []
    component = need.component
    if isinstance(component, Unresolved) and by_component:
        return (
            "the artifact's component cannot be read, so whether a cited component clause "
            "applies is open"
        )
    scope = {impact.artifact, component} if isinstance(component, EntityRef) else {impact.artifact}
    applying = [constraint for constraint in cited if constraint.applies_to in scope]
    unreadable = sorted(
        constraint.clause_id
        for constraint in applying
        if not isinstance(
            establish(view, clause_ref(constraint.clause_id), PredicateName.REQUIRES), KnownTrue
        )
    )
    if unreadable:
        return (
            "a clause the report cites for this impact states no requirement that can be "
            f"read: {', '.join(unreadable)}"
        )
    return [
        requirement
        for requirement in applicable_requirements(view, need, applying)
        if isinstance(requirement, ResolvedRequirement)
    ]


def _actions(claims: Sequence[Claim]) -> list[CoverageAction]:
    return [claim for claim in claims if isinstance(claim, CoverageAction)]


def _assessed(claims: Sequence[Claim], impact: ImpactKey) -> frozenset[EmployeeId]:
    """Everyone the report assesses for ``impact``."""
    return frozenset(
        claim.employee_id
        for claim in claims
        if isinstance(claim, CandidateAssessment) and claim.impact_key == impact
    )


__all__ = [
    "CheckFamily",
    "CheckFinding",
    "CoverageGap",
    "coverage_gaps",
    "oracle_checks",
    "report_checks",
]
