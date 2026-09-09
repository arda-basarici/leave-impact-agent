"""The chain checks: whether a report's claims hang together, read from the report alone.

The word ``unknown`` appears at three levels with one relation between them (DESIGN,
"Three coverage outcomes, and the unknowns chain"): an unknown claim records a missing
fact and its reason, an assessment whose verdict is unknown derives from such claims,
a coverage action whose action is unknown rests on such assessments. These checks
verify that chain and its siblings inside one report — an assign action's assignees
each hold a viable assessment, an uncovered action holds no viable one, a conflict
resolved to the system of record's observation, every impact answered by exactly one
action — and they are named for what they know: nothing about the world. What a
report claims is compared with the fact base by the evaluator, which is grading; a
report that is internally incoherent is a graded outcome too, which is why these
return problems rather than raise, like the structural check they extend.

Two checks look alike and are not. ``chain_problems`` is report-internal: an
uncovered action passes it when the report holds no viable assessment, which proves
nothing about the world, since a report that simply stopped assessing would pass too.
``completeness_problems`` takes the candidate universe — the organization, never the
``must_assess`` set — and lists every member without an assessment for each impact,
so ``uncovered`` is never inferred from a report that did not look. The evaluator runs
it with the org; the generator runs it against its own truth.

An unknown assessment's unknown claims are checked for shape, not for truth: each is
about the candidate, or about the impact's artifact, or about a clause, on a predicate
the viability rule reads for that subject — and a clause only when the report's own
constraint claims cite it for something that could apply to the impact, the artifact
itself or, for a work item, a component. Whether the ticket really belongs to that
component is truth; that the report has not justified an unknown with an unrelated
policy clause is coherence. Which criterion was actually unresolved is not in the
report, since an unknown assessment carries no reasons, and matching it against the
fact base is the evaluator's.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from leaveimpact.core.authority import resolve
from leaveimpact.core.claims import (
    CandidateAssessment,
    Claim,
    Constraint,
    CoverageAction,
    CoverageActionKind,
    Impact,
    ImpactKey,
    SourceConflict,
    Unknown,
    Verdict,
)
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import ClaimId, EmployeeId
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import EntityRef, clause_ref, employee_ref

ABOUT_THE_CANDIDATE: frozenset[PredicateName] = frozenset(
    {
        PredicateName.HAS_SKILL,
        PredicateName.MEMBER_OF_COMPONENT,
        PredicateName.ON_LEAVE,
        PredicateName.EMPLOYED_AS,
    }
)
"""The predicates the viability rule asks about the candidate."""

ABOUT_THE_ARTIFACT: frozenset[PredicateName] = frozenset(
    {PredicateName.IN_COMPONENT, PredicateName.SCHEDULED_AT, PredicateName.ATTENDS_EVENT}
)
"""The predicates the viability rule asks about the impact's artifact."""


def chain_problems(claims: Sequence[Claim]) -> tuple[str, ...]:
    """Every way ``claims`` fail to hang together as one report; empty when the chains hold.

    Assumes the set is structurally well-formed (``structural_problems`` is empty): claim
    ids resolve and grading keys are unique. Checked: an unknown assessment derives from
    at least one unknown claim and only from ones shaped as the rule emits; an unknown
    action derives from at least one unknown assessment for its impact; an assign
    action's assignees each hold a viable assessment for its impact; an uncovered action
    holds no viable assessment for its impact; a conflict resolved to the system of
    record's observation under the rule it cites; every impact has exactly one coverage
    action and every action an impact.
    """
    by_id: dict[ClaimId, Claim] = {claim.claim_id: claim for claim in claims}
    assessments = [claim for claim in claims if isinstance(claim, CandidateAssessment)]
    actions = [claim for claim in claims if isinstance(claim, CoverageAction)]
    impacts = [claim for claim in claims if isinstance(claim, Impact)]
    constraints = [claim for claim in claims if isinstance(claim, Constraint)]
    problems: list[str] = []
    for assessment in assessments:
        problems.extend(_unknown_assessment_problems(assessment, by_id, constraints))
    for action in actions:
        problems.extend(_action_problems(action, assessments, by_id))
    for claim in claims:
        if isinstance(claim, SourceConflict):
            problems.extend(_conflict_problems(claim))
    problems.extend(_answer_problems(impacts, actions))
    return tuple(problems)


def completeness_problems(
    claims: Sequence[Claim], universe: Iterable[EmployeeId]
) -> tuple[str, ...]:
    """Every candidate of ``universe`` without an assessment for an impact the report names.

    The one check that needs something outside the report — who could have been
    assessed — and the reason ``uncovered`` is never inferred from a report that stopped
    assessing.

    >>> completeness_problems((), ())
    ()
    """
    assessed: dict[ImpactKey, set[EmployeeId]] = {}
    for claim in claims:
        if isinstance(claim, CandidateAssessment):
            assessed.setdefault(claim.impact_key, set()).add(claim.employee_id)
    candidates = tuple(universe)
    problems: list[str] = []
    for claim in claims:
        if not isinstance(claim, Impact):
            continue
        missing = [who for who in candidates if who not in assessed.get(claim.key, set())]
        if missing:
            problems.append(
                f"{claim.claim_id} has no assessment for {', '.join(missing)} "
                f"of the candidate universe"
            )
    return tuple(problems)


