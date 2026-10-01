"""Matching a report against the oracle on a throwaway golden-plan world: a truthful report is
right in every row, an empty one misses exactly the required keys, and each way a report can be
wrong moves the one row it should — a missed impact, a planted distractor named with its reason, a
near miss, another leave's impact, an impact the outage left open, a wrong verdict, wrong reasons,
a candidate outside the probe set, a stranger, a wrong outcome, a wrong resolution, a conflict
real and beside the point, one the view does not hold, a wrong reason, a gap where the world is
complete, a gap nobody asked about. A structurally invalid claim set is not matched at all. A row
refuses the combinations that mean nothing."""

from collections.abc import Callable
from dataclasses import replace

import pytest

from leaveimpact.core import (
    AssessmentReason,
    AuthorityRule,
    CandidateAssessment,
    Claim,
    Constraint,
    CoverageAction,
    CoverageActionKind,
    EntityKind,
    EntityRef,
    Impact,
    ImpactKey,
    ImpactSubtype,
    Observation,
    PredicateName,
    RunCondition,
    Source,
    SourceConflict,
    Unknown,
    UnknownKey,
    UnknownReason,
    Verdict,
    conflicts_in,
    employee_ref,
)
from leaveimpact.core.ids import ClauseId, EmployeeId, LeaveId, claim_id
from leaveimpact.evaluator.matching import match_claims, required_unknowns
from leaveimpact.evaluator.oracle import Answerable, oracle_for
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
    UnknownRow,
    UnknownStanding,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.report_fixture import of_type, renumbered, swapped, truthful_report, without
from tests.unit.throwaway_world import loaded_world

NORMAL = RunCondition.all_reachable()
SPARE = 9_000
"""A claim number no truthful report reaches, for a claim a test adds."""


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def answer(world: SealedWorld, scenario: Scenario, condition: RunCondition = NORMAL) -> Answerable:
    oracle = oracle_for(world, scenario, condition)
    assert isinstance(oracle, Answerable)
    return oracle


def first(world: SealedWorld, holds: Callable[[Answerable], object]) -> Answerable:
    """The oracle of the first scenario for which ``holds(oracle)`` is true."""
    for scenario in world.scenarios:
        oracle = answer(world, scenario)
        if holds(oracle):
            return oracle
    raise AssertionError("the throwaway world holds no scenario of the shape this test needs")


Row = ImpactRow | ConstraintRow | AssessmentRow | ActionRow | ConflictRow | UnknownRow


def all_rows(rows: ClaimRows) -> list[Row]:
    return [
        *rows.impacts,
        *rows.constraints,
        *rows.assessments,
        *rows.actions,
        *rows.conflicts,
        *rows.unknowns,
    ]


def new_impact(key: ImpactKey) -> Impact:
    return Impact(
        claim_id=claim_id(SPARE),
        evidence_refs=(),
        leave_id=key.leave_id,
        subtype=key.subtype,
        artifact=key.artifact,
    )


# --- The whole report ---------------------------------------------------------------------


def test_a_truthful_report_is_right_in_every_row_of_every_scenario(world: SealedWorld) -> None:
    for scenario in world.scenarios:
        oracle = answer(world, scenario)
        rows = match_claims(oracle, truthful_report(oracle))
        assert rows.structurally_valid
        assert all(row.claim_id is not None and row.standing is None for row in all_rows(rows))
        assert all(row.expectation is Expectation.REQUIRED for row in rows.impacts)
        assert all(row.payload_correct for row in rows.assessments)
        assert all(row.outcome_matches for row in rows.actions)
        assert all(row.payload_correct and row.observations_hold for row in rows.conflicts)
        assert all(row.reason_matches for row in rows.unknowns)
        # The probe set is required and the rest of the organization optional, per impact.
        required = [r for r in rows.assessments if r.expectation is Expectation.REQUIRED]
        assert len(required) == sum(len(truth.probe) for truth in oracle.impacts)
        assert len(rows.assessments) == len(oracle.impacts) * len(oracle.universe)
        required_gaps = [r for r in rows.unknowns if r.expectation is Expectation.REQUIRED]
        assert {r.key for r in required_gaps} == set(required_unknowns(oracle))


