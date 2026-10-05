"""The registered analysis: every table the preregistration names, computed from a set of
evaluated runs in one pure pass.

The registration says what is reported and the tables say how each number is computed;
this module is the reading of the one through the other (the investigator milestone's
sixth build step, rulings 2, 4 and 6; the contract step's rulings on the registration), so
that what an evaluation artifact holds is what was registered and nothing chosen after the
runs were seen. Nothing here is stored or printed; the artifact and its codec are another
module's.

Over every scenario of the world, there being one scenario set: no scenario of the
measured world is tuned on, so none is held apart.

- every arm, a system under a condition at a corpus level, at the whole, each tier and
  each class: the accounting, the attempt summary and the cost ledger. An arm under an
  answer-quality condition also carries the registered checks in both readings and every
  row of every registered measure: the answer side over all claims and per claim type,
  grounding and citations over graded and over limited runs apart, source discipline and
  retrieval. An arm under a degraded-condition assignment carries the degraded table
  instead: there is no claim-level answer to score it against. An arm that arrived without
  being registered is described like a degraded one, never scored.
- the primary comparison, the one a claim is made from, and the secondary ones: each the
  overall contrast with the breakdowns named in advance beside it.
- the descriptive comparisons: every registered pair at every registered place. A
  comparison is made on a measure's leading row, and only on the measures the registration
  lists for comparison; the rest are reported per arm.
- the level contrasts: one system against itself across two corpus levels.
- the repeat-consistency diagnostic on the primary check, when the plan repeats runs.
- the headroom at each place the reference system runs under an answer-quality condition,
  and the incidents: the scenarios where a source contradicted itself in some run, the
  runs that are out of the tables read for it like the ones that are in.
- the mechanism measure: what it is pending on, until it is resolved; then, for every
  scored arm of a system that states facts, the four stages at the whole and at each tier
  with the stages by predicate and the supporting detail, and the stages contrasted on the
  pairs the registration already compares, the primary's, each secondary's and each level
  contrast's, at the strata each of those names. It is contrasted nowhere else: the
  descriptive product has no registered reading of a stage.

Nothing registered is dropped. A comparison one of whose arms could not be built, its
system still pending or its conditional group not decided as run, is kept and says so,
since a missing row would read as a smaller plan; so are a level contrast and a place's
headroom.

A system's normal and outage arms are side by side here and never differenced: their
oracles differ, so a difference between them would compare two questions. Two levels of one
system under one condition are differenced, the answers being the same at both.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.enums import Source
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.ids import ScenarioId
from leaveimpact.core.registration import (
    Comparison,
    LevelContrast,
    MechanismMeasure,
    Registration,
    ReportingScope,
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
)
from leaveimpact.evaluator.diagnostics import (
    DegradedRow,
    RepeatConsistency,
    degraded_table,
    repeat_consistency,
)
from leaveimpact.evaluator.headroom import Headroom, headroom_at
from leaveimpact.evaluator.incidents import Incident, incident_scenarios, incidents_of
from leaveimpact.evaluator.mechanism import (
    STAGE_MEASURES,
    STAGE_MEASURES_BY_PREDICATE,
    FactDetail,
    fact_detail,
)
from leaveimpact.evaluator.registered import (
    Unbuilt,
    mechanism_pending,
    preregistered,
    registered_check,
    registered_measures,
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

_ArmKey = tuple[SystemKind, str, str]
"""A registered arm by its system's kind, its condition's identifier and its level."""


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
    """One system under one assigned condition at one corpus level: the condition by its
    registered identifier, how the registration reports it (``None`` when the arm is not
    registered), its cells, and the repeat-consistency diagnostic on the primary check
    where the plan repeats runs and the arm is scored."""

    system: System
    condition: str
    level: str
    reporting: ReportingScope | None
    cells: tuple[CellAnalysis, ...]
    consistency: tuple[RepeatConsistency, ...]


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """One registered comparison between two systems: the overall contrast, which is the
    comparison, the registered breakdowns beside it, or why it could not be computed."""

    registered: Comparison
    overall: CheckComparison | None
    breakdowns: tuple[CheckComparison, ...]
    unavailable: str | None


@dataclass(frozen=True, slots=True)
class LevelContrastResult:
    """One registered contrast of a system with itself across two corpus levels: the
    overall contrast, the registered breakdowns, or why it could not be computed."""

    registered: LevelContrast
    overall: CheckComparison | None
    breakdowns: tuple[CheckComparison, ...]
    unavailable: str | None


@dataclass(frozen=True, slots=True)
class DescriptiveResult:
    """The descriptive comparisons of one pair of systems at one place, at every registered
    stratum: the checks in the registered readings and the measures over all claims.
    ``unavailable`` says why when an arm of the pair could not be built."""

    systems: tuple[SystemKind, SystemKind]
    condition: str
    level: str
    checks: tuple[CheckComparison, ...]
    measures: tuple[RatioComparison, ...]
    unavailable: str | None


@dataclass(frozen=True, slots=True)
class ArmRef:
    """A registered arm by its system's kind, its condition's identifier and its level."""

    system: SystemKind
    condition: str
    level: str


@dataclass(frozen=True, slots=True)
class MechanismArm:
    """The mechanism measure in one arm: the four stages at the whole and at each tier, a
    stratum's four together in the funnel's order; the stages by predicate at the whole; and
    the supporting detail at the whole and at each tier."""

    system: System
    condition: str
    level: str
    stages: tuple[RatioEstimate, ...]
    by_predicate: tuple[RatioEstimate, ...]
    detail: tuple[FactDetail, ...]


class ContrastOf(StrEnum):
    """Which registered comparison a contrast of the stages rides on; a member is the wire
    format."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    LEVEL_CONTRAST = "level_contrast"


