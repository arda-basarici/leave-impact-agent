"""The registration as the evaluator reads it. The three registered checks answer mechanically:
a truthful report over a full read passes all three, a missing or a wrong-kind action fails
the action check and correct whole and leaves the replay alone, correct whole fails on each
thing it names (a wrong verdict or reasons, a plan finding against the oracle, a wrong
conflict resolution or unknown reason, an unexpected claim, an invalid claim set), a claim
the reads do not support fails the replay alone, an empty report is outside the replay
check, and a run that was not graded is outside the other two. The registries resolve the
registered names and refuse any other. The projection gives the plan the tables are cut
under, a registered cell an arm of it unless its system has a value pending or its
conditional group is not decided as run, and names each cell it left out with why; a
prefetch or an anchor table that is not this code's, an interval method or a resolved
mechanism measure this evaluator does not hold, refuse whole. And a repeat the plan
intended and nobody made keeps its scenario a repeated one."""

from dataclasses import replace

import pytest

from leaveimpact.core import (
    AssessmentReason,
    CandidateAssessment,
    ClaimType,
    CoverageAction,
    CoverageActionKind,
    FailureCategory,
    Impact,
    Pending,
    RunCondition,
    Source,
    SourceConflict,
    System,
    SystemKind,
    Unknown,
    UnknownReason,
    Verdict,
)
from leaveimpact.evaluator.cells import CountedAttempt, MissingRepeat, arms, cells_of
from leaveimpact.evaluator.grading import Graded, correct_whole
from leaveimpact.evaluator.intervals import Unresolved
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.registered import (
    CHECKS,
    INTERVAL_METHODS,
    MEASURES,
    MECHANISM_MEASURES,
    WhyUnbuilt,
    mechanism_pending,
    preregistered,
    registered_check,
    registered_measures,
)
from leaveimpact.evaluator.rows import Expectation
from leaveimpact.evaluator.run_checks import CORRECT_WHOLE, EXPECTED_ACTION, REPRODUCED_WHOLE
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.tables import Reading, compare_check, estimate_check
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from leaveimpact.world import Scenario
from tests.unit.evaluation_fixture import NORMAL, REFERENCE, evaluated, relabelled, truthful
from tests.unit.export_fixture import provider_failed_export
from tests.unit.registration_fixture import DRAFT, MECHANISM, decided, frozen, named
from tests.unit.report_fixture import of_type, renumbered, swapped, without
from tests.unit.throwaway_world import loaded_world

LONE = Unresolved.FEWER_THAN_TWO_ELIGIBLE_SCENARIOS
GROUP = "full_context_under_outage"


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


def graded(evaluation: Evaluation) -> Graded:
    assert isinstance(evaluation.outcome, Graded), type(evaluation.outcome).__name__
    return evaluation.outcome


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


def test_a_wrong_verdict_or_wrong_reasons_on_an_assessment_fails_correct_whole(
    world: SealedWorld, assigning: Scenario
) -> None:
    report = truthful(world, assigning, NORMAL)
    ruled_out = next(
        claim
        for claim in of_type(report, CandidateAssessment)
        if claim.verdict is Verdict.NON_VIABLE
    )
    other = next(reason for reason in AssessmentReason if reason not in ruled_out.reasons)
    for changed, flags in (
        (replace(ruled_out, reasons=(other,)), (True, False)),
        (replace(ruled_out, verdict=Verdict.VIABLE, reasons=()), (False, False)),
    ):
        outcome = graded(evaluated(world, assigning, claims=swapped(report, ruled_out, changed)))
        row = next(r for r in outcome.rows.assessments if r.claim_id == ruled_out.claim_id)
        assert (row.verdict_matches, row.reasons_match) == flags
        # The one row is all that is wrong: nobody assigned changed, the plan checks are quiet.
        assert outcome.oracle_findings == () and not correct_whole(outcome)