def test_an_empty_report_misses_exactly_the_required_keys(world: SealedWorld) -> None:
    for scenario in world.scenarios:
        oracle = answer(world, scenario)
        rows = match_claims(oracle, ())
        every = all_rows(rows)
        assert all(row.claim_id is None for row in every)
        assert all(row.expectation is Expectation.REQUIRED for row in every)
        assert [row.key for row in rows.impacts] == [truth.key for truth in oracle.impacts]
        assert [row.key for row in rows.constraints] == list(oracle.constraints)
        assert len(rows.assessments) == sum(len(truth.probe) for truth in oracle.impacts)
        assert len(rows.actions) == len(oracle.impacts)
        assert len(rows.conflicts) == len(oracle.conflicts)
        assert {row.key for row in rows.unknowns} == set(required_unknowns(oracle))
        # A missed row still says what was expected.
        assert all(row.expected is not None and row.reported is None for row in rows.assessments)


# --- Impacts and constraints ----------------------------------------------------------------


def test_a_missed_impact_is_one_missed_row_and_nothing_else_moves(world: SealedWorld) -> None:
    oracle = answer(world, world.scenarios[0])
    report = truthful_report(oracle)
    [impact, *_] = of_type(report, Impact)
    rows = match_claims(oracle, without(report, impact))
    [missed] = [row for row in rows.impacts if row.claim_id is None]
    assert (missed.key, missed.expectation) == (impact.key, Expectation.REQUIRED)
    # The assessments and the action of that impact are still on an expected impact.
    assert all(row.standing is None for row in (*rows.assessments, *rows.actions))


def test_a_planted_distractor_reported_as_an_impact_is_named_with_its_reason(
    world: SealedWorld,
) -> None:
    oracle = first(world, lambda o: o.scenario.key.distractors)
    scenario = oracle.scenario
    distractor = scenario.key.distractors[0]
    subtype = (
        ImpactSubtype.MEETING
        if distractor.entity.kind is EntityKind.EVENT
        else ImpactSubtype.DEADLINE
    )
    claimed = new_impact(ImpactKey(scenario.spec.leave_id, subtype, distractor.entity))
    rows = match_claims(oracle, (*truthful_report(oracle), claimed))
    [row] = [row for row in rows.impacts if row.expectation is Expectation.UNEXPECTED]
    assert row.standing is ImpactStanding.DISTRACTOR
    assert row.distractor_reason is distractor.reason
    assert row.near_miss_of is None


def test_an_impact_on_the_right_artifact_under_another_subtype_is_a_near_miss(
    world: SealedWorld,
) -> None:
    oracle = first(world, lambda o: any(t.key.subtype is ImpactSubtype.DEADLINE for t in o.impacts))
    report = truthful_report(oracle)
    right = next(i for i in of_type(report, Impact) if i.subtype is ImpactSubtype.DEADLINE)
    wrong = replace(right, subtype=ImpactSubtype.RESPONSIBILITY)
    rows = match_claims(oracle, swapped(report, right, wrong))
    [unexpected] = [row for row in rows.impacts if row.expectation is Expectation.UNEXPECTED]
    assert unexpected.standing is ImpactStanding.FALSE_POSITIVE
    assert unexpected.near_miss_of == right.key
    # No credit: the expected impact is missed all the same.
    assert [row.key for row in rows.impacts if row.claim_id is None] == [right.key]


def test_another_leaves_impact_is_a_false_positive(world: SealedWorld) -> None:
    oracle = answer(world, world.scenarios[0])
    key = oracle.impacts[0].key
    other = new_impact(replace(key, leave_id=LeaveId("leave_999")))
    rows = match_claims(oracle, (*truthful_report(oracle), other))
    [row] = [row for row in rows.impacts if row.expectation is Expectation.UNEXPECTED]
    assert row.standing is ImpactStanding.FALSE_POSITIVE
    assert row.near_miss_of == key


def test_an_impact_the_outage_leaves_open_is_unsupported_and_not_false(
    world: SealedWorld,
) -> None:
    jira_down = NORMAL.without(Source.JIRA)
    scenario = next(
        s
        for s in world.scenarios
        if any(e.key.artifact.kind is EntityKind.WORK_ITEM for e in s.key.impacts)
    )
    lost = next(e.key for e in scenario.key.impacts if e.key.artifact.kind is EntityKind.WORK_ITEM)
    oracle = answer(world, scenario, jira_down)
    assert oracle.impact(lost) is None
    rows = match_claims(oracle, (*truthful_report(oracle), new_impact(lost)))
    [row] = [row for row in rows.impacts if row.key == lost]
    # The impact is real, the run could not have established it: neither true nor false.
    assert row.expectation is Expectation.UNEXPECTED
    assert row.standing is ImpactStanding.UNSUPPORTED_UNDER_THE_CONDITION