@dataclass(frozen=True, slots=True)
class MechanismContrast:
    """The four stages in one arm less another, on a pair the registration compares: at the
    whole and at each registered breakdown, a stratum's four together. ``unavailable`` says
    why when an arm of the pair could not be built."""

    of: ContrastOf
    first: ArmRef
    second: ArmRef
    stages: tuple[RatioComparison, ...]
    unavailable: str | None


@dataclass(frozen=True, slots=True)
class MechanismAnalysis:
    """The mechanism measure as registered, by its name and its stages, with every arm it
    applies to and every contrast of it. It explains where a system gained or lost on the
    way to its report and carries no claim of its own."""

    name: str
    stages: tuple[str, ...]
    arms: tuple[MechanismArm, ...]
    contrasts: tuple[MechanismContrast, ...]


@dataclass(frozen=True, slots=True)
class Analysis:
    """The registered analysis of a set of runs: the plan it was cut under, the registered
    cells that plan does not hold, the world's scenarios, and everything registered over
    them. ``mechanism_pending`` is what the mechanism measure waits on, ``None`` once it
    is resolved, and ``mechanism`` is set exactly then."""

    plan: Preregistered
    unbuilt: tuple[Unbuilt, ...]
    scenarios: tuple[ScenarioId, ...]
    arms: tuple[ArmAnalysis, ...]
    primary: ComparisonResult
    secondary: tuple[ComparisonResult, ...]
    descriptive: tuple[DescriptiveResult, ...]
    level_contrasts: tuple[LevelContrastResult, ...]
    mechanism_pending: str | None
    mechanism: MechanismAnalysis | None
    headroom: tuple[Headroom, ...]
    incidents: tuple[Incident, ...]


def analyse(
    world: SealedWorld,
    evaluations: Iterable[Evaluation],
    registration: Registration,
    *,
    outside: Sequence[tuple[str, Evaluation]] = (),
) -> Analysis:
    """What ``registration`` reports of ``evaluations`` against ``world``.

    ``outside`` are the evaluated exports of this world that are out of the tables, each
    with its key in the store. They enter no arm and no estimate; the incidents are read
    from them as from every other trace.

    Raises ``ValueError`` for what the projection refuses: a name this evaluator does not
    hold, a prefetch or an anchor table that is not this code's, no cell that can be built.
    """
    projection = preregistered(registration)
    plan = projection.plan
    built = arms(world, evaluations, plan)
    incidents = incidents_of(built, outside)
    reading = _Reading(
        registration,
        plan,
        {
            (arm.system.kind, _condition_of(arm.assigned), arm.level): arm
            for arm in built
            if arm.registered
        },
        {unbuilt.cell.place: unbuilt for unbuilt in projection.unbuilt},
        incident_scenarios(incidents),
    )
    statistics = registration.statistics
    pending = mechanism_pending(registration)
    return Analysis(
        plan=plan,
        unbuilt=projection.unbuilt,
        scenarios=tuple(scenario.spec.id for scenario in world.scenarios),
        arms=tuple(_arm_analysis(arm, registration, plan) for arm in built),
        primary=reading.comparison(statistics.primary),
        secondary=tuple(reading.comparison(each) for each in statistics.secondary),
        descriptive=tuple(
            reading.descriptive(pair, place.condition, place.level)
            for place in statistics.descriptive.places
            for pair in statistics.descriptive.pairs
        ),
        level_contrasts=tuple(reading.level_contrast(each) for each in statistics.level_contrasts),
        mechanism_pending=pending,
        mechanism=reading.mechanism() if pending is None else None,
        headroom=reading.headroom(),
        incidents=incidents,
    )


