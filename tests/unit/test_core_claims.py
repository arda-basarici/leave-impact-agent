"""The claim vocabulary: keys computed from payloads, each type's invariants refused at
construction, a match over the union is exhaustive, and the structural checks over a
claim set name every defect."""

from dataclasses import FrozenInstanceError, replace
from typing import assert_never

import pytest

from leaveimpact.core import (
    AssessmentReason,
    AuthorityRule,
    CandidateAssessment,
    Claim,
    ClaimType,
    Constraint,
    CoverageAction,
    CoverageActionKind,
    EvidenceRef,
    Impact,
    ImpactKey,
    ImpactSubtype,
    Observation,
    PredicateName,
    Source,
    SourceConflict,
    Unknown,
    UnknownReason,
    Verdict,
    clause_ref,
    employee_ref,
    event_ref,
    leave_ref,
    require_well_formed,
    structural_problems,
    work_item_ref,
)
from leaveimpact.core.ids import (
    ClaimId,
    claim_id,
    clause_id,
    employee_id,
    event_id,
    leave_id,
    work_item_id,
)

TICKET = work_item_ref(work_item_id(42))
EVENT = event_ref(event_id(9))
CLAUSE = clause_id(11)
LEAVE = leave_id(5)
DEADLINE = ImpactKey(LEAVE, ImpactSubtype.DEADLINE, TICKET)


def _impact(number: int = 1, key: ImpactKey = DEADLINE) -> Impact:
    return Impact(
        claim_id=claim_id(number),
        evidence_refs=(),
        leave_id=key.leave_id,
        subtype=key.subtype,
        artifact=key.artifact,
    )


def _constraint(number: int = 2, *derived: ClaimId) -> Constraint:
    return Constraint(
        claim_id=claim_id(number),
        evidence_refs=(),
        derived_from_claim_ids=derived,
        clause_id=CLAUSE,
        applies_to=TICKET,
    )


def _assessment(
    verdict: Verdict, reasons: tuple[AssessmentReason, ...] = ()
) -> CandidateAssessment:
    return CandidateAssessment(
        claim_id=claim_id(5),
        evidence_refs=(),
        impact_key=DEADLINE,
        employee_id=employee_id(31),
        verdict=verdict,
        reasons=reasons,
    )


def _conflict(
    observations: tuple[Observation, ...], resolved: Observation | None = None
) -> SourceConflict:
    return SourceConflict(
        claim_id=claim_id(3),
        evidence_refs=(),
        entity=TICKET,
        predicate=PredicateName.OWNS_WORK_ITEM,
        observations=observations,
        resolved_value=(resolved or observations[0]).value,
        authority_rule=AuthorityRule.SYSTEM_OF_RECORD_WINS,
    )


def _action(
    kind: CoverageActionKind, *assignees: int, rationale: str | None = None
) -> CoverageAction:
    return CoverageAction(
        claim_id=claim_id(7),
        evidence_refs=(),
        impact_key=DEADLINE,
        action=kind,
        assignee_ids=tuple(employee_id(number) for number in assignees),
        rationale=rationale,
    )


# --- Keys ---------------------------------------------------------------------------


def test_the_key_is_computed_from_the_payload_and_shared_where_the_contract_says() -> None:
    impact = _impact()
    action = _action(CoverageActionKind.UNCOVERED)
    assessment = _assessment(Verdict.VIABLE)
    assert impact.key == action.key == DEADLINE
    assert assessment.key.impact_key == DEADLINE
    assert _constraint().key.clause_id == CLAUSE


def test_an_impact_subtype_admits_only_its_artifact_kinds() -> None:
    ImpactKey(LEAVE, ImpactSubtype.RESPONSIBILITY, TICKET)
    ImpactKey(LEAVE, ImpactSubtype.RESPONSIBILITY, clause_ref(CLAUSE))
    ImpactKey(LEAVE, ImpactSubtype.MEETING, EVENT)
    with pytest.raises(ValueError, match="a deadline impact is about a work_item, got an event"):
        ImpactKey(LEAVE, ImpactSubtype.DEADLINE, EVENT)
    with pytest.raises(ValueError, match="about a clause or a work_item, got an event"):
        ImpactKey(LEAVE, ImpactSubtype.RESPONSIBILITY, EVENT)