def test_a_constraint_outside_the_expected_ones_is_a_false_positive(world: SealedWorld) -> None:
    oracle = first(world, lambda o: o.constraints)
    report = truthful_report(oracle)
    [stated, *_] = of_type(report, Constraint)
    elsewhere = replace(stated, clause_id=ClauseId("clause_999"), claim_id=claim_id(SPARE))
    rows = match_claims(oracle, (*without(report, stated), elsewhere))
    [unexpected] = [row for row in rows.constraints if row.standing is not None]
    assert unexpected.standing is ConstraintStanding.FALSE_POSITIVE
    assert [row.key for row in rows.constraints if row.claim_id is None] == [stated.key]


# --- Assessments and actions ----------------------------------------------------------------


def test_a_probed_candidates_verdict_and_reasons_are_flagged_apart(world: SealedWorld) -> None:
    oracle = first(
        world,
        lambda o: any(
            len(a.reasons) > 1 for t in o.impacts for a in t.assessments if a.employee_id in t.probe
        ),
    )
    report = truthful_report(oracle)
    truth = next(t for t in oracle.impacts if any(len(a.reasons) > 1 for a in t.assessments))
    probed = next(
        claim
        for claim in of_type(report, CandidateAssessment)
        if claim.impact_key == truth.key
        and claim.employee_id in truth.probe
        and len(claim.reasons) > 1
    )
    # Right verdict, one reason dropped.
    fewer = replace(probed, reasons=probed.reasons[:1])
    [row] = [
        r
        for r in match_claims(oracle, swapped(report, probed, fewer)).assessments
        if r.claim_id == probed.claim_id
    ]
    assert row.expectation is Expectation.REQUIRED
    assert (row.verdict_matches, row.reasons_match, row.payload_correct) == (True, False, False)
    assert row.expected == (probed.verdict, probed.reasons)
    # Wrong verdict: a matched key with a wrong payload is never a true positive.
    viable = replace(probed, verdict=Verdict.VIABLE, reasons=())
    [row] = [
        r
        for r in match_claims(oracle, swapped(report, probed, viable)).assessments
        if r.claim_id == probed.claim_id
    ]
    assert (row.verdict_matches, row.payload_correct) == (False, False)


def test_a_candidate_outside_the_probe_set_is_optional_and_still_judged(
    world: SealedWorld,
) -> None:
    oracle = answer(world, world.scenarios[0])
    report = truthful_report(oracle)
    truth = oracle.impacts[0]
    outsider = next(
        claim
        for claim in of_type(report, CandidateAssessment)
        if claim.impact_key == truth.key
        and claim.employee_id not in truth.probe
        and claim.verdict is Verdict.NON_VIABLE
    )
    # Left out: no row, and no miss.
    rows = match_claims(oracle, without(report, outsider))
    assert not [r for r in rows.assessments if r.key == outsider.key]
    # Stated wrongly: judged, and wrong.
    wrong = replace(outsider, verdict=Verdict.VIABLE, reasons=())
    [row] = [
        r
        for r in match_claims(oracle, swapped(report, outsider, wrong)).assessments
        if r.key == outsider.key
    ]
    assert row.expectation is Expectation.OPTIONAL and row.payload_correct is False


def test_an_assessment_of_a_stranger_or_on_an_unexpected_impact_is_not_judged(
    world: SealedWorld,
) -> None:
    oracle = answer(world, world.scenarios[0])
    report = truthful_report(oracle)
    [one, *_] = of_type(report, CandidateAssessment)
    stranger = replace(one, employee_id=EmployeeId("emp_999"), claim_id=claim_id(SPARE))
    elsewhere = replace(
        one,
        impact_key=replace(one.impact_key, leave_id=LeaveId("leave_999")),
        claim_id=claim_id(SPARE + 1),
    )
    rows = match_claims(oracle, (*report, stranger, elsewhere))
    by_claim = {row.claim_id: row for row in rows.assessments}
    assert by_claim[stranger.claim_id].standing is AssessmentStanding.NOT_IN_THE_ORGANIZATION
    assert by_claim[elsewhere.claim_id].standing is AssessmentStanding.ON_AN_UNEXPECTED_IMPACT
    for claim in (stranger, elsewhere):
        row = by_claim[claim.claim_id]
        assert row.expectation is Expectation.UNEXPECTED
        assert (row.expected, row.payload_correct) == (None, None)