def _condition_of(assigned: RunCondition) -> str:
    return condition_id(frozenset(Source) - assigned.reachable)


def _arm_analysis(arm: Arm, registration: Registration, plan: Preregistered) -> ArmAnalysis:
    condition = _condition_of(arm.assigned)
    registered = registration.outage.condition(condition) if arm.registered else None
    reporting = registered.reporting if registered is not None else None
    scored = reporting is ReportingScope.ANSWER_QUALITY
    cells = tuple(_cell_analysis(cell, scored, registration, plan) for cell in cells_of(arm))
    consistency: tuple[RepeatConsistency, ...] = ()
    if scored:
        check = registered_check(registration.statistics.primary.check)
        found = repeat_consistency(cells_of(arm)[0], check, plan)
        consistency = () if found is None else (found,)
    return ArmAnalysis(arm.system, condition, arm.level, reporting, cells, consistency)


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


@dataclass(frozen=True, slots=True)
class _Reading:
    """What every comparison is read from: the registration, the plan, the registered arms
    that were built, the registered cells that were not, and the scenarios with an incident."""

    registration: Registration
    plan: Preregistered
    built: dict[_ArmKey, Arm]
    unbuilt: dict[_ArmKey, Unbuilt]
    incidents: frozenset[ScenarioId]

    def absent(self, *keys: _ArmKey) -> str | None:
        """Why a comparison over the arms ``keys`` cannot be made, naming each arm that
        could not be built with what the registration says of it; ``None`` when all were."""
        missing = [
            f"{system.value} under {condition} at {level}"
            + (
                f" ({self.unbuilt[system, condition, level].why.value}: "
                f"{self.unbuilt[system, condition, level].detail})"
                if (system, condition, level) in self.unbuilt
                else ""
            )
            for system, condition, level in keys
            if (system, condition, level) not in self.built
        ]
        return f"no arm could be built for {' and '.join(missing)}" if missing else None

    def contrast(
        self,
        first: _ArmKey,
        second: _ArmKey,
        check: str,
        reading: Reading,
        breakdowns: tuple[StratumLevel, ...],
    ) -> tuple[CheckComparison | None, tuple[CheckComparison, ...]]:
        """``check`` in the arm ``first`` less the arm ``second``: at the whole, and at each
        stratum of ``breakdowns`` both arms hold."""
        levels = (StratumLevel.OVERALL, *breakdowns)
        ours, theirs = (_strata(self.built[key], levels) for key in (first, second))
        results = [
            compare_check(
                ours[stratum],
                theirs[stratum],
                registered_check(check),
                reading,
                self.plan,
                incidents=self.incidents,
            )
            for stratum in ours
            if stratum in theirs
        ]
        overall = [each for each in results if each.stratum.kind is StratumKind.OVERALL]
        rest = tuple(each for each in results if each.stratum.kind is not StratumKind.OVERALL)
        return (overall[0] if overall else None), rest

    def comparison(self, registered: Comparison) -> ComparisonResult:
        first, second = (
            (system, registered.condition, registered.level) for system in registered.systems
        )
        reason = self.absent(first, second)
        if reason is not None:
            return ComparisonResult(registered, None, (), reason)
        overall, breakdowns = self.contrast(
            first,
            second,
            registered.check,
            Reading(registered.reading.value),
            registered.breakdowns,
        )
        return ComparisonResult(registered, overall, breakdowns, None)

    def level_contrast(self, registered: LevelContrast) -> LevelContrastResult:
        first, second = (
            (registered.system, registered.condition, level) for level in registered.levels
        )
        reason = self.absent(first, second)
        if reason is not None:
            return LevelContrastResult(registered, None, (), reason)
        overall, breakdowns = self.contrast(
            first,
            second,
            registered.check,
            Reading(registered.reading.value),
            registered.breakdowns,
        )
        return LevelContrastResult(registered, overall, breakdowns, None)

    def descriptive(
        self, systems: tuple[SystemKind, SystemKind], condition: str, level: str
    ) -> DescriptiveResult:
        first, second = ((system, condition, level) for system in systems)
        reason = self.absent(first, second)
        if reason is not None:
            return DescriptiveResult(systems, condition, level, (), (), reason)
        registered = self.registration.statistics.descriptive
        ours, theirs = (_strata(self.built[key], registered.strata) for key in (first, second))
        shared = [stratum for stratum in ours if stratum in theirs]
        checks = tuple(
            compare_check(
                ours[stratum],
                theirs[stratum],
                registered_check(name),
                Reading(reading.value),
                self.plan,
                incidents=self.incidents,
            )
            for stratum in shared
            for name in registered.checks
            for reading in registered.readings
        )
        measures = tuple(
            compare_ratio(
                ours[stratum],
                theirs[stratum],
                registered_measures(name)[0],
                self.plan,
                incidents=self.incidents,
            )
            for stratum in shared
            for name in registered.measures
        )
        return DescriptiveResult(systems, condition, level, checks, measures, None)

    def mechanism(self) -> MechanismAnalysis:
        """The resolved mechanism measure: per arm, and contrasted on the registered pairs."""
        registered = self.registration.statistics.mechanism
        assert isinstance(registered, MechanismMeasure)
        statistics = self.registration.statistics
        contrasts: list[MechanismContrast] = []
        for of, compared in (
            (ContrastOf.PRIMARY, (statistics.primary,)),
            (ContrastOf.SECONDARY, statistics.secondary),
        ):
            for each in compared:
                first, second = ((system, each.condition, each.level) for system in each.systems)
                contrasts.append(self._stage_contrast(of, first, second, each.breakdowns))
        for contrast in statistics.level_contrasts:
            first, second = (
                (contrast.system, contrast.condition, level) for level in contrast.levels
            )
            contrasts.append(
                self._stage_contrast(ContrastOf.LEVEL_CONTRAST, first, second, contrast.breakdowns)
            )
        return MechanismAnalysis(
            registered.name,
            registered.stages,
            tuple(
                self._mechanism_arm(key, arm)
                for key, arm in self.built.items()
                if self._states_and_is_scored(key)
            ),
            tuple(contrasts),
        )

    def _states_and_is_scored(self, key: _ArmKey) -> bool:
        """Whether the mechanism measure applies to the arm ``key`` names: a system that
        states facts, under a condition whose answers are scored."""
        system, condition, _ = key
        registered = self.registration.outage.condition(condition)
        return (
            system is not SystemKind.RULES_ONLY
            and registered is not None
            and registered.reporting is ReportingScope.ANSWER_QUALITY
        )

    def _mechanism_arm(self, key: _ArmKey, arm: Arm) -> MechanismArm:
        strata = _strata(arm, (StratumLevel.OVERALL, StratumLevel.TIER))
        whole = cells_of(arm)[0]
        return MechanismArm(
            arm.system,
            key[1],
            arm.level,
            tuple(
                estimate_ratio(cell, measure, self.plan)
                for cell in strata.values()
                for measure in STAGE_MEASURES
            ),
            tuple(
                estimate_ratio(whole, measure, self.plan) for measure in STAGE_MEASURES_BY_PREDICATE
            ),
            tuple(fact_detail(cell) for cell in strata.values()),
        )

    def _stage_contrast(
        self,
        of: ContrastOf,
        first: _ArmKey,
        second: _ArmKey,
        breakdowns: tuple[StratumLevel, ...],
    ) -> MechanismContrast:
        reason = self.absent(first, second)
        if reason is not None:
            return MechanismContrast(of, ArmRef(*first), ArmRef(*second), (), reason)
        levels = (StratumLevel.OVERALL, *breakdowns)
        ours, theirs = (_strata(self.built[key], levels) for key in (first, second))
        return MechanismContrast(
            of,
            ArmRef(*first),
            ArmRef(*second),
            tuple(
                compare_ratio(
                    ours[stratum], theirs[stratum], measure, self.plan, incidents=self.incidents
                )
                for stratum in ours
                if stratum in theirs
                for measure in STAGE_MEASURES
            ),
            None,
        )

    def headroom(self) -> tuple[Headroom, ...]:
        """The headroom at each place the reference system has a registered cell under an
        answer-quality condition, in the registration's order."""
        procedure = self.registration.statistics.headroom
        check = registered_check(procedure.check)
        reading = Reading(procedure.reading.value)
        found: list[Headroom] = []
        for cell in self.registration.cells:
            condition = self.registration.outage.condition(cell.condition)
            assert condition is not None, cell
            if (
                cell.system is not procedure.reference
                or condition.reporting is not ReportingScope.ANSWER_QUALITY
            ):
                continue
            arm = self.built.get(cell.place)
            if arm is None:
                reason = self.absent(cell.place)
                found.append(Headroom(cell.condition, cell.level, None, None, reason))
                continue
            whole = cells_of(arm)[0]
            found.append(
                headroom_at(cell.condition, cell.level, whole, check, reading, self.plan)
            )
        return tuple(found)


__all__ = [
    "Analysis",
    "ArmAnalysis",
    "ArmRef",
    "CellAnalysis",
    "ComparisonResult",
    "ContrastOf",
    "DescriptiveResult",
    "LevelContrastResult",
    "MechanismAnalysis",
    "MechanismArm",
    "MechanismContrast",
    "analyse",
]
