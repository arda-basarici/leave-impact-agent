"""A run's attempt history: the earliest attempt that did not fail by infrastructure is the
run, else the last; a gap in the attempt numbers leaves no counted attempt under any rule,
the run made, unverifiable, not passed end to end and absent from the conditional reading,
its attempts still paid for; an attempt above the maximum and an attempt after a stopping
outcome are findings on a run still counted; and the attempt summary shows the
infrastructure failure a recovered retry hides from the accounting."""

from dataclasses import replace

import pytest

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
from leaveimpact.evaluator.grading import Excluded, ExcludedReason, Graded
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.tables import Check, Reading, cost_ledger, estimate_check
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from tests.unit.evaluation_fixture import NORMAL, evaluated, relabelled
from tests.unit.export_fixture import provider_failed_export
from tests.unit.throwaway_world import loaded_world

EARLIEST = CountedAttempt.EARLIEST_NOT_INFRASTRUCTURE
GAP = HistoryFinding.GAP
EXCESS = HistoryFinding.EXCESS_ATTEMPT
AFTER_STOP = HistoryFinding.ATTEMPT_AFTER_STOPPING_OUTCOME
RUN = "run-8"
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
    registered = ((failed.outcome.header.system, NORMAL),)
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
    assert (excess.findings, excess.counted) == ((EXCESS,), numbered(good, 4))
    after = run_history(RUN, [good, numbered(good, 2)], EARLIEST, 3)
    assert (after.findings, after.counted) == ((AFTER_STOP,), good)


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
    assert summary.history == ()


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
