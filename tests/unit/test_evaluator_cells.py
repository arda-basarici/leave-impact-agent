"""Evaluated runs are grouped by system and assigned condition, every scenario of the world in
every arm, and cut at the whole, each tier and each class. The arm is the condition a run was
assigned, whatever its reads met. A retried run is one run whose counted attempt the plan
names, with every attempt kept; a scenario short of its intended runs is counted missing and
one beyond them surplus. The accounting says how each counted run ended. The arms are the
ones the plan registers: one that produced no export is built with every run missing, and one
that arrived unregistered says so."""

from dataclasses import replace

import pytest

from leaveimpact.core import RunCondition, ScenarioId, Source, System, SystemKind
from leaveimpact.evaluator.cells import (
    OVERALL,
    Cell,
    CountedAttempt,
    MissingRepeat,
    Preregistered,
    StratumKind,
    accounting_of,
    arms,
    cells_of,
    condition_name,
)
from leaveimpact.evaluator.grading import Excluded, ExcludedReason, Graded, LimitedReason
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import evaluate_run
from leaveimpact.world.scenario import Tier
from tests.unit.evaluation_fixture import NORMAL, REFERENCE, evaluated, relabelled, truthful
from tests.unit.export_fixture import provider_failed_export
from tests.unit.report_fixture import renumbered
from tests.unit.throwaway_world import loaded_world

OTHER = System(SystemKind.RULES_ONLY, "other")
TRACKER_DOWN = NORMAL.without(Source.JIRA)


def plan(
    intended_repeats: int = 1,
    counted_attempt: CountedAttempt = CountedAttempt.FIRST,
    registered: tuple[tuple[System, RunCondition], ...] = ((REFERENCE, NORMAL),),
) -> Preregistered:
    return Preregistered(
        0.95, 7, 1_000, intended_repeats, counted_attempt, MissingRepeat.NOT_PASSED, registered, 3
    )


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def test_every_arm_holds_every_scenario_and_is_cut_at_the_whole_each_tier_and_each_class(
    world: SealedWorld,
) -> None:
    reference = [evaluated(world, scenario) for scenario in world.scenarios]
    # A second system that ran only the first tier's scenarios.
    partial = [
        relabelled(evaluation, system=OTHER)
        for evaluation, scenario in zip(reference, world.scenarios, strict=True)
        if scenario.key.tier is Tier.STRUCTURED
    ]
    both = plan(registered=((OTHER, NORMAL), (REFERENCE, NORMAL)))
    first, second = arms(world, [*partial, *reference], both)
    assert (first.name, second.name) == ("rules_only/other normal", "rules_only/reference normal")
    for arm in (first, second):
        assert [runs.scenario_id for runs in arm.scenarios] == [s.spec.id for s in world.scenarios]
        assert arm.unplaced == ()
    # A scenario a system never ran is a missing run of its arm, not an absent row.
    assert sum(len(runs.counted) for runs in first.scenarios) == 10
    assert sum(runs.missing for runs in first.scenarios) == 20

    cells = cells_of(second)
    assert cells[0].stratum == OVERALL and len(cells[0].scenarios) == 30
    tiers = [cell for cell in cells if cell.stratum.kind is StratumKind.TIER]
    assert [(cell.stratum.name, len(cell.scenarios)) for cell in tiers] == [
        ("structured", 10),
        ("fragmented", 10),
        ("adversarial", 10),
    ]
    classes = [cell for cell in cells if cell.stratum.kind is StratumKind.CLASS]
    assert sum(len(cell.scenarios) for cell in classes) == 30
    assert all(1 <= len(cell.scenarios) <= 4 for cell in classes)
    # A tier and the whole carry intervals; a class shows its raw counts only.
    assert all(cell.stratum.estimated for cell in (cells[0], *tiers))
    assert not any(cell.stratum.estimated for cell in classes)
    # The whole is resampled within its tiers, a tier within itself.
    assert [len(group) for group in cells[0].by_tier()] == [10, 10, 10]
    assert [len(group) for group in tiers[1].by_tier()] == [10]


