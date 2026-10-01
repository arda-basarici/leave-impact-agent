"""Matching: a report's claims against what the oracle expects, one row per key.

Grading identity is computed from a claim's fields (``core.claims``): the same world fact
has the same grading key in a report and in the oracle, whatever claim id either minted
for it. Matching takes the union of the keys the oracle requires and the keys the report
holds, per claim type, and writes one row for each (``rows`` says what a row is). A
required key the report holds is judged on its payload; one it does not hold is a missed
row; a held key the oracle does not require is either optional and judged, or unexpected
and put in the named standing its type has.

What is required, per type, under the oracle's condition:

- an *impact* for every impact the rules ground;
- a *constraint* for every expected constraint;
- an *assessment* for every candidate of an expected impact's sealed probe set, the
  must-assess set; the rest of the organization is optional for that impact, judged when
  assessed and no miss when not;
- a *coverage action* for every expected impact;
- a *conflict* for every expected conflict;
- an *unknown* for every open question behind a probed candidate's assessment; the open
  questions behind the other candidates' are optional. Whether a report that concludes
  nobody can cover must have looked at everyone is the coverage check's, not recall's.

An unexpected claim is asked of the oracle's view before it is called wrong. An impact is
asked by its exact key: open under the condition is *unsupported*, a different thing from
false, and a planted near-miss is named with its reason. A conflict is real when the
sources disagree in the view, and then its resolution is judged though the investigation
did not need it. An unknown is a false gap when the view settles the fact.

Matching runs only on a structurally valid claim set (unique claim ids, resolving
derivations, an acyclic provenance graph, one claim per grading key and type). An invalid
set is not salvaged: which of two claims on one key would count is a rule nobody should
have to write, so every required key is recorded as missed and every reported claim as
not matched, with the structural findings beside them.
"""

from __future__ import annotations

from collections.abc import Sequence

from leaveimpact.core.authority import conflicts_in
from leaveimpact.core.claims import (
    AssessmentKey,
    CandidateAssessment,
    Claim,
    ConflictKey,
    Constraint,
    CoverageAction,
    Impact,
    SourceConflict,
    Unknown,
    UnknownKey,
    UnknownReason,
    structural_problems,
)
from leaveimpact.core.closure import Unresolved, establish
from leaveimpact.core.grounding import Grounded, ground_impact
from leaveimpact.evaluator.oracle import Answerable
from leaveimpact.evaluator.rows import (
    ActionRow,
    ActionStanding,
    AssessmentRow,
    AssessmentStanding,
    ClaimRows,
    ConflictRow,
    ConflictStanding,
    ConstraintRow,
    ConstraintStanding,
    Expectation,
    ImpactRow,
    ImpactStanding,
    Resolution,
    UnknownRow,
    UnknownStanding,
)


def match_claims(oracle: Answerable, claims: Sequence[Claim]) -> ClaimRows:
    """Every row of ``claims`` graded against ``oracle``: the report's rows in claim order,
    then the required keys it missed, per claim type."""
    problems = structural_problems(claims)
    if problems:
        return _not_matched(oracle, claims, problems)
    return ClaimRows(
        impacts=_impact_rows(oracle, [c for c in claims if isinstance(c, Impact)]),
        constraints=_constraint_rows(oracle, [c for c in claims if isinstance(c, Constraint)]),
        assessments=_assessment_rows(
            oracle, [c for c in claims if isinstance(c, CandidateAssessment)]
        ),
        actions=_action_rows(oracle, [c for c in claims if isinstance(c, CoverageAction)]),
        conflicts=_conflict_rows(oracle, [c for c in claims if isinstance(c, SourceConflict)]),
        unknowns=_unknown_rows(oracle, [c for c in claims if isinstance(c, Unknown)]),
    )