def test_an_assignee_the_oracle_rules_out_fails_correct_whole_by_the_plan_finding_alone(
    world: SealedWorld, assigning: Scenario
) -> None:
    report = truthful(world, assigning, NORMAL)
    action = next(
        claim
        for claim in of_type(report, CoverageAction)
        if claim.action is CoverageActionKind.ASSIGN
    )
    ruled_out = next(
        claim
        for claim in of_type(report, CandidateAssessment)
        if claim.impact_key == action.impact_key and claim.verdict is Verdict.NON_VIABLE
    )
    named = replace(action, assignee_ids=(ruled_out.employee_id,))
    outcome = graded(evaluated(world, assigning, claims=swapped(report, action, named)))
    # An action's row is judged by its kind, so every row is still right; the plan check
    # against the oracle is what objects, and without its finding the rows would pass.
    assert outcome.oracle_findings
    assert correct_whole(replace(outcome, oracle_findings=()))
    assert not correct_whole(outcome)


def test_a_wrong_conflict_resolution_or_a_wrong_unknown_reason_fails_correct_whole(
    world: SealedWorld,
) -> None:
    disputed, report, conflict = next(
        (scenario, report, conflicts[0])
        for scenario in world.scenarios
        if (conflicts := of_type(report := truthful(world, scenario, NORMAL), SourceConflict))
    )
    loser = next(o.value for o in conflict.observations if o.value != conflict.resolved_value)
    resolved_wrong = swapped(report, conflict, replace(conflict, resolved_value=loser))
    outcome = graded(evaluated(world, disputed, claims=resolved_wrong))
    row = next(r for r in outcome.rows.conflicts if r.claim_id == conflict.claim_id)
    assert (row.value_matches, row.rule_matches, row.observations_hold) == (False, True, True)
    assert outcome.oracle_findings == () and not correct_whole(outcome)

    open_question, report, unknown = next(
        (scenario, report, unknowns[0])
        for scenario in world.scenarios
        if (unknowns := of_type(report := truthful(world, scenario, NORMAL), Unknown))
    )
    reason = next(reason for reason in UnknownReason if reason is not unknown.reason)
    misreasoned = swapped(report, unknown, replace(unknown, reason=reason))
    outcome = graded(evaluated(world, open_question, claims=misreasoned))
    row = next(r for r in outcome.rows.unknowns if r.claim_id == unknown.claim_id)
    assert row.reason_matches is False
    assert outcome.oracle_findings == () and not correct_whole(outcome)


def test_an_unexpected_claim_or_an_invalid_claim_set_fails_correct_whole(
    world: SealedWorld, assigning: Scenario
) -> None:
    report = truthful(world, assigning, NORMAL)
    mine = of_type(report, Impact)
    held = {impact.artifact for impact in mine}
    elsewhere = next(
        impact
        for scenario in world.scenarios
        for impact in of_type(truthful(world, scenario, NORMAL), Impact)
        if impact.artifact not in held
    )
    # Another leave's impact stated of this one: everything the oracle expects is still
    # there and right, with one claim it does not expect.
    stray = renumbered(
        replace(mine[0], subtype=elsewhere.subtype, artifact=elsewhere.artifact), 9_999
    )
    outcome = graded(evaluated(world, assigning, claims=(*report, stray)))
    row = next(r for r in outcome.rows.impacts if r.claim_id == stray.claim_id)
    assert row.expectation is Expectation.UNEXPECTED
    assert outcome.oracle_findings == () and not correct_whole(outcome)

    # The same impact stated twice is no claim set at all: no row is matched.
    twice = graded(evaluated(world, assigning, claims=(*report, renumbered(mine[0], 9_999))))
    assert not twice.rows.structurally_valid
    assert all(r.expectation is Expectation.NOT_MATCHED for r in twice.rows.impacts if r.claim_id)
    assert not correct_whole(twice)


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
    # A measure is a family of rows, the leading one first.
    recall_rows = [measure.name for measure in registered_measures("recall")]
    assert recall_rows[0] == "recall: all claims" and len(recall_rows) == 1 + len(ClaimType)
    assert "recall: coverage_action" in recall_rows
    # Payload accuracy has a row only for a claim type that has a payload.
    assert len(registered_measures("payload_accuracy")) == 5
    assert [measure.name for measure in registered_measures("claims_grounded_end_to_end")] == [
        "claims grounded end to end: graded runs",
        "claims grounded end to end: limited runs",
    ]
    assert [measure.name for measure in registered_measures("searches_with_a_hit")] == [
        "searches with a hit"
    ]
    # Twenty-five registered families, and no row belongs to two.
    rows = [measure.name for name in MEASURES for measure in registered_measures(name)]
    assert (len(MEASURES), len(rows), len(set(rows))) == (25, 58, 58)
    with pytest.raises(ValueError, match="no check is registered as 'plausible'"):
        registered_check("plausible")
    with pytest.raises(ValueError, match="no measure is registered as 'f1'"):
        registered_measures("f1")


