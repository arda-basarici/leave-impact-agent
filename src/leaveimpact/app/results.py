"""The results view: the committed public results of the investigator milestone's
measurement as the plain data one page states, built by pure functions and rendered by a
template that formats nothing itself.

The page is a rendering of the committed file and never a live decode of the evaluation
artifact (the demo milestone's entry ruling on the evaluation on the page): every figure
here is read through the package's own reader, whose equivalence with the artifact the
offline acceptance command holds, so the page can show nothing the file does not hold. Of
the file it shows what the entry ruling lists, the arm table with its intervals, the
registered comparisons, the mechanism's stages, the per-cell costs, the cells not run, the
disclosures and the provenance, with the headroom and the descriptive pairs beside them
(the results step's forks, after their external read): the descriptive pairs because the
base-level pair of the investigator and full context is where the investigator loses, and
a page showing only the padded comparison would show the one it wins. The classes and the
sixty measures of a cell stay in the file, as the standalone report leaves them.

Counts are shown over their denominators and never as bare ratios; an interval is named
with its method and its direction (Wilson for an arm's count, a paired scenario bootstrap
for a difference, stated as the first system minus the second); an unresolved interval
shows its recorded reason and an unavailable comparison its reason, never a blank. A
cell's total divided by its runs is a mean and is labelled one, beside the recorded
per-run median and range; a total with a lower-bound run says "at least" and is rounded
down, and a cell with no runs or no spread renders unavailable, never as nothing spent.
Rows keep the file's order, and nothing here sorts by a measure, so the page suggests no
ranking the registration did not fix.

The labels are observations the entry ruling requires on the page, each one constant,
rendered as a block before the figures and again as the caption of the table it
qualifies, so a sentence cannot be rephrased in one place and not the other; the one
about the served world is rendered on every page of the surface. A label that states a
fact the file holds (the repeats, the changed files, the world's disclosure) is built from
the file, so the sentence and the figure cannot disagree.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from leaveimpact.app.amounts import dollars
from leaveimpact.results.public import (
    Cell,
    CheckComparison,
    CheckEstimate,
    ComparisonResult,
    DescriptiveResult,
    Disclosures,
    LevelContrastResult,
    MechanismArm,
    Provenance,
    PublicResults,
    ResultArm,
)

__all__ = [
    "MECHANISM_CAPTION",
    "SERVED_WORLD_LABEL",
    "TRUNCATION_LABEL",
    "ArmRow",
    "ComparisonRow",
    "CostView",
    "DifferenceView",
    "DisclosureView",
    "HeadroomRow",
    "MechanismRow",
    "MechanismView",
    "NotRunRow",
    "ProvenanceView",
    "ResultsView",
    "SpendView",
    "StageCount",
    "TierCount",
    "TwoByTwo",
    "changed_code_label",
    "embargo_label",
    "repeats_label",
    "results_view",
    "system_name",
]

HEADLINE_CHECK = "correct_whole"
"""The check every arm row and every comparison states: the report correct whole."""
HEADLINE_READING = "end_to_end"

SERVED_WORLD_LABEL = (
    "This demo serves a development world, one the investigator was built against. The "
    "results page's numbers come from a withheld world, generated after the procedure was "
    "frozen."
)
"""On every page of the surface, and first in the results page's block."""

TRUNCATION_LABEL = (
    "The one-call systems' padded failures came with calls stopped at the registered output "
    "maximum. That stop is reported as an observed mechanism, not as an established sole "
    "cause and not as evidence of an input-context limit; the counts of stopped calls are in "
    "the report, not in this file. Every system's base result is shown beside its padded "
    "result."
)
"""The freeze's wording on the padded level; the caption of the comparisons."""

MECHANISM_CAPTION = (
    "Counts are needed facts reaching each stage, over the facts the first stage counts: not "
    "scenarios and not model calls."
)

_SYSTEM_NAMES = {
    "agent": "the investigator",
    "full_context": "full context",
    "single_shot": "single shot",
    "rules_only": "rules only",
}


