"""Cells: evaluated runs grouped into what a table reports, with the accounting every table
carries.

A *cell* is one system, one assigned condition and one stratum, and nothing is pooled
across systems or conditions (the investigator milestone's fourth build step, ruling 6).
The arm is the condition a run was *assigned*, never the one it observed, so a system's
own behaviour cannot choose its arm. The strata are the whole set, each tier, and each
scenario class; a tier and the whole carry intervals, a class only its raw counts, one to
four scenarios being enough to localize a failure and not to estimate a rate.

The unit is the scenario with all its runs. A scenario run several times is one cluster
holding several runs, never several scenarios, and the repeats of two systems are never
paired slot to slot. A run retried is one run: which of its attempts is the counted one is
the preregistration's rule, given here as an argument, so that a successful retry cannot
quietly replace a failed first attempt. Every attempt stays in the cell for the cost
ledger, since a retry was paid for.

Nothing the preregistration owns is chosen here. ``Preregistered`` is the one record of
what it fixes for estimation: the confidence level, the seed and the number of resamples,
how many runs of each scenario were intended, which attempt of a retried run counts, how
an intended run that was never made counts toward end-to-end success, and the arms that
were registered, each a system under an assigned condition. It has no default anywhere; a
table records the plan it was cut under.

The arms come from the registration and not from what arrived. An arm that produced no
export at all is built all the same, every scenario with its intended runs missing: a
system that failed to run would otherwise leave no row to say so. An arm that arrived
without being registered is built too and says it was not registered; whether it enters a
reported table is the reporting step's.

The *accounting* is what keeps an exclusion a visible smaller denominator and never a
better score. Per cell: the runs intended, made and missing; how each counted run ended,
graded, limited by reason, excluded by reason; the conditions the runs observed against
the one assigned, with the assigned outages a run never exercised and the faults nobody
scheduled; the runs whose record disagreed with their trace, and the ones that carry an
integrity, an operation, a cost or a prefetch finding, with the runs whose prefetch was
planned under another rule and so not held to this one. Whether a run with a finding
enters a reported table is the preregistration's; here it is counted.

An attempt whose scenario the sealed world does not hold cannot be placed in a tier or a
class. It is kept on its arm as unplaced, counted in the accounting of the whole and paid
for in the whole's cost ledger, never dropped; no measure and no check reads it, having no
scenario to be a run of.

One export is one attempt. The same run and attempt given twice for one scenario of one arm
would count twice in every sum, so it is refused where the runs are grouped.

A run's attempts are read as a history (``attempts``): the counted attempt by the plan's
rule, and what the history shows that the retry protocol never produces. A run whose
attempt numbers have a gap has no counted attempt: it is counted as made under its own
reason, and no measure, check or outcome tally reads it. The accounting is over counted
attempts, so an infrastructure failure a retry recovered from would show nowhere in it;
the *attempt summary* is the same tallies over every attempt, with the runs retried, the
runs recovered and the history findings, so that a retry never hides what it replaced.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.enums import Source
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.ids import ScenarioId
from leaveimpact.core.run_record import System
from leaveimpact.evaluator.attempts import CountedAttempt, HistoryFinding, RunHistory, run_history
from leaveimpact.evaluator.grading import (
    Excluded,
    ExcludedReason,
    Graded,
    Limited,
    LimitedReason,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import Evaluation
from leaveimpact.world.scenario import ScenarioClassName, Tier


class MissingRepeat(StrEnum):
    """How an intended run that was never made counts toward end-to-end success."""

    NOT_PASSED = "not_passed"
    LEFT_OUT = "left_out"


@dataclass(frozen=True, slots=True)
class Preregistered:
    """What the preregistration fixes for estimation; every field is given, none defaulted."""

    confidence: float
    seed: int
    resamples: int
    intended_repeats: int
    counted_attempt: CountedAttempt
    missing_repeat: MissingRepeat
    arms: tuple[tuple[System, RunCondition], ...]
    max_attempts: int

    def __post_init__(self) -> None:
        if not self.arms:
            raise ValueError("at least one arm is registered: a system under an assigned condition")
        if len(set(self.arms)) != len(self.arms):
            raise ValueError("an arm is registered once")
        if not 0 < self.confidence < 1:
            raise ValueError(
                f"a confidence level lies strictly between 0 and 1, got {self.confidence}"
            )
        if self.resamples < 1:
            raise ValueError(f"at least one resample is drawn, got {self.resamples}")
        if self.intended_repeats < 1:
            raise ValueError(
                f"at least one run per scenario is intended, got {self.intended_repeats}"
            )
        if self.max_attempts < 1:
            raise ValueError(f"a run has at least one attempt, got {self.max_attempts}")


class StratumKind(StrEnum):
    """The three levels a table is cut at; a member is the wire format."""

    OVERALL = "overall"
    TIER = "tier"
    CLASS = "class"


@dataclass(frozen=True, slots=True)
class Stratum:
    """One level of one table: the whole set, a tier, or a scenario class, by name."""

    kind: StratumKind
    name: str

    @property
    def estimated(self) -> bool:
        """Whether the stratum carries intervals; a class shows its raw counts only."""
        return self.kind is not StratumKind.CLASS


OVERALL = Stratum(StratumKind.OVERALL, "overall")


@dataclass(frozen=True, slots=True)
class ScenarioRuns:
    """One scenario's runs in one arm of one system: the cluster every estimate resamples.

    ``counted`` holds one evaluation per run whose history gives one, the attempt the plan
    counts, in run order; ``attempts`` every attempt of every run, for the cost ledger;
    ``missing`` how many intended runs were never made; ``histories`` every run's attempt
    history, in run order.
    """

    scenario_id: ScenarioId
    tier: Tier
    scenario_class: ScenarioClassName
    counted: tuple[Evaluation, ...]
    attempts: tuple[Evaluation, ...]
    missing: int
    histories: tuple[RunHistory, ...]

    @property
    def unverifiable(self) -> int:
        """How many runs were made and have no counted attempt, their history holding a gap."""
        return sum(history.counted is None for history in self.histories)


@dataclass(frozen=True, slots=True)
class Arm:
    """One system under one assigned condition: every scenario of the world in the plan's
    order, with the runs it has, and the attempts no scenario of the world could place.
    ``registered`` says the plan names the arm; one that only arrived is built and says not."""

    system: System
    assigned: RunCondition
    scenarios: tuple[ScenarioRuns, ...]
    unplaced: tuple[Evaluation, ...]
    registered: bool

    @property
    def name(self) -> str:
        """The arm by its system and its assigned condition, as an interval's seed names it."""
        return f"{self.system.kind.value}/{self.system.variant} {condition_name(self.assigned)}"


