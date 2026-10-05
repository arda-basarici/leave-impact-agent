"""Tables: a measure or a check estimated in a cell, two systems compared, and what a cell cost.

Everything here is a reading of evaluated runs already grouped into cells, and each estimate
keeps what it was computed from, so a number on a page can be traced to its counts, its
scenarios and the plan it was cut under (the investigator milestone's fourth build step,
ruling 6).

*A claim-level ratio* is the sum of a measure's numerators over the sum of its
denominators, across the scenarios of the cell, a scenario's repeats pooled first. Its
interval resamples those scenarios within their tiers. The scenarios resampled are the ones
with a run in the measure's scope: a conditional quality is conditional on the run being
one the measure applies to, and the count of scenarios it rests on is shown beside it. An
observed zero denominator is ``0/0``, not estimable, with no value and no interval, and
the scenarios in scope that had nothing to count are counted.

Wherever a bootstrap interval is asked for, the estimate holds either the interval or the
reason the bootstrap resolved none (``intervals.Unresolved``), never neither: an absent
interval with no reason reads as an omission, and one of no width as certainty. The point
estimate and its counts are there in both cases.

*A yes-or-no check* is read two ways, and a table shows both. *Conditional* quality is
over the runs the check applies to. *End to end* is over every run a scenario was meant to
have: a limited or an excluded run does not pass, and is counted apart from a run that was
checked and failed, so a provider fault is never scored as a wrong answer and never
improves a score by leaving. Whether an intended run that was never made counts as not
passed or is left out is the plan's. A scenario's value is its pass fraction over its
runs; the cell's is the mean of those. With exactly one run behind every scenario that is
x of n and the interval is Wilson's; otherwise it is the bootstrap of the mean. One run
means one run held, not one run the check applied to: a scenario run twice with one run
limited is a repeated scenario whose conditional value happens to rest on one of its
runs, and it stays a cluster. The same holds for a scenario the plan meant to run more
than once: with one of two intended runs never made it is a repeated scenario short of a
run, so the form of an interval and of a comparison follows the plan and the runs made,
never how many answers happened to arrive.

*A comparison* is paired on scenario and assigned condition: the same stratum of two
arms under one condition, over the scenarios both have in scope, the paired count stated.
The two arms are two systems at one corpus level, or one system at two levels, the answers
being the same at every level; never both at once, and never two conditions, whose
oracles differ. Each comparison also says how many of its paired scenarios carry an
incident, a source that contradicted itself in some run of the measurement, since such a
scenario touches every arm that rests on it and not only the one that met it. For a ratio
every resample draws the same scenarios for both systems and
takes the difference of the two ratios of sums. For a check it is the difference of the
mean pass fractions, by the same resampling at any number of runs per scenario: whole
scenarios within their tiers, a scenario's repeats kept together and never paired slot to
slot. With one run per scenario on each side a pass fraction is nought or one, the same
method applies, and the two-by-two table is given beside the interval: both passed, the
first only, the second only, neither.

*Cost and duration carry no interval.* A cell's cost is the total over every attempt,
retries included, with the median and the range per run and the number of runs whose cost
is a floor: a run with a send the provider reported no usage for, one nobody can prove
was not sent, or one the embedded rates could not price. Costs are in pico-dollars and a
duration is evidenced active time, which is a lower bound for a run with an attempt whose
segment was killed before its end was recorded: the ledger counts those runs and gives the
segments per run beside the durations, so an interrupted run never reads as an unusually
fast one. A run with no possible send, because it called no model
or every request was refused before sending, cost nothing, and that is a
complete
cost of zero. The whole's ledger also holds the arm's attempts that no scenario of the
world could place: they belong to no tier and were paid for all the same.

A class stratum gets its raw counts and no interval, anywhere in this module.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass
from enum import StrEnum
from math import lcm
from statistics import median

from leaveimpact.core.ids import ScenarioId
from leaveimpact.evaluator.cells import Cell, MissingRepeat, Preregistered, ScenarioRuns, Stratum
from leaveimpact.evaluator.intervals import (
    BootstrapInterval,
    Cluster,
    Unresolved,
    WilsonInterval,
    bootstrap_difference,
    bootstrap_ratio,
    derived_seed,
    wilson,
)
from leaveimpact.evaluator.measures import Measure
from leaveimpact.evaluator.trace_metrics import Evaluation
from leaveimpact.world.scenario import Tier


@dataclass(frozen=True, slots=True)
class Check:
    """A yes-or-no question of one run, by name: ``True`` or ``False`` where it applies, and
    ``None`` for a run it does not apply to, a limited or an excluded one as a rule."""

    name: str
    of: Callable[[Evaluation], bool | None]


class Reading(StrEnum):
    """Which runs a check is read over; a member is the wire format."""

    CONDITIONAL = "conditional"
    END_TO_END = "end_to_end"


@dataclass(frozen=True, slots=True)
class RatioEstimate:
    """A measure in a cell: the two sums, the scenarios they are over, and the interval.

    ``scenarios`` had a run in the measure's scope and are what the interval resamples;
    ``empty`` of them had nothing to count. A tier and the whole hold ``interval`` or
    ``unresolved``, the reason the bootstrap gave none; a class stratum holds neither.
    """

    measure: str
    arm: str
    stratum: Stratum
    numerator: int
    denominator: int
    scenarios: int
    empty: int
    interval: BootstrapInterval | None
    unresolved: Unresolved | None

    @property
    def value(self) -> float | None:
        """The ratio of sums, or ``None`` when the denominator is zero: not estimable."""
        return self.numerator / self.denominator if self.denominator else None


@dataclass(frozen=True, slots=True)
class CheckEstimate:
    """A check in a cell under one reading.

    ``scenarios`` are the ones with at least one run counted under the reading and
    ``passed`` the sum of their pass fractions, so ``passed / scenarios`` is the cell's
    value. ``runs`` were looked at; ``not_checked`` of them the check did not apply to,
    which under the end-to-end reading count as not passed; ``missing`` intended runs were
    never made and count as the plan says; ``unverifiable`` runs were made with a gap in
    their attempt history, have no counted attempt, and did not pass end to end. For a
    tier and for the whole exactly one of three is set: Wilson's interval when every
    scenario rests on exactly one run, the bootstrap's otherwise, or ``unresolved``, the
    reason the bootstrap gave none.
    """

    check: str
    arm: str
    stratum: Stratum
    reading: Reading
    passed: float
    scenarios: int
    runs: int
    not_checked: int
    missing: int
    unverifiable: int
    wilson: WilsonInterval | None
    bootstrap: BootstrapInterval | None
    unresolved: Unresolved | None

    @property
    def value(self) -> float | None:
        """The mean pass fraction over the scenarios, or ``None`` with no scenario."""
        return self.passed / self.scenarios if self.scenarios else None


@dataclass(frozen=True, slots=True)
class RatioComparison:
    """A measure in the same stratum of two arms, over the scenarios both have in scope.

    ``first`` and ``second`` are each arm's ratio of sums over those ``paired`` scenarios,
    ``None`` when its denominator there is zero; the interval is of ``first - second``, and
    a tier and the whole hold it or ``unresolved``, the reason the bootstrap gave none.
    ``paired_with_incident`` of the paired scenarios carry an incident.
    """

    measure: str
    first_arm: str
    second_arm: str
    stratum: Stratum
    paired: int
    paired_with_incident: int
    first: float | None
    second: float | None
    interval: BootstrapInterval | None
    unresolved: Unresolved | None

    @property
    def difference(self) -> float | None:
        if self.first is None or self.second is None:
            return None
        return self.first - self.second


@dataclass(frozen=True, slots=True)
class CheckComparison:
    """A check in the same stratum of two arms under one reading, over the scenarios both
    count.

    ``first`` and ``second`` are the mean pass fractions over the ``paired`` scenarios and
    the interval is of ``first - second``, by one method at any number of runs; a tier and
    the whole hold it or ``unresolved``, the reason the bootstrap gave none. With one run
    per scenario on each side, ``two_by_two`` also holds the scenarios where both passed,
    the first only, the second only and neither; with repeats it is ``None``.
    ``paired_with_incident`` of the paired scenarios carry an incident.
    """

    check: str
    first_arm: str
    second_arm: str
    stratum: Stratum
    reading: Reading
    paired: int
    paired_with_incident: int
    first: float | None
    second: float | None
    two_by_two: tuple[int, int, int, int] | None
    interval: BootstrapInterval | None
    unresolved: Unresolved | None


@dataclass(frozen=True, slots=True)
class Spread:
    """The middle and the range of a quantity per run."""

    median: float
    low: int
    high: int


@dataclass(frozen=True, slots=True)
class CostLedger:
    """What a cell's runs cost and how long they took, every attempt counted.

    ``pico_usd`` is the total over every attempt and a floor when ``floors`` is not zero:
    that many runs hold an attempt whose cost is unknown or incomplete. ``per_run``,
    ``duration_ms`` and ``segments`` are over runs, a run's attempts summed, ``None`` with
    no run. ``lower_bound_durations`` is how many runs hold an attempt whose timing is
    incomplete, a segment's end never recorded: their durations are lower bounds.
    """

    arm: str
    stratum: Stratum
    runs: int
    attempts: int
    pico_usd: int
    floors: int
    per_run: Spread | None
    duration_ms: Spread | None
    lower_bound_durations: int
    segments: Spread | None


def estimate_ratio(cell: Cell, measure: Measure, plan: Preregistered) -> RatioEstimate:
    """``measure`` in ``cell``: the ratio of sums over its scenarios in scope, with its
    interval under ``plan`` where the stratum carries one."""
    clusters = _clusters(cell, measure)
    numerator = sum(counts[0] for _, counts in clusters)
    denominator = sum(counts[1] for _, counts in clusters)
    interval, unresolved = None, None
    if cell.stratum.estimated:
        interval, unresolved = _resolved(
            bootstrap_ratio(
                _by_tier(clusters),
                confidence=plan.confidence,
                seed=derived_seed(plan.seed, cell.arm.name, *_names(cell.stratum), measure.name),
                resamples=plan.resamples,
            )
        )
    return RatioEstimate(
        measure.name,
        cell.arm.name,
        cell.stratum,
        numerator,
        denominator,
        len(clusters),
        sum(counts[1] == 0 for _, counts in clusters),
        interval,
        unresolved,
    )


def estimate_check(
    cell: Cell, check: Check, reading: Reading, plan: Preregistered
) -> CheckEstimate:
    """``check`` in ``cell`` under ``reading``, with its interval under ``plan`` where the
    stratum carries one."""
    trials = [_trials(runs, check, reading, plan) for runs in cell.scenarios]
    counted = [(runs, each) for runs, each in zip(cell.scenarios, trials, strict=True) if each.of]
    passed = sum(each.fraction for _, each in counted)
    single = all(each.single for _, each in counted)
    interval_w: WilsonInterval | None = None
    interval_b: BootstrapInterval | None = None
    unresolved: Unresolved | None = None
    if cell.stratum.estimated:
        if counted and single:
            interval_w = wilson(round(passed), len(counted), plan.confidence)
        else:
            interval_b, unresolved = _resolved(
                bootstrap_ratio(
                    _by_tier(
                        list(
                            zip(
                                (runs.tier for runs, _ in counted),
                                _over_one_denominator([each for _, each in counted]),
                                strict=True,
                            )
                        )
                    ),
                    confidence=plan.confidence,
                    seed=derived_seed(
                        plan.seed, cell.arm.name, *_names(cell.stratum), check.name, reading.value
                    ),
                    resamples=plan.resamples,
                )
            )
    return CheckEstimate(
        check.name,
        cell.arm.name,
        cell.stratum,
        reading,
        passed,
        len(counted),
        sum(each.runs for each in trials),
        sum(each.not_checked for each in trials),
        sum(runs.missing for runs in cell.scenarios),
        sum(runs.unverifiable for runs in cell.scenarios),
        interval_w,
        interval_b,
        unresolved,
    )


def compare_ratio(
    first: Cell,
    second: Cell,
    measure: Measure,
    plan: Preregistered,
    *,
    incidents: Collection[ScenarioId] = (),
) -> RatioComparison:
    """``measure`` in ``first`` against ``second``, paired on scenario: the same stratum of two
    arms under one assigned condition. ``incidents`` are the scenarios that carry an
    incident. ``ValueError`` when the two cells are not that."""
    _require_paired(first, second)
    ours = dict(_scenario_clusters(first, measure))
    theirs = dict(_scenario_clusters(second, measure))
    shared = [
        runs for runs in first.scenarios if runs.scenario_id in ours and runs.scenario_id in theirs
    ]
    paired = [
        (runs.tier, (_as_cluster(ours[runs.scenario_id]), _as_cluster(theirs[runs.scenario_id])))
        for runs in shared
    ]
    interval, unresolved = None, None
    if first.stratum.estimated:
        interval, unresolved = _resolved(
            bootstrap_difference(
                _by_tier(paired),
                confidence=plan.confidence,
                seed=derived_seed(
                    plan.seed, first.arm.name, second.arm.name, *_names(first.stratum), measure.name
                ),
                resamples=plan.resamples,
            )
        )
    return RatioComparison(
        measure.name,
        first.arm.name,
        second.arm.name,
        first.stratum,
        len(paired),
        sum(runs.scenario_id in incidents for runs in shared),
        _ratio([pair[0] for _, pair in paired]),
        _ratio([pair[1] for _, pair in paired]),
        interval,
        unresolved,
    )


def compare_check(
    first: Cell,
    second: Cell,
    check: Check,
    reading: Reading,
    plan: Preregistered,
    *,
    incidents: Collection[ScenarioId] = (),
) -> CheckComparison:
    """``check`` in ``first`` against ``second`` under ``reading``, paired on scenario.
    ``incidents`` are the scenarios that carry an incident. ``ValueError`` when the two
    cells are not the same stratum of two arms under one assigned condition."""
    _require_paired(first, second)
    theirs = {runs.scenario_id: runs for runs in second.scenarios}
    paired: list[tuple[Tier, _Trials, _Trials]] = []
    with_incident = 0
    for runs in first.scenarios:
        other = theirs.get(runs.scenario_id)
        if other is None:
            continue
        mine = _trials(runs, check, reading, plan)
        yours = _trials(other, check, reading, plan)
        if mine.of and yours.of:
            paired.append((runs.tier, mine, yours))
            with_incident += runs.scenario_id in incidents
    single = all(mine.single and yours.single for _, mine, yours in paired)
    two_by_two: tuple[int, int, int, int] | None = None
    interval: BootstrapInterval | None = None
    unresolved: Unresolved | None = None
    if paired and single:
        outcomes = [(mine.fraction == 1, yours.fraction == 1) for _, mine, yours in paired]
        two_by_two = (
            outcomes.count((True, True)),
            outcomes.count((True, False)),
            outcomes.count((False, True)),
            outcomes.count((False, False)),
        )
    if first.stratum.estimated:
        interval, unresolved = _resolved(
            bootstrap_difference(
                _by_tier(_paired_over_one_denominator(paired)),
                confidence=plan.confidence,
                seed=derived_seed(
                    plan.seed,
                    first.arm.name,
                    second.arm.name,
                    *_names(first.stratum),
                    check.name,
                    reading.value,
                ),
                resamples=plan.resamples,
            )
        )
    count = len(paired)
    return CheckComparison(
        check.name,
        first.arm.name,
        second.arm.name,
        first.stratum,
        reading,
        count,
        with_incident,
        sum(mine.fraction for _, mine, _ in paired) / count if count else None,
        sum(yours.fraction for _, _, yours in paired) / count if count else None,
        two_by_two,
        interval,
        unresolved,
    )


def scenario_passes(
    cell: Cell, check: Check, reading: Reading, plan: Preregistered
) -> tuple[tuple[ScenarioId, int, int], ...]:
    """Each scenario of ``cell`` with its passes and its trials on ``check`` under
    ``reading``, the two whole numbers a pass fraction is made of; a scenario with no
    trial is given with nought of nought."""
    return tuple(
        (runs.scenario_id, trials.passes, trials.of)
        for runs in cell.scenarios
        for trials in (_trials(runs, check, reading, plan),)
    )


def cost_ledger(cell: Cell) -> CostLedger:
    """What ``cell``'s runs cost and how long they took, every attempt of every run counted."""
    costs: list[int] = []
    durations: list[int] = []
    segments: list[int] = []
    floors = 0
    lower_bounds = 0
    attempts = 0
    for held in (*(runs.attempts for runs in cell.scenarios), cell.unplaced):
        by_run: dict[tuple[str, str], list[Evaluation]] = {}
        for attempt in held:
            header = attempt.outcome.header
            by_run.setdefault((header.scenario_id, header.run_id), []).append(attempt)
        for made in by_run.values():
            attempts += len(made)
            costs.append(sum(_pico_usd(attempt) for attempt in made))
            durations.append(sum(attempt.metrics.cost.duration_ms for attempt in made))
            floors += any(not _cost_is_complete(attempt) for attempt in made)
            segments.append(sum(attempt.metrics.ending.segments for attempt in made))
            lower_bounds += any(not attempt.metrics.ending.timing_complete for attempt in made)
    return CostLedger(
        cell.arm.name,
        cell.stratum,
        len(costs),
        attempts,
        sum(costs),
        floors,
        _spread(costs),
        _spread(durations),
        lower_bounds,
        _spread(segments),
    )