def system_name(system: str) -> str:
    """The name the page gives a registered system, the identifier itself for one the
    page has no name for, so a new arm renders rather than fails.

    >>> system_name("agent"), system_name("oracle")
    ('the investigator', 'oracle')
    """
    return _SYSTEM_NAMES.get(system, system)


# --- The view ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TierCount:
    """One tier's headline count, ``count`` as "n of N"."""

    tier: str
    count: str


@dataclass(frozen=True, slots=True)
class CostView:
    """A cell's model spend: the total (prefixed "at least" when a run's cost is a lower
    bound), the mean per run (the total over the runs), the recorded median with its range,
    and the run count the mean divides by."""

    total: str
    mean_per_run: str
    median_per_run: str
    runs: int


@dataclass(frozen=True, slots=True)
class ArmRow:
    """One arm's line of the table: the headline count at the overall stratum with its
    Wilson interval, or why the arm has none; the count per tier; the cost, or why it has
    none."""

    system: str
    name: str
    level: str
    condition: str
    count: str | None
    interval: str | None
    unavailable: str | None
    tiers: tuple[TierCount, ...]
    cost: CostView | None
    cost_unavailable: str | None


@dataclass(frozen=True, slots=True)
class TwoByTwo:
    """The paired scenarios by outcome: both systems passed, the first only, the second
    only, neither."""

    both: int
    first_only: int
    second_only: int
    neither: int


@dataclass(frozen=True, slots=True)
class DifferenceView:
    """Two systems on the headline check at one stratum: each system's count over the
    paired scenarios (from the two-by-two table, so the counts are exact), the table, the
    difference's interval as "+0.20 to +0.47" or the recorded reason there is none."""

    stratum: str
    first_count: str | None
    second_count: str | None
    two_by_two: TwoByTwo | None
    paired: int
    interval: str | None
    unresolved: str | None


@dataclass(frozen=True, slots=True)
class ComparisonRow:
    """One comparison the file holds: its kind and the names of its two sides, the
    direction every interval is read in, the overall difference and the per-tier ones,
    or the reason the comparison is unavailable."""

    kind: str
    title: str
    first_name: str
    second_name: str
    direction: str
    overall: DifferenceView | None
    breakdowns: tuple[DifferenceView, ...]
    unavailable: str | None


@dataclass(frozen=True, slots=True)
class StageCount:
    stage: str
    count: str


@dataclass(frozen=True, slots=True)
class MechanismRow:
    system: str
    name: str
    level: str
    stages: tuple[StageCount, ...]


@dataclass(frozen=True, slots=True)
class MechanismView:
    """The mechanism measure's stage counts per arm at the overall stratum, or what the
    measure is pending on."""

    name: str | None
    stages: tuple[str, ...]
    rows: tuple[MechanismRow, ...]
    pending: str | None


@dataclass(frozen=True, slots=True)
class HeadroomRow:
    level: str
    text: str


@dataclass(frozen=True, slots=True)
class NotRunRow:
    system: str
    name: str
    condition: str
    level: str
    why: str


@dataclass(frozen=True, slots=True)
class SpendView:
    """Every arm's overall cell summed: the model spend of the measurement workload and
    nothing else, ``floor`` when any cell's total is a lower bound."""

    total: str
    runs: int
    floor: bool


@dataclass(frozen=True, slots=True)
class DisclosureView:
    world: str
    changed_code: str
    repeats: str
    incidents: str


@dataclass(frozen=True, slots=True)
class ProvenanceView:
    """The fields that authenticate the figures, as (label, value) pairs in a fixed order."""

    items: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ResultsView:
    """Everything the results page states, in the order it states it."""

    labels: tuple[str, ...]
    arms_caption: str
    comparisons_caption: str
    mechanism_caption: str
    interval_method: str
    arms: tuple[ArmRow, ...]
    primary: ComparisonRow
    secondary: tuple[ComparisonRow, ...]
    level_contrasts: tuple[ComparisonRow, ...]
    descriptive: tuple[ComparisonRow, ...]
    mechanism: MechanismView
    headroom: tuple[HeadroomRow, ...]
    not_run: tuple[NotRunRow, ...]
    spend: SpendView
    disclosures: DisclosureView
    provenance: ProvenanceView