# --- The projection ----------------------------------------------------------------------------


def test_the_draft_projects_the_rules_only_cells_and_names_the_eighteen_it_left_out() -> None:
    projection = preregistered(DRAFT)
    plan = projection.plan
    assert (plan.confidence, plan.seed, plan.resamples) == (0.95, 20261003, 10_000)
    assert (plan.intended_repeats, plan.max_attempts) == (1, 3)
    assert plan.counted_attempt is CountedAttempt.EARLIEST_NOT_INFRASTRUCTURE
    assert plan.missing_repeat is MissingRepeat.NOT_PASSED
    reference = System(SystemKind.RULES_ONLY, "reference")
    normal = RunCondition.all_reachable()
    # The baseline at both levels under the normal condition, and under each outage at the
    # base level: a pending padded size blocks no system.
    assert plan.arms == (
        (reference, normal, "base"),
        (reference, normal, "padded"),
        (reference, normal.without(Source.JIRA), "base"),
        (reference, normal.without(Source.CALENDAR), "base"),
        (reference, normal.without(Source.FRAPPE), "base"),
        (reference, normal.without(Source.CORPUS), "base"),
    )
    assert len(plan.arms) + len(projection.unbuilt) == len(DRAFT.cells) == 24
    by_why = {
        why: [left.cell for left in projection.unbuilt if left.why is why] for why in WhyUnbuilt
    }
    # Full context under an outage waits on its group's one decision, whatever else it
    # waits on; every other model cell on what its system's execution needs.
    assert {(cell.system, cell.group) for cell in by_why[WhyUnbuilt.GROUP_NOT_RUN]} == {
        (SystemKind.FULL_CONTEXT, GROUP)
    }
    assert len(by_why[WhyUnbuilt.GROUP_NOT_RUN]) == 4
    pending = by_why[WhyUnbuilt.SYSTEM_PENDING]
    assert [sum(cell.system is kind for cell in pending) for kind in SystemKind] == [6, 0, 6, 2]
    details = {left.cell.system: left.detail for left in projection.unbuilt}
    assert details[SystemKind.AGENT] == (
        "systems.agent.variant, systems.agent.roles, run_accounting.redispatch, attribution, "
        "stated_facts.entry_schema"
    )
    assert {left.detail for left in projection.unbuilt if left.why is WhyUnbuilt.GROUP_NOT_RUN} == {
        GROUP
    }
    assert mechanism_pending(DRAFT) == "resolved when the evaluator's fact-stage measures are built"


def test_a_cell_is_built_once_its_system_is_resolved_and_its_group_decided_as_run() -> None:
    resolved = preregistered(named())
    built = [(system.kind, level) for system, _, level in resolved.plan.arms]
    # The agent's six, the baseline's six, full context under the normal condition at both.
    assert [sum(kind is each for kind, _ in built) for each in SystemKind] == [6, 6, 0, 2]
    assert (SystemKind.FULL_CONTEXT, "padded") in built
    # Single-shot's query protocol can only be pending in this format: never built here.
    assert {left.cell.system for left in resolved.unbuilt} == {
        SystemKind.SINGLE_SHOT,
        SystemKind.FULL_CONTEXT,
    }
    run = preregistered(decided(named(), True))
    assert len(run.plan.arms) == 18
    assert {left.why for left in run.unbuilt} == {WhyUnbuilt.SYSTEM_PENDING}
    # Decided against, the four cells are left out for the group, with nothing pending.
    not_run = preregistered(decided(named(), False))
    assert len(not_run.plan.arms) == 14
    assert sum(left.why is WhyUnbuilt.GROUP_NOT_RUN for left in not_run.unbuilt) == 4