# --- Clusters ----------------------------------------------------------------------------


def _scenario_clusters(cell: Cell, measure: Measure) -> list[tuple[ScenarioId, tuple[int, int]]]:
    """Each scenario of ``cell`` with a run in the measure's scope, and its counts pooled over
    those runs."""
    clusters: list[tuple[ScenarioId, tuple[int, int]]] = []
    for runs in cell.scenarios:
        in_scope = [counts for run in runs.counted if (counts := measure.of(run)) is not None]
        if in_scope:
            pooled = (sum(n for n, _ in in_scope), sum(d for _, d in in_scope))
            clusters.append((runs.scenario_id, pooled))
    return clusters


def _clusters(cell: Cell, measure: Measure) -> list[tuple[Tier, tuple[int, int]]]:
    tiers = {runs.scenario_id: runs.tier for runs in cell.scenarios}
    return [(tiers[scenario], counts) for scenario, counts in _scenario_clusters(cell, measure)]


def _by_tier[T](held: list[tuple[Tier, T]]) -> list[list[T]]:
    """``held`` grouped by tier, in the tiers' order: the strata a resample is drawn within."""
    return [[value for tier, value in held if tier is each] for each in Tier]


def _as_cluster(counts: tuple[int, int]) -> Cluster:
    return (int(counts[0]), int(counts[1]))


