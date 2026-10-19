"""The public results schema: what a results page may show of a measurement, as plain data.

Every type here is a projection of the evaluator's analysis over a narrower population,
copied as recorded and never recomputed: an estimate keeps its counts and its interval or
the reason the bootstrap resolved none; a cost keeps its floors; a comparison keeps its
two-by-two table; a null stays null. Three statistical families carry every figure (a
yes-or-no check estimated in a cell, a ratio estimated in a cell, a paired comparison of
two arms), so a new named statistic is a new row and never a new type. What the
projection leaves out is decided per field at the demo milestone's first build step (the
mapping in the step's forks file): the per-run listing, the scenario ids, the audit
counters a cell's accounting carries beyond what happened to its runs, the mechanism's
supporting fact tallies, the repeat-consistency diagnostic, and the sealed world objects'
digests and store version ids. The embargo covers two of those digests; the rest are
left out because a page has no use for them, and the artifact's own digest in the
provenance authenticates every figure that stays.

The file's format is its own, ``PUBLIC_RESULTS_FORMAT``, and moves apart from the artifact
format it was projected from, which the provenance records; the two change for different
reasons. Every kind of arm the evaluator writes has its place: an answer-quality arm
carries checks and measures, a degraded-condition arm the degraded table instead, a plan
with repeats the repeat-consistency rows, and a mechanism measure still pending is
written as pending, so a projection never has a hole where the artifact had a value.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "PUBLIC_RESULTS_FORMAT",
    "ArmRef",
    "BootstrapInterval",
    "Cell",
    "CellAccounting",
    "CellCost",
    "ChangedPath",
    "CheckComparison",
    "CheckEstimate",
    "ComparisonResult",
    "Coverage",
    "DegradedRow",
    "DescriptiveResult",
    "Disclosures",
    "Headroom",
    "LevelContrastResult",
    "Mechanism",
    "MechanismArm",
    "MechanismContrast",
    "NotRun",
    "Plan",
    "PlanArm",
    "Provenance",
    "PublicResults",
    "RatioComparison",
    "RatioEstimate",
    "RegisteredComparison",
    "RepeatConsistency",
    "RegisteredLevelContrast",
    "ResultArm",
    "Spread",
    "Stratum",
    "WilsonInterval",
]

PUBLIC_RESULTS_FORMAT = 1
"""The format of the public results file; bumped when a type here changes shape."""


@dataclass(frozen=True, slots=True)
class Stratum:
    """Where a figure was cut: the whole (``overall``), a tier, or a scenario class, by its
    kind and its name, as the evaluator writes them."""

    kind: str
    name: str


@dataclass(frozen=True, slots=True)
class WilsonInterval:
    """Wilson's interval for a pass count, at ``confidence``."""

    low: float
    high: float
    confidence: float


@dataclass(frozen=True, slots=True)
class BootstrapInterval:
    """A percentile interval from resampled clusters with everything that produced it: the
    seed of the interval's own stream (derived from the plan's seed and the estimate's
    names, resampling provenance and nothing the embargo covers), how many resamples were
    asked for and how many had a statistic, the quantile rule and the stratification."""

    low: float
    high: float
    confidence: float
    seed: int
    resamples: int
    valid: int
    quantile_rule: str
    stratification: str


@dataclass(frozen=True, slots=True)
class RatioEstimate:
    """A measure at a stratum: the sum of numerators over the sum of denominators across
    the ``scenarios`` in scope, ``empty`` of which had nothing to count; the interval, or
    the reason there is none. ``measure`` is the registered name."""

    measure: str
    stratum: Stratum
    numerator: int
    denominator: int
    scenarios: int
    empty: int
    interval: BootstrapInterval | None
    unresolved: str | None


