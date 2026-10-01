"""The plan checks: whether a report's plan is valid against the truth, and whether the report
hangs together with itself. Two questions, kept apart, each with its own findings.

*Against the oracle* (the plan ruling of the investigator milestone's third build step):

- *Plan validity.* For every coverage action the report makes on an expected impact, the
  plan rule is fed the oracle's requirements and the oracle's verdicts. An assign is valid
  only when every assignee belongs to the organization, is viable in the oracle for that
  impact, and the viable assignees meet the count each applicable clause asks for. The
  action's kind is judged apart, as outcome match on its row; here the question is whom
  the plan names. No assignee set is truth, so nothing is compared with an expected set.
- *Oracle coverage.* Where the oracle expects uncovered or unknown, a conclusion about
  everyone, every organization member outside the impact's probe set needs an assessment,
  whatever action the report made. The trigger is the oracle's and not the report's, so
  the count's denominator is fixed by truth and is the same for every system graded.

*Within the report* (coherence):

- *The chain.* ``core``'s chain checks over the whole report: an unknown assessment rests
  on an unknown claim, an assign on viable assessments, a conflict resolves to the system
  of record, every impact has one action.
- *Declared-constraint consistency.* The plan rule again, fed the report's own assessments
  and the clauses the report itself cites for that impact. A clause's content is read
  from the fact base, since a report states which clause applies and never transcribes
  it, which is why the name does not say "internal". A report that missed a constraint
  fails validity and stays consistent; one that contradicts a clause it cited fails here.
  A cited clause whose content cannot be read (the fact base holds no requirement for it,
  or its source is unreachable) makes the check *uncheckable* for that action. It is never
  read as imposing no requirement.
- *Report coverage.* Where the report itself concludes uncovered or unknown, every
  organization member needs an assessment for that impact: uncovered is never inferred
  from a report that stopped assessing, and "nobody is known viable" is as universal a
  claim as "nobody is viable".

Each omission has one home. A probed candidate with no assessment is a recall miss on its
row, not a coverage finding; an assignee with no reported assessment is a consistency
finding; a colleague outside the probe set unassessed where the oracle expects a universal
conclusion is an oracle coverage finding; an unknown assessment with no unknown claim
behind it is a chain finding.

A finding is a small envelope: the check family, the impact it concerns when it concerns
one, the people it names, and the result itself, the plan rule's typed violation where it
produced one and the returned message otherwise. Both functions take a structurally valid
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
    ORACLE_COVERAGE = "oracle_coverage"
    CHAIN = "chain"
    DECLARED_CONSTRAINT = "declared_constraint"
    REPORT_COVERAGE = "report_coverage"


@dataclass(frozen=True, slots=True)
class CheckFinding:
    """One thing a check found.

    ``result`` is the plan rule's violation record for the two families it feeds and the
    check's own message otherwise. ``people`` are the employees the finding names, so a
    table can count colleagues left unassessed without reading a message. ``uncheckable``
    marks a check that could not run for this action, which is a finding about the report
    (it cited a clause nobody can read) and never a pass.
    """

    family: CheckFamily
    impact: ImpactKey | None
    result: Violation | str
    people: tuple[EmployeeId, ...] = ()
    uncheckable: bool = False


def oracle_checks(oracle: Answerable, claims: Sequence[Claim]) -> tuple[CheckFinding, ...]:
    """Plan validity and oracle coverage of ``claims`` against ``oracle``; empty when both hold."""
    require_well_formed(claims)
    return (*_plan_validity(oracle, claims), *_oracle_coverage(oracle, claims))


def report_checks(
    claims: Sequence[Claim], scenario: Scenario, view: FactView, universe: Sequence[EmployeeId]
) -> tuple[CheckFinding, ...]:
    """The chain, declared-constraint consistency and report coverage of ``claims``.

    ``view`` is the fact base a cited clause's content is read from and ``universe`` the
    organization; ``scenario`` supplies the leave's span and the reference timezone the
    need behind an impact is read with. Nothing here needs an answerable oracle, so these
    run on whatever a system emitted, a degraded run's report included.
    """
    require_well_formed(claims)
    return (
        *(CheckFinding(CheckFamily.CHAIN, None, problem) for problem in chain_problems(claims)),
        *_declared_constraints(claims, scenario, view),
        *_report_coverage(claims, universe),
    )


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


def _oracle_coverage(oracle: Answerable, claims: Sequence[Claim]) -> list[CheckFinding]:
    findings: list[CheckFinding] = []
    for truth in oracle.impacts:
        if truth.outcome not in UNIVERSAL:
            continue
        assessed = _assessed(claims, truth.key)
        missing = tuple(
            employee
            for employee in oracle.universe
            if employee not in truth.probe and employee not in assessed
        )
        if missing:
            findings.append(
                CheckFinding(
                    CheckFamily.ORACLE_COVERAGE,
                    truth.key,
                    f"{len(missing)} of the {len(oracle.universe) - len(truth.probe)} colleagues "
                    "outside the probe set have no assessment where the truth concludes about "
                    "everyone",
                    missing,
                )
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
        if action.action is not CoverageActionKind.ASSIGN:
            continue  # only an assign names people a clause could ask something of
        impact = action.impact_key
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
    try:
        need = need_of(
            view, impact, scenario.investigated_leave.span, scenario.spec.reference_timezone
        )
    except ValueError:
        need = None  # an artifact the fact base knows nothing of
    if need is None or isinstance(need, Unresolved):
        if cited:
            return "the impact's artifact cannot be read, so which cited clause applies is open"
        return []
    component = need.component
    if isinstance(component, Unresolved) and any(
        constraint.applies_to.kind is EntityKind.COMPONENT for constraint in cited
    ):
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


def _report_coverage(claims: Sequence[Claim], universe: Sequence[EmployeeId]) -> list[CheckFinding]:
    findings: list[CheckFinding] = []
    for action in _actions(claims):
        if action.action not in UNIVERSAL:
            continue
        assessed = _assessed(claims, action.impact_key)
        missing = tuple(employee for employee in universe if employee not in assessed)
        if missing:
            findings.append(
                CheckFinding(
                    CheckFamily.REPORT_COVERAGE,
                    action.impact_key,
                    f"the report concludes {action.action.value} with {len(missing)} of "
                    f"{len(universe)} colleagues unassessed",
                    missing,
                )
            )
    return findings


def _actions(claims: Sequence[Claim]) -> list[CoverageAction]:
    return [claim for claim in claims if isinstance(claim, CoverageAction)]


def _assessed(claims: Sequence[Claim], impact: ImpactKey) -> frozenset[EmployeeId]:
    """Everyone the report assesses for ``impact``."""
    return frozenset(
        claim.employee_id
        for claim in claims
        if isinstance(claim, CandidateAssessment) and claim.impact_key == impact
    )


__all__ = ["CheckFamily", "CheckFinding", "oracle_checks", "report_checks"]