def required_unknowns(oracle: Answerable) -> dict[UnknownKey, UnknownReason]:
    """The open questions behind the probed candidates' assessments, with the reason for each.

    Read off the oracle's own assessments per impact, so "seeds a must-assess candidate" is
    exact: a candidate probed for one impact and not for another contributes only the
    questions of the impact they are probed for.
    """
    required: dict[UnknownKey, UnknownReason] = {}
    for truth in oracle.impacts:
        for assessment in truth.assessments:
            if assessment.employee_id in truth.probe:
                for question in assessment.unresolved:
                    required[UnknownKey(question.subject, question.predicate)] = question.reason
    return required


# --- Impacts and constraints: the key is the whole fact -------------------------------------


def _impact_rows(oracle: Answerable, reported: Sequence[Impact]) -> tuple[ImpactRow, ...]:
    expected = [truth.key for truth in oracle.impacts]
    rows = [
        ImpactRow(claim.key, Expectation.REQUIRED, claim.claim_id)
        if claim.key in expected
        else _unexpected_impact(oracle, claim)
        for claim in reported
    ]
    held = {claim.key for claim in reported}
    rows.extend(ImpactRow(key, Expectation.REQUIRED, None) for key in expected if key not in held)
    return tuple(rows)


def _unexpected_impact(oracle: Answerable, claim: Impact) -> ImpactRow:
    scenario, key = oracle.scenario, claim.key
    near_miss = next(
        (truth.key for truth in oracle.impacts if truth.key.artifact == key.artifact), None
    )
    standing, reason = ImpactStanding.FALSE_POSITIVE, None
    if key.leave_id == scenario.spec.leave_id:
        leave = scenario.investigated_leave
        grounding = ground_impact(
            oracle.view, key, leave.employee_id, leave.span, scenario.spec.reference_timezone
        )
        # Grounded cannot occur here: every impact the rules ground is an expected one.
        assert not isinstance(grounding, Grounded), key
        planted = {d.entity: d.reason for d in scenario.key.distractors}
        if isinstance(grounding, Unresolved):
            standing = ImpactStanding.UNSUPPORTED_UNDER_THE_CONDITION
        elif key.artifact in planted:
            standing, reason = ImpactStanding.DISTRACTOR, planted[key.artifact]
    return ImpactRow(key, Expectation.UNEXPECTED, claim.claim_id, standing, reason, near_miss)


def _constraint_rows(
    oracle: Answerable, reported: Sequence[Constraint]
) -> tuple[ConstraintRow, ...]:
    rows = [
        ConstraintRow(claim.key, Expectation.REQUIRED, claim.claim_id)
        if claim.key in oracle.constraints
        else ConstraintRow(
            claim.key, Expectation.UNEXPECTED, claim.claim_id, ConstraintStanding.FALSE_POSITIVE
        )
        for claim in reported
    ]
    held = {claim.key for claim in reported}
    rows.extend(
        ConstraintRow(key, Expectation.REQUIRED, None)
        for key in oracle.constraints
        if key not in held
    )
    return tuple(rows)


# --- Assessments and actions: keyed on an expected impact -----------------------------------


def _assessment_rows(
    oracle: Answerable, reported: Sequence[CandidateAssessment]
) -> tuple[AssessmentRow, ...]:
    rows = [_assessment_row(oracle, claim) for claim in reported]
    held = {claim.key for claim in reported}
    for truth in oracle.impacts:
        for candidate in truth.probe:
            key = AssessmentKey(truth.key, candidate)
            derived = truth.assessment_of(candidate)
            if key not in held and derived is not None:
                rows.append(
                    AssessmentRow(
                        key,
                        Expectation.REQUIRED,
                        None,
                        expected=(derived.verdict, derived.reasons),
                    )
                )
    return tuple(rows)