@dataclass(frozen=True, slots=True)
class CheckEstimate:
    """A yes-or-no check at a stratum under one reading (``conditional`` over the runs it
    applies to, ``end_to_end`` over every intended run): ``passed`` of ``scenarios``, the
    runs behind them, how many were not checked, missing or unverifiable, and Wilson's
    interval when every scenario has one run, the bootstrap of the mean otherwise, or the
    reason neither resolved."""

    check: str
    stratum: Stratum
    reading: str
    passed: float
    scenarios: int
    runs: int
    not_checked: int
    missing: int
    unverifiable: int
    wilson: WilsonInterval | None
    bootstrap: BootstrapInterval | None
    unresolved: str | None


@dataclass(frozen=True, slots=True)
class Spread:
    """A median with the lowest and highest value it summarizes."""

    median: float
    low: int
    high: int


@dataclass(frozen=True, slots=True)
class CellCost:
    """What a cell cost, with no interval: the total in pico-dollars over every attempt,
    retries included; ``floors`` the runs whose cost is a lower bound (a send the provider
    reported no usage for, or one the embedded rates could not price); the per-run
    spread, the evidenced active time per run in milliseconds with the runs whose duration
    is a lower bound, and the segments per run."""

    runs: int
    attempts: int
    pico_usd: int
    floors: int
    per_run: Spread | None
    duration_ms: Spread | None
    lower_bound_durations: int
    segments: Spread | None


@dataclass(frozen=True, slots=True)
class CellAccounting:
    """What happened to the runs of a cell: ``intended`` by the plan, ``made``, the
    ``missing`` shortfall and the ``surplus`` beyond, every exported attempt, the runs
    graded, the structurally invalid reports among them, and the runs limited or excluded
    by reason with their counts. The evaluator's audit counters (its prefetch, membership,
    attribution and account findings) stay in the artifact."""

    scenarios: int
    intended: int
    made: int
    missing: int
    surplus: int
    attempts: int
    graded: int
    structurally_invalid: int
    limited: tuple[tuple[str, int], ...]
    excluded: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class DegradedRow:
    """How many counted runs of a cell under a degraded condition share one exposure,
    outcome, report state and replay state; ``reason`` is the outcome's own for a limited
    or an excluded run."""

    exposure: str
    outcome: str
    reason: str | None
    report: str
    replay: str
    runs: int


@dataclass(frozen=True, slots=True)
class Cell:
    """One arm at one stratum: its accounting, its cost, and either every registered check
    in both readings with every registered measure (an answer-quality arm) or the
    degraded table (an arm under a condition the oracle has no claim-level answer for);
    exactly one side is set."""

    stratum: Stratum
    accounting: CellAccounting
    cost: CellCost
    checks: tuple[CheckEstimate, ...] | None
    measures: tuple[RatioEstimate, ...] | None
    degraded: tuple[DegradedRow, ...] | None


@dataclass(frozen=True, slots=True)
class RepeatConsistency:
    """How a cell's scenarios fare across their repeats on one check: by whether their
    runs all pass, all fail or disagree, and the ones that cannot be classified; present
    only where the plan repeats runs."""

    check: str
    scenarios: int
    all_pass: int
    all_fail: int
    disagree: int
    incomplete: int


@dataclass(frozen=True, slots=True)
class ResultArm:
    """One system under one assigned condition at one corpus level, by the system's kind
    and variant, the condition's registered identifier and the level; how the
    registration reports it (``answer_quality`` or ``degraded_condition``, ``None`` for an
    arm it does not register); its cells at every stratum the evaluator cut; and the
    repeat-consistency rows where the plan repeats runs."""

    system: str
    variant: str
    condition: str
    level: str
    reporting: str | None
    cells: tuple[Cell, ...]
    consistency: tuple[RepeatConsistency, ...]


