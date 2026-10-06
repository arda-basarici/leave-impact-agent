"""A run's attempt history: the earliest attempt that did not fail by infrastructure is the
run, else the last, chosen among the attempts numbered within the registered maximum, so an
excess attempt never counts; a gap among those leaves no counted attempt under any rule,
the run made, unverifiable, not passed end to end and absent from the conditional reading,
its attempts still paid for; an attempt above the maximum and an attempt after a stopping
outcome are findings on a run still counted; and the attempt summary shows the
infrastructure failure a recovered retry hides from the accounting."""

from dataclasses import replace

import pytest

from leaveimpact.core import System
from leaveimpact.core.eligibility import EligibilityRule
from leaveimpact.evaluator.attempts import (
    CountedAttempt,
    HistoryFinding,
    failed_by_infrastructure,
    run_history,
)
from leaveimpact.evaluator.cells import (
    MissingRepeat,
    Preregistered,
    accounting_of,
    arms,
    attempt_summary_of,
    cells_of,
)
from leaveimpact.evaluator.eligibility_check import (
    EligibilityCheck,
    EndingKind,
    ProjectedEnding,
)
from leaveimpact.evaluator.grading import Excluded, ExcludedReason, Graded
from leaveimpact.evaluator.intervals import Unresolved
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.tables import (
    Check,
    Reading,
    compare_check,
    cost_ledger,
    estimate_check,
)
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from tests.unit.evaluation_fixture import NORMAL, evaluated, relabelled
from tests.unit.export_fixture import provider_failed_export
from tests.unit.throwaway_world import loaded_world

EARLIEST = CountedAttempt.EARLIEST_NOT_INFRASTRUCTURE
GAP = HistoryFinding.GAP
EXCESS = HistoryFinding.EXCESS_ATTEMPT
AFTER_STOP = HistoryFinding.ATTEMPT_AFTER_STOPPING_OUTCOME
NOT_PERMITTED = HistoryFinding.ATTEMPT_NOT_PERMITTED
RUN = "run-8"
LONE = Unresolved.FEWER_THAN_TWO_ELIGIBLE_SCENARIOS
PASSES = Check("graded", lambda e: True if isinstance(e.outcome, Graded) else None)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def failed(world: SealedWorld) -> Evaluation:
    """An attempt the provider failed, of the agent's run-8."""
    evaluation = evaluate_run(world, provider_failed_export(world, world.scenarios[0]))
    assert failed_by_infrastructure(evaluation)
    return evaluation


@pytest.fixture(scope="module")
def good(world: SealedWorld, failed: Evaluation) -> Evaluation:
    """A graded attempt of the same run."""
    evaluation = relabelled(
        evaluated(world, world.scenarios[0]), run_id=RUN, system=failed.outcome.header.system
    )
    assert isinstance(evaluation.outcome, Graded)
    return evaluation


def numbered(evaluation: Evaluation, attempt: int) -> Evaluation:
    return relabelled(evaluation, attempt=attempt)


def defect(evaluation: Evaluation) -> Evaluation:
    """``evaluation`` as an attempt a defect ended."""
    excluded = Excluded(evaluation.outcome.header, ExcludedReason.FAILED_BY_DEFECT)
    return replace(evaluation, outcome=excluded)


def plan(
    failed: Evaluation,
    counted_attempt: CountedAttempt = EARLIEST,
    missing_repeat: MissingRepeat = MissingRepeat.NOT_PASSED,
) -> Preregistered:
    registered = ((failed.outcome.header.system, NORMAL, "base"),)
    return Preregistered(0.95, 7, 1_000, 1, counted_attempt, missing_repeat, registered, 3)


# --- Which attempt is the run ------------------------------------------------------------------