@dataclass(frozen=True, slots=True)
class Cell:
    """One arm cut at one stratum: the scenarios of the stratum, in the plan's order."""

    arm: Arm
    stratum: Stratum
    scenarios: tuple[ScenarioRuns, ...]

    @property
    def unplaced(self) -> tuple[Evaluation, ...]:
        """The arm's attempts that no scenario of the world could place: held by the whole,
        and by no tier or class."""
        return self.arm.unplaced if self.stratum.kind is StratumKind.OVERALL else ()

    def by_tier(self) -> tuple[tuple[ScenarioRuns, ...], ...]:
        """The cell's scenarios grouped by tier, the groups a resample is drawn within."""
        return tuple(
            tuple(runs for runs in self.scenarios if runs.tier is tier)
            for tier in Tier
            if any(runs.tier is tier for runs in self.scenarios)
        )


@dataclass(frozen=True, slots=True)
class Accounting:
    """What happened to the runs of a cell; every count is over counted runs unless it says
    attempts.

    ``intended`` is the plan's repeats times the scenarios; ``made`` the runs present,
    ``missing`` the shortfall and ``surplus`` the runs beyond what was intended, each summed
    per scenario so that one scenario's surplus never hides another's shortfall.
    ``unverifiable_history`` counts the runs made whose attempt numbers have a gap: they
    are among ``made`` and in no count of how a run ended, having no counted attempt.
    ``attempts`` counts every attempt, retries included. A structurally invalid report is
    counted where its run ended: among the graded, where it was graded with zero credit, or
    among the limited. ``observed`` is over the graded
    and the limited runs, the ones whose trace was read for a condition. A run is
    ``unexercised`` when a source its assignment scheduled out was reachable in its trace,
    and has an ``unscheduled`` fault when a source nobody scheduled out was not.
    ``with_prefetch_findings`` counts the runs whose prefetch reads are not the ones the
    plan obliged, and ``prefetch_not_evaluated`` the runs planned under another prefetch
    rule, which carry no such finding because they were held to no plan.
    ``unplaced`` counts the attempts of the arm that no scenario of the world could place,
    in the whole only; they are in no other count here.
    """

    scenarios: int
    intended: int
    made: int
    missing: int
    surplus: int
    attempts: int
    graded: int
    structurally_invalid: int
    limited_structurally_invalid: int
    limited: tuple[tuple[LimitedReason, int], ...]
    excluded: tuple[tuple[ExcludedReason, int], ...]
    observed: tuple[tuple[RunCondition, int], ...]
    unexercised: int
    unscheduled: int
    record_disagreements: int
    with_integrity_findings: int
    with_operation_findings: int
    with_cost_findings: int
    unplaced: int
    unverifiable_history: int
    with_prefetch_findings: int
    prefetch_not_evaluated: int


