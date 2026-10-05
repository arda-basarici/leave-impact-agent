"""The report: the rules' conclusions written as claims, under the one reporting policy every
rules-composed system is frozen to.

A system whose claims the rules write states what the shared rules conclude over its own
view and nothing it decided itself (the investigator milestone's fifth build step, rulings
2 and 6; the contract step made the path every model system's, the baseline being the same
path with no stated fact and so no constraint). For every impact
the view grounds: one impact claim; one assessment of every employee in the candidate
universe, exactly as the viability rule returned it; and exactly one coverage action, the
plan rule's result over the complete assessment set, an assign naming the first viable
employees in the code-point order of their ids, as many as the required count, a declared
tie-break and not a preference. Every employee is assessed because stopping once enough
viable candidates are found loses most of the rows a report must hold (807 of 1,240 on
twenty worlds) and leaves a coverage gap wherever the oracle calls for everyone.

The unknown claims are the ones the assessments derive from: one per subject and fact,
each assessment linked to the unknowns its open questions name, and the report refused
when one such key would need two reasons, which no reading of the rules produces. The
conflicts are those met while resolving the evidence an emitted impact or assessment
used, and no other.

A constraint is stated for each scope pairing the rules were given whose clause states a
requirement the view can read and whose target lies inside the scope of a reported impact:
the impact's artifact, or its component when that could be read. That is the set an answer
key expects, so a requirement bound to something the leave does not touch is applied by
the rules to nothing, stated as no claim, and counted against nobody. The baseline is
given no pairing and states none; its empty constraint list is a premise its record
declares.

Each claim cites the directly citable records of its own proof: a fact's or a gap's
record, and the record whose return settled a negative. An enumeration, a window and a
source left unclosed name no record, and an action copies none of its premises' evidence.

Claims are ordered by type (impacts, constraints, unknowns, assessments, actions,
conflicts) and by grading key within a type, and ids are assigned after that ordering, so
identical observations give an identical report, byte for byte once exported.

The policy has a declared identity, ``REPORTING_POLICY``: an identifier, a version and the
tie-break by name. The version is a semantic version kept by hand, raised whenever what
this module reports for the same conclusions changes; nothing derives it. The three are
inside the composing policy's specification (``composer``), whose digest the
preregistration binds, and the harness refuses to run when the registered digest differs
from the one it computes. The evaluator cannot import this package and does not verify
the value: what binds a run to the policy is the clean harness commit its record names,
the claims it exported, and the construction gate that grades the baseline end to end.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from leaveimpact.core.authority import conflicts_on
from leaveimpact.core.claims import (
    CandidateAssessment,
    Claim,
    ConflictKey,
    Constraint,
    ConstraintKey,
    CoverageAction,
    CoverageActionKind,
    Impact,
    SourceConflict,
    Unknown,
    UnknownKey,
    Verdict,
    key_order,
)
from leaveimpact.core.closure import KnownTrue, Unresolved, Witness, citable_record, establish
from leaveimpact.core.facts import Fact, FactView
from leaveimpact.core.grounding import Grounded
from leaveimpact.core.ids import ClaimId, claim_id
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.readings import ImpactConclusion
from leaveimpact.core.refs import SOURCE_BY_TARGET_KIND, EntityRef, EvidenceRef, clause_ref
from leaveimpact.core.run_trace import require_integer, require_opaque_id
from leaveimpact.core.viability import Need


@dataclass(frozen=True, slots=True)
class ReportingPolicy:
    """The reporting policy by its declared identifier and version, with the tie-break among
    viable assignees by name. The version is a declared semantic version kept by hand;
    nothing derives it."""

    identifier: str
    version: int
    tie_break: str

    def __post_init__(self) -> None:
        require_opaque_id(self.identifier, "a reporting policy identifier")
        require_integer(self.version, "a reporting policy version", minimum=1)
        require_opaque_id(self.tie_break, "a tie-break rule")


REPORTING_POLICY = ReportingPolicy("rules-only-report", 1, "first_viable_in_id_code_point_order")
"""The policy this module implements, as the preregistration names it."""


def rules_only_report(conclusions: Sequence[ImpactConclusion], view: FactView) -> tuple[Claim, ...]:
    """The claims the reporting policy makes of ``conclusions`` reached with no constraint:
    the baseline's report."""
    return compose_report(conclusions, view, ())