def test_a_key_checks_the_namespace_of_its_bare_ids() -> None:
    with pytest.raises(ValueError, match="a leave id has the form leave_NNN"):
        ImpactKey(leave_id(5).replace("leave", "emp"), ImpactSubtype.DEADLINE, TICKET)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="a clause id has the form clause_NNN"):
        replace(_constraint(), clause_id=work_item_id(1))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="an employee id has the form emp_NNN"):
        replace(_assessment(Verdict.VIABLE), employee_id=work_item_id(1))  # type: ignore[arg-type]


def test_a_conflict_or_an_unknown_is_about_the_predicate_subject_kind() -> None:
    with pytest.raises(ValueError, match="has_skill is a fact about an employee, got a work_item"):
        Unknown(
            claim_id=claim_id(4),
            evidence_refs=(),
            subject=TICKET,
            required_fact=PredicateName.HAS_SKILL,
            reason=UnknownReason.ABSENT,
        )
    with pytest.raises(ValueError, match="owns_work_item is a fact about a work_item"):
        replace(_conflict(_two_owners()), entity=employee_ref(employee_id(17)))


# --- Shared fields ----------------------------------------------------------------------


def test_claim_ids_have_their_own_namespace() -> None:
    with pytest.raises(ValueError, match="a claim id has the form claim_NNN, got 'emp_001'"):
        replace(_impact(), claim_id=employee_id(1))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="a claim id has the form claim_NNN, got 'LIA-42'"):
        _constraint(2, ClaimId("LIA-42"))


def test_a_claim_is_not_derived_from_itself_nor_twice_from_one_claim() -> None:
    with pytest.raises(ValueError, match="cannot be derived from itself"):
        _constraint(2, claim_id(2))
    with pytest.raises(ValueError, match="once, not twice"):
        _constraint(2, claim_id(1), claim_id(1))


def test_an_evidence_reference_is_cited_once() -> None:
    evidence = EvidenceRef(Source.JIRA, TICKET, "due_on")
    with pytest.raises(ValueError, match="an evidence reference is cited once"):
        replace(_impact(), evidence_refs=(evidence, evidence))


def test_claims_are_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        _impact().subtype = ImpactSubtype.MEETING  # type: ignore[misc]


def test_entity_refs_are_derived_from_the_key() -> None:
    assert _impact().entity_refs == (leave_ref(LEAVE), TICKET)
    assert _action(CoverageActionKind.ASSIGN, 17, 23).entity_refs == (
        leave_ref(LEAVE),
        TICKET,
        employee_ref(employee_id(17)),
        employee_ref(employee_id(23)),
    )
    assert _assessment(Verdict.VIABLE).entity_refs[0] == employee_ref(employee_id(31))


# --- Per-type invariants ----------------------------------------------------------------


def test_reasons_are_stated_exactly_when_non_viable() -> None:
    _assessment(Verdict.NON_VIABLE, (AssessmentReason.SKILL, AssessmentReason.LOAD))
    with pytest.raises(ValueError, match="a non-viable assessment states its reasons"):
        _assessment(Verdict.NON_VIABLE)
    with pytest.raises(ValueError, match="a viable assessment carries no reasons"):
        _assessment(Verdict.VIABLE, (AssessmentReason.SKILL,))
    with pytest.raises(ValueError, match="an unknown assessment carries no reasons"):
        _assessment(Verdict.UNKNOWN, (AssessmentReason.SKILL,))
    with pytest.raises(ValueError, match="a reason is given once"):
        _assessment(Verdict.NON_VIABLE, (AssessmentReason.SKILL, AssessmentReason.SKILL))


def _two_owners() -> tuple[Observation, Observation]:
    return (
        Observation(Source.JIRA, employee_ref(employee_id(17))),
        Observation(Source.CORPUS, employee_ref(employee_id(3))),
    )


def test_a_conflict_observes_two_distinct_sources_inside_the_domain() -> None:
    _conflict(_two_owners())
    with pytest.raises(ValueError, match="at least two observations"):
        _conflict(_two_owners()[:1])
    with pytest.raises(ValueError, match="observes each source once"):
        _conflict((_two_owners()[0], Observation(Source.JIRA, "emp_099")))
    with pytest.raises(ValueError, match="calendar is outside the evidence domain of owns_work"):
        stray = Observation(Source.CALENDAR, employee_ref(employee_id(3)))
        _conflict((_two_owners()[0], stray))


