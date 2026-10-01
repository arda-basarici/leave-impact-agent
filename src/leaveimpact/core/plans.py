"""The plan side of the rules: whether a coverage action satisfies its requirements, and which
outcome the truth expects.

A requirement's count lives here and nowhere else (DESIGN, "What a valid answer is"): the
viability rule judges people, this module judges the plan made of them. Both functions
return records rather than raise, because a defective plan is a graded outcome the
evaluator records, not a crash.

``plan_violations`` reads one coverage action against the requirements that apply to
its impact and the verdicts held for that impact, by employee. Whose verdicts they are
is the caller's question and the reason the rule takes verdicts and not assessment
claims: a report checked against its own assessments is coherence, a report checked
against the truth's verdicts is validity, and the truth's assessments are not claims
(they carry no claim id and no evidence references), so one rule serves both without a
claim invented to carry a verdict. ``verdicts_by_employee`` reads the mapping off a
report. An assign action is checked per requirement — the assignees holding a viable
verdict must number at least the requirement's count — with an implicit minimum of one
when no clause applies. Under the current conjunctive model a viable assignee satisfies
every applicable criterion, so the per-requirement loop reduces to the largest count;
that is a property of the present requirement semantics, kept as a loop so a clause
with its own criteria needs no restructuring. An assignee with no verdict is a
violation of its own, and an unknown assignee is not viable for an assign, since assign
is a positive conclusion nobody unknown can carry. ``uncovered`` and ``unknown`` actions
have no cardinality to violate; their consistency with the assessments is the chain
checks' question.

``expected_action`` is the truth side. Over an explicit candidate universe — the
organization, never the ``must_assess`` set — with ``V`` viable and ``U`` unknown
against the required count ``n``: ``V ≥ n`` is assign, ``V + U < n`` is uncovered
(the evidence suffices and nobody qualifies), anything else is unknown (an epistemic
limit). The expected action is truth; an expected assignee set is not, because "the
best person" has no exact truth unless an optimization rule is declared, and none is.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.claims import (
    CandidateAssessment,
    CoverageAction,
    CoverageActionKind,
    ImpactKey,
    Verdict,
)
from leaveimpact.core.ids import ClauseId, EmployeeId
from leaveimpact.core.viability import ResolvedRequirement


class ViolationKind(StrEnum):
    """How a plan fails its requirements; a member is the wire format."""

    INSUFFICIENT_CARDINALITY = "insufficient_cardinality"
    MISSING_ASSESSMENT = "missing_assessment"
    NON_VIABLE_ASSIGNEE = "non_viable_assignee"


@dataclass(frozen=True, slots=True)
class Violation:
    """One way a coverage action fails: which impact, what kind, under which clause if any."""

    impact: ImpactKey
    kind: ViolationKind
    clause_id: ClauseId | None
    detail: str


def required_count(requirements: Iterable[ResolvedRequirement]) -> int:
    """The people a plan must name: the largest applicable count, one when no clause applies."""
    return max((resolved.requirement.count for resolved in requirements), default=1)


def verdicts_by_employee(
    impact: ImpactKey, assessments: Iterable[CandidateAssessment]
) -> dict[EmployeeId, Verdict]:
    """The verdicts ``assessments`` hold for ``impact``, by employee; other impacts' are left out.

    The report side of ``plan_violations``' input. A well-formed report holds one
    assessment per impact and employee, so nothing is lost in the mapping.
    """
    return {
        assessment.employee_id: assessment.verdict
        for assessment in assessments
        if assessment.impact_key == impact
    }


def plan_violations(
    action: CoverageAction,
    requirements: Sequence[ResolvedRequirement],
    verdicts: Mapping[EmployeeId, Verdict],
) -> tuple[Violation, ...]:
    """Every way ``action`` fails ``requirements`` given the ``verdicts`` held for its impact,
    by employee; empty when the plan holds. Only an assign action can violate cardinality.

    ``verdicts`` are for the action's own impact, the caller's to scope: the report's
    assessments (``verdicts_by_employee``) or the truth's. An assignee the mapping does
    not hold is a missing assessment, whatever the reason it is not there.
    """
    if action.action is not CoverageActionKind.ASSIGN:
        return ()
    impact = action.impact_key
    violations: list[Violation] = []
    viable: list[EmployeeId] = []
    for assignee in action.assignee_ids:
        verdict = verdicts.get(assignee)
        if verdict is None:
            violations.append(
                Violation(
                    impact,
                    ViolationKind.MISSING_ASSESSMENT,
                    None,
                    f"{assignee} is assigned without an assessment",
                )
            )
        elif verdict is not Verdict.VIABLE:
            violations.append(
                Violation(
                    impact,
                    ViolationKind.NON_VIABLE_ASSIGNEE,
                    None,
                    f"{assignee} is assigned with {verdict.value} verdict",
                )
            )
        else:
            viable.append(assignee)
    if not requirements and not viable:
        violations.append(
            Violation(
                impact,
                ViolationKind.INSUFFICIENT_CARDINALITY,
                None,
                "an assign action names at least one viable assignee",
            )
        )
    for resolved in requirements:
        needed = resolved.requirement.count
        if len(viable) < needed:
            violations.append(
                Violation(
                    impact,
                    ViolationKind.INSUFFICIENT_CARDINALITY,
                    resolved.clause_id,
                    f"{resolved.clause_id} asks for {needed}, {len(viable)} viable assigned",
                )
            )
    return tuple(violations)


def expected_action(verdicts: Iterable[Verdict], required: int) -> CoverageActionKind:
    """The coverage outcome the truth expects from the verdicts over the candidate universe.

    >>> expected_action([Verdict.VIABLE, Verdict.NON_VIABLE], 1)
    <CoverageActionKind.ASSIGN: 'assign'>
    >>> expected_action([Verdict.VIABLE, Verdict.NON_VIABLE], 2)
    <CoverageActionKind.UNCOVERED: 'uncovered'>
    >>> expected_action([Verdict.VIABLE, Verdict.UNKNOWN], 2)
    <CoverageActionKind.UNKNOWN: 'unknown'>
    """
    if required < 1:
        raise ValueError(f"a plan requires at least one person, got {required}")
    counted = list(verdicts)
    viable = sum(verdict is Verdict.VIABLE for verdict in counted)
    unknown = sum(verdict is Verdict.UNKNOWN for verdict in counted)
    if viable >= required:
        return CoverageActionKind.ASSIGN
    if viable + unknown < required:
        return CoverageActionKind.UNCOVERED
    return CoverageActionKind.UNKNOWN