def test_the_earliest_attempt_not_failed_by_infrastructure_is_the_run_else_the_last(
    failed: Evaluation, good: Evaluation
) -> None:
    recovered = run_history(RUN, [numbered(good, 2), failed], EARLIEST, 3)
    assert recovered.counted == numbered(good, 2)
    assert recovered.attempts == (failed, numbered(good, 2))
    assert (recovered.findings, recovered.retried, recovered.recovered) == ((), True, True)

    alone = run_history(RUN, [good], EARLIEST, 3)
    assert (alone.counted, alone.findings) == (good, ())
    assert (alone.retried, alone.recovered) == (False, False)

    never = [failed, numbered(failed, 2), numbered(failed, 3)]
    exhausted = run_history(RUN, never, EARLIEST, 3)
    assert exhausted.counted == numbered(failed, 3)
    assert (exhausted.findings, exhausted.retried, exhausted.recovered) == ((), True, False)


def test_a_defect_is_a_stopping_outcome_that_a_later_attempt_cannot_replace(
    good: Evaluation,
) -> None:
    broke = defect(good)
    history = run_history(RUN, [broke, numbered(good, 2)], EARLIEST, 3)
    assert history.counted == broke
    assert history.findings == (AFTER_STOP,)
    assert not history.recovered


def test_a_failure_after_the_counted_attempt_is_nothing_the_run_recovered_from(
    failed: Evaluation, good: Evaluation
) -> None:
    history = run_history(RUN, [good, numbered(failed, 2)], EARLIEST, 3)
    assert history.counted == good
    assert history.findings == (AFTER_STOP,)
    assert history.retried and not history.recovered


def test_the_first_and_the_last_rules_still_choose_by_position(
    failed: Evaluation, good: Evaluation
) -> None:
    attempts = [failed, numbered(good, 2)]
    assert run_history(RUN, attempts, CountedAttempt.FIRST, 3).counted == failed
    assert run_history(RUN, attempts, CountedAttempt.LAST, 3).counted == numbered(good, 2)
    # Under the first-attempt rule the retry recovered nothing that is counted.
    assert not run_history(RUN, attempts, CountedAttempt.FIRST, 3).recovered


# --- What a history shows ----------------------------------------------------------------------


def test_each_history_finding_fires_alone_and_a_conforming_history_has_none(
    failed: Evaluation, good: Evaluation
) -> None:
    conforming = [failed, numbered(failed, 2), numbered(good, 3)]
    assert run_history(RUN, conforming, EARLIEST, 3).findings == ()
    assert run_history(RUN, [numbered(good, 2)], EARLIEST, 3).findings == (GAP,)
    four = [failed, numbered(failed, 2), numbered(failed, 3), numbered(good, 4)]
    excess = run_history(RUN, four, EARLIEST, 3)
    assert (excess.findings, excess.counted) == ((EXCESS,), numbered(failed, 3))
    after = run_history(RUN, [good, numbered(good, 2)], EARLIEST, 3)
    assert (after.findings, after.counted) == ((AFTER_STOP,), good)


@pytest.mark.parametrize("rule", list(CountedAttempt))
def test_an_excess_attempt_never_counts_under_any_rule(
    failed: Evaluation, good: Evaluation, rule: CountedAttempt
) -> None:
    # Three infrastructure failures and a fourth attempt that passed: the registered system
    # has three attempts, and none of them is the fourth.
    four = [failed, numbered(failed, 2), numbered(failed, 3), numbered(good, 4)]
    history = run_history(RUN, four, rule, 3)
    assert history.counted is not None
    assert history.counted.outcome.header.attempt <= 3
    assert failed_by_infrastructure(history.counted)
    assert history.findings == (EXCESS,)
    assert history.attempts[-1] == numbered(good, 4)
    assert not history.recovered


