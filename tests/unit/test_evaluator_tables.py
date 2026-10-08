"""A measure or a check estimated in a cell, two systems paired, and what a cell cost. The
group's gate is here: truthful reports over full reads put every answer measure at its ceiling
with the accounting adding up; eight of ten scenarios passing a check is 49 to 94 percent; a
zero denominator is not estimable and never a zero; a seeded interval reproduces whatever was
computed before it; and a system compared with itself differs by exactly nothing."""

from collections.abc import Set
from dataclasses import replace

import pytest

from leaveimpact.core import (
    AttributionKind,
    CandidateAssessment,
    DispatchPhase,
    DispatchSite,
    Failure,
    FailureCategory,
    ModelCall,
    ModelCallId,
    RefusedBeforeSend,
    ReportedUsage,
    RunCondition,
    ScenarioId,
    Source,
    System,
    SystemKind,
    cost_of_reported,
)
from leaveimpact.evaluator.cells import (
    Arm,
    Cell,
    CountedAttempt,
    MissingRepeat,
    Preregistered,
    StratumKind,
    accounting_of,
    arms,
    cells_of,
)
from leaveimpact.evaluator.evidence_measures import (
    RETRIEVAL_MEASURES,
    SOURCE_MEASURES,
    grounded_end_to_end_share,
    resolving_share,
    standing_share,
    strictly_grounded_share,
)
from leaveimpact.evaluator.grading import Graded, Limited
from leaveimpact.evaluator.intervals import Unresolved
from leaveimpact.evaluator.measures import ANSWER_MEASURES, recall, strict_precision
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.replay import Standing
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.tables import (
    Check,
    Reading,
    Spread,
    compare_check,
    compare_ratio,
    cost_ledger,
    estimate_check,
    estimate_ratio,
)
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from leaveimpact.world import Scenario
from leaveimpact.world.scenario import Tier
from tests.unit.evaluation_fixture import (
    BASE,
    NORMAL,
    PADDED,
    REFERENCE,
    evaluated,
    relabelled,
    truthful,
)
from tests.unit.export_fixture import (
    BASIS,
    ROLE,
    SELECTION,
    agent_export,
    answered_call,
    dispatch,
    provider_failed_export,
)
from tests.unit.report_fixture import of_type, without
from tests.unit.throwaway_world import loaded_world

OTHER = System(SystemKind.RULES_ONLY, "other")
CONDITIONAL, END_TO_END = Reading.CONDITIONAL, Reading.END_TO_END


def plan(
    intended_repeats: int = 1,
    missing_repeat: MissingRepeat = MissingRepeat.NOT_PASSED,
    registered: tuple[tuple[System, RunCondition, str], ...] = ((REFERENCE, NORMAL, BASE),),
) -> Preregistered:
    return Preregistered(
        0.95,
        20_261_002,
        2_000,
        intended_repeats,
        CountedAttempt.FIRST,
        missing_repeat,
        registered,
        3,
    )


TWO_SYSTEMS = ((OTHER, NORMAL, BASE), (REFERENCE, NORMAL, BASE))


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def truthful_runs(world: SealedWorld) -> list[Evaluation]:
    return [evaluated(world, scenario) for scenario in world.scenarios]


def cell_of(arm: Arm, kind: StratumKind = StratumKind.OVERALL, name: str = "overall") -> Cell:
    return next(c for c in cells_of(arm) if (c.stratum.kind, c.stratum.name) == (kind, name))


def tier_of(arm: Arm, tier: Tier) -> Cell:
    return cell_of(arm, StratumKind.TIER, tier.value)


def lacking_a_required_assessment(world: SealedWorld, scenario: Scenario) -> Evaluation:
    """A run of ``scenario`` whose report leaves out one assessment the oracle requires."""
    oracle = oracle_for(world, scenario, NORMAL)
    assert isinstance(oracle, Answerable)
    report = truthful(world, scenario, NORMAL)
    required = next(
        claim
        for claim in of_type(report, CandidateAssessment)
        if (truth := oracle.impact(claim.impact_key)) and claim.employee_id in truth.probe
    )
    return evaluated(world, scenario, claims=without(report, required))


