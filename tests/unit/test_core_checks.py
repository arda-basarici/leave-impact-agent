"""The chain checks over the shared claim set: the coherent story passes, and each break in a
chain — an unknown assessment with no unknown claim or an ill-shaped one, an unknown action
resting on nothing unknown, an assign without a viable assessment, an uncovered beside a
viable, a conflict resolved against the record, an unanswered impact — is named; the
completeness check needs the universe and says who was never assessed."""

from dataclasses import replace

import pytest

from leaveimpact.core import (
    AssessmentReason,
    AuthorityRule,
    CandidateAssessment,
    Claim,
    CoverageAction,
    CoverageActionKind,
    Impact,
    PredicateName,
    SourceConflict,
    Unknown,
    UnknownReason,
    Verdict,
    chain_problems,
    completeness_problems,
    employee_ref,
    work_item_ref,
)
from leaveimpact.core.ids import claim_id, employee_id, work_item_id
from tests.unit.conftest import CANDIDATE_UNRECORDED, CANDIDATE_UNSKILLED, LEAVER, STALE_OWNER


def _of[T: Claim](claims: tuple[Claim, ...], kind: type[T]) -> T:
    return next(claim for claim in claims if isinstance(claim, kind))


def _swap(claims: tuple[Claim, ...], old: Claim, new: Claim) -> tuple[Claim, ...]:
    return tuple(new if claim is old else claim for claim in claims)


def test_the_coherent_story_has_no_chain_problems(sample_claims: tuple[Claim, ...]) -> None:
    assert chain_problems(sample_claims) == ()


def test_an_unknown_assessment_derives_from_an_unknown_claim_the_rule_could_ask(
    sample_claims: tuple[Claim, ...],
) -> None:
    assessment = _of(sample_claims, CandidateAssessment)
    orphan = replace(assessment, derived_from_claim_ids=())
    assert chain_problems(_swap(sample_claims, assessment, orphan)) == (
        "claim_005 is unknown but derives from no unknown claim",
    )
    unknown = _of(sample_claims, Unknown)
    # A question about someone else is not this assessment's unknown.
    about_another = replace(unknown, subject=employee_ref(CANDIDATE_UNSKILLED))
    problems = chain_problems(_swap(sample_claims, unknown, about_another))
    assert problems == (
        "claim_005 derives from claim_004, which is not a question the viability rule asks "
        "about emp_023 for ticket_042",
    )
    # A question about the artifact on a predicate the rule reads there is fine.
    about_the_ticket = replace(
        unknown,
        subject=work_item_ref(work_item_id(42)),
        required_fact=PredicateName.IN_COMPONENT,
        reason=UnknownReason.INACCESSIBLE,
        evidence_refs=(),
    )
    assert chain_problems(_swap(sample_claims, unknown, about_the_ticket)) == ()
    # The artifact on a predicate the rule asks of people is not.
    wrong_predicate = replace(about_the_ticket, required_fact=PredicateName.OWNS_WORK_ITEM)
    assert len(chain_problems(_swap(sample_claims, unknown, wrong_predicate))) == 1


def test_an_unknown_action_rests_on_an_unknown_assessment(
    sample_claims: tuple[Claim, ...],
) -> None:
    action = _of(sample_claims, CoverageAction)
    # Derived only from the non-viable assessment: nothing unknown underneath.
    unsupported = replace(action, derived_from_claim_ids=(claim_id(6),))
    assert chain_problems(_swap(sample_claims, action, unsupported)) == (
        "claim_007 is unknown but derives from no unknown assessment for its impact",
    )


def test_an_assign_names_only_the_viable_and_an_uncovered_names_nobody_viable(
    sample_claims: tuple[Claim, ...],
) -> None:
    action = _of(sample_claims, CoverageAction)
    assigned = replace(
        action,
        action=CoverageActionKind.ASSIGN,
        assignee_ids=(CANDIDATE_UNRECORDED, STALE_OWNER),
    )
    assert chain_problems(_swap(sample_claims, action, assigned)) == (
        "claim_007 assigns emp_003 without a viable assessment",
        "claim_007 assigns emp_023 without a viable assessment",
    )
    unskilled = next(
        claim
        for claim in sample_claims
        if isinstance(claim, CandidateAssessment) and claim.employee_id == CANDIDATE_UNSKILLED
    )
    viable = replace(unskilled, verdict=Verdict.VIABLE, reasons=())
    uncovered = replace(action, action=CoverageActionKind.UNCOVERED)
    with_viable = _swap(_swap(sample_claims, unskilled, viable), action, uncovered)
    assert chain_problems(with_viable) == (
        "claim_007 is uncovered while emp_031 is assessed viable",
    )
    # The weak form, by design: uncovered with no viable assessment in the report passes.
    assert chain_problems(_swap(sample_claims, action, uncovered)) == ()


def test_a_conflict_resolves_to_the_record_under_the_rule_it_cites(
    sample_claims: tuple[Claim, ...],
) -> None:
    conflict = _of(sample_claims, SourceConflict)
    stale_wins = replace(conflict, resolved_value=employee_ref(STALE_OWNER))
    (problem,) = chain_problems(_swap(sample_claims, conflict, stale_wins))
    assert problem.startswith("claim_003 resolves owns_work_item to")
    assert "while the system of record jira observes" in problem
    assert conflict.authority_rule is AuthorityRule.SYSTEM_OF_RECORD_WINS
    assert employee_ref(LEAVER) == conflict.resolved_value


def test_every_impact_is_answered_by_an_action_and_every_action_answers_an_impact(
    sample_claims: tuple[Claim, ...],
) -> None:
    impact = _of(sample_claims, Impact)
    action = _of(sample_claims, CoverageAction)
    without_action = tuple(claim for claim in sample_claims if claim is not action)
    assert chain_problems(without_action) == ("claim_001 has no coverage action",)
    without_impact = tuple(claim for claim in sample_claims if claim is not impact)
    assert chain_problems(without_impact) == (
        "claim_007 answers an impact the report does not claim",
    )


def test_completeness_needs_the_universe_and_names_who_was_never_assessed(
    sample_claims: tuple[Claim, ...],
) -> None:
    assessed = (CANDIDATE_UNRECORDED, CANDIDATE_UNSKILLED)
    assert completeness_problems(sample_claims, assessed) == ()
    universe = (*assessed, LEAVER, employee_id(40))
    assert completeness_problems(sample_claims, universe) == (
        "claim_001 has no assessment for emp_017, emp_040 of the candidate universe",
    )


@pytest.mark.parametrize("verdict", [Verdict.VIABLE, Verdict.NON_VIABLE])
def test_a_settled_assessment_needs_no_unknown_claim(
    sample_claims: tuple[Claim, ...], verdict: Verdict
) -> None:
    assessment = _of(sample_claims, CandidateAssessment)
    settled = replace(
        assessment,
        verdict=verdict,
        reasons=() if verdict is Verdict.VIABLE else (AssessmentReason.SKILL,),
        derived_from_claim_ids=(),
    )
    problems = chain_problems(_swap(sample_claims, assessment, settled))
    # Only the unknown action's chain complains, since its unknown assessment is gone.
    assert problems == (
        "claim_007 is unknown but derives from no unknown assessment for its impact",
    )