# --- The labels built from the file ---------------------------------------------------


def repeats_label(disclosures: Disclosures) -> str:
    """The one-repeat observation, from the file's own repeat count: an interval over one
    run per scenario describes variation across scenarios and not between runs.

    >>> repeats_label(Disclosures("embargoed", False, (), 1, 0, 0))[:22]
    'One run per scenario: '
    >>> repeats_label(Disclosures("embargoed", False, (), 3, 0, 0))[:23]
    '3 runs per scenario: an'
    """
    repeats = disclosures.repeats_per_scenario
    if repeats == 1:
        return (
            "One run per scenario: an interval describes variation across the scenarios of "
            "one world and not between runs."
        )
    return (
        f"{repeats} runs per scenario: an interval describes variation across the scenarios "
        "of one world, with the repeats pooled."
    )


def changed_code_label(disclosures: Disclosures) -> str:
    """The changed-code disclosure naming its files, or the statement that the evaluation
    ran at the registration's bind."""
    if not disclosures.evaluated_by_changed_code:
        return "The evaluation was produced by the code the registration binds."
    paths = ", ".join(change.path for change in disclosures.changed)
    count = len(disclosures.changed)
    files = "one file" if count == 1 else f"{count} files"
    return (
        f"The evaluation was produced by code {files} different from the registration's "
        f"bind: {paths}."
    )


def embargo_label(disclosures: Disclosures) -> str:
    """The measurement world's disclosure as sealed: an embargoed world keeps its prose,
    seed and digests withheld and nothing per scenario is shown."""
    if disclosures.world_disclosure == "embargoed":
        return (
            "The measurement world is embargoed: its prose, seed and digests stay withheld "
            "until the last measurement on it, and nothing per scenario is shown."
        )
    return f"The measurement world's disclosure is recorded as {disclosures.world_disclosure}."


# --- The view builder ----------------------------------------------------------------


def results_view(results: PublicResults) -> ResultsView:
    """The page's data over the committed results, the file's order kept throughout."""
    labels = (
        SERVED_WORLD_LABEL,
        repeats_label(results.disclosures),
        TRUNCATION_LABEL,
        changed_code_label(results.disclosures),
        embargo_label(results.disclosures),
    )
    plan = results.plan
    percent = f"{plan.confidence * 100:g}%"
    return ResultsView(
        labels=labels,
        arms_caption=labels[1],
        comparisons_caption=TRUNCATION_LABEL,
        mechanism_caption=MECHANISM_CAPTION,
        interval_method=(
            f"Intervals are at {percent}: Wilson for a count; a paired scenario bootstrap of "
            f"{plan.resamples:,} resamples for a difference, read as the first system minus "
            "the second."
        ),
        arms=tuple(_arm_row(arm) for arm in results.arms),
        primary=_comparison_row("primary", results.primary),
        secondary=tuple(_comparison_row("secondary", c) for c in results.secondary),
        level_contrasts=tuple(_level_contrast_row(c) for c in results.level_contrasts),
        descriptive=tuple(_descriptive_row(d) for d in results.descriptive),
        mechanism=_mechanism_view(results),
        headroom=tuple(_headroom_rows(results)),
        not_run=tuple(
            NotRunRow(
                row.system,
                system_name(row.system),
                row.condition,
                row.level,
                f"{_words(row.why)}: {row.detail}",
            )
            for row in results.not_run
        ),
        spend=_spend(results.arms),
        disclosures=DisclosureView(
            world=embargo_label(results.disclosures),
            changed_code=changed_code_label(results.disclosures),
            repeats=repeats_label(results.disclosures),
            incidents=(
                f"{results.disclosures.incidents} incidents recorded by the evaluation, "
                f"{results.disclosures.provenance_incidents} of provenance."
            ),
        ),
        provenance=_provenance_view(results.provenance),
    )


