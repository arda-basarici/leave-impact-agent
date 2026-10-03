"""The registration as the evaluator reads it. The three registered checks answer mechanically:
a truthful report over a full read passes all three, a missing or a wrong-kind action fails
the action check and correct whole and leaves the replay alone, a claim the reads do not
support fails the replay alone, an empty report is outside the replay check, and a run that
was not graded is outside the other two. The registries resolve the registered names and
refuse any other. The projection gives the plan the tables are cut under, over the arms whose
variant is resolved, naming the ones it left out. The scenario sets and the development
selection: two per tier, the same draw every time, by tier alone; the primary set is the
rest, refused while the selection is pending. And a repeat the plan intended and nobody made
keeps its scenario a repeated one."""

import re
from dataclasses import replace
from pathlib import Path
from traceback import format_exception

import pytest

from leaveimpact.core import (
    CandidateAssessment,
    ClaimType,
    CoverageAction,
    CoverageActionKind,
    FailureCategory,
    Pending,
    Registration,
    RunCondition,
    ScenarioId,
    ScenarioSetName,
    Source,
    System,
    SystemKind,
    decode_registration_bytes,
)
from leaveimpact.evaluator.cells import (
    CountedAttempt,
    MissingRepeat,
    arms,
    cells_of,
    within,
)
from leaveimpact.evaluator.grading import Graded
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.registered import (
    CHECKS,
    MEASURES,
    development_selection,
    preregistered,
    registered_check,
    registered_measure,
    scenario_set,
)
from leaveimpact.evaluator.run_checks import CORRECT_WHOLE, EXPECTED_ACTION, REPRODUCED_WHOLE
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.tables import Reading, compare_check, estimate_check
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from leaveimpact.world import Scenario
from leaveimpact.world.scenario import Tier
from tests.unit.evaluation_fixture import NORMAL, REFERENCE, evaluated, relabelled, truthful
from tests.unit.export_fixture import provider_failed_export
from tests.unit.report_fixture import of_type, swapped, without
from tests.unit.throwaway_world import loaded_world

DRAFT = decode_registration_bytes(
    (Path(__file__).resolve().parents[2] / "preregistration" / "registration.json").read_bytes()
)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def assigning(world: SealedWorld) -> Scenario:
    """A scenario whose truthful report assigns someone."""
    return next(
        scenario
        for scenario in world.scenarios
        if any(
            action.action is CoverageActionKind.ASSIGN
            for action in of_type(truthful(world, scenario, NORMAL), CoverageAction)
        )
    )


def answers(evaluation: Evaluation) -> tuple[bool | None, bool | None, bool | None]:
    """A run's answers to correct whole, expected action and reproduced whole."""
    return (
        CORRECT_WHOLE.of(evaluation),
        EXPECTED_ACTION.of(evaluation),
        REPRODUCED_WHOLE.of(evaluation),
    )


def with_development(registration: Registration, *ids: str) -> Registration:
    sets = replace(registration.scenario_sets, development=tuple(ScenarioId(i) for i in ids))
    return replace(registration, scenario_sets=sets)


# --- The three checks --------------------------------------------------------------------------


def test_a_truthful_report_over_a_full_read_passes_all_three_checks(world: SealedWorld) -> None:
    for scenario in world.scenarios:
        assert answers(evaluated(world, scenario)) == (True, True, True), scenario.spec.id


def test_a_missing_or_a_wrong_kind_action_fails_the_action_check(
    world: SealedWorld, assigning: Scenario
) -> None:
    report = truthful(world, assigning, NORMAL)
    action = next(
        claim
        for claim in of_type(report, CoverageAction)
        if claim.action is CoverageActionKind.ASSIGN
    )
    # Nothing was claimed that the reads do not support: the replay is left alone.
    dropped = evaluated(world, assigning, claims=without(report, action))
    assert answers(dropped) == (False, False, True)

    uncovered = replace(action, action=CoverageActionKind.UNCOVERED, assignee_ids=())
    wrong = evaluated(world, assigning, claims=swapped(report, action, uncovered))
    assert isinstance(wrong.outcome, Graded) and wrong.outcome.rows.structurally_valid
    assert answers(wrong) == (False, False, False)