def test_the_projection_refuses_what_this_evaluator_does_not_implement() -> None:
    statistics = DRAFT.statistics
    more_checks = replace(statistics, checks=(*statistics.checks, "plausible"))
    unknown = replace(DRAFT, statistics=more_checks)
    with pytest.raises(ValueError, match="no check is registered as 'plausible'"):
        preregistered(unknown)
    unknown = replace(DRAFT, statistics=replace(statistics, measures=(*statistics.measures, "f1")))
    with pytest.raises(ValueError, match="no measure is registered as 'f1'"):
        preregistered(unknown)

    assert statistics.interval_method in INTERVAL_METHODS and len(INTERVAL_METHODS) == 1
    other = replace(DRAFT, statistics=replace(statistics, interval_method="wilson_per_tier"))
    with pytest.raises(ValueError, match="no interval method is registered as 'wilson_per_tier'"):
        preregistered(other)

    # The mechanism measure is not built yet: pending it is shown as pending, and a
    # resolved name is one more name this evaluator does not hold.
    assert MECHANISM_MEASURES == ()
    resolved = replace(DRAFT, statistics=replace(statistics, mechanism=MECHANISM))
    with pytest.raises(ValueError, match="no mechanism measure is registered as 'needed_prose_f"):
        preregistered(resolved)
    with pytest.raises(ValueError, match="no mechanism measure is registered as"):
        preregistered(frozen())

    accounting = DRAFT.run_accounting
    retry = replace(accounting.retry, after=FailureCategory.DEFECT)
    after_defect = replace(accounting, retry=retry)
    with pytest.raises(ValueError, match="the registration retries after defect"):
        preregistered(replace(DRAFT, run_accounting=after_defect))

    # The anchor table is the one part of the stated-fact contract this package computes.
    stated = replace(DRAFT.stated_facts, anchor_table="0" * 64)
    with pytest.raises(ValueError, match="the registered anchor table is 0{64}, this evaluator"):
        preregistered(replace(DRAFT, stated_facts=stated))
    # The composing policy is the harness's: an evaluator cannot compute it and does not
    # refuse on it here. It holds each export's recorded policy to the registered one.
    policy = replace(DRAFT.stated_facts.composing_policy, digest="0" * 64)
    composed = replace(DRAFT, stated_facts=replace(DRAFT.stated_facts, composing_policy=policy))
    assert len(preregistered(composed).plan.arms) == 6

    systems = tuple(replace(system, variant=Pending("not named")) for system in DRAFT.systems)
    with pytest.raises(ValueError, match="no registered cell can be built"):
        preregistered(replace(DRAFT, systems=systems))


# --- The form follows the plan -----------------------------------------------------------------


def test_a_repeat_intended_and_never_made_keeps_its_scenario_a_repeated_one(
    world: SealedWorld,
) -> None:
    other = System(SystemKind.RULES_ONLY, "other")
    two_runs = replace(
        preregistered(DRAFT).plan,
        intended_repeats=2,
        arms=((other, NORMAL, "base"), (REFERENCE, NORMAL, "base")),
    )
    scenario = world.scenarios[0]
    once = evaluated(world, scenario)
    theirs, mine = arms(world, [once, relabelled(once, system=other)], two_runs)
    first = replace(cells_of(mine)[0], scenarios=(mine.scenarios[0],))
    second = replace(cells_of(theirs)[0], scenarios=(theirs.scenarios[0],))
    for reading in Reading:
        estimate = estimate_check(first, CORRECT_WHOLE, reading, two_runs)
        assert (estimate.runs, estimate.missing, estimate.unverifiable) == (1, 1, 0)
        # The bootstrap's form, which one scenario alone cannot resolve.
        assert (estimate.wilson, estimate.unresolved) == (None, LONE), reading
        comparison = compare_check(first, second, CORRECT_WHOLE, reading, two_runs)
        assert (comparison.two_by_two, comparison.unresolved) == (None, LONE), reading

    # With one run intended and one made, the scenario is a single trial as before.
    one_run = replace(two_runs, intended_repeats=1)
    theirs, mine = arms(world, [once, relabelled(once, system=other)], one_run)
    first = replace(cells_of(mine)[0], scenarios=(mine.scenarios[0],))
    second = replace(cells_of(theirs)[0], scenarios=(theirs.scenarios[0],))
    estimate = estimate_check(first, CORRECT_WHOLE, Reading.CONDITIONAL, one_run)
    assert estimate.wilson is not None and estimate.bootstrap is None
    comparison = compare_check(first, second, CORRECT_WHOLE, Reading.CONDITIONAL, one_run)
    assert comparison.two_by_two == (1, 0, 0, 0)
    # One method at any repeat count: the single trial has its counts and the same state.
    assert (comparison.interval, comparison.unresolved) == (None, LONE)