@dataclass(frozen=True, slots=True)
class AttemptSummary:
    """What happened to every attempt of a cell's runs, the ones a retry replaced included.

    The outcome and finding counts are ``Accounting``'s, the two prefetch counts among
    them, over all attempts instead of the counted ones. ``runs_retried`` are the runs with
    more than one attempt and ``runs_recovered`` those where an attempt before the counted
    one failed by infrastructure and the counted one did not; ``history`` is how many runs
    carry each history finding. The attempts no
    scenario of the world could place are not here, having no run history to be read in.
    """

    attempts: int
    graded: int
    limited: tuple[tuple[LimitedReason, int], ...]
    excluded: tuple[tuple[ExcludedReason, int], ...]
    record_disagreements: int
    with_integrity_findings: int
    with_operation_findings: int
    with_cost_findings: int
    runs_retried: int
    runs_recovered: int
    history: tuple[tuple[HistoryFinding, int], ...]
    with_prefetch_findings: int
    prefetch_not_evaluated: int


def condition_name(condition: RunCondition) -> str:
    """A condition by what it cannot reach: ``normal``, or the sources down, in name order.

    >>> condition_name(RunCondition.all_reachable().without(Source.JIRA, Source.CALENDAR))
    'calendar+jira down'
    """
    down = sorted(source.value for source in Source if source not in condition.reachable)
    return f"{'+'.join(down)} down" if down else "normal"


def arms(
    world: SealedWorld, evaluations: Iterable[Evaluation], plan: Preregistered
) -> tuple[Arm, ...]:
    """``evaluations`` grouped into arms: by system, and within a system the normal condition
    first, then the outages by how many sources they take and by name.

    Every arm the plan registers is built, with or without a run, and every arm holds every
    scenario of ``world``: a scenario a system never ran is a missing run of that arm, and
    an arm that never ran is thirty of them, not an absent table.
    """
    by_arm: dict[tuple[System, RunCondition], list[Evaluation]] = {arm: [] for arm in plan.arms}
    for evaluation in evaluations:
        key = (evaluation.outcome.header.system, evaluation.assigned)
        by_arm.setdefault(key, []).append(evaluation)
    built: list[Arm] = []
    for (system, assigned), held in by_arm.items():
        by_scenario: dict[ScenarioId, list[Evaluation]] = {}
        for evaluation in held:
            by_scenario.setdefault(evaluation.outcome.header.scenario_id, []).append(evaluation)
        scenarios = tuple(
            _scenario_runs(
                scenario.spec.id,
                scenario.key.tier,
                scenario.key.scenario_class,
                by_scenario.pop(scenario.spec.id, []),
                plan,
            )
            for scenario in world.scenarios
        )
        unplaced = tuple(each for left in by_scenario.values() for each in _in_order(left))
        registered = (system, assigned) in plan.arms
        built.append(Arm(system, assigned, scenarios, unplaced, registered))
    return tuple(sorted(built, key=_arm_order))