def test_a_missing_required_assessment_fails_correct_whole_and_not_the_action_check(
    world: SealedWorld, assigning: Scenario
) -> None:
    oracle = oracle_for(world, assigning, NORMAL)
    assert isinstance(oracle, Answerable)
    report = truthful(world, assigning, NORMAL)
    required = next(
        claim
        for claim in of_type(report, CandidateAssessment)
        if (truth := oracle.impact(claim.impact_key)) and claim.employee_id in truth.probe
    )
    lacking = evaluated(world, assigning, claims=without(report, required))
    correct, action, _ = answers(lacking)
    assert (correct, action) == (False, True)


def test_a_report_the_reads_do_not_support_fails_the_replay_check_alone(
    world: SealedWorld, assigning: Scenario
) -> None:
    unread = evaluated(world, assigning, operations=())
    assert isinstance(unread.outcome, Graded)
    assert answers(unread) == (True, True, False)


def test_an_empty_report_is_outside_the_replay_check_and_fails_the_others(
    world: SealedWorld, assigning: Scenario
) -> None:
    empty = evaluated(world, assigning, claims=())
    assert isinstance(empty.outcome, Graded)
    assert answers(empty) == (False, False, None)


def test_a_run_that_was_not_graded_is_outside_correct_whole_and_the_action_check(
    world: SealedWorld, assigning: Scenario
) -> None:
    failed = evaluate_run(world, provider_failed_export(world, assigning))
    assert answers(failed) == (None, None, None)
    # A limited run has no expected answer, and its report is still replayed.
    limited = evaluated(
        world,
        assigning,
        down=(Source.FRAPPE,),
        assigned=(),
        claims=truthful(world, assigning, NORMAL),
    )
    assert not isinstance(limited.outcome, Graded)
    correct, action, reproduced = answers(limited)
    assert (correct, action) == (None, None)
    assert reproduced is False


# --- The registries ----------------------------------------------------------------------------


def test_every_name_the_draft_registers_resolves_and_any_other_is_refused() -> None:
    assert set(DRAFT.statistics.checks) == set(CHECKS)
    assert set(DRAFT.statistics.measures) == set(MEASURES)
    for name in DRAFT.statistics.checks:
        assert registered_check(name).name == name
    assert registered_measure("strict_precision").name == "strict precision: all claims"
    typed = registered_measure("recall", ClaimType.COVERAGE_ACTION)
    assert typed.name == "recall: coverage_action"
    with pytest.raises(ValueError, match="no check is registered as 'plausible'"):
        registered_check("plausible")
    with pytest.raises(ValueError, match="no measure is registered as 'f1'"):
        registered_measure("f1")


# --- The projection ----------------------------------------------------------------------------


def test_the_draft_projects_the_rules_only_arms_and_names_the_ten_it_left_out() -> None:
    projection = preregistered(DRAFT)
    plan = projection.plan
    assert (plan.confidence, plan.seed, plan.resamples) == (0.95, 20261003, 10_000)
    assert (plan.intended_repeats, plan.max_attempts) == (1, 3)
    assert plan.counted_attempt is CountedAttempt.EARLIEST_NOT_INFRASTRUCTURE
    assert plan.missing_repeat is MissingRepeat.NOT_PASSED
    reference = System(SystemKind.RULES_ONLY, "reference")
    normal = RunCondition.all_reachable()
    assert plan.arms == tuple(
        (reference, normal.without(*down))
        for down in ((), (Source.JIRA,), (Source.CALENDAR,), (Source.FRAPPE,), (Source.CORPUS,))
    )
    assert len(projection.pending_arms) == 10
    assert {arm.system for arm in projection.pending_arms} == {
        SystemKind.AGENT,
        SystemKind.SINGLE_SHOT,
    }