@dataclass(frozen=True, slots=True)
class RegisteredComparison:
    """A registered comparison between two systems as the registration states it: the
    check under a reading, at a condition and level, the systems in the order the
    difference is taken, and the breakdowns named in advance."""

    check: str
    reading: str
    condition: str
    level: str
    systems: tuple[str, str]
    breakdowns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RegisteredLevelContrast:
    """A registered contrast of one system with itself across two corpus levels, the
    first less the second, as the registration states it."""

    system: str
    check: str
    reading: str
    condition: str
    levels: tuple[str, str]
    breakdowns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CheckComparison:
    """Two arms on a check, paired on scenario at a stratum: the paired count and how many
    of the pairs carry an incident, each arm's pass fraction, the two-by-two table (both
    passed, the first only, the second only, neither) and the interval of the difference,
    or the reason there is none. The arms are named as the evaluator names them."""

    check: str
    first_arm: str
    second_arm: str
    stratum: Stratum
    reading: str
    paired: int
    paired_with_incident: int
    first: float | None
    second: float | None
    two_by_two: tuple[int, int, int, int] | None
    interval: BootstrapInterval | None
    unresolved: str | None


@dataclass(frozen=True, slots=True)
class RatioComparison:
    """Two arms on a measure, paired on scenario at a stratum: each arm's ratio and the
    interval of the difference, or the reason there is none."""

    measure: str
    first_arm: str
    second_arm: str
    stratum: Stratum
    paired: int
    paired_with_incident: int
    first: float | None
    second: float | None
    interval: BootstrapInterval | None
    unresolved: str | None


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """A registered comparison with its overall contrast, which is the comparison, the
    breakdowns beside it, or why it could not be computed."""

    registered: RegisteredComparison
    overall: CheckComparison | None
    breakdowns: tuple[CheckComparison, ...]
    unavailable: str | None


@dataclass(frozen=True, slots=True)
class LevelContrastResult:
    """A registered level contrast with its overall contrast, the breakdowns, or why it
    could not be computed."""

    registered: RegisteredLevelContrast
    overall: CheckComparison | None
    breakdowns: tuple[CheckComparison, ...]
    unavailable: str | None


@dataclass(frozen=True, slots=True)
class DescriptiveResult:
    """The descriptive comparisons of one pair of systems at one place, every registered
    stratum: the checks in both readings and the measures over all claims, from which no
    claim is made."""

    systems: tuple[str, str]
    condition: str
    level: str
    checks: tuple[CheckComparison, ...]
    measures: tuple[RatioComparison, ...]
    unavailable: str | None


@dataclass(frozen=True, slots=True)
class ArmRef:
    """A registered arm by its system's kind, its condition's identifier and its level."""

    system: str
    condition: str
    level: str


@dataclass(frozen=True, slots=True)
class MechanismArm:
    """The mechanism measure in one arm: the stages at every stratum, a stratum's stages
    together in the funnel's order, and the stages by predicate at the whole."""

    system: str
    variant: str
    condition: str
    level: str
    stages: tuple[RatioEstimate, ...]
    by_predicate: tuple[RatioEstimate, ...]


@dataclass(frozen=True, slots=True)
class MechanismContrast:
    """The stages in one arm less another on a pair the registration compares (``of``
    names which comparison), at the whole and at each registered breakdown."""

    of: str
    first: ArmRef
    second: ArmRef
    stages: tuple[RatioComparison, ...]
    unavailable: str | None


@dataclass(frozen=True, slots=True)
class Mechanism:
    """The mechanism measure as registered, by name and stages, in every arm it applies to
    and every contrast of it; it explains where a system gained or lost on the way to its
    report and carries no claim of its own."""

    name: str
    stages: tuple[str, ...]
    arms: tuple[MechanismArm, ...]
    contrasts: tuple[MechanismContrast, ...]


@dataclass(frozen=True, slots=True)
class Headroom:
    """At a condition and level, ``not_passed`` of ``scenarios`` are not already passed by
    the reference system, or ``unavailable`` says why neither count exists."""

    condition: str
    level: str
    scenarios: int | None
    not_passed: int | None
    unavailable: str | None


@dataclass(frozen=True, slots=True)
class NotRun:
    """A registered cell the plan does not hold: its place, its conditional group, why
    (``group_not_run`` or ``system_pending``) and what in the registration says so."""

    system: str
    condition: str
    level: str
    group: str | None
    why: str
    detail: str