def _overall(arm: ResultArm) -> Cell | None:
    return next((cell for cell in arm.cells if cell.stratum.kind == "overall"), None)


def _headline(cell: Cell) -> CheckEstimate | None:
    return next(
        (
            check
            for check in cell.checks or ()
            if check.check == HEADLINE_CHECK and check.reading == HEADLINE_READING
        ),
        None,
    )


def _arm_row(arm: ResultArm) -> ArmRow:
    overall = _overall(arm)
    headline = _headline(overall) if overall is not None else None
    count = interval = unavailable = None
    if overall is None:
        unavailable = "no overall cell"
    elif headline is None:
        unavailable = (
            f"no {HEADLINE_CHECK} check"
            if overall.checks
            else f"no answer-quality checks ({_words(arm.reporting or 'unreported')})"
        )
    else:
        count = _of(int(headline.passed), headline.scenarios)
        interval = _range(headline.wilson.low, headline.wilson.high) if headline.wilson else None
    tiers = tuple(
        TierCount(cell.stratum.name, _of(int(check.passed), check.scenarios))
        for cell in arm.cells
        if cell.stratum.kind == "tier"
        for check in (_headline(cell),)
        if check is not None
    )
    cost, cost_unavailable = (None, "no overall cell") if overall is None else _cost(overall)
    return ArmRow(
        arm.system,
        system_name(arm.system),
        arm.level,
        arm.condition,
        count,
        interval,
        unavailable,
        tiers,
        cost,
        cost_unavailable,
    )


