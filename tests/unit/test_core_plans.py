"""The plan side: an assign action is checked per requirement against the viable assignees in
the report, an unknown assignee is not viable for an assign, non-assign actions have no
cardinality, and the truth's expected outcome follows the V / U / n rule over the whole
candidate universe."""

import pytest

from leaveimpact.core import (
    AssessmentReason,
    CandidateAssessment,
    CoverageAction,
    CoverageActionKind,
    EvidenceRef,
    ImpactKey,
    ResolvedRequirement,
    RunCondition,
    Source,
    Verdict,
    Violation,
    ViolationKind,
    assess_impact,
    clause_ref,
    expected_action,
    plan_violations,
    required_count,
)
from leaveimpact.core.ids import ClaimId, EmployeeId, claim_id
from tests.unit import world_fixture as w

NORMAL = RunCondition.all_reachable()
VIEW = w.WORLD.at(w.NOW, NORMAL)
TWO_EMPLOYEES = ResolvedRequirement(
    w.TWO_EMPLOYEES_CLAUSE,
    w.TWO_KAFKA_EMPLOYEES,
    w.requires(w.TWO_EMPLOYEES_CLAUSE, w.TWO_KAFKA_EMPLOYEES),
)
ONE_KAFKA = ResolvedRequirement(
    w.KAFKA_CLAUSE, w.ONE_KAFKA, w.requires(w.KAFKA_CLAUSE, w.ONE_KAFKA)
)


def assessment(
    impact: ImpactKey, who: EmployeeId, verdict: Verdict, number: ClaimId
) -> CandidateAssessment:
    return CandidateAssessment(
        claim_id=number,
        evidence_refs=(),
        impact_key=impact,
        employee_id=who,
        verdict=verdict,
        reasons=(AssessmentReason.SKILL,) if verdict is Verdict.NON_VIABLE else (),
    )


def assign(impact: ImpactKey, *assignees: EmployeeId) -> CoverageAction:
    return CoverageAction(
        claim_id=claim_id(99),
        evidence_refs=(),
        impact_key=impact,
        action=CoverageActionKind.ASSIGN,
        assignee_ids=assignees,
    )


REPORT = (
    assessment(w.MEETING, w.DENIZ, Verdict.VIABLE, claim_id(1)),
    assessment(w.MEETING, w.BOB, Verdict.NON_VIABLE, claim_id(2)),
    assessment(w.MEETING, w.CAN, Verdict.UNKNOWN, claim_id(3)),
    assessment(w.DEADLINE, w.DENIZ, Verdict.VIABLE, claim_id(4)),
)


def test_a_plan_that_holds_has_no_violations() -> None:
    assert plan_violations(assign(w.DEADLINE, w.DENIZ), (ONE_KAFKA,), REPORT) == ()
    assert plan_violations(assign(w.DEADLINE, w.DENIZ), (), REPORT) == ()


def test_cardinality_is_checked_per_requirement_with_the_count_a_minimum() -> None:
    violations = plan_violations(assign(w.MEETING, w.DENIZ), (TWO_EMPLOYEES,), REPORT)
    assert violations == (
        Violation(
            w.MEETING,
            ViolationKind.INSUFFICIENT_CARDINALITY,
            w.TWO_EMPLOYEES_CLAUSE,
            "clause_013 asks for 2, 1 viable assigned",
        ),
    )
    three_viable = (
        REPORT[0],
        assessment(w.MEETING, w.ALICE, Verdict.VIABLE, claim_id(5)),
        assessment(w.MEETING, w.BOB, Verdict.VIABLE, claim_id(6)),
    )
    three_named = assign(w.MEETING, w.DENIZ, w.ALICE, w.BOB)
    assert plan_violations(three_named, (TWO_EMPLOYEES,), three_viable) == ()


def test_an_unknown_or_non_viable_assignee_and_a_missing_assessment_are_violations() -> None:
    violations = plan_violations(
        assign(w.MEETING, w.DENIZ, w.BOB, w.CAN, w.ALICE), (TWO_EMPLOYEES,), REPORT
    )
    # Assignees are canonical by id on the claim: Bob, Alice, Deniz, Can.
    assert [violation.kind for violation in violations] == [
        ViolationKind.NON_VIABLE_ASSIGNEE,
        ViolationKind.MISSING_ASSESSMENT,
        ViolationKind.NON_VIABLE_ASSIGNEE,
        ViolationKind.INSUFFICIENT_CARDINALITY,
    ]
    assert violations[1].detail == "emp_017 is assigned without an assessment"
    assert violations[2].detail == "emp_031 is assigned with unknown verdict"


def test_an_assign_with_no_clause_still_needs_one_viable_assignee() -> None:
    non_viable, short = plan_violations(assign(w.MEETING, w.BOB), (), REPORT)
    assert non_viable.kind is ViolationKind.NON_VIABLE_ASSIGNEE
    assert short.kind is ViolationKind.INSUFFICIENT_CARDINALITY
    assert short.clause_id is None


def test_non_assign_actions_have_no_cardinality() -> None:
    for kind in (CoverageActionKind.UNCOVERED, CoverageActionKind.UNKNOWN):
        action = CoverageAction(
            claim_id=claim_id(98), evidence_refs=(), impact_key=w.MEETING, action=kind
        )
        assert plan_violations(action, (TWO_EMPLOYEES,), REPORT) == ()


def test_the_required_count_is_the_largest_applicable_or_one() -> None:
    assert required_count(()) == 1
    assert required_count((ONE_KAFKA, TWO_EMPLOYEES)) == 2


def test_the_expected_action_follows_the_rule_over_the_whole_universe() -> None:
    meeting = assess_impact(
        VIEW, w.MEETING, w.EVERYONE, w.CONSTRAINTS, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE
    )
    verdicts = [assessment.verdict for assessment in meeting]
    # Deniz alone is viable against a two-person clause in a complete world: uncovered.
    assert (
        expected_action(verdicts, required_count((TWO_EMPLOYEES,))) is CoverageActionKind.UNCOVERED
    )
    deadline = assess_impact(
        VIEW, w.DEADLINE, w.EVERYONE, w.CONSTRAINTS, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE
    )
    assert (
        expected_action(
            [assessment.verdict for assessment in deadline], required_count((ONE_KAFKA,))
        )
        is CoverageActionKind.ASSIGN
    )
    # With the tracker down nobody is settled except the leaver: an epistemic limit, not uncovered.
    jira_down = w.WORLD.at(w.NOW, NORMAL.without(Source.JIRA))
    degraded = assess_impact(
        jira_down, w.DEADLINE, w.EVERYONE, w.CONSTRAINTS, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE
    )
    assert expected_action([a.verdict for a in degraded], 1) is CoverageActionKind.UNKNOWN
    with pytest.raises(ValueError, match="at least one person, got 0"):
        expected_action([], 0)


def test_evidence_of_a_resolved_requirement_names_its_clause() -> None:
    assert ONE_KAFKA.fact.evidence == EvidenceRef(Source.CORPUS, clause_ref(w.KAFKA_CLAUSE))