def test_an_actions_outcome_is_judged_and_its_assignees_are_only_recorded(
    world: SealedWorld,
) -> None:
    oracle = first(world, lambda o: o.impacts[0].outcome is CoverageActionKind.ASSIGN)
    report = truthful_report(oracle)
    action = next(a for a in of_type(report, CoverageAction) if a.key == oracle.impacts[0].key)
    [row] = [r for r in match_claims(oracle, report).actions if r.key == action.key]
    assert (row.outcome_matches, row.assignees) == (True, action.assignee_ids)
    uncovered = replace(action, action=CoverageActionKind.UNCOVERED, assignee_ids=())
    [row] = [
        r
        for r in match_claims(oracle, swapped(report, action, uncovered)).actions
        if r.key == action.key
    ]
    assert (row.expected, row.reported) == (CoverageActionKind.ASSIGN, CoverageActionKind.UNCOVERED)
    assert row.outcome_matches is False
    # Left out, the action is a missed required row; on another leave's impact, unjudged.
    [missed] = [
        r for r in match_claims(oracle, without(report, action)).actions if r.claim_id is None
    ]
    assert (missed.key, missed.expected) == (action.key, CoverageActionKind.ASSIGN)
    moved = replace(action, impact_key=replace(action.key, leave_id=LeaveId("leave_999")))
    [row] = [
        r
        for r in match_claims(oracle, swapped(report, action, moved)).actions
        if r.standing is not None
    ]
    assert row.standing is ActionStanding.ON_AN_UNEXPECTED_IMPACT and row.outcome_matches is None


# --- Conflicts ------------------------------------------------------------------------------


def test_an_expected_conflict_is_judged_on_its_resolution_and_its_observations(
    world: SealedWorld,
) -> None:
    oracle = first(world, lambda o: o.conflicts)
    report = truthful_report(oracle)
    [conflict, *_] = of_type(report, SourceConflict)
    loser = next(o.value for o in conflict.observations if o.value != conflict.resolved_value)
    wrong = replace(conflict, resolved_value=loser)
    [row] = [
        r
        for r in match_claims(oracle, swapped(report, conflict, wrong)).conflicts
        if r.key == conflict.key
    ]
    assert row.expectation is Expectation.REQUIRED
    assert (row.value_matches, row.rule_matches, row.payload_correct) == (False, True, False)
    assert row.observations_hold is True
    [missed] = [
        r for r in match_claims(oracle, without(report, conflict)).conflicts if r.claim_id is None
    ]
    assert missed.expected == (conflict.resolved_value, AuthorityRule.SYSTEM_OF_RECORD_WINS)


def test_a_conflict_real_and_beside_the_point_is_a_relevance_error_and_still_judged(
    world: SealedWorld,
) -> None:
    # A stale document one scenario plants stands for every run of the world: real in the
    # view of a scenario that never needed the fact it contradicts.
    oracle = first(world, lambda o: not o.conflicts and conflicts_in(o.view))
    finding = conflicts_in(oracle.view)[0]
    beside = SourceConflict(
        claim_id=claim_id(SPARE),
        evidence_refs=(),
        entity=finding.subject,
        predicate=finding.predicate,
        observations=finding.observations,
        resolved_value=finding.resolution.value,
        authority_rule=finding.resolution.rule,
    )
    [row] = match_claims(oracle, (*truthful_report(oracle), beside)).conflicts
    assert (row.expectation, row.standing) == (
        Expectation.UNEXPECTED,
        ConflictStanding.RELEVANCE_ERROR,
    )
    assert row.payload_correct is True and row.observations_hold is True


def test_a_conflict_the_view_does_not_hold_is_unsupported(world: SealedWorld) -> None:
    oracle = first(
        world, lambda o: any(t.key.artifact.kind is EntityKind.WORK_ITEM for t in o.impacts)
    )
    ticket = next(
        t.key.artifact for t in oracle.impacts if t.key.artifact.kind is EntityKind.WORK_ITEM
    )
    [owner] = oracle.view.facts_about(ticket, PredicateName.OWNS_WORK_ITEM)
    somebody_else = next(employee_ref(e) for e in oracle.universe if employee_ref(e) != owner.value)
    invented = SourceConflict(
        claim_id=claim_id(SPARE),
        evidence_refs=(),
        entity=ticket,
        predicate=PredicateName.OWNS_WORK_ITEM,
        observations=(
            Observation(Source.JIRA, owner.value),
            Observation(Source.CORPUS, somebody_else),
        ),
        resolved_value=owner.value,
        authority_rule=AuthorityRule.SYSTEM_OF_RECORD_WINS,
    )
    [row] = [
        r
        for r in match_claims(oracle, (*truthful_report(oracle), invented)).conflicts
        if r.claim_id == invented.claim_id
    ]
    assert row.standing is ConflictStanding.UNSUPPORTED
    # No document says so: one observation holds, the invented one does not.
    assert row.observations_hold is False
    assert (row.expected, row.payload_correct) == (None, None)