def test_the_arm_is_the_condition_assigned_whatever_the_reads_met(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    # Scheduled to lose the tracker, and every read was answered: the outage was never met.
    never_met = evaluated(world, scenario, assigned=(Source.JIRA,))
    # Scheduled nothing, and the tracker failed all the same.
    unscheduled = relabelled(
        evaluated(world, scenario, down=(Source.JIRA,), assigned=()), run_id="run-2"
    )
    met = relabelled(evaluated(world, scenario, down=(Source.JIRA,)), run_id="run-3")
    assert isinstance(never_met.outcome, Graded) and never_met.outcome.condition == NORMAL
    assert never_met.assigned == TRACKER_DOWN

    two_arms = plan(
        intended_repeats=2, registered=((REFERENCE, NORMAL), (REFERENCE, TRACKER_DOWN))
    )
    normal, tracker_down = arms(world, [never_met, unscheduled, met], two_arms)
    assert normal.registered and tracker_down.registered
    assert (normal.assigned, tracker_down.assigned) == (NORMAL, TRACKER_DOWN)
    assert condition_name(tracker_down.assigned) == "jira down"
    in_the_outage_arm = accounting_of(cells_of(tracker_down)[0], plan(intended_repeats=2))
    assert in_the_outage_arm.made == 2
    assert in_the_outage_arm.observed == ((TRACKER_DOWN, 1), (NORMAL, 1))
    assert (in_the_outage_arm.unexercised, in_the_outage_arm.unscheduled) == (1, 0)
    in_the_normal_arm = accounting_of(cells_of(normal)[0], plan(intended_repeats=2))
    assert in_the_normal_arm.observed == ((TRACKER_DOWN, 1),)
    assert (in_the_normal_arm.unexercised, in_the_normal_arm.unscheduled) == (0, 1)


def test_a_retried_run_is_one_run_and_the_plan_says_which_attempt_counts(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    failed = evaluate_run(world, provider_failed_export(world, scenario))
    retried = relabelled(
        evaluated(world, scenario), run_id="run-8", attempt=2, system=failed.outcome.header.system
    )
    assert isinstance(failed.outcome, Excluded) and failed.outcome.header.run_id == "run-8"

    for counted_attempt, counted_is in (
        (CountedAttempt.FIRST, failed),
        (CountedAttempt.LAST, retried),
    ):
        chosen = plan(
            counted_attempt=counted_attempt,
            registered=((failed.outcome.header.system, NORMAL),),
        )
        (arm,) = arms(world, [retried, failed], chosen)
        runs = arm.scenarios[0]
        assert runs.counted == (counted_is,)
        # Both attempts were paid for and both are kept, in attempt order.
        assert runs.attempts == (failed, retried)
        accounting = accounting_of(cells_of(arm)[0], chosen)
        assert (accounting.made, accounting.attempts) == (1, 2)
        first = counted_attempt is CountedAttempt.FIRST
        assert accounting.graded == (0 if first else 1)
        assert accounting.excluded == (
            ((ExcludedReason.FAILED_BY_INFRASTRUCTURE, 1),) if first else ()
        )


def test_a_shortfall_and_a_surplus_of_runs_are_counted_per_scenario_and_never_cancel(
    world: SealedWorld,
) -> None:
    one, two, three = world.scenarios[:3]
    runs = [
        evaluated(world, one),
        *(relabelled(evaluated(world, three), run_id=f"run-{n}") for n in (1, 2, 3)),
    ]
    two_intended = plan(intended_repeats=2)
    (arm,) = arms(world, runs, two_intended)
    by_id = {each.scenario_id: each for each in arm.scenarios}
    assert [by_id[s.spec.id].missing for s in (one, two, three)] == [1, 2, 0]
    accounting = accounting_of(Cell(arm, OVERALL, arm.scenarios[:3]), two_intended)
    assert (accounting.intended, accounting.made) == (6, 4)
    assert (accounting.missing, accounting.surplus) == (3, 1)


def test_the_accounting_says_how_each_counted_run_ended(world: SealedWorld) -> None:
    first, second, third, fourth, fifth = world.scenarios[:5]
    claims = truthful(world, second, NORMAL)
    foreign = relabelled(evaluated(world, fifth))
    foreign = replace(
        foreign,
        outcome=replace(
            foreign.outcome,
            header=replace(foreign.outcome.header, scenario_id=ScenarioId("scn_999")),
        ),
    )
    runs = [
        evaluated(world, first),
        evaluated(world, second, claims=(*claims, renumbered(claims[0], 9_999))),
        evaluated(
            world, third, down=(Source.FRAPPE,), assigned=(), claims=truthful(world, third, NORMAL)
        ),
        relabelled(evaluate_run(world, provider_failed_export(world, fourth)), system=REFERENCE),
        foreign,
    ]
    (arm,) = arms(world, runs, plan())
    # A run of a scenario the sealed world does not hold is kept on its arm, unplaced.
    assert arm.unplaced == (foreign,)
    accounting = accounting_of(Cell(arm, OVERALL, arm.scenarios[:5]), plan())
    assert (accounting.scenarios, accounting.intended, accounting.made, accounting.missing) == (
        5,
        5,
        4,
        1,
    )
    assert (accounting.graded, accounting.structurally_invalid) == (2, 1)
    assert accounting.limited == ((LimitedReason.UNREADABLE_LEAVE, 1),)
    assert accounting.excluded == ((ExcludedReason.FAILED_BY_INFRASTRUCTURE, 1),)
    assert accounting.unscheduled == 1  # the HR system failed and nobody scheduled it
    assert (
        accounting.record_disagreements,
        accounting.with_integrity_findings,
        accounting.with_operation_findings,
        accounting.with_cost_findings,
    ) == (0, 0, 0, 0)
    # The unplaced attempt is counted in the whole, and in no tier or class.
    assert accounting.unplaced == 1
    assert all(accounting_of(cell, plan()).unplaced == 0 for cell in cells_of(arm)[1:])


def test_one_export_given_twice_is_refused_where_its_runs_are_grouped(world: SealedWorld) -> None:
    run = evaluated(world, world.scenarios[0])
    with pytest.raises(ValueError, match="holds one attempt twice"):
        arms(world, [run, run], plan())
    # The same run under another attempt number is a retry, and is fine.
    arms(world, [run, relabelled(run, attempt=2)], plan())


def test_a_registered_arm_with_no_export_is_built_with_every_run_missing(
    world: SealedWorld,
) -> None:
    # The second system never produced an export: its arm must not vanish from the tables.
    runs = [evaluated(world, scenario) for scenario in world.scenarios]
    registered = plan(intended_repeats=2, registered=((OTHER, NORMAL), (REFERENCE, NORMAL)))
    silent, reference = arms(world, runs, registered)
    assert (silent.system, silent.assigned, silent.registered) == (OTHER, NORMAL, True)
    assert [runs.scenario_id for runs in silent.scenarios] == [s.spec.id for s in world.scenarios]
    accounting = accounting_of(cells_of(silent)[0], registered)
    assert (accounting.intended, accounting.made, accounting.missing) == (60, 0, 60)
    assert (accounting.graded, accounting.attempts) == (0, 0)
    assert accounting_of(cells_of(reference)[0], registered).missing == 30
    # With nothing registered but the reference, the silent arm has no row to be missing from.
    assert len(arms(world, runs, plan())) == 1


def test_an_arm_that_arrived_unregistered_is_built_and_says_so(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    stray = relabelled(evaluated(world, scenario, down=(Source.JIRA,)), system=OTHER)
    unregistered, reference = arms(world, [evaluated(world, scenario), stray], plan())
    assert (reference.registered, unregistered.registered) == (True, False)
    assert (unregistered.system, unregistered.assigned) == (OTHER, TRACKER_DOWN)
    assert accounting_of(cells_of(unregistered)[0], plan()).made == 1


def test_a_structurally_invalid_report_is_counted_where_its_run_ended(world: SealedWorld) -> None:
    graded_one, limited_one = world.scenarios[:2]
    claims = truthful(world, graded_one, NORMAL)
    other_claims = truthful(world, limited_one, NORMAL)
    runs = [
        evaluated(world, graded_one, claims=(*claims, renumbered(claims[0], 9_999))),
        evaluated(
            world,
            limited_one,
            down=(Source.FRAPPE,),
            assigned=(),
            claims=(*other_claims, renumbered(other_claims[0], 9_999)),
        ),
    ]
    (arm,) = arms(world, runs, plan())
    accounting = accounting_of(cells_of(arm)[0], plan())
    assert (accounting.graded, accounting.structurally_invalid) == (1, 1)
    assert accounting.limited == ((LimitedReason.UNREADABLE_LEAVE, 1),)
    assert accounting.limited_structurally_invalid == 1


def test_the_plan_refuses_what_no_preregistration_could_mean() -> None:
    kept = (CountedAttempt.FIRST, MissingRepeat.LEFT_OUT, ((REFERENCE, NORMAL),), 3)
    with pytest.raises(ValueError, match="at least one arm is registered"):
        Preregistered(0.95, 7, 1_000, 1, *kept[:2], (), 3)
    with pytest.raises(ValueError, match="registered once"):
        Preregistered(0.95, 7, 1_000, 1, *kept[:2], ((REFERENCE, NORMAL), (REFERENCE, NORMAL)), 3)
    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        Preregistered(1.0, 7, 1_000, 1, *kept)
    with pytest.raises(ValueError, match="at least one resample"):
        Preregistered(0.95, 7, 0, 1, *kept)
    with pytest.raises(ValueError, match="at least one run per scenario"):
        Preregistered(0.95, 7, 1_000, 0, *kept)
