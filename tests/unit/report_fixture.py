"""A truthful report built from the oracle, for the evaluator's tests to grade and then to break.

Test infrastructure. The evaluator's tests need a report that is right in every part, so
that each test can change one thing and assert the one row that moves. Writing thirty such
reports by hand would be the tests' largest source of error, so this reads the oracle and
states what it concludes in the claim vocabulary: an impact per expected impact, the
expected constraints, an assessment of every organization member for each impact with the
unknown claims an unknown verdict derives from, the expected conflicts with the
observations the view holds, and one coverage action per impact that names viable people
when the outcome is assign.

It is not the rules-only baseline. That system reads the world through the ports and may
not see the oracle; this reads the answer and exists to be graded as correct.

The truthful report cites nothing, and is never read as citation-perfect: a claim with no
citation is neither. ``citing`` is the same report with each claim citing exactly the
records its own proof can be cited by, read off a replay of it, so every citation it makes
resolves, was retrieved and is used.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import replace

from leaveimpact.core import (
    SOURCE_BY_TARGET_KIND,
    CandidateAssessment,
    Claim,
    Constraint,
    CoverageAction,
    CoverageActionKind,
    EvidenceRef,
    Impact,
    SourceConflict,
    Unknown,
    UnknownKey,
    Verdict,
    conflicts_in,
)
from leaveimpact.core.ids import ClaimId, claim_id
from leaveimpact.evaluator.citations import citable_witnesses
from leaveimpact.evaluator.oracle import Answerable
from leaveimpact.evaluator.replay import ClaimGrounding


def truthful_report(oracle: Answerable) -> tuple[Claim, ...]:
    """A complete, coherent report stating exactly what ``oracle`` concludes."""
    numbers = iter(range(1, 10_000))

    def mint() -> ClaimId:
        return claim_id(next(numbers))

    claims: list[Claim] = [
        Impact(
            claim_id=mint(),
            evidence_refs=(),
            leave_id=truth.key.leave_id,
            subtype=truth.key.subtype,
            artifact=truth.key.artifact,
        )
        for truth in oracle.impacts
    ]
    claims.extend(
        Constraint(
            claim_id=mint(),
            evidence_refs=(),
            clause_id=constraint.clause_id,
            applies_to=constraint.applies_to,
        )
        for constraint in oracle.constraints
    )
    unknowns: dict[UnknownKey, Unknown] = {}
    for truth in oracle.impacts:
        assessed: list[CandidateAssessment] = []
        for assessment in truth.assessments:
            behind: list[ClaimId] = []
            for question in assessment.unresolved:
                key = UnknownKey(question.subject, question.predicate)
                if key not in unknowns:
                    unknowns[key] = Unknown(
                        claim_id=mint(),
                        evidence_refs=(),
                        subject=question.subject,
                        required_fact=question.predicate,
                        reason=question.reason,
                    )
                behind.append(unknowns[key].claim_id)
            assessed.append(
                CandidateAssessment(
                    claim_id=mint(),
                    evidence_refs=(),
                    impact_key=truth.key,
                    employee_id=assessment.employee_id,
                    verdict=assessment.verdict,
                    reasons=assessment.reasons,
                    derived_from_claim_ids=tuple(behind),
                )
            )
        claims.extend(assessed)
        viable = [a for a in assessed if a.verdict is Verdict.VIABLE]
        unknown = [a for a in assessed if a.verdict is Verdict.UNKNOWN]
        assign = truth.outcome is CoverageActionKind.ASSIGN
        basis = unknown if truth.outcome is CoverageActionKind.UNKNOWN else ()
        claims.append(
            CoverageAction(
                claim_id=mint(),
                evidence_refs=(),
                impact_key=truth.key,
                action=truth.outcome,
                assignee_ids=tuple(a.employee_id for a in viable[: truth.required])
                if assign
                else (),
                derived_from_claim_ids=tuple(a.claim_id for a in basis),
            )
        )
    claims.extend(unknowns.values())
    expected = {(conflict.entity, conflict.predicate) for conflict in oracle.conflicts}
    claims.extend(
        SourceConflict(
            claim_id=mint(),
            evidence_refs=(),
            entity=finding.subject,
            predicate=finding.predicate,
            observations=finding.observations,
            resolved_value=finding.resolution.value,
            authority_rule=finding.resolution.rule,
        )
        for finding in conflicts_in(oracle.view)
        if (finding.subject, finding.predicate) in expected
    )
    return tuple(claims)


def citing(claims: Sequence[Claim], groundings: Sequence[ClaimGrounding]) -> tuple[Claim, ...]:
    """``claims`` with each one citing the citable witnesses of its own proof, as the replay
    records in ``groundings`` hold it: nothing more, and nothing of its premises'."""
    by_id = {record.claim_id: record for record in groundings}
    return tuple(
        replace(
            claim,
            evidence_refs=tuple(
                EvidenceRef(SOURCE_BY_TARGET_KIND[target.kind], target)
                for target in citable_witnesses(by_id[claim.claim_id])
            ),
        )
        for claim in claims
    )


def without(claims: Sequence[Claim], *dropped: Claim) -> tuple[Claim, ...]:
    """``claims`` with ``dropped`` removed, the links to them left as the report had them."""
    return tuple(claim for claim in claims if claim not in dropped)


def swapped(claims: Sequence[Claim], old: Claim, new: Claim) -> tuple[Claim, ...]:
    """``claims`` with ``old`` replaced by ``new`` in place."""
    return tuple(new if claim is old else claim for claim in claims)


def renumbered(claim: Claim, number: int) -> Claim:
    """``claim`` under another claim id: the same statement made a second time."""
    return replace(claim, claim_id=claim_id(number))


def of_type[T: Claim](claims: Iterable[Claim], kind: type[T]) -> list[T]:
    """The claims of one type, in report order."""
    return [claim for claim in claims if isinstance(claim, kind)]


__all__ = ["citing", "of_type", "renumbered", "swapped", "truthful_report", "without"]