def within(arm: Arm, scenarios: Iterable[ScenarioId]) -> Arm:
    """``arm`` cut to ``scenarios``, a scenario set of the registration, in the arm's order.

    The attempts no scenario of the world could place belong to no set and are left with
    the whole arm; a set that names a scenario the arm does not hold is refused.
    """
    kept = set(scenarios)
    strangers = sorted(kept - {runs.scenario_id for runs in arm.scenarios})
    if strangers:
        raise ValueError(f"the arm holds no scenario {', '.join(strangers)}")
    held = tuple(runs for runs in arm.scenarios if runs.scenario_id in kept)
    return Arm(arm.system, arm.assigned, held, (), arm.registered)


def cells_of(arm: Arm) -> tuple[Cell, ...]:
    """``arm`` cut at every stratum it has: the whole, each tier, each scenario class."""
    cells = [Cell(arm, OVERALL, arm.scenarios)]
    for tier in Tier:
        held = tuple(runs for runs in arm.scenarios if runs.tier is tier)
        if held:
            cells.append(Cell(arm, Stratum(StratumKind.TIER, tier.value), held))
    for name in ScenarioClassName:
        held = tuple(runs for runs in arm.scenarios if runs.scenario_class is name)
        if held:
            cells.append(Cell(arm, Stratum(StratumKind.CLASS, name.value), held))
    return tuple(cells)


def accounting_of(cell: Cell, plan: Preregistered) -> Accounting:
    """What happened to the runs of ``cell``."""
    scenarios = cell.scenarios
    counted = [evaluation for runs in scenarios for evaluation in runs.counted]
    outcomes = [evaluation.outcome for evaluation in counted]
    graded = [outcome for outcome in outcomes if isinstance(outcome, Graded)]
    limited = [outcome for outcome in outcomes if isinstance(outcome, Limited)]
    excluded = [outcome for outcome in outcomes if isinstance(outcome, Excluded)]
    observed = [
        (evaluation.assigned, evaluation.outcome.condition)
        for evaluation in counted
        if isinstance(evaluation.outcome, Graded | Limited)
    ]
    read = [*graded, *limited]
    return Accounting(
        scenarios=len(scenarios),
        intended=plan.intended_repeats * len(scenarios),
        made=sum(len(runs.histories) for runs in scenarios),
        missing=sum(runs.missing for runs in scenarios),
        surplus=sum(max(len(runs.histories) - plan.intended_repeats, 0) for runs in scenarios),
        attempts=sum(len(runs.attempts) for runs in scenarios),
        graded=len(graded),
        structurally_invalid=sum(not outcome.rows.structurally_valid for outcome in graded),
        limited_structurally_invalid=sum(bool(outcome.structural_problems) for outcome in limited),
        limited=_tally(outcome.reason for outcome in limited),
        excluded=_tally(outcome.reason for outcome in excluded),
        observed=tuple(
            sorted(
                Counter(condition for _, condition in observed).items(),
                key=lambda item: condition_name(item[0]),
            )
        ),
        unexercised=sum(
            bool((frozenset(Source) - assigned.reachable) & seen.reachable)
            for assigned, seen in observed
        ),
        unscheduled=sum(bool(assigned.reachable - seen.reachable) for assigned, seen in observed),
        record_disagreements=sum(bool(outcome.harness_findings) for outcome in read),
        with_integrity_findings=sum(bool(outcome.integrity) for outcome in read),
        with_operation_findings=sum(
            bool(evaluation.metrics.discipline.findings) for evaluation in counted
        ),
        with_cost_findings=sum(bool(evaluation.metrics.cost.findings) for evaluation in counted),
        unplaced=len(cell.unplaced),
        unverifiable_history=sum(runs.unverifiable for runs in scenarios),
        with_prefetch_findings=sum(
            bool(evaluation.metrics.prefetch.findings) for evaluation in counted
        ),
        prefetch_not_evaluated=sum(
            not evaluation.metrics.prefetch.evaluated for evaluation in counted
        ),
    )