def compose_report(
    conclusions: Sequence[ImpactConclusion], view: FactView, constraints: Sequence[ConstraintKey]
) -> tuple[Claim, ...]:
    """The claims the reporting policy makes of ``conclusions`` over ``view``, the rules having
    been given ``constraints`` as the scope pairings in force.

    Only an impact the rules ground is reported; a conclusion whose grounding is open or
    negative contributes nothing, since silence is never a negative here. Raises
    ``ValueError`` when two assessments leave one subject's fact open for different
    reasons, a report the policy cannot state.
    """
    grounded = sorted(
        (c for c in conclusions if isinstance(c.reading.grounding, Grounded)),
        key=lambda c: key_order(c.impact),
    )
    numbers = iter(range(1, 1_000_000))

    def mint() -> ClaimId:
        return claim_id(next(numbers))

    impacts = [
        Impact(
            claim_id=mint(),
            evidence_refs=_cites(c.reading.grounding.proof),
            leave_id=c.impact.leave_id,
            subtype=c.impact.subtype,
            artifact=c.impact.artifact,
        )
        for c in grounded
    ]
    stated = [
        Constraint(
            claim_id=mint(),
            evidence_refs=_cites(requirement.proof),
            clause_id=key.clause_id,
            applies_to=key.applies_to,
        )
        for key, requirement in _stated_constraints(grounded, view, constraints)
    ]
    questions = _open_questions(grounded)
    unknowns = {
        key: Unknown(
            claim_id=mint(),
            evidence_refs=_cites(question.proof),
            subject=question.subject,
            required_fact=question.predicate,
            reason=question.reason,
        )
        for key, question in sorted(questions.items(), key=lambda item: key_order(item[0]))
    }
    assessments: list[CandidateAssessment] = []
    actions: list[CoverageAction] = []
    for c in grounded:
        assessed = [
            CandidateAssessment(
                claim_id=mint(),
                evidence_refs=_cites(a.proof),
                impact_key=c.impact,
                employee_id=a.employee_id,
                verdict=a.verdict,
                reasons=a.reasons,
                derived_from_claim_ids=tuple(
                    unknowns[UnknownKey(q.subject, q.predicate)].claim_id for q in a.unresolved
                ),
            )
            for a in sorted(c.reading.assessments, key=lambda a: a.employee_id)
        ]
        assessments.extend(assessed)
    for c, assessed in zip(grounded, _per_impact(assessments, grounded), strict=True):
        viable = [a for a in assessed if a.verdict is Verdict.VIABLE]
        unknown = [a for a in assessed if a.verdict is Verdict.UNKNOWN]
        actions.append(
            CoverageAction(
                claim_id=mint(),
                evidence_refs=(),
                impact_key=c.impact,
                action=c.outcome,
                assignee_ids=tuple(a.employee_id for a in viable[: c.required])
                if c.outcome is CoverageActionKind.ASSIGN
                else (),
                derived_from_claim_ids=tuple(a.claim_id for a in unknown)
                if c.outcome is CoverageActionKind.UNKNOWN
                else (),
            )
        )
    conflicts = [
        SourceConflict(
            claim_id=mint(),
            evidence_refs=_cites(finding.facts),
            entity=finding.subject,
            predicate=finding.predicate,
            observations=finding.observations,
            resolved_value=finding.resolution.value,
            authority_rule=finding.resolution.rule,
        )
        for finding in sorted(
            conflicts_on(view, _evidence_used(grounded)),
            key=lambda f: key_order(ConflictKey(f.subject, f.predicate)),
        )
    ]
    return (*impacts, *stated, *unknowns.values(), *assessments, *actions, *conflicts)


def _stated_constraints(
    grounded: Sequence[ImpactConclusion], view: FactView, constraints: Sequence[ConstraintKey]
) -> list[tuple[ConstraintKey, KnownTrue]]:
    """The pairings a report states, each with the reading of its clause's requirement: those
    whose target is inside a reported impact's scope and whose clause the view can read,
    in key order, each once."""
    in_scope: set[EntityRef] = set()
    for c in grounded:
        in_scope.add(c.impact.artifact)
        if isinstance(c.need, Need) and isinstance(c.need.component, EntityRef):
            in_scope.add(c.need.component)
    stated: list[tuple[ConstraintKey, KnownTrue]] = []
    for key in sorted(dict.fromkeys(constraints), key=key_order):
        if key.applies_to not in in_scope:
            continue
        requirement = establish(view, clause_ref(key.clause_id), PredicateName.REQUIRES)
        if isinstance(requirement, KnownTrue):
            stated.append((key, requirement))
    return stated


def _open_questions(grounded: Iterable[ImpactConclusion]) -> dict[UnknownKey, Unresolved]:
    """The one open question per subject and fact the assessments leave, or a refusal when
    two assessments leave the same one open for different reasons."""
    questions: dict[UnknownKey, Unresolved] = {}
    for c in grounded:
        for assessment in c.reading.assessments:
            for question in assessment.unresolved:
                key = UnknownKey(question.subject, question.predicate)
                earlier = questions.setdefault(key, question)
                if earlier.reason is not question.reason:
                    raise ValueError(
                        f"the rules left {question.predicate.value} of {question.subject.id} "
                        f"open as {earlier.reason.value} and as {question.reason.value}; the "
                        "report states one reason per question"
                    )
    return questions


def _per_impact(
    assessments: Sequence[CandidateAssessment], grounded: Sequence[ImpactConclusion]
) -> list[list[CandidateAssessment]]:
    return [[a for a in assessments if a.impact_key == c.impact] for c in grounded]


def _evidence_used(grounded: Iterable[ImpactConclusion]) -> list[Fact]:
    """Every fact an emitted impact or assessment rests on: what a reported conflict must be
    about."""
    facts: list[Fact] = []
    for c in grounded:
        grounding = c.reading.grounding
        assert isinstance(grounding, Grounded)
        facts.extend(grounding.facts)
        facts.extend(fact for a in c.reading.assessments for fact in a.evidence)
    return facts


def _cites(proof: Iterable[Witness]) -> tuple[EvidenceRef, ...]:
    """The evidence references a claim makes of its own proof: each citable record once."""
    targets = dict.fromkeys(
        target for witness in proof if (target := citable_record(witness)) is not None
    )
    return tuple(EvidenceRef(SOURCE_BY_TARGET_KIND[target.kind], target) for target in targets)


__all__ = ["REPORTING_POLICY", "compose_report", "rules_only_report"]