def test_the_resolved_value_is_one_of_the_observed_values() -> None:
    with pytest.raises(ValueError, match="the resolved value is one of the observed values"):
        _conflict(_two_owners(), Observation(Source.JIRA, employee_ref(employee_id(99))))


def test_assignees_are_named_exactly_when_assigning() -> None:
    _action(CoverageActionKind.ASSIGN, 17, 23, rationale="both hold the skill")
    with pytest.raises(ValueError, match="an assign action names at least one assignee"):
        _action(CoverageActionKind.ASSIGN)
    with pytest.raises(ValueError, match="an uncovered action names nobody"):
        _action(CoverageActionKind.UNCOVERED, 17)
    with pytest.raises(ValueError, match="an assignee is named once"):
        _action(CoverageActionKind.ASSIGN, 17, 17)
    with pytest.raises(ValueError, match="an employee id has the form emp_NNN"):
        replace(_action(CoverageActionKind.ASSIGN, 17), assignee_ids=(work_item_id(1),))  # type: ignore[arg-type]


def test_a_rationale_is_text_or_absent() -> None:
    assert _action(CoverageActionKind.UNKNOWN).rationale is None
    with pytest.raises(ValueError, match="never blank"):
        _action(CoverageActionKind.UNKNOWN, rationale="   ")


# --- The union ------------------------------------------------------------------------------


def _tag(claim: Claim) -> ClaimType:
    match claim:
        case Impact():
            return ClaimType.IMPACT
        case Constraint():
            return ClaimType.CONSTRAINT
        case CandidateAssessment():
            return ClaimType.CANDIDATE_ASSESSMENT
        case SourceConflict():
            return ClaimType.SOURCE_CONFLICT
        case Unknown():
            return ClaimType.UNKNOWN
        case CoverageAction():
            return ClaimType.COVERAGE_ACTION
        case _:
            assert_never(claim)


def test_a_match_over_the_union_is_exhaustive_and_agrees_with_the_class_tag(
    sample_claims: tuple[Claim, ...],
) -> None:
    assert {claim.claim_type for claim in sample_claims} == set(ClaimType)
    for claim in sample_claims:
        assert _tag(claim) is claim.claim_type


# --- The claim set ---------------------------------------------------------------------------


def test_the_sample_set_is_well_formed(sample_claims: tuple[Claim, ...]) -> None:
    assert structural_problems(sample_claims) == ()
    require_well_formed(sample_claims)


def test_a_reused_claim_id_is_a_problem() -> None:
    assert structural_problems((_impact(1), _constraint(1))) == ("claim_001 is used by two claims",)


def test_a_derivation_from_outside_the_set_is_a_problem() -> None:
    assert structural_problems((_constraint(2, claim_id(9)),)) == (
        "claim_002 is derived from claim_009, which is not in the set",
    )


def test_a_provenance_cycle_is_a_problem() -> None:
    two_cycle = (_constraint(2, claim_id(3)), _constraint(3, claim_id(2)))
    assert structural_problems(two_cycle) == (
        "provenance cycle: claim_002 -> claim_003 -> claim_002",
        "claim_003 and claim_002 are two constraint claims with one grading key",
    )
    chain = (_constraint(2, claim_id(3)), _constraint(3, claim_id(4)), _constraint(4))
    assert [p for p in structural_problems(chain) if p.startswith("provenance")] == []


def test_one_grading_key_per_type_and_the_same_key_across_types_is_fine() -> None:
    assert structural_problems((_impact(1), _impact(2))) == (
        "claim_002 and claim_001 are two impact claims with one grading key",
    )
    assert structural_problems((_impact(1), _action(CoverageActionKind.UNCOVERED))) == ()


def test_require_well_formed_lists_every_problem() -> None:
    expected = r"not well-formed:\n  claim_001 is used by two claims\n  claim_001 and"
    with pytest.raises(ValueError, match=expected):
        require_well_formed((_impact(1), _impact(1)))
