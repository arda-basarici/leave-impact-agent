"""The plan reading both coherence and the grounding replay call: a report's cited clauses
resolved to their requirements, the plan rule over the report's own assessments, and, with a
universe, the action the rule expects once everyone in it is assessed. An unreadable clause,
artifact or component is a reason and never an empty requirement or an exception."""

import pytest

from leaveimpact.core import (
    CandidateAssessment,
    Claim,
    Constraint,
    ConstraintKey,
    CoverageAction,
    CoverageActionKind,
    EntityKind,
    RunCondition,
    Source,
)
from leaveimpact.core.ids import ClauseId, claim_id
from leaveimpact.evaluator.oracle import Answerable, ImpactTruth, oracle_for
from leaveimpact.evaluator.plan_reading import PlanReading, PlanUnreadable, Unreadable, read_plan
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.report_fixture import of_type, truthful_report, without
from tests.unit.throwaway_world import loaded_world

NORMAL = RunCondition.all_reachable()


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def answers(world: SealedWorld, condition: RunCondition = NORMAL) -> list[Answerable]:
    found = [oracle_for(world, scenario, condition) for scenario in world.scenarios]
    return [oracle for oracle in found if isinstance(oracle, Answerable)]


def plan_of(
    oracle: Answerable,
    truth: ImpactTruth,
    claims: tuple[Claim, ...],
    *,
    universe: bool = True,
) -> PlanReading | PlanUnreadable:
    scenario: Scenario = oracle.scenario
    action = next(a for a in of_type(claims, CoverageAction) if a.impact_key == truth.key)
    return read_plan(
        action,
        [claim.key for claim in of_type(claims, Constraint)],
        of_type(claims, CandidateAssessment),
        oracle.view,
        scenario.investigated_leave.span,
        scenario.spec.reference_timezone,
        oracle.universe if universe else None,
    )


def test_over_a_truthful_report_the_reading_is_the_oracles_plan(world: SealedWorld) -> None:
    outcomes: set[CoverageActionKind] = set()
    for oracle in answers(world):
        claims = truthful_report(oracle)
        for truth in oracle.impacts:
            plan = plan_of(oracle, truth, claims)
            assert isinstance(plan, PlanReading)
            assert plan.violations == ()
            assert plan.unassessed == ()
            assert plan.expected is truth.outcome
            assert plan.requirements == truth.requirements
            assert [c.clause_id for c in plan.applied] == [r.clause_id for r in plan.requirements]
            outcomes.add(truth.outcome)
    assert outcomes == set(CoverageActionKind)


def test_without_a_universe_only_the_people_an_action_names_are_judged(
    world: SealedWorld,
) -> None:
    oracle = answers(world)[0]
    claims = truthful_report(oracle)
    plan = plan_of(oracle, oracle.impacts[0], claims, universe=False)
    assert isinstance(plan, PlanReading)
    assert (plan.unassessed, plan.expected) == ((), None)


def test_a_missing_assessment_leaves_the_expected_action_open(world: SealedWorld) -> None:
    oracle = answers(world)[0]
    truth = oracle.impacts[0]
    claims = truthful_report(oracle)
    action = next(a for a in of_type(claims, CoverageAction) if a.impact_key == truth.key)
    dropped = next(
        claim
        for claim in of_type(claims, CandidateAssessment)
        if claim.impact_key == truth.key and claim.employee_id not in action.assignee_ids
    )
    plan = plan_of(oracle, truth, without(claims, dropped))
    assert isinstance(plan, PlanReading)
    # Not a non-viable candidate: the rule is not asked what it expects until everyone is in.
    assert plan.unassessed == (dropped.employee_id,)
    assert plan.expected is None


def test_a_cited_clause_that_states_no_requirement_makes_the_plan_unreadable(
    world: SealedWorld,
) -> None:
    oracle = next(oracle for oracle in answers(world) if oracle.impacts)
    truth = oracle.impacts[0]
    silent = next(
        ClauseId(ref.id)
        for ref in world.index.parts
        if ref.kind is EntityKind.CLAUSE and ClauseId(ref.id) not in world.index.scope
    )
    claims = truthful_report(oracle)
    extra = Constraint(
        claim_id=claim_id(9_999),
        evidence_refs=(),
        clause_id=silent,
        applies_to=truth.key.artifact,
    )
    plan = plan_of(oracle, truth, (*claims, extra))
    assert isinstance(plan, PlanUnreadable)
    assert (plan.what, plan.clauses) == (Unreadable.CLAUSE, (silent,))
    assert silent in plan.message


def test_a_clause_cited_for_an_artifact_nobody_can_read_makes_the_plan_unreadable(
    world: SealedWorld,
) -> None:
    # With the calendar down the meeting's own record is unreadable; a clause the report
    # cites for it may or may not apply, and the plan says so.
    for scenario in world.scenarios:
        normal = oracle_for(world, scenario, NORMAL)
        assert isinstance(normal, Answerable)
        meeting = next(
            (t for t in normal.impacts if t.key.artifact.kind is EntityKind.EVENT), None
        )
        cited = [c for c in normal.constraints if meeting and c.applies_to == meeting.key.artifact]
        if meeting is None or not cited:
            continue
        claims = truthful_report(normal)
        down = oracle_for(world, scenario, NORMAL.without(Source.CALENDAR))
        assert isinstance(down, Answerable)
        action = next(a for a in of_type(claims, CoverageAction) if a.impact_key == meeting.key)
        plan = read_plan(
            action,
            [ConstraintKey(c.clause_id, c.applies_to) for c in cited],
            of_type(claims, CandidateAssessment),
            down.view,
            scenario.investigated_leave.span,
            scenario.spec.reference_timezone,
        )
        assert isinstance(plan, PlanUnreadable)
        assert plan.what is Unreadable.ARTIFACT
        return
    raise AssertionError("the golden plan scopes no clause by a meeting")