def _assessment_row(oracle: Answerable, claim: CandidateAssessment) -> AssessmentRow:
    reported = (claim.verdict, claim.reasons)
    truth = oracle.impact(claim.impact_key)
    if truth is None:
        return AssessmentRow(
            claim.key,
            Expectation.UNEXPECTED,
            claim.claim_id,
            AssessmentStanding.ON_AN_UNEXPECTED_IMPACT,
            reported=reported,
        )
    derived = truth.assessment_of(claim.employee_id)
    if derived is None:
        return AssessmentRow(
            claim.key,
            Expectation.UNEXPECTED,
            claim.claim_id,
            AssessmentStanding.NOT_IN_THE_ORGANIZATION,
            reported=reported,
        )
    probed = claim.employee_id in truth.probe
    return AssessmentRow(
        claim.key,
        Expectation.REQUIRED if probed else Expectation.OPTIONAL,
        claim.claim_id,
        expected=(derived.verdict, derived.reasons),
        reported=reported,
        verdict_matches=claim.verdict is derived.verdict,
        # Both sides hold their reasons in one canonical order, so equality is set equality.
        reasons_match=claim.reasons == derived.reasons,
    )


def _action_rows(oracle: Answerable, reported: Sequence[CoverageAction]) -> tuple[ActionRow, ...]:
    rows: list[ActionRow] = []
    for claim in reported:
        truth = oracle.impact(claim.impact_key)
        if truth is None:
            rows.append(
                ActionRow(
                    claim.key,
                    Expectation.UNEXPECTED,
                    claim.claim_id,
                    ActionStanding.ON_AN_UNEXPECTED_IMPACT,
                    reported=claim.action,
                    assignees=claim.assignee_ids,
                )
            )
        else:
            rows.append(
                ActionRow(
                    claim.key,
                    Expectation.REQUIRED,
                    claim.claim_id,
                    expected=truth.outcome,
                    reported=claim.action,
                    assignees=claim.assignee_ids,
                    outcome_matches=claim.action is truth.outcome,
                )
            )
    held = {claim.key for claim in reported}
    rows.extend(
        ActionRow(truth.key, Expectation.REQUIRED, None, expected=truth.outcome)
        for truth in oracle.impacts
        if truth.key not in held
    )
    return tuple(rows)


# --- Conflicts and unknowns: where the evidence chain could not be established --------------


def _conflict_rows(
    oracle: Answerable, reported: Sequence[SourceConflict]
) -> tuple[ConflictRow, ...]:
    expected: dict[ConflictKey, Resolution] = {
        ConflictKey(conflict.entity, conflict.predicate): (
            conflict.resolved_value,
            conflict.authority_rule,
        )
        for conflict in oracle.conflicts
    }
    # Every disagreement the view holds, the expected ones and the ones beside the point.
    real: dict[ConflictKey, Resolution] = {
        ConflictKey(finding.subject, finding.predicate): (
            finding.resolution.value,
            finding.resolution.rule,
        )
        for finding in conflicts_in(oracle.view)
    }
    rows: list[ConflictRow] = []
    for claim in reported:
        key = claim.key
        said: Resolution = (claim.resolved_value, claim.authority_rule)
        held_in_the_view = {
            (fact.source, fact.value) for fact in oracle.view.facts_about(key.entity, key.predicate)
        }
        observations_hold = all(
            (observation.source, observation.value) in held_in_the_view
            for observation in claim.observations
        )
        resolution = expected.get(key) or real.get(key)
        if resolution is None:
            rows.append(
                ConflictRow(
                    key,
                    Expectation.UNEXPECTED,
                    claim.claim_id,
                    ConflictStanding.UNSUPPORTED,
                    reported=said,
                    observations_hold=observations_hold,
                )
            )
            continue
        required = key in expected
        rows.append(
            ConflictRow(
                key,
                Expectation.REQUIRED if required else Expectation.UNEXPECTED,
                claim.claim_id,
                None if required else ConflictStanding.RELEVANCE_ERROR,
                expected=resolution,
                reported=said,
                value_matches=claim.resolved_value == resolution[0],
                rule_matches=claim.authority_rule is resolution[1],
                observations_hold=observations_hold,
            )
        )
    held = {claim.key for claim in reported}
    rows.extend(
        ConflictRow(key, Expectation.REQUIRED, None, expected=resolution)
        for key, resolution in expected.items()
        if key not in held
    )
    return tuple(rows)