def passes_in(passing: Set[str]) -> Check:
    """A stand-in check: a graded run of a scenario in ``passing`` passes. The named checks
    are the preregistration's; the aggregation is a function over any."""

    def of(evaluation: Evaluation) -> bool | None:
        if not isinstance(evaluation.outcome, Graded):
            return None
        return evaluation.outcome.header.scenario_id in passing

    return Check("stand-in", of)


# --- The gate ---------------------------------------------------------------------------


def test_truthful_reports_put_every_answer_measure_at_its_ceiling_and_the_accounting_adds_up(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    (arm,) = arms(world, truthful_runs, plan())
    ceiling = (
        *ANSWER_MEASURES,
        standing_share(Standing.REPRODUCED, Graded),
        grounded_end_to_end_share(Graded),
        RETRIEVAL_MEASURES[0],
        *SOURCE_MEASURES[:2],
    )
    for cell in cells_of(arm):
        accounting = accounting_of(cell, plan())
        assert (accounting.intended, accounting.made, accounting.graded) == (
            (len(cell.scenarios),) * 3
        )
        assert (accounting.missing, accounting.limited, accounting.excluded) == (0, (), ())
        for measure in ceiling:
            estimate = estimate_ratio(cell, measure, plan())
            if estimate.denominator == 0:
                # Nothing of the kind in this cell: not estimable, and not a perfect score.
                assert (estimate.value, estimate.interval) == (None, None)
                continue
            assert estimate.value == 1.0, (cell.stratum.name, measure.name)
            assert estimate.scenarios == len(cell.scenarios)
            if cell.stratum.estimated:
                # At the ceiling every resample is 1.0: the bootstrap resolves nothing, and
                # says so instead of printing an interval of no width.
                assert estimate.interval is None
                assert estimate.unresolved is Unresolved.EVERY_RESAMPLE_EQUAL
            else:
                # A class shows its raw counts, no interval and no reason for lacking one.
                assert (estimate.interval, estimate.unresolved) == (None, None)
    overall = estimate_ratio(cell_of(arm), recall(), plan())
    assert (overall.numerator, overall.denominator, overall.scenarios) == (161, 161, 30)


def test_eight_of_ten_scenarios_passing_a_check_is_forty_nine_to_ninety_four_percent(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    (arm,) = arms(world, truthful_runs, plan())
    structured = tier_of(arm, Tier.STRUCTURED)
    passing = {runs.scenario_id for runs in structured.scenarios[:8]}
    estimate = estimate_check(structured, passes_in(passing), CONDITIONAL, plan())
    assert (estimate.passed, estimate.scenarios, estimate.value) == (8, 10, 0.8)
    # One run per scenario: x of n, and Wilson's interval.
    assert estimate.wilson is not None and estimate.bootstrap is None
    assert (round(estimate.wilson.low, 2), round(estimate.wilson.high, 2)) == (0.49, 0.94)
    # A class has its counts and no interval.
    in_a_class = next(c for c in cells_of(arm) if c.stratum.kind is StratumKind.CLASS)
    by_class = estimate_check(in_a_class, passes_in(passing), CONDITIONAL, plan())
    assert (by_class.wilson, by_class.bootstrap) == (None, None)


def test_a_zero_denominator_is_not_estimable_and_never_a_zero(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    (arm,) = arms(world, truthful_runs, plan())
    overall = cell_of(arm)
    # The truthful report cites nothing: thirty scenarios in scope, nothing to count in any.
    uncited = estimate_ratio(overall, resolving_share(Graded), plan())
    assert (uncited.numerator, uncited.denominator) == (0, 0)
    assert (uncited.value, uncited.interval) == (None, None)
    assert uncited.unresolved is Unresolved.ZERO_DENOMINATOR
    assert (uncited.scenarios, uncited.empty) == (30, 30)
    # No limited run in the cell: no scenario is in the measure's scope at all.
    of_limited = estimate_ratio(overall, grounded_end_to_end_share(Limited), plan())
    assert (of_limited.scenarios, of_limited.value, of_limited.interval) == (0, None, None)
    assert of_limited.unresolved is Unresolved.NO_ELIGIBLE_SCENARIO
    # Conflicts are expected in a few scenarios only: a replicate that drew none of them has
    # no ratio and is left out, never read as zero, and the ones that remain are all 1.0.
    conflicts = next(m for m in ANSWER_MEASURES if m.name == "recall: source_conflict")
    sparse = estimate_ratio(tier_of(arm, Tier.ADVERSARIAL), conflicts, plan())
    assert sparse.value == 1.0 and 0 < sparse.empty < sparse.scenarios
    assert (sparse.interval, sparse.unresolved) == (None, Unresolved.EVERY_RESAMPLE_EQUAL)


def test_a_seeded_interval_reproduces_whatever_was_computed_before_it(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    (arm,) = arms(world, truthful_runs, plan())
    overall = cell_of(arm)
    strict = strictly_grounded_share(Graded)
    first = estimate_ratio(overall, strict, plan())
    estimate_ratio(overall, recall(), plan())
    estimate_ratio(tier_of(arm, Tier.FRAGMENTED), strict, plan())
    assert estimate_ratio(overall, strict, plan()) == first
    assert (first.numerator, first.denominator) == (573, 1_001)
    interval = first.interval
    assert interval is not None and first.value is not None
    assert interval.low < first.value < interval.high
    assert (interval.confidence, interval.resamples, interval.valid) == (0.95, 2_000, 2_000)
    # Its own stream: another stratum draws from another seed, and so does another measure,
    # which the seed test of the intervals holds by name.
    by_tier = estimate_ratio(tier_of(arm, Tier.FRAGMENTED), strict, plan()).interval
    other = estimate_ratio(tier_of(arm, Tier.ADVERSARIAL), strict, plan()).interval
    assert by_tier is not None and other is not None
    assert len({interval.seed, by_tier.seed, other.seed}) == 3
    # Another seed in the plan, another interval.
    reseeded = estimate_ratio(overall, strict, replace(plan(), seed=1)).interval
    assert reseeded is not None and (reseeded.low, reseeded.high) != (interval.low, interval.high)


def test_a_system_compared_with_itself_differs_by_nothing_and_resolves_no_interval(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    twin = [relabelled(run, system=OTHER) for run in truthful_runs]
    theirs, ours = arms(world, [*truthful_runs, *twin], plan(registered=TWO_SYSTEMS))
    strict = strictly_grounded_share(Graded)
    for first, second in zip(cells_of(ours), cells_of(theirs), strict=True):
        same = compare_ratio(first, second, strict, plan())
        assert same.paired == len(first.scenarios)
        assert same.difference == 0.0
        expected = Unresolved.EVERY_RESAMPLE_EQUAL if first.stratum.estimated else None
        assert (same.interval, same.unresolved) == (None, expected)


# --- The two readings of a check ------------------------------------------------------------


def test_a_run_the_check_does_not_apply_to_is_left_out_conditionally_and_not_passed_end_to_end(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    structured = [s for s in world.scenarios if s.key.tier is Tier.STRUCTURED]
    limited_one, failed_one, never_run = structured[0], structured[1], structured[2]
    runs = [
        run
        for run in truthful_runs
        if run.outcome.header.scenario_id
        not in {s.spec.id for s in (limited_one, failed_one, never_run)}
    ]
    runs.append(
        evaluated(
            world,
            limited_one,
            down=(Source.FRAPPE,),
            assigned=(),
            claims=truthful(world, limited_one, NORMAL),
        )
    )
    runs.append(
        relabelled(evaluate_run(world, provider_failed_export(world, failed_one)), system=REFERENCE)
    )
    everyone_passes = passes_in({s.spec.id for s in world.scenarios})

    (arm,) = arms(world, runs, plan())
    cell = tier_of(arm, Tier.STRUCTURED)
    conditional = estimate_check(cell, everyone_passes, CONDITIONAL, plan())
    assert (conditional.passed, conditional.scenarios, conditional.value) == (7, 7, 1.0)
    assert (conditional.runs, conditional.not_checked, conditional.missing) == (9, 2, 1)

    # End to end the limited and the failed run did not pass, and are counted apart from a
    # run that was checked and failed; the run never made counts as the plan says.
    end_to_end = estimate_check(cell, everyone_passes, END_TO_END, plan())
    assert (end_to_end.passed, end_to_end.scenarios, end_to_end.value) == (7, 10, 0.7)
    assert (end_to_end.not_checked, end_to_end.missing) == (2, 1)
    assert end_to_end.wilson is not None

    left_out = plan(missing_repeat=MissingRepeat.LEFT_OUT)
    (arm,) = arms(world, runs, left_out)
    without_it = estimate_check(
        tier_of(arm, Tier.STRUCTURED), everyone_passes, END_TO_END, left_out
    )
    assert (without_it.passed, without_it.scenarios, without_it.missing) == (7, 9, 1)


def test_repeats_are_bundled_in_their_scenario_and_estimated_by_the_bootstrap(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    structured = [s.spec.id for s in world.scenarios if s.key.tier is Tier.STRUCTURED]
    # Two runs of every scenario; the second run of the first four structured ones fails.
    second = [relabelled(run, run_id="run-second") for run in truthful_runs]
    flaky = set(structured[:4])
    first_scenario = world.scenarios[0]
    limited = relabelled(
        evaluated(
            world,
            first_scenario,
            down=(Source.FRAPPE,),
            assigned=(),
            claims=truthful(world, first_scenario, NORMAL),
        ),
        run_id="run-second",
    )

    def of(evaluation: Evaluation) -> bool | None:
        header = evaluation.outcome.header
        return not (header.run_id == "run-second" and header.scenario_id in flaky)

    two_runs = plan(intended_repeats=2)
    (arm,) = arms(world, [*truthful_runs, *second], two_runs)
    estimate = estimate_check(
        tier_of(arm, Tier.STRUCTURED), Check("flaky", of), CONDITIONAL, two_runs
    )
    # Ten scenarios, not twenty runs: four pass half the time, six always.
    assert (estimate.scenarios, estimate.runs, estimate.passed) == (10, 20, 8.0)
    assert estimate.value == 0.8
    assert estimate.wilson is None and estimate.bootstrap is not None
    assert estimate.bootstrap.low < 0.8 < estimate.bootstrap.high
    # A scenario run twice with one run the check does not apply to is still a repeated
    # scenario: one applicable trial is not one run, and it stays a cluster (the batch
    # review of group E).
    limited_second = [
        replace(run, outcome=limited.outcome) if position == 0 else run
        for position, run in enumerate(second)
    ]
    assert limited_second[0].outcome.header.scenario_id == limited.outcome.header.scenario_id
    graded_only = Check("graded", lambda e: True if isinstance(e.outcome, Graded) else None)
    (mixed,) = arms(world, [*truthful_runs, *limited_second], two_runs)
    half_checked = estimate_check(cell_of(mixed), graded_only, CONDITIONAL, two_runs)
    assert (half_checked.scenarios, half_checked.runs, half_checked.not_checked) == (30, 60, 1)
    # Every scenario passes, so the bootstrap it is read by resolves no interval.
    assert (half_checked.wilson, half_checked.unresolved) == (None, Unresolved.EVERY_RESAMPLE_EQUAL)
    # A ratio pools a scenario's repeats before any ratio is taken.
    pooled = estimate_ratio(cell_of(arm), recall(), two_runs)
    assert (pooled.numerator, pooled.denominator, pooled.scenarios) == (322, 322, 30)


# --- Paired comparisons ---------------------------------------------------------------------


def test_a_comparison_is_paired_on_the_scenarios_both_systems_have_in_scope(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    fragmented = [s for s in world.scenarios if s.key.tier is Tier.FRAGMENTED]
    weaker_on = {s.spec.id for s in fragmented[:3]}
    limited_on = fragmented[9]
    other: list[Evaluation] = []
    for scenario, run in zip(world.scenarios, truthful_runs, strict=True):
        if scenario.spec.id in weaker_on:
            run = lacking_a_required_assessment(world, scenario)
        elif scenario is limited_on:
            run = evaluated(
                world,
                scenario,
                down=(Source.FRAPPE,),
                assigned=(),
                claims=truthful(world, scenario, NORMAL),
            )
        other.append(relabelled(run, system=OTHER))
    theirs, ours = arms(world, [*truthful_runs, *other], plan(registered=TWO_SYSTEMS))

    whole = compare_ratio(cell_of(ours), cell_of(theirs), recall(), plan())
    # The scenario the other system could not be graded on is in neither side's sums.
    assert whole.paired == 29
    assert whole.first == 1.0 and whole.second is not None and whole.second < 1.0
    assert whole.difference is not None and whole.difference > 0
    assert whole.interval is not None and 0 <= whole.interval.low <= whole.interval.high
    # Three scenarios of thirty differ: precision is untouched, a claim left out is no wrong claim.
    precise = compare_ratio(cell_of(ours), cell_of(theirs), strict_precision(), plan())
    assert precise.difference == 0.0

    by_tier = compare_ratio(
        tier_of(ours, Tier.FRAGMENTED), tier_of(theirs, Tier.FRAGMENTED), recall(), plan()
    )
    # Three of the tier's nine paired scenarios differ, and a resample of nine holds none
    # of the three in (6/9)^9 of draws, 2.6 percent: the lower end sits at nought or just
    # above it by the seed, so what holds for every seed is that it is not below.
    assert by_tier.paired == 9 and by_tier.interval is not None
    assert by_tier.interval.low >= 0 and by_tier.interval.high > 0

    # One run per scenario on each side: the two-by-two table (both, ours only, theirs only,
    # neither) beside the interval, which is the same method as with repeats.
    full_recall = Check(
        "every required claim held",
        lambda e: (counts := recall().of(e)) and counts[0] == counts[1],
    )
    table = compare_check(
        tier_of(ours, Tier.FRAGMENTED),
        tier_of(theirs, Tier.FRAGMENTED),
        full_recall,
        CONDITIONAL,
        plan(),
    )
    assert (table.paired, table.two_by_two, table.unresolved) == (9, (6, 3, 0, 0), None)
    assert (table.first, table.second) == (1.0, 6 / 9)
    assert table.interval is not None
    assert 0 <= table.interval.low < 3 / 9 < table.interval.high
    assert table.interval.valid == table.interval.resamples
    # End to end the limited run stays, as a scenario that did not pass.
    kept = compare_check(
        tier_of(ours, Tier.FRAGMENTED),
        tier_of(theirs, Tier.FRAGMENTED),
        full_recall,
        END_TO_END,
        plan(),
    )
    assert (kept.paired, kept.two_by_two) == (10, (6, 4, 0, 0))
    assert kept.interval is not None and kept.interval.low < 4 / 10 < kept.interval.high


def test_a_comparison_refuses_cells_that_are_not_paired(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    twin = [relabelled(run, system=OTHER) for run in truthful_runs]
    outage = [
        relabelled(evaluated(world, scenario, down=(Source.JIRA,)), system=OTHER)
        for scenario in world.scenarios[:3]
    ]
    padded = [relabelled(run, system=OTHER, level=PADDED) for run in truthful_runs]
    registered = (*TWO_SYSTEMS, (OTHER, NORMAL, PADDED), (OTHER, NORMAL.without(Source.JIRA), BASE))
    theirs, their_padded, their_outage, ours = arms(
        world, [*truthful_runs, *twin, *padded, *outage], plan(registered=registered)
    )
    with pytest.raises(ValueError, match="within one stratum"):
        compare_ratio(cell_of(ours), tier_of(theirs, Tier.STRUCTURED), recall(), plan())
    with pytest.raises(ValueError, match="assigned condition"):
        compare_ratio(cell_of(ours), cell_of(their_outage), recall(), plan())
    with pytest.raises(ValueError, match="both cells are one arm's"):
        compare_ratio(cell_of(ours), cell_of(ours), recall(), plan())
    # Another system at another level is two differences at once, and neither is isolated.
    with pytest.raises(ValueError, match="the two arms differ in both"):
        compare_ratio(cell_of(ours), cell_of(their_padded), recall(), plan())


def test_one_system_is_paired_with_itself_across_two_levels_and_incidents_are_counted(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    # The padded level loses the action on the first four scenarios; the answers are the
    # same at both levels, so the contrast is one question asked twice.
    missed = {scenario.spec.id for scenario in world.scenarios[:4]}
    padded = [
        relabelled(
            evaluated(world, scenario, claims=truthful(world, scenario, NORMAL)[:1])
            if scenario.spec.id in missed
            else run,
            level=PADDED,
        )
        for scenario, run in zip(world.scenarios, truthful_runs, strict=True)
    ]
    levels = ((REFERENCE, NORMAL, BASE), (REFERENCE, NORMAL, PADDED))
    at_base, at_padded = arms(world, [*truthful_runs, *padded], plan(registered=levels))
    assert (at_base.level, at_padded.level) == (BASE, PADDED)
    assert at_base.name == "rules_only/reference normal at base"
    touched = [world.scenarios[0].spec.id, world.scenarios[10].spec.id]
    whole = Check("full recall", lambda e: (c := recall().of(e)) and c[0] == c[1])
    contrast = compare_check(
        cell_of(at_padded), cell_of(at_base), whole, END_TO_END, plan(), incidents=touched
    )
    assert (contrast.first_arm, contrast.second_arm) == (at_padded.name, at_base.name)
    assert (contrast.paired, contrast.two_by_two) == (30, (26, 0, 4, 0))
    assert contrast.paired_with_incident == 2
    assert contrast.interval is not None and contrast.interval.high < 0
    # With no incident named, none is counted; a ratio counts the scenarios it paired.
    assert compare_check(
        cell_of(at_padded), cell_of(at_base), whole, END_TO_END, plan()
    ).paired_with_incident == 0
    ratio = compare_ratio(cell_of(at_padded), cell_of(at_base), recall(), plan(), incidents=touched)
    assert (ratio.paired, ratio.paired_with_incident) == (30, 2)


def test_repeated_runs_are_compared_by_the_difference_of_pass_fractions(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    structured = [s.spec.id for s in world.scenarios if s.key.tier is Tier.STRUCTURED]
    two_runs = plan(intended_repeats=2, registered=TWO_SYSTEMS)
    ours = [*truthful_runs, *(relabelled(run, run_id="run-second") for run in truthful_runs)]
    theirs = [relabelled(run, system=OTHER) for run in ours]
    flaky = set(structured[:4])

    def of(evaluation: Evaluation) -> bool | None:
        header = evaluation.outcome.header
        failing = header.system == OTHER and header.run_id == "run-second"
        return not (failing and header.scenario_id in flaky)

    their_arm, our_arm = arms(world, [*ours, *theirs], two_runs)
    found = compare_check(
        tier_of(our_arm, Tier.STRUCTURED),
        tier_of(their_arm, Tier.STRUCTURED),
        Check("flaky", of),
        CONDITIONAL,
        two_runs,
    )
    assert (found.paired, found.first, found.second) == (10, 1.0, 0.8)
    # Repeats have no slot to pair: no two-by-two, the bootstrap of the difference instead.
    assert found.two_by_two is None and found.interval is not None
    assert found.unresolved is None
    assert 0 < found.interval.low < 0.2 < found.interval.high


# --- Cost -----------------------------------------------------------------------------------


def test_a_cells_cost_is_over_every_attempt_and_a_floor_where_a_cost_is_unknown(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    (reference,) = arms(world, truthful_runs, plan())
    free = cost_ledger(cell_of(reference))
    # No model was called: a complete cost of zero, never an unknown one.
    assert (free.runs, free.attempts, free.pico_usd, free.floors) == (30, 30, 0, 0)
    assert free.per_run == Spread(0.0, 0, 0)
    assert free.duration_ms == Spread(1_200.0, 1_200, 1_200)

    def priced(scenario: Scenario, input_tokens: int, run_id: str, attempt: int) -> Evaluation:
        usage: dict[str, object] = {"inputTokens": input_tokens, "outputTokens": 100}
        cost = cost_of_reported(ReportedUsage(usage), SELECTION, BASIS)
        call = answered_call(1, usage, cost)
        export = agent_export(world, scenario, (call,), claims=truthful(world, scenario, NORMAL))
        return evaluate_run(world, replace(export, run_id=run_id, attempt=attempt))

    one, two = world.scenarios[:2]
    failed_first = evaluate_run(world, provider_failed_export(world, one))  # run-8, attempt 1
    retried = priced(one, 1_000, "run-8", 2)
    clean = priced(two, 3_000, "run-9", 1)
    agents = plan(registered=((failed_first.outcome.header.system, NORMAL, BASE),))
    (agent,) = arms(world, [failed_first, retried, clean], agents)
    ledger = cost_ledger(cell_of(agent))
    cost_of_retry = 1_000 * 1_100_000 + 100 * 5_500_000
    cost_of_clean = 3_000 * 1_100_000 + 100 * 5_500_000
    assert (ledger.runs, ledger.attempts) == (2, 3)
    assert ledger.pico_usd == cost_of_retry + cost_of_clean
    # The failed attempt reported no usage: that run's cost is a floor. The retry was paid for.
    assert ledger.floors == 1
    assert ledger.per_run == Spread(
        (cost_of_retry + cost_of_clean) / 2, cost_of_retry, cost_of_clean
    )
    assert ledger.duration_ms == Spread(1_800.0, 1_200, 2_400)

    # An attempt no scenario of the world can place is paid for in the whole, and in no tier.
    stray = priced(two, 2_000, "run-10", 1)
    stray = replace(
        stray,
        outcome=replace(
            stray.outcome, header=replace(stray.outcome.header, scenario_id=ScenarioId("scn_999"))
        ),
    )
    (agent,) = arms(world, [failed_first, retried, clean, stray], agents)
    whole = cost_ledger(cell_of(agent))
    assert (whole.runs, whole.attempts) == (3, 4)
    assert whole.pico_usd == ledger.pico_usd + 2_000 * 1_100_000 + 100 * 5_500_000
    tiers = [cell for cell in cells_of(agent) if cell.stratum.kind is StratumKind.TIER]
    assert sum(cost_ledger(cell).pico_usd for cell in tiers) == ledger.pico_usd

    # A run whose every request was refused before sending sent nothing: a complete cost of
    # zero, where a send that timed out is a floor.
    refused = ModelCall(
        ModelCallId("call-1"),
        ROLE,
        (dispatch(1, RefusedBeforeSend("ParamValidationError"), AttributionKind.DEFECT),),
        None,
    )
    # Read as a defect, so the attempt ended there by defect: the export holds no other.
    at_its_send = Failure(
        FailureCategory.DEFECT,
        DispatchSite(ModelCallId("call-1"), 1, DispatchPhase.SEND),
        "the request broke the harness's own contract",
    )
    never_sent = evaluate_run(world, agent_export(world, one, (refused,), failure=at_its_send))
    (agent,) = arms(world, [never_sent], agents)
    unsent = cost_ledger(cell_of(agent))
    assert (unsent.runs, unsent.pico_usd, unsent.floors) == (1, 0, 0)
    (agent,) = arms(world, [failed_first], agents)
    assert cost_ledger(cell_of(agent)).floors == 1
