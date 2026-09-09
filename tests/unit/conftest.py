"""Shared fixtures for the unit level: one well-formed claim set that exercises all six types.

The set tells one small story — a leave affects a ticket, a clause constrains it, a
runbook disagrees with the tracker about the owner, one candidate's skills are
unrecorded, two candidates are assessed, and the plan admits it does not know — so the
tests for the vocabulary, the structural checks and the codec all read the same claims.
"""

from datetime import date

import pytest

from leaveimpact.core import (
    AssessmentReason,
    AuthorityRule,
    CandidateAssessment,
    Claim,
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
    leave_ref,
    work_item_ref,
)
from leaveimpact.core.ids import claim_id, clause_id, employee_id, leave_id, work_item_id

TICKET = work_item_ref(work_item_id(42))
LEAVE = leave_id(5)
LEAVER = employee_id(17)
CANDIDATE_UNRECORDED = employee_id(23)
CANDIDATE_UNSKILLED = employee_id(31)
STALE_OWNER = employee_id(3)
DEADLINE_KEY = ImpactKey(LEAVE, ImpactSubtype.DEADLINE, TICKET)


@pytest.fixture
def sample_claims() -> tuple[Claim, ...]:
    return (
        Impact(
            claim_id=claim_id(1),
            evidence_refs=(
                EvidenceRef(Source.JIRA, TICKET, "due_on"),
                EvidenceRef(Source.FRAPPE, leave_ref(LEAVE)),
            ),
            leave_id=LEAVE,
            subtype=ImpactSubtype.DEADLINE,
            artifact=TICKET,
        ),
        Constraint(
            claim_id=claim_id(2),
            evidence_refs=(EvidenceRef(Source.CORPUS, clause_ref(clause_id(11))),),
            clause_id=clause_id(11),
            applies_to=TICKET,
        ),
        SourceConflict(
            claim_id=claim_id(3),
            evidence_refs=(
                EvidenceRef(Source.JIRA, TICKET, "owner_id"),
                EvidenceRef(Source.CORPUS, clause_ref(clause_id(12))),
            ),
            entity=TICKET,
            predicate=PredicateName.OWNS_WORK_ITEM,
            observations=(
                Observation(Source.JIRA, employee_ref(LEAVER)),
                Observation(Source.CORPUS, employee_ref(STALE_OWNER)),
            ),
            resolved_value=employee_ref(LEAVER),
            authority_rule=AuthorityRule.SYSTEM_OF_RECORD_WINS,
        ),
        Unknown(
            claim_id=claim_id(4),
            evidence_refs=(
                EvidenceRef(Source.FRAPPE, employee_ref(CANDIDATE_UNRECORDED), "skills"),
            ),
            subject=employee_ref(CANDIDATE_UNRECORDED),
            required_fact=PredicateName.HAS_SKILL,
            reason=UnknownReason.ABSENT,
        ),
        CandidateAssessment(
            claim_id=claim_id(5),
            evidence_refs=(),
            derived_from_claim_ids=(claim_id(4),),
            impact_key=DEADLINE_KEY,
            employee_id=CANDIDATE_UNRECORDED,
            verdict=Verdict.UNKNOWN,
        ),
        CandidateAssessment(
            claim_id=claim_id(6),
            evidence_refs=(
                EvidenceRef(Source.FRAPPE, employee_ref(CANDIDATE_UNSKILLED), "skills"),
            ),
            impact_key=DEADLINE_KEY,
            employee_id=CANDIDATE_UNSKILLED,
            verdict=Verdict.NON_VIABLE,
            reasons=(AssessmentReason.SKILL,),
        ),
        CoverageAction(
            claim_id=claim_id(7),
            evidence_refs=(),
            derived_from_claim_ids=(claim_id(5), claim_id(6)),
            impact_key=DEADLINE_KEY,
            action=CoverageActionKind.UNKNOWN,
            rationale="Deniz's skills are not on record; nobody else qualifies — İK to confirm.",
        ),
    )


@pytest.fixture
def a_date() -> date:
    return date(2026, 9, 14)