def _unknown_rows(oracle: Answerable, reported: Sequence[Unknown]) -> tuple[UnknownRow, ...]:
    required = required_unknowns(oracle)
    derived = {
        UnknownKey(unknown.subject, unknown.required_fact): unknown.reason
        for unknown in oracle.unknowns
    }
    rows: list[UnknownRow] = []
    for claim in reported:
        key = claim.key
        if key in derived:
            reason = derived[key]
            rows.append(
                UnknownRow(
                    key,
                    Expectation.REQUIRED if key in required else Expectation.OPTIONAL,
                    claim.claim_id,
                    expected=reason,
                    reported=claim.reason,
                    reason_matches=claim.reason is reason,
                )
            )
            continue
        # No assessment left this open. Asked of the view directly, it is either settled,
        # a gap claimed where the world is complete, or open and beside the point.
        settled = establish(oracle.view, key.subject, key.required_fact)
        if isinstance(settled, Unresolved):
            rows.append(
                UnknownRow(
                    key,
                    Expectation.UNEXPECTED,
                    claim.claim_id,
                    UnknownStanding.NOT_ASKED_BY_THE_RULES,
                    expected=settled.reason,
                    reported=claim.reason,
                    reason_matches=claim.reason is settled.reason,
                )
            )
        else:
            rows.append(
                UnknownRow(
                    key,
                    Expectation.UNEXPECTED,
                    claim.claim_id,
                    UnknownStanding.RESOLVED_IN_THE_ORACLE,
                    reported=claim.reason,
                )
            )
    held = {claim.key for claim in reported}
    rows.extend(
        UnknownRow(key, Expectation.REQUIRED, None, expected=reason)
        for key, reason in required.items()
        if key not in held
    )
    return tuple(rows)


# --- A structurally invalid claim set -------------------------------------------------------


def _not_matched(
    oracle: Answerable, claims: Sequence[Claim], problems: tuple[str, ...]
) -> ClaimRows:
    """Every required key missed, every reported claim kept and not matched."""
    missed = match_claims(oracle, ())
    invalid = Expectation.NOT_MATCHED
    return ClaimRows(
        impacts=(
            *(
                ImpactRow(c.key, invalid, c.claim_id, ImpactStanding.STRUCTURALLY_INVALID)
                for c in claims
                if isinstance(c, Impact)
            ),
            *missed.impacts,
        ),
        constraints=(
            *(
                ConstraintRow(c.key, invalid, c.claim_id, ConstraintStanding.STRUCTURALLY_INVALID)
                for c in claims
                if isinstance(c, Constraint)
            ),
            *missed.constraints,
        ),
        assessments=(
            *(
                AssessmentRow(
                    c.key,
                    invalid,
                    c.claim_id,
                    AssessmentStanding.STRUCTURALLY_INVALID,
                    reported=(c.verdict, c.reasons),
                )
                for c in claims
                if isinstance(c, CandidateAssessment)
            ),
            *missed.assessments,
        ),
        actions=(
            *(
                ActionRow(
                    c.key,
                    invalid,
                    c.claim_id,
                    ActionStanding.STRUCTURALLY_INVALID,
                    reported=c.action,
                    assignees=c.assignee_ids,
                )
                for c in claims
                if isinstance(c, CoverageAction)
            ),
            *missed.actions,
        ),
        conflicts=(
            *(
                ConflictRow(
                    c.key,
                    invalid,
                    c.claim_id,
                    ConflictStanding.STRUCTURALLY_INVALID,
                    reported=(c.resolved_value, c.authority_rule),
                )
                for c in claims
                if isinstance(c, SourceConflict)
            ),
            *missed.conflicts,
        ),
        unknowns=(
            *(
                UnknownRow(
                    c.key,
                    invalid,
                    c.claim_id,
                    UnknownStanding.STRUCTURALLY_INVALID,
                    reported=c.reason,
                )
                for c in claims
                if isinstance(c, Unknown)
            ),
            *missed.unknowns,
        ),
        structural_problems=problems,
    )


__all__ = ["match_claims", "required_unknowns"]