def _ratio(clusters: list[Cluster]) -> float | None:
    denominator = sum(d for _, d in clusters)
    return sum(n for n, _ in clusters) / denominator if denominator else None


def _names(stratum: Stratum) -> tuple[str, str]:
    return (stratum.kind.value, stratum.name)


def _resolved(
    result: BootstrapInterval | Unresolved,
) -> tuple[BootstrapInterval | None, Unresolved | None]:
    """A bootstrap's result as the two fields an estimate holds, exactly one of them set."""
    if isinstance(result, Unresolved):
        return None, result
    return result, None


# --- Checks ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Trials:
    """One scenario's runs under one reading of a check: ``passes`` of ``of`` trials, from
    ``runs`` runs of which the check did not apply to ``not_checked``; ``made`` runs were
    made in all, the ones with no counted attempt included, and ``intended`` is the plan's
    number."""

    passes: int
    of: int
    runs: int
    not_checked: int
    made: int
    intended: int

    @property
    def fraction(self) -> float:
        return self.passes / self.of if self.of else 0.0

    @property
    def single(self) -> bool:
        """Whether the scenario is one yes-or-no trial: one trial, where at most one run was
        made and at most one intended, the one intended run never made that counts as not
        passed being the other way to be one. A run made and left out of the trials, the
        check not applying to it or its attempt history holding a gap, is still a repeat,
        and so is an intended repeat that was never made: the scenario is not a single
        trial."""
        return self.of == 1 and self.made <= 1 and self.intended <= 1