# --- Unknowns -------------------------------------------------------------------------------


def test_a_required_unknown_is_judged_on_its_reason_and_missed_when_absent(
    world: SealedWorld,
) -> None:
    oracle = first(world, required_unknowns)
    report = truthful_report(oracle)
    key, reason = next(iter(required_unknowns(oracle).items()))
    stated = next(u for u in of_type(report, Unknown) if u.key == key)
    other_reason = next(r for r in UnknownReason if r is not reason)
    [row] = [
        r
        for r in match_claims(
            oracle, swapped(report, stated, replace(stated, reason=other_reason))
        ).unknowns
        if r.key == key
    ]
    assert (row.expectation, row.expected, row.reason_matches) == (
        Expectation.REQUIRED,
        reason,
        False,
    )
    [missed] = [
        r for r in match_claims(oracle, without(report, stated)).unknowns if r.claim_id is None
    ]
    assert (missed.key, missed.expected) == (key, reason)


def test_an_unknown_behind_an_unprobed_candidate_is_optional(world: SealedWorld) -> None:
    oracle = first(world, lambda o: len(o.unknowns) > len(required_unknowns(o)))
    report = truthful_report(oracle)
    required = required_unknowns(oracle)
    optional = next(u for u in of_type(report, Unknown) if u.key not in required)
    rows = match_claims(oracle, report)
    [row] = [r for r in rows.unknowns if r.key == optional.key]
    assert (row.expectation, row.reason_matches) == (Expectation.OPTIONAL, True)
    # Left out it is no miss; the candidate's unknown assessment now has nothing behind it,
    # which is the chain check's to say and not recall's.
    assert not [
        r for r in match_claims(oracle, without(report, optional)).unknowns if r.key == optional.key
    ]


def test_a_gap_claimed_where_the_world_is_complete_and_a_gap_nobody_asked_about(
    world: SealedWorld,
) -> None:
    # A structured scenario: no clause asks anybody for a skill, so no skill is in question.
    oracle = first(world, lambda o: not o.constraints and not o.unknowns)
    blank = next(
        gap.subject for gap in oracle.view.gaps if gap.predicate is PredicateName.HAS_SKILL
    )
    complete = next(
        employee_ref(e)
        for e in oracle.universe
        if not oracle.view.gaps_about(employee_ref(e), PredicateName.HAS_SKILL)
    )

    def claim(subject: EntityRef, number: int) -> Unknown:
        return Unknown(
            claim_id=claim_id(number),
            evidence_refs=(),
            subject=subject,
            required_fact=PredicateName.HAS_SKILL,
            reason=UnknownReason.ABSENT,
        )

    unasked, false_gap = claim(blank, SPARE), claim(complete, SPARE + 1)
    rows = match_claims(oracle, (*truthful_report(oracle), unasked, false_gap))
    by_key = {row.key: row for row in rows.unknowns}
    open_row = by_key[UnknownKey(blank, PredicateName.HAS_SKILL)]
    assert open_row.standing is UnknownStanding.NOT_ASKED_BY_THE_RULES
    assert (open_row.expected, open_row.reason_matches) == (UnknownReason.ABSENT, True)
    settled_row = by_key[UnknownKey(complete, PredicateName.HAS_SKILL)]
    assert settled_row.standing is UnknownStanding.RESOLVED_IN_THE_ORACLE
    assert (settled_row.expected, settled_row.reason_matches) == (None, None)


# --- A structurally invalid claim set -------------------------------------------------------