def test_a_gap_is_an_eligible_attempt_absent_and_nothing_else(
    failed: Evaluation, good: Evaluation
) -> None:
    # Attempt five shows a third was made: the last eligible attempt is absent.
    absent_third = run_history(RUN, [failed, numbered(failed, 2), numbered(good, 5)], EARLIEST, 3)
    assert (absent_third.counted, absent_third.findings) == (None, (GAP, EXCESS))
    # Every eligible attempt present, an excess one beyond a hole among the excess: no gap.
    whole = [failed, numbered(failed, 2), numbered(failed, 3), numbered(good, 5)]
    beyond = run_history(RUN, whole, EARLIEST, 3)
    assert (beyond.counted, beyond.findings) == (numbered(failed, 3), (EXCESS,))
    # Two attempts and nothing after them owe no third.
    short = run_history(RUN, [failed, numbered(failed, 2)], EARLIEST, 3)
    assert (short.counted, short.findings) == (numbered(failed, 2), ())
    # Only excess attempts present: every eligible one is absent.
    only_excess = run_history(RUN, [numbered(good, 4)], EARLIEST, 3)
    assert (only_excess.counted, only_excess.findings) == (None, (GAP, EXCESS))
    # An absent eligible attempt is a gap even behind a stopping outcome: a gap is defined
    # once, for every counting rule, and under the last-attempt rule the third would count.
    stopped = run_history(RUN, [failed, numbered(good, 2), numbered(good, 4)], EARLIEST, 3)
    assert (stopped.counted, stopped.findings) == (None, (GAP, EXCESS))


@pytest.mark.parametrize("rule", list(CountedAttempt))
def test_a_gap_leaves_no_counted_attempt_under_any_rule(
    failed: Evaluation, good: Evaluation, rule: CountedAttempt
) -> None:
    for attempts in ([numbered(good, 2)], [failed, numbered(good, 3)]):
        history = run_history(RUN, attempts, rule, 3)
        assert history.counted is None
        assert GAP in history.findings
        assert not history.recovered
    # A stopping outcome before a gap is not a predecessor of the attempt after it.
    apart = run_history(RUN, [good, numbered(good, 3)], rule, 3)
    assert apart.findings == (GAP,)


def test_a_history_is_of_attempts_each_numbered_once(good: Evaluation) -> None:
    with pytest.raises(ValueError, match=r"run run-8 has attempts, each number once, got \[\]"):
        run_history(RUN, [], EARLIEST, 3)
    with pytest.raises(ValueError, match=r"each number once, got \[1, 1\]"):
        run_history(RUN, [good, good], EARLIEST, 3)
    with pytest.raises(ValueError, match="a run has at least one attempt, got 0"):
        Preregistered(0.95, 7, 1_000, 1, EARLIEST, MissingRepeat.NOT_PASSED, plan(good).arms, 0)


# --- In the cells and the tables ---------------------------------------------------------------


@pytest.mark.parametrize("missing_repeat", list(MissingRepeat))
def test_a_run_with_a_gap_is_made_unverifiable_and_in_no_quality_estimate(
    world: SealedWorld, failed: Evaluation, good: Evaluation, missing_repeat: MissingRepeat
) -> None:
    chosen = plan(failed, missing_repeat=missing_repeat)
    (arm,) = arms(world, [failed, numbered(good, 3)], chosen)
    runs = arm.scenarios[0]
    assert (runs.counted, runs.unverifiable, runs.missing) == ((), 1, 0)
    assert runs.attempts == (failed, numbered(good, 3))
    cell = cells_of(arm)[0]

    accounting = accounting_of(cell, chosen)
    assert (accounting.made, accounting.unverifiable_history, accounting.attempts) == (1, 1, 2)
    assert (accounting.graded, accounting.excluded) == (0, ())
    assert accounting.missing == len(world.scenarios) - 1

    # Made and not passed end to end, whatever the missing-run rule; absent conditionally.
    held = replace(cell, scenarios=(runs,))
    end_to_end = estimate_check(held, PASSES, Reading.END_TO_END, chosen)
    assert (end_to_end.scenarios, end_to_end.passed, end_to_end.runs) == (1, 0.0, 0)
    conditional = estimate_check(held, PASSES, Reading.CONDITIONAL, chosen)
    assert (conditional.scenarios, conditional.runs) == (0, 0)

    # Both attempts were paid for.
    assert cost_ledger(held).attempts == 2