def _unknown_assessment_problems(
    assessment: CandidateAssessment,
    by_id: Mapping[ClaimId, Claim],
    constraints: Sequence[Constraint],
) -> list[str]:
    if assessment.verdict is not Verdict.UNKNOWN:
        return []
    unknowns = [
        claim
        for claim in (by_id[other] for other in assessment.derived_from_claim_ids)
        if isinstance(claim, Unknown)
    ]
    if not unknowns:
        return [f"{assessment.claim_id} is unknown but derives from no unknown claim"]
    candidate = employee_ref(assessment.employee_id)
    artifact = assessment.impact_key.artifact
    cited = {
        clause_ref(constraint.clause_id)
        for constraint in constraints
        if _could_apply(constraint.applies_to, artifact)
    }
    return [
        f"{assessment.claim_id} derives from {unknown.claim_id}, which is not a question the "
        f"viability rule asks about {assessment.employee_id} for {artifact.id}"
        for unknown in unknowns
        if not _asked_by_the_rule(unknown, candidate, artifact, cited)
    ]


def _asked_by_the_rule(
    unknown: Unknown, candidate: EntityRef, artifact: EntityRef, cited: set[EntityRef]
) -> bool:
    if unknown.subject == candidate:
        return unknown.required_fact in ABOUT_THE_CANDIDATE
    if unknown.subject == artifact:
        return unknown.required_fact in ABOUT_THE_ARTIFACT
    if unknown.subject in cited:
        return unknown.required_fact is PredicateName.REQUIRES
    return False


def _could_apply(applies_to: EntityRef, artifact: EntityRef) -> bool:
    """Whether a constraint's target could be this impact's, read from the report alone: the
    artifact itself, or a component when the artifact is a work item — whether the ticket is
    in that component is the fact base's to say."""
    if applies_to == artifact:
        return True
    return artifact.kind is EntityKind.WORK_ITEM and applies_to.kind is EntityKind.COMPONENT


def _action_problems(
    action: CoverageAction,
    assessments: Sequence[CandidateAssessment],
    by_id: Mapping[ClaimId, Claim],
) -> list[str]:
    for_impact = {
        assessment.employee_id: assessment
        for assessment in assessments
        if assessment.impact_key == action.impact_key
    }
    match action.action:
        case CoverageActionKind.ASSIGN:
            return [
                f"{action.claim_id} assigns {assignee} without a viable assessment"
                for assignee in action.assignee_ids
                if assignee not in for_impact or for_impact[assignee].verdict is not Verdict.VIABLE
            ]
        case CoverageActionKind.UNCOVERED:
            viable = sorted(
                who
                for who, assessment in for_impact.items()
                if assessment.verdict is Verdict.VIABLE
            )
            if viable:
                return [
                    f"{action.claim_id} is uncovered while {', '.join(viable)} "
                    f"{'is' if len(viable) == 1 else 'are'} assessed viable"
                ]
            return []
        case CoverageActionKind.UNKNOWN:
            rests_on_unknown = any(
                isinstance(claim, CandidateAssessment)
                and claim.impact_key == action.impact_key
                and claim.verdict is Verdict.UNKNOWN
                for claim in (by_id[other] for other in action.derived_from_claim_ids)
            )
            if not rests_on_unknown:
                return [
                    f"{action.claim_id} is unknown but derives from no unknown assessment "
                    f"for its impact"
                ]
            return []


def _conflict_problems(conflict: SourceConflict) -> list[str]:
    resolution = resolve(conflict.predicate, conflict.observations)
    problems: list[str] = []
    if conflict.resolved_value != resolution.value:
        problems.append(
            f"{conflict.claim_id} resolves {conflict.predicate.value} to "
            f"{conflict.resolved_value!r} while the system of record "
            f"{resolution.winner.source.value} observes {resolution.value!r}"
        )
    if conflict.authority_rule is not resolution.rule:
        problems.append(
            f"{conflict.claim_id} cites {conflict.authority_rule.value} where the table "
            f"applies {resolution.rule.value}"
        )
    return problems


def _answer_problems(impacts: Sequence[Impact], actions: Sequence[CoverageAction]) -> list[str]:
    answered = {action.impact_key: action for action in actions}
    raised = {impact.key: impact for impact in impacts}
    problems = [
        f"{impact.claim_id} has no coverage action"
        for impact in impacts
        if impact.key not in answered
    ]
    problems.extend(
        f"{action.claim_id} answers an impact the report does not claim"
        for action in actions
        if action.impact_key not in raised
    )
    return problems