def test_a_structurally_invalid_claim_set_is_not_matched_and_misses_every_required_key(
    world: SealedWorld,
) -> None:
    oracle = first(world, lambda o: o.conflicts and o.constraints)
    report = truthful_report(oracle)
    # The same impact stated twice: one grading key, two claims.
    twice: tuple[Claim, ...] = (*report, renumbered(of_type(report, Impact)[0], SPARE))
    rows = match_claims(oracle, twice)
    assert not rows.structurally_valid
    assert any("two impact claims with one grading key" in p for p in rows.structural_problems)
    reported = [row for row in all_rows(rows) if row.claim_id is not None]
    missed = [row for row in all_rows(rows) if row.claim_id is None]
    # Every reported claim is kept, none is matched; every required key is missed.
    assert len(reported) == len(twice)
    assert all(row.expectation is Expectation.NOT_MATCHED for row in reported)
    assert all(
        row.standing is not None and row.standing.value == "structurally_invalid"
        for row in reported
    )
    assert len(missed) == len(all_rows(match_claims(oracle, ())))
    # Nothing was judged, though each kept row still says what the report stated.
    assert all(row.payload_correct is None for row in rows.assessments)
    assert all(row.reported is not None for row in rows.assessments if row.claim_id is not None)


# --- Rows refuse what means nothing ---------------------------------------------------------


def test_a_row_refuses_the_combinations_that_mean_nothing(world: SealedWorld) -> None:
    oracle = answer(world, world.scenarios[0])
    truth = oracle.impacts[0]
    rows = match_claims(oracle, truthful_report(oracle))
    impact, action = rows.impacts[0], rows.actions[0]
    assessment = next(r for r in rows.assessments if r.expectation is Expectation.REQUIRED)
    conflict_key = match_claims(first(world, lambda o: o.conflicts), ()).conflicts[0].key
    with pytest.raises(ValueError, match="a required key has no standing"):
        replace(impact, standing=ImpactStanding.FALSE_POSITIVE)
    with pytest.raises(ValueError, match="never optional"):
        replace(impact, expectation=Expectation.OPTIONAL)
    with pytest.raises(ValueError, match="an unexpected row is a reported claim"):
        ImpactRow(truth.key, Expectation.UNEXPECTED, None, ImpactStanding.FALSE_POSITIVE)
    with pytest.raises(ValueError, match="a distractor carries its planted reason"):
        ImpactRow(truth.key, Expectation.UNEXPECTED, claim_id(1), ImpactStanding.DISTRACTOR)
    with pytest.raises(ValueError, match="reported and structurally invalid"):
        ImpactRow(truth.key, Expectation.NOT_MATCHED, claim_id(1), ImpactStanding.FALSE_POSITIVE)
    # A missed row holds no reported payload, and a flag needs both sides.
    with pytest.raises(ValueError, match="a reported payload exactly for a reported claim"):
        replace(assessment, claim_id=None)
    with pytest.raises(ValueError, match="verdict is judged exactly when both payloads exist"):
        replace(assessment, verdict_matches=None)
    with pytest.raises(ValueError, match="the oracle's judgment exactly for a required or"):
        AssessmentRow(
            assessment.key,
            Expectation.UNEXPECTED,
            claim_id(1),
            AssessmentStanding.ON_AN_UNEXPECTED_IMPACT,
            expected=(Verdict.NON_VIABLE, (AssessmentReason.SKILL,)),
            reported=(Verdict.VIABLE, ()),
        )
    with pytest.raises(ValueError, match="a missed action names nobody"):
        ActionRow(
            action.key,
            Expectation.REQUIRED,
            None,
            expected=CoverageActionKind.ASSIGN,
            assignees=(EmployeeId("emp_001"),),
        )
    with pytest.raises(ValueError, match="the oracle's resolution exactly when the disagreement"):
        ConflictRow(
            conflict_key,
            Expectation.UNEXPECTED,
            claim_id(1),
            ConflictStanding.UNSUPPORTED,
            expected=(employee_ref(EmployeeId("emp_001")), AuthorityRule.SYSTEM_OF_RECORD_WINS),
            reported=(employee_ref(EmployeeId("emp_001")), AuthorityRule.SYSTEM_OF_RECORD_WINS),
            observations_hold=True,
        )
    with pytest.raises(ValueError, match="the oracle's reason exactly when the fact is open"):
        UnknownRow(
            UnknownKey(employee_ref(EmployeeId("emp_001")), PredicateName.HAS_SKILL),
            Expectation.UNEXPECTED,
            claim_id(1),
            UnknownStanding.RESOLVED_IN_THE_ORACLE,
            expected=UnknownReason.ABSENT,
            reported=UnknownReason.ABSENT,
            reason_matches=True,
        )