def test_a_gapped_repeat_keeps_its_scenario_a_repeated_one_in_both_readings(
    world: SealedWorld, failed: Evaluation, good: Evaluation
) -> None:
    system = failed.outcome.header.system
    two_runs = replace(plan(failed), intended_repeats=2)
    valid = relabelled(good, run_id="run-a")
    gapped = relabelled(good, run_id="run-b", attempt=2)
    (arm,) = arms(world, [valid, gapped], two_runs)
    held = replace(cells_of(arm)[0], scenarios=(arm.scenarios[0],))
    for reading in Reading:
        estimate = estimate_check(held, PASSES, reading, two_runs)
        assert (estimate.wilson, estimate.runs) == (None, 1), reading
        # The bootstrap's form, which one scenario alone cannot resolve.
        assert (estimate.bootstrap, estimate.unresolved) == (None, LONE), reading

    # Against an arm with one clean run of the scenario, the comparison is of a repeated
    # design: never the two-by-two counts of single runs.
    other = System(system.kind, "other")
    both = replace(two_runs, arms=((system, NORMAL, "base"), (other, NORMAL, "base")))
    clean = relabelled(good, run_id="run-c", system=other)
    theirs, mine = arms(world, [valid, gapped, clean], both)
    assert (mine.system, theirs.system) == (system, other)
    first = replace(cells_of(mine)[0], scenarios=(mine.scenarios[0],))
    second = replace(cells_of(theirs)[0], scenarios=(theirs.scenarios[0],))
    comparison = compare_check(first, second, PASSES, Reading.CONDITIONAL, both)
    assert comparison.two_by_two is None
    assert (comparison.interval, comparison.unresolved) == (None, LONE)


def test_a_record_disagreement_on_a_gapped_run_shows_in_the_summary_alone(
    world: SealedWorld, failed: Evaluation, good: Evaluation
) -> None:
    assert isinstance(good.outcome, Graded) and good.outcome.harness_findings == ()
    disagreeing = replace(good, outcome=replace(good.outcome, harness_findings=("disagrees",)))
    chosen = plan(failed)
    (arm,) = arms(world, [numbered(disagreeing, 2)], chosen)
    cell = cells_of(arm)[0]
    assert accounting_of(cell, chosen).record_disagreements == 0
    assert accounting_of(cell, chosen).unverifiable_history == 1
    assert attempt_summary_of(cell).record_disagreements == 1


def test_the_attempt_summary_shows_the_failure_a_recovered_retry_hides(
    world: SealedWorld, failed: Evaluation, good: Evaluation
) -> None:
    chosen = plan(failed)
    (arm,) = arms(world, [failed, numbered(good, 2)], chosen)
    cell = cells_of(arm)[0]

    accounting = accounting_of(cell, chosen)
    assert (accounting.made, accounting.graded, accounting.excluded) == (1, 1, ())

    summary = attempt_summary_of(cell)
    assert (summary.attempts, summary.graded) == (2, 1)
    assert summary.excluded == ((ExcludedReason.FAILED_BY_INFRASTRUCTURE, 1),)
    assert (summary.runs_retried, summary.runs_recovered) == (1, 1)
    assert (summary.history, summary.record_disagreements) == ((), 0)


def test_the_attempt_summary_counts_the_runs_carrying_each_history_finding(
    world: SealedWorld, failed: Evaluation, good: Evaluation
) -> None:
    def as_run(evaluation: Evaluation, run_id: str, attempt: int) -> Evaluation:
        return relabelled(evaluation, run_id=run_id, attempt=attempt)

    held = [
        # run-1: a gap. run-2: a retry after a graded attempt. run-3: clean.
        as_run(good, "run-1", 2),
        as_run(good, "run-2", 1),
        as_run(good, "run-2", 2),
        as_run(good, "run-3", 1),
    ]
    chosen = replace(plan(failed), intended_repeats=3)
    (arm,) = arms(world, held, chosen)
    summary = attempt_summary_of(cells_of(arm)[0])
    assert (summary.attempts, summary.graded, summary.runs_retried) == (4, 4, 1)
    assert summary.history == ((AFTER_STOP, 1), (GAP, 1))
    accounting = accounting_of(cells_of(arm)[0], chosen)
    assert (accounting.made, accounting.graded, accounting.unverifiable_history) == (3, 2, 1)