def attempt_summary_of(cell: Cell) -> AttemptSummary:
    """What happened to every attempt of ``cell``'s runs, and what their histories show."""
    histories = [history for runs in cell.scenarios for history in runs.histories]
    attempts = [attempt for history in histories for attempt in history.attempts]
    outcomes = [attempt.outcome for attempt in attempts]
    read = [outcome for outcome in outcomes if isinstance(outcome, Graded | Limited)]
    return AttemptSummary(
        attempts=len(attempts),
        graded=sum(isinstance(outcome, Graded) for outcome in outcomes),
        limited=_tally(outcome.reason for outcome in outcomes if isinstance(outcome, Limited)),
        excluded=_tally(outcome.reason for outcome in outcomes if isinstance(outcome, Excluded)),
        record_disagreements=sum(bool(outcome.harness_findings) for outcome in read),
        with_integrity_findings=sum(bool(outcome.integrity) for outcome in read),
        with_operation_findings=sum(
            bool(attempt.metrics.discipline.findings) for attempt in attempts
        ),
        with_cost_findings=sum(bool(attempt.metrics.cost.findings) for attempt in attempts),
        runs_retried=sum(history.retried for history in histories),
        runs_recovered=sum(history.recovered for history in histories),
        history=_tally(finding for history in histories for finding in history.findings),
        with_prefetch_findings=sum(bool(attempt.metrics.prefetch.findings) for attempt in attempts),
        prefetch_not_evaluated=sum(not attempt.metrics.prefetch.evaluated for attempt in attempts),
    )


def _scenario_runs(
    scenario_id: ScenarioId,
    tier: Tier,
    scenario_class: ScenarioClassName,
    evaluations: Sequence[Evaluation],
    plan: Preregistered,
) -> ScenarioRuns:
    """One scenario's evaluations as its runs: each run's history, the counted attempt of
    each that has one, and every attempt."""
    by_run: dict[str, list[Evaluation]] = {}
    for evaluation in evaluations:
        by_run.setdefault(evaluation.outcome.header.run_id, []).append(evaluation)
    for run_id, made in by_run.items():
        numbers = [evaluation.outcome.header.attempt for evaluation in made]
        if len(set(numbers)) != len(numbers):
            raise ValueError(
                f"{scenario_id}: run {run_id} holds one attempt twice; an export is aggregated "
                "once"
            )
    histories = tuple(
        run_history(run_id, by_run[run_id], plan.counted_attempt, plan.max_attempts)
        for run_id in sorted(by_run)
    )
    return ScenarioRuns(
        scenario_id,
        tier,
        scenario_class,
        tuple(history.counted for history in histories if history.counted is not None),
        tuple(each for history in histories for each in history.attempts),
        max(plan.intended_repeats - len(by_run), 0),
        histories,
    )


def _arm_order(arm: Arm) -> tuple[str, str, int, str]:
    down = len(Source) - len(arm.assigned.reachable)
    return (arm.system.kind.value, arm.system.variant, down, condition_name(arm.assigned))


def _in_order(evaluations: Sequence[Evaluation]) -> list[Evaluation]:
    """Evaluations by run and attempt, the order an export's identity gives them."""
    return sorted(
        evaluations,
        key=lambda evaluation: (
            evaluation.outcome.header.run_id,
            evaluation.outcome.header.attempt,
        ),
    )


def _tally[T: StrEnum](values: Iterable[T]) -> tuple[tuple[T, int], ...]:
    """How many of each value, the values that occur, in name order."""
    return tuple(sorted(Counter(values).items(), key=lambda item: item[0].value))


__all__ = [
    "OVERALL",
    "Accounting",
    "Arm",
    "AttemptSummary",
    "Cell",
    "CountedAttempt",
    "MissingRepeat",
    "Preregistered",
    "ScenarioRuns",
    "Stratum",
    "StratumKind",
    "accounting_of",
    "arms",
    "attempt_summary_of",
    "cells_of",
    "condition_name",
    "within",
]