def test_the_projection_refuses_what_this_evaluator_does_not_implement() -> None:
    statistics = DRAFT.statistics
    descriptive = replace(statistics.descriptive, checks=("plausible",))
    unknown = replace(
        DRAFT,
        statistics=replace(statistics, checks=("plausible",), primary=(), descriptive=descriptive),
    )
    with pytest.raises(ValueError, match="no check is registered as 'plausible'"):
        preregistered(unknown)

    accounting = DRAFT.run_accounting
    retry = replace(accounting.retry, after=FailureCategory.DEFECT)
    after_defect = replace(accounting, retry=retry)
    with pytest.raises(ValueError, match="the registration retries after defect"):
        preregistered(replace(DRAFT, run_accounting=after_defect))

    systems = tuple(
        replace(system, variant=Pending("not named")) for system in DRAFT.systems
    )
    with pytest.raises(ValueError, match="every system's variant is pending"):
        preregistered(replace(DRAFT, systems=systems))


# --- The scenario sets -------------------------------------------------------------------------


def test_the_development_selection_is_two_per_tier_and_the_same_every_time(
    world: SealedWorld,
) -> None:
    selected = development_selection(world, DRAFT)
    assert selected == development_selection(world, DRAFT)
    assert len(selected) == len(set(selected)) == 6 and list(selected) == sorted(selected)
    tiers = [scenario.key.tier for id in selected if (scenario := world.scenario(id))]
    assert {tier: tiers.count(tier) for tier in Tier} == dict.fromkeys(Tier, 2)

    # Another seed draws another selection: the draw is the registration's, not the code's.
    reseeded = replace(DRAFT, statistics=replace(DRAFT.statistics, seed=DRAFT.statistics.seed + 1))
    assert development_selection(world, reseeded) != selected

    three_each = replace(DRAFT.scenario_sets, development_size=9, development_per_tier=3)
    assert len(development_selection(world, replace(DRAFT, scenario_sets=three_each))) == 9
    eight = replace(DRAFT.scenario_sets, development_size=8, development_per_tier=2)
    with pytest.raises(ValueError, match="need 4 tiers, the world has 3"):
        development_selection(world, replace(DRAFT, scenario_sets=eight))


def test_the_primary_set_is_the_rest_and_is_refused_while_the_selection_is_pending(
    world: SealedWorld,
) -> None:
    every = tuple(scenario.spec.id for scenario in world.scenarios)
    assert scenario_set(world, DRAFT, ScenarioSetName.FULL) == every
    with pytest.raises(ValueError, match="the development scenarios are pending"):
        scenario_set(world, DRAFT, ScenarioSetName.PRIMARY)

    selected = development_selection(world, DRAFT)
    resolved = with_development(DRAFT, *selected)
    primary = scenario_set(world, resolved, ScenarioSetName.PRIMARY)
    assert len(primary) == 24 and not set(primary) & set(selected)
    assert set(primary) | set(selected) == set(every)
    held_out = [scenario.key.tier for id in primary if (scenario := world.scenario(id))]
    assert {tier: held_out.count(tier) for tier in Tier} == dict.fromkeys(Tier, 8)

    strangers = with_development(DRAFT, *selected[:5], "scenario_999")
    with pytest.raises(ValueError, match="the world holds no scenario scenario_999"):
        scenario_set(world, strangers, ScenarioSetName.PRIMARY)