# --- The eligibility audit ----------------------------------------------------------------------


def permitting(evaluation: Evaluation, permitted: bool) -> Evaluation:
    """``evaluation`` with an evaluated eligibility: an infrastructure failure at a send,
    read by a row whose flag is ``permitted``."""
    check = EligibilityCheck(
        ProjectedEnding(EndingKind.SEND_FAILURE, "throttled", permitted),
        permitted,
        EligibilityRule.SEND_ROW,
        "throttled",
    )
    return replace(evaluation, metrics=replace(evaluation.metrics, eligibility=check))


def test_an_attempt_its_predecessor_did_not_permit_is_never_counted_nor_any_after_it(
    failed: Evaluation, good: Evaluation
) -> None:
    # Failed by infrastructure under a row flagged for no new attempt, then a graded attempt:
    # the coarse reading permits, the fine one does not, and the fine one decides.
    refused = permitting(failed, False)
    history = run_history(RUN, [refused, numbered(good, 2)], EARLIEST, 3)
    assert (history.findings, history.counted) == ((NOT_PERMITTED,), refused)
    assert not history.recovered
    for rule in CountedAttempt:
        assert run_history(RUN, [refused, numbered(good, 2)], rule, 3).counted == refused
    # A third attempt its own predecessor permitted descends from the one that should not
    # exist: never counted either.
    third = [refused, numbered(permitting(failed, True), 2), numbered(good, 3)]
    assert run_history(RUN, third, EARLIEST, 3).counted == refused
    # The row permitting: counted as before, no finding.
    allowed = run_history(RUN, [permitting(failed, True), numbered(good, 2)], EARLIEST, 3)
    assert (allowed.findings, allowed.counted) == ((), numbered(good, 2))


def test_a_predecessor_with_no_evaluated_eligibility_leaves_the_pair_unverified(
    failed: Evaluation, good: Evaluation
) -> None:
    assert failed.metrics.eligibility is None
    history = run_history(RUN, [failed, numbered(good, 2)], EARLIEST, 3)
    assert (history.findings, history.counted) == ((), numbered(good, 2))


def test_an_attempt_after_a_stopping_outcome_is_never_counted_under_the_last_rule_either(
    good: Evaluation,
) -> None:
    two_completed = [good, numbered(good, 2)]
    assert run_history(RUN, two_completed, CountedAttempt.LAST, 3).counted == good
    assert run_history(RUN, two_completed, CountedAttempt.LAST, 3).findings == (AFTER_STOP,)


def test_the_summary_counts_the_runs_not_permitted_and_the_cells_count_the_audits(
    world: SealedWorld, failed: Evaluation, good: Evaluation
) -> None:
    chosen = plan(failed)
    (arm,) = arms(world, [permitting(failed, False), numbered(good, 2)], chosen)
    cell = cells_of(arm)[0]
    summary = attempt_summary_of(cell)
    assert summary.history == ((NOT_PERMITTED, 1),)
    assert (summary.runs_retried, summary.runs_recovered) == (1, 0)
    accounting = accounting_of(cell, chosen)
    assert accounting.excluded == ((ExcludedReason.FAILED_BY_INFRASTRUCTURE, 1),)
    # The failed attempt is an agent's export evaluated under no registration: its account
    # is read, its count check's registration parts, its call check and (but for the
    # eligibility set by hand) its eligibility are not. The graded one is rules-only: no
    # reservation, so no account.
    assert (
        summary.with_account_findings,
        summary.with_count_findings,
        summary.with_call_findings,
        summary.count_not_evaluated,
        summary.call_not_evaluated,
        summary.eligibility_not_evaluated,
        summary.account_not_evaluated,
    ) == (0, 0, 0, 2, 2, 1, 1)
    # The accounting is over the counted attempt alone, the refused one: an agent's export.
    assert (accounting.count_not_evaluated, accounting.account_not_evaluated) == (1, 0)