@dataclass(frozen=True, slots=True)
class PlanArm:
    """An arm the plan holds: the system by kind and variant, the sources its assigned
    condition makes unreachable, and the corpus level."""

    system: str
    variant: str
    unreachable: tuple[str, ...]
    level: str


@dataclass(frozen=True, slots=True)
class Plan:
    """The estimation plan the tables were cut under: the interval confidence, the plan's
    seed and resample count, the intended repeats per scenario, which attempt of a run is
    counted, what a missing repeat counts as, the retry cap, and the arms."""

    confidence: float
    seed: int
    resamples: int
    intended_repeats: int
    counted_attempt: str
    missing_repeat: str
    max_attempts: int
    arms: tuple[PlanArm, ...]


@dataclass(frozen=True, slots=True)
class ChangedPath:
    """A file the evaluator's commit changed against the registration's bind, by its blob
    before and after (``None`` before when the file did not exist)."""

    path: str
    before: str | None
    after: str | None


@dataclass(frozen=True, slots=True)
class Coverage:
    """The attempts the harness intended against what the evaluation found: how many were
    admitted, exported, still open or closed without an export, the publication
    incidents, and the attempts failed by defect or by infrastructure."""

    intended: int
    admitted: int
    never_admitted: int
    admitted_beyond_intended: int
    attempts: int
    exported: int
    open: int
    closed_without_export: int
    publication_incidents: int
    failed_by_defect: int
    failed_by_infrastructure: int


@dataclass(frozen=True, slots=True)
class Provenance:
    """What the figures were cut from: the artifact by its byte digest, format and label;
    the measurement world by its version alone; the evaluator's commit and the commit its
    registration was read at; the registration's status, digest, procedure digest, bound
    commit and declarations; the harness inventory the evaluation was held to, by digest,
    attempt count, builder commit, ledger and time taken; the runs listed by disposition,
    and the coverage."""

    artifact_digest: str
    artifact_format_version: int
    label: str
    world_version: str
    evaluator_commit: str
    registration_commit: str
    registration_status: str
    registration_digest: str
    registration_procedure: str
    registration_frozen_commit: str | None
    registration_amends: str | None
    registration_prior_full_set_results: bool
    inventory_digest: str
    inventory_attempts: int
    inventory_builder_commit: str
    inventory_ledger_id: str
    inventory_taken_at: str
    runs_listed: tuple[tuple[str, int], ...]
    coverage: Coverage


@dataclass(frozen=True, slots=True)
class Disclosures:
    """What a reader is told beside the figures: the measurement world's disclosure mark as
    sealed (``embargoed`` keeps its prose, seed and enumerable digests out of every public
    output until the last measurement on it), whether the evaluation was produced by code
    other than the registration's bind and which files differ, the repeats per scenario the
    intervals rest on, and the incidents the evaluation recorded, as counts."""

    world_disclosure: str
    evaluated_by_changed_code: bool
    changed: tuple[ChangedPath, ...]
    repeats_per_scenario: int
    incidents: int
    provenance_incidents: int


@dataclass(frozen=True, slots=True)
class PublicResults:
    """One measurement's public figures, whole: the provenance, the disclosures, the plan,
    the arms, the registered comparisons (the primary, the secondary ones, the level
    contrasts, the descriptive pairs), the mechanism measure or what it is pending on,
    the headroom and the cells not run."""

    format_version: int
    provenance: Provenance
    disclosures: Disclosures
    plan: Plan
    arms: tuple[ResultArm, ...]
    primary: ComparisonResult
    secondary: tuple[ComparisonResult, ...]
    level_contrasts: tuple[LevelContrastResult, ...]
    descriptive: tuple[DescriptiveResult, ...]
    mechanism_pending: str | None
    mechanism: Mechanism | None
    headroom: tuple[Headroom, ...]
    not_run: tuple[NotRun, ...]