def test_a_development_list_that_is_not_two_from_each_tier_is_refused_without_saying_which(
    world: SealedWorld,
) -> None:
    structured = [s.spec.id for s in world.scenarios if s.key.tier is Tier.STRUCTURED]
    selected = development_selection(world, DRAFT)
    one_tier = with_development(DRAFT, *structured[:6])
    # Balanced but for one scenario moved between tiers: three, one and two.
    moved = with_development(
        DRAFT, *selected[:2], next(s for s in structured if s not in selected), *selected[3:]
    )
    for lopsided in (one_tier, moved):
        with pytest.raises(ValueError) as refused:
            scenario_set(world, lopsided, ScenarioSetName.PRIMARY)
        printed = "".join(format_exception(refused.value))
        assert "are not 2 from each tier of the world" in printed
        # Which listed scenarios share a tier is sealed: no tier, no id, no count per tier.
        assert not any(tier.value in printed for tier in Tier)
        assert re.search(r"scenario_\d", printed) is None
        assert refused.value.__cause__ is None and refused.value.__context__ is None
    # The full set never depended on the list.
    assert len(scenario_set(world, one_tier, ScenarioSetName.FULL)) == 30


def test_an_arm_cut_to_a_scenario_set_holds_those_scenarios_in_its_own_order(
    world: SealedWorld,
) -> None:
    plan = preregistered(DRAFT).plan
    runs = [evaluated(world, scenario) for scenario in world.scenarios]
    stray = evaluated(world, world.scenarios[0])
    header = replace(stray.outcome.header, scenario_id=ScenarioId("scn_999"), run_id="run-x")
    stray = replace(stray, outcome=replace(stray.outcome, header=header))
    arm = next(arm for arm in arms(world, [*runs, stray], plan) if arm.assigned == NORMAL)
    assert len(arm.unplaced) == 1

    selected = development_selection(world, DRAFT)
    primary = scenario_set(world, with_development(DRAFT, *selected), ScenarioSetName.PRIMARY)
    cut = within(arm, primary)
    assert tuple(held.scenario_id for held in cut.scenarios) == primary
    # An attempt no scenario could place belongs to no set.
    assert cut.unplaced == () and cut.registered
    assert len(cells_of(cut)[0].scenarios) == 24
    with pytest.raises(ValueError, match="the arm holds no scenario scenario_999"):
        within(arm, [ScenarioId("scenario_999")])


# --- The form follows the plan -----------------------------------------------------------------


def test_a_repeat_intended_and_never_made_keeps_its_scenario_a_repeated_one(
    world: SealedWorld,
) -> None:
    other = System(SystemKind.RULES_ONLY, "other")
    two_runs = replace(
        preregistered(DRAFT).plan, intended_repeats=2, arms=((other, NORMAL), (REFERENCE, NORMAL))
    )
    scenario = world.scenarios[0]
    once = evaluated(world, scenario)
    theirs, mine = arms(world, [once, relabelled(once, system=other)], two_runs)
    first = replace(cells_of(mine)[0], scenarios=(mine.scenarios[0],))
    second = replace(cells_of(theirs)[0], scenarios=(theirs.scenarios[0],))
    for reading in Reading:
        estimate = estimate_check(first, CORRECT_WHOLE, reading, two_runs)
        assert (estimate.runs, estimate.missing, estimate.unverifiable) == (1, 1, 0)
        assert estimate.wilson is None and estimate.bootstrap is not None, reading
        comparison = compare_check(first, second, CORRECT_WHOLE, reading, two_runs)
        assert comparison.two_by_two is None and comparison.interval is not None, reading

    # With one run intended and one made, the scenario is a single trial as before.
    one_run = replace(two_runs, intended_repeats=1)
    theirs, mine = arms(world, [once, relabelled(once, system=other)], one_run)
    first = replace(cells_of(mine)[0], scenarios=(mine.scenarios[0],))
    second = replace(cells_of(theirs)[0], scenarios=(theirs.scenarios[0],))
    estimate = estimate_check(first, CORRECT_WHOLE, Reading.CONDITIONAL, one_run)
    assert estimate.wilson is not None and estimate.bootstrap is None
    comparison = compare_check(first, second, CORRECT_WHOLE, Reading.CONDITIONAL, one_run)
    assert comparison.two_by_two == (1, 0, 0, 0)