def _trials(runs: ScenarioRuns, check: Check, reading: Reading, plan: Preregistered) -> _Trials:
    answers = [check.of(run) for run in runs.counted]
    passes = sum(answer is True for answer in answers)
    not_checked = sum(answer is None for answer in answers)
    made = len(runs.histories)
    if reading is Reading.CONDITIONAL:
        of = len(answers) - not_checked
        return _Trials(passes, of, len(answers), not_checked, made, plan.intended_repeats)
    missed = runs.missing if plan.missing_repeat is MissingRepeat.NOT_PASSED else 0
    # A run made whose attempt history has a gap has no counted attempt: it did not pass
    # end to end whatever the missing-run rule says, being made and not missing.
    of = len(answers) + missed + runs.unverifiable
    return _Trials(passes, of, len(answers), not_checked, made, plan.intended_repeats)


def _over_one_denominator(trials: list[_Trials]) -> list[Cluster]:
    """Each scenario's pass fraction as whole counts over one denominator shared by all of
    them, so that the ratio of the clusters' sums is the mean pass fraction and the
    bootstrap's arithmetic is exact. Every one of ``trials`` has at least one trial."""
    shared = lcm(*(each.of for each in trials)) if trials else 1
    return [(each.passes * (shared // each.of), shared) for each in trials]


def _paired_over_one_denominator(
    paired: list[tuple[Tier, _Trials, _Trials]],
) -> list[tuple[Tier, tuple[Cluster, Cluster]]]:
    """The paired scenarios' pass fractions, both systems' over one shared denominator."""
    exact = _over_one_denominator([each for _, mine, yours in paired for each in (mine, yours)])
    return [
        (tier, (exact[2 * position], exact[2 * position + 1]))
        for position, (tier, _, _) in enumerate(paired)
    ]


def _require_paired(first: Cell, second: Cell) -> None:
    if first.stratum != second.stratum:
        raise ValueError(
            f"a comparison is within one stratum, got {first.stratum.name} and "
            f"{second.stratum.name}"
        )
    if first.arm.assigned != second.arm.assigned:
        raise ValueError(
            "a comparison is paired on the assigned condition; the two arms were assigned "
            "different ones"
        )
    same_system = first.arm.system == second.arm.system
    same_level = first.arm.level == second.arm.level
    if same_system and same_level:
        raise ValueError(
            "a comparison is between two systems, or between two levels of one; both cells "
            "are one arm's"
        )
    if not same_system and not same_level:
        raise ValueError(
            "a comparison is between two systems at one corpus level, or one system at two; "
            "the two arms differ in both"
        )


# --- Cost --------------------------------------------------------------------------------


def _pico_usd(attempt: Evaluation) -> int:
    cost = attempt.metrics.cost.cost
    return 0 if cost is None else cost.pico_usd


def _cost_is_complete(attempt: Evaluation) -> bool:
    """Whether the attempt's recomputed cost is a total: every possible send priced in
    full, or no possible send at all (no model called, or every request refused before it
    was sent)."""
    check = attempt.metrics.cost
    if check.cost is None:
        return check.possible_sends == 0
    return check.cost.complete


def _spread(values: list[int]) -> Spread | None:
    if not values:
        return None
    return Spread(float(median(values)), min(values), max(values))


__all__ = [
    "Check",
    "CheckComparison",
    "CheckEstimate",
    "CostLedger",
    "RatioComparison",
    "RatioEstimate",
    "Reading",
    "Spread",
    "compare_check",
    "compare_ratio",
    "cost_ledger",
    "estimate_check",
    "estimate_ratio",
    "scenario_passes",
]
