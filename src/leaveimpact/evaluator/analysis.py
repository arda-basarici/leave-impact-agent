"""The registered analysis: every table the preregistration names, computed from a set of
evaluated runs in one pure pass.

The registration says what is reported and the tables say how each number is computed;
this module is the reading of the one through the other (the investigator milestone's
sixth build step, rulings 2, 4 and 6), so that what an evaluation artifact holds is what
was registered and nothing chosen after the runs were seen. Nothing here is stored or
printed; the artifact and its codec are a later module's.

Per scenario set, the full set and the primary one:

- every arm, at the whole, each tier and each class: the accounting, the attempt summary
  and the cost ledger. An arm under an answer-quality condition also carries the
  registered checks in the registered readings and every row of every registered
  measure: the answer side over all claims and per claim type, grounding and citations
  over graded and over limited runs apart, source discipline and retrieval. An arm under
  a degraded-condition assignment carries the
  degraded table instead: there is no claim-level answer to score it against. An arm that
  arrived without being registered is described like a degraded one, never scored.
- the primary comparisons registered for the set, and the descriptive product. A
  comparison is made on a measure's leading row, and only on the measures the
  registration lists for comparison; the rest are reported per arm. A
  comparison one of whose arms cannot be built, its system's variant still pending, is
  kept and says so; it is never dropped, since a missing row would read as a smaller plan.
- the repeat-consistency diagnostic on each primary check, when the plan repeats runs.

The primary set exists once the development scenarios are registered; until then the set
is reported as unavailable with the reason, the comparisons registered on it are kept
with that reason, and the full set stands alone.

A system's normal and outage arms are side by side here and never differenced: their
oracles differ, so a difference between them would compare two questions.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from leaveimpact.core.enums import Source
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.ids import ScenarioId
from leaveimpact.core.registration import (
    Pending,
    PrimaryComparison,
    RegisteredArm,
    Registration,
    ReportingScope,
    ScenarioSetName,
    StratumLevel,
    condition_id,
)
from leaveimpact.core.run_record import System, SystemKind
from leaveimpact.evaluator.cells import (
    Accounting,
    Arm,
    AttemptSummary,
    Cell,
    Preregistered,
    Stratum,
    StratumKind,
    accounting_of,
    arms,
    attempt_summary_of,
    cells_of,
    within,
)
from leaveimpact.evaluator.diagnostics import (
    DegradedRow,
    RepeatConsistency,
    degraded_table,
    repeat_consistency,
)
from leaveimpact.evaluator.registered import (
    preregistered,
    registered_check,
    registered_measures,
    scenario_set,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.tables import (
    CheckComparison,
    CheckEstimate,
    CostLedger,
    RatioComparison,
    RatioEstimate,
    Reading,
    compare_check,
    compare_ratio,
    cost_ledger,
    estimate_check,
    estimate_ratio,
)
from leaveimpact.evaluator.trace_metrics import Evaluation


@dataclass(frozen=True, slots=True)
class CellAnalysis:
    """One arm at one stratum. ``checks`` and ``measures`` are set for an answer-quality
    arm, ``degraded`` for any other, and exactly one side is."""

    stratum: Stratum
    accounting: Accounting
    attempts: AttemptSummary
    cost: CostLedger
    checks: tuple[CheckEstimate, ...] | None
    measures: tuple[RatioEstimate, ...] | None
    degraded: tuple[DegradedRow, ...] | None


@dataclass(frozen=True, slots=True)
class ArmAnalysis:
    """One system under one assigned condition: the condition by its registered
    identifier, how the registration reports it (``None`` when the arm is not registered),
    its cells, and the repeat-consistency diagnostic on each primary check where the plan
    repeats runs and the arm is scored."""

    system: System
    condition: str
    reporting: ReportingScope | None
    cells: tuple[CellAnalysis, ...]
    consistency: tuple[RepeatConsistency, ...]


@dataclass(frozen=True, slots=True)
class PrimaryResult:
    """One registered primary comparison: its result at each stratum of the registered
    level, one for the whole, or why it could not be computed."""

    registered: PrimaryComparison
    results: tuple[CheckComparison, ...]
    unavailable: str | None


@dataclass(frozen=True, slots=True)
class DescriptiveResult:
    """The descriptive comparisons of one pair of systems under one condition, at every
    registered stratum: the checks in the registered readings and the measures over all
    claims. ``unavailable`` says why when an arm of the pair cannot be built."""

    systems: tuple[SystemKind, SystemKind]
    condition: str
    checks: tuple[CheckComparison, ...]
    measures: tuple[RatioComparison, ...]
    unavailable: str | None


@dataclass(frozen=True, slots=True)
class SetAnalysis:
    """Everything registered over one scenario set, or why the set could not be cut."""

    name: ScenarioSetName
    scenarios: tuple[ScenarioId, ...]
    arms: tuple[ArmAnalysis, ...]
    primary: tuple[PrimaryResult, ...]
    descriptive: tuple[DescriptiveResult, ...]
    unavailable: str | None


@dataclass(frozen=True, slots=True)
class Analysis:
    """The registered analysis of a set of runs: the plan it was cut under, the registered
    arms that could not be built, and each scenario set, the full one first."""

    plan: Preregistered
    pending_arms: tuple[RegisteredArm, ...]
    sets: tuple[SetAnalysis, ...]


def analyse(
    world: SealedWorld, evaluations: Iterable[Evaluation], registration: Registration
) -> Analysis:
    """What ``registration`` reports of ``evaluations`` against ``world``.

    Raises ``ValueError`` for what the projection and the scenario sets refuse: a name
    this evaluator does not hold, no arm that can be built, a registered development list
    that does not fit the world.
    """
    projection = preregistered(registration)
    plan = projection.plan
    built = arms(world, evaluations, plan)
    sets: list[SetAnalysis] = []
    for name in (ScenarioSetName.FULL, ScenarioSetName.PRIMARY):
        development = registration.scenario_sets.development
        if name is ScenarioSetName.PRIMARY and isinstance(development, Pending):
            reason = f"the development scenarios are pending ({development.awaiting})"
            kept = tuple(
                PrimaryResult(comparison, (), reason)
                for comparison in registration.statistics.primary
                if comparison.scenario_set is name
            )
            sets.append(SetAnalysis(name, (), (), kept, (), reason))
            continue
        scenarios = scenario_set(world, registration, name)
        whole = name is ScenarioSetName.FULL
        cut = tuple(arm if whole else within(arm, scenarios) for arm in built)
        sets.append(_set_analysis(name, scenarios, cut, registration, plan))
    return Analysis(plan, projection.pending_arms, tuple(sets))


def _set_analysis(
    name: ScenarioSetName,
    scenarios: tuple[ScenarioId, ...],
    built: tuple[Arm, ...],
    registration: Registration,
    plan: Preregistered,
) -> SetAnalysis:
    statistics = registration.statistics
    by_arm = {
        (arm.system.kind, _condition_of(arm.assigned)): arm for arm in built if arm.registered
    }
    primary = tuple(
        _primary(comparison, by_arm, plan)
        for comparison in statistics.primary
        if comparison.scenario_set is name
    )
    descriptive: tuple[DescriptiveResult, ...] = ()
    if name in statistics.descriptive.scenario_sets:
        descriptive = tuple(
            _descriptive(pair, condition, by_arm, registration, plan)
            for pair in statistics.descriptive.pairs
            for condition in statistics.descriptive.conditions
        )
    return SetAnalysis(
        name,
        scenarios,
        tuple(_arm_analysis(arm, registration, plan) for arm in built),
        primary,
        descriptive,
        None,
    )


def _condition_of(assigned: RunCondition) -> str:
    return condition_id(frozenset(Source) - assigned.reachable)


def _arm_analysis(arm: Arm, registration: Registration, plan: Preregistered) -> ArmAnalysis:
    condition = _condition_of(arm.assigned)
    registered = registration.outage.condition(condition) if arm.registered else None
    reporting = registered.reporting if registered is not None else None
    scored = reporting is ReportingScope.ANSWER_QUALITY
    statistics = registration.statistics
    cells = tuple(_cell_analysis(cell, scored, registration, plan) for cell in cells_of(arm))
    consistency: list[RepeatConsistency] = []
    if scored:
        for name in dict.fromkeys(comparison.check for comparison in statistics.primary):
            found = repeat_consistency(cells_of(arm)[0], registered_check(name), plan)
            if found is not None:
                consistency.append(found)
    return ArmAnalysis(arm.system, condition, reporting, cells, tuple(consistency))


def _cell_analysis(
    cell: Cell, scored: bool, registration: Registration, plan: Preregistered
) -> CellAnalysis:
    statistics = registration.statistics
    checks: tuple[CheckEstimate, ...] | None = None
    measures: tuple[RatioEstimate, ...] | None = None
    degraded: tuple[DegradedRow, ...] | None = None
    if scored:
        checks = tuple(
            estimate_check(cell, registered_check(name), reading, plan)
            for name in statistics.checks
            for reading in Reading
        )
        measures = tuple(
            estimate_ratio(cell, measure, plan)
            for name in statistics.measures
            for measure in registered_measures(name)
        )
    else:
        degraded = degraded_table(cell)
    return CellAnalysis(
        cell.stratum,
        accounting_of(cell, plan),
        attempt_summary_of(cell),
        cost_ledger(cell),
        checks,
        measures,
        degraded,
    )


def _strata(arm: Arm, levels: Iterable[StratumLevel]) -> dict[Stratum, Cell]:
    """The cells of ``arm`` at ``levels``: the whole, and each tier."""
    kinds = {
        StratumLevel.OVERALL: StratumKind.OVERALL,
        StratumLevel.TIER: StratumKind.TIER,
    }
    wanted = {kinds[level] for level in levels}
    return {cell.stratum: cell for cell in cells_of(arm) if cell.stratum.kind in wanted}


def _pending_reason(
    systems: tuple[SystemKind, SystemKind],
    condition: str,
    by_arm: dict[tuple[SystemKind, str], Arm],
) -> str | None:
    absent = [system.value for system in systems if (system, condition) not in by_arm]
    if not absent:
        return None
    return f"no arm could be built for {' and '.join(absent)} under {condition}"


def _primary(
    comparison: PrimaryComparison,
    by_arm: dict[tuple[SystemKind, str], Arm],
    plan: Preregistered,
) -> PrimaryResult:
    reason = _pending_reason(comparison.systems, comparison.condition, by_arm)
    if reason is not None:
        return PrimaryResult(comparison, (), reason)
    first, second = (
        _strata(by_arm[system, comparison.condition], (comparison.stratum,))
        for system in comparison.systems
    )
    check = registered_check(comparison.check)
    reading = Reading(comparison.reading.value)
    results = tuple(
        compare_check(first[stratum], second[stratum], check, reading, plan)
        for stratum in first
        if stratum in second
    )
    return PrimaryResult(comparison, results, None)


def _descriptive(
    systems: tuple[SystemKind, SystemKind],
    condition: str,
    by_arm: dict[tuple[SystemKind, str], Arm],
    registration: Registration,
    plan: Preregistered,
) -> DescriptiveResult:
    reason = _pending_reason(systems, condition, by_arm)
    if reason is not None:
        return DescriptiveResult(systems, condition, (), (), reason)
    registered = registration.statistics.descriptive
    first, second = (_strata(by_arm[system, condition], registered.strata) for system in systems)
    shared = [stratum for stratum in first if stratum in second]
    checks = tuple(
        compare_check(
            first[stratum],
            second[stratum],
            registered_check(name),
            Reading(reading.value),
            plan,
        )
        for stratum in shared
        for name in registered.checks
        for reading in registered.readings
    )
    measures = tuple(
        compare_ratio(first[stratum], second[stratum], registered_measures(name)[0], plan)
        for stratum in shared
        for name in registered.measures
    )
    return DescriptiveResult(systems, condition, checks, measures, None)


__all__ = [
    "Analysis",
    "ArmAnalysis",
    "CellAnalysis",
    "DescriptiveResult",
    "PrimaryResult",
    "SetAnalysis",
    "analyse",
]