def _cost(cell: Cell) -> tuple[CostView | None, str | None]:
    cost = cell.cost
    if cost.runs == 0:
        return None, "no runs"
    if cost.per_run is None:
        return None, "no per-run spread recorded"
    floor = cost.floors > 0
    total = dollars(cost.pico_usd, floor=floor)
    mean = dollars(cost.pico_usd // cost.runs, floor=floor)
    if floor:
        total, mean = f"at least {total}", f"at least {mean}"
    spread = cost.per_run
    median = f"{dollars(int(spread.median))} (from {dollars(spread.low)} to {dollars(spread.high)})"
    return CostView(total, mean, median, cost.runs), None


def _difference(comparison: CheckComparison) -> DifferenceView:
    table = comparison.two_by_two
    two_by_two = TwoByTwo(*table) if table is not None else None
    first = second = None
    if two_by_two is not None:
        first = _of(two_by_two.both + two_by_two.first_only, comparison.paired)
        second = _of(two_by_two.both + two_by_two.second_only, comparison.paired)
    elif comparison.first is not None and comparison.second is not None:
        first, second = f"{comparison.first:.2f}", f"{comparison.second:.2f}"
    interval = comparison.interval
    return DifferenceView(
        comparison.stratum.name,
        first,
        second,
        two_by_two,
        comparison.paired,
        _signed_range(interval.low, interval.high) if interval is not None else None,
        f"no interval: {_words(comparison.unresolved)}" if comparison.unresolved else None,
    )


def _differences(
    overall: CheckComparison | None, breakdowns: tuple[CheckComparison, ...]
) -> tuple[DifferenceView | None, tuple[DifferenceView, ...]]:
    return (
        _difference(overall) if overall is not None else None,
        tuple(_difference(b) for b in breakdowns),
    )


def _comparison_row(kind: str, result: ComparisonResult) -> ComparisonRow:
    registered = result.registered
    first, second = (system_name(s) for s in registered.systems)
    overall, breakdowns = _differences(result.overall, result.breakdowns)
    return ComparisonRow(
        kind,
        f"{first} against {second}, {registered.level}",
        first,
        second,
        f"{first} minus {second}",
        overall,
        breakdowns,
        _words(result.unavailable) if result.unavailable else None,
    )


def _level_contrast_row(result: LevelContrastResult) -> ComparisonRow:
    registered = result.registered
    name = system_name(registered.system)
    first, second = registered.levels
    overall, breakdowns = _differences(result.overall, result.breakdowns)
    return ComparisonRow(
        "level contrast",
        f"{name}, {first} against {second}",
        f"{name} at {first}",
        f"{name} at {second}",
        f"{first} minus {second}",
        overall,
        breakdowns,
        _words(result.unavailable) if result.unavailable else None,
    )


def _descriptive_row(result: DescriptiveResult) -> ComparisonRow:
    first, second = (system_name(s) for s in result.systems)
    headline = [
        c for c in result.checks if c.check == HEADLINE_CHECK and c.reading == HEADLINE_READING
    ]
    overall = next((c for c in headline if c.stratum.kind == "overall"), None)
    breakdowns = tuple(c for c in headline if c.stratum.kind == "tier")
    unavailable = result.unavailable
    if unavailable is None and overall is None:
        unavailable = f"no {HEADLINE_CHECK} comparison at the overall stratum"
    overall_view, breakdown_views = _differences(overall, breakdowns)
    return ComparisonRow(
        "descriptive",
        f"{first} against {second}, {result.level}",
        first,
        second,
        f"{first} minus {second}",
        overall_view,
        breakdown_views,
        _words(unavailable) if unavailable else None,
    )


def _mechanism_view(results: PublicResults) -> MechanismView:
    mechanism = results.mechanism
    if mechanism is None:
        pending = results.mechanism_pending or "not recorded"
        return MechanismView(None, (), (), _words(pending))
    return MechanismView(
        _words(mechanism.name),
        mechanism.stages,
        tuple(_mechanism_row(arm) for arm in mechanism.arms),
        None,
    )


def _mechanism_row(arm: MechanismArm) -> MechanismRow:
    overall = [stage for stage in arm.stages if stage.stratum.kind == "overall"]
    return MechanismRow(
        arm.system,
        system_name(arm.system),
        arm.level,
        tuple(
            StageCount(_words(stage.measure), _of(stage.numerator, stage.denominator))
            for stage in overall
        ),
    )


def _headroom_rows(results: PublicResults) -> Iterator[HeadroomRow]:
    for row in results.headroom:
        if row.not_passed is None or row.scenarios is None:
            yield HeadroomRow(row.level, f"unavailable: {_words(row.unavailable or 'no reason')}")
            continue
        yield HeadroomRow(
            row.level,
            f"{row.not_passed} of {row.scenarios} scenarios the rules-only reference did not pass",
        )


def _spend(arms: tuple[ResultArm, ...]) -> SpendView:
    cells = [cell for arm in arms for cell in (_overall(arm),) if cell is not None]
    pico = sum(cell.cost.pico_usd for cell in cells)
    runs = sum(cell.cost.runs for cell in cells)
    floor = any(cell.cost.floors for cell in cells)
    total = dollars(pico, floor=floor)
    return SpendView(f"at least {total}" if floor else total, runs, floor)


def _provenance_view(provenance: Provenance) -> ProvenanceView:
    coverage = provenance.coverage
    return ProvenanceView(
        (
            ("Evaluation artifact", provenance.artifact_digest),
            ("Artifact label", provenance.label),
            ("Measurement world", provenance.world_version),
            ("Registration", provenance.registration_digest),
            ("Registration status", provenance.registration_status),
            ("Registration commit", provenance.registration_commit),
            ("Evaluator commit", provenance.evaluator_commit),
            ("Harness inventory", provenance.inventory_digest),
            (
                "Coverage",
                f"{coverage.intended} attempts intended, {coverage.admitted} admitted, "
                f"{coverage.exported} exported, {coverage.failed_by_defect} failed by defect, "
                f"{coverage.failed_by_infrastructure} by infrastructure",
            ),
        )
    )


# --- Formatting ----------------------------------------------------------------------


def _of(count: int, denominator: int) -> str:
    return f"{count} of {denominator}"


def _range(low: float, high: float) -> str:
    return f"{low:.2f} to {high:.2f}"


def _signed_range(low: float, high: float) -> str:
    return f"{low:+.2f} to {high:+.2f}"


def _words(identifier: str) -> str:
    return identifier.replace("_", " ")
