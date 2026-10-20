"""The report's pins: every figure a chapter may state, by name, read from the record that
holds it, so the prose cannot carry a number the build did not read.

Four sources, each named on its pin. ``results`` is the committed public results file
through the package's own reader, which holds every statistical figure and every cell's
cost. ``registration`` is the bound registration file, which holds the corpus levels, the
caps, the roles' settings and the budget. ``findings`` and ``design`` are passages of
FINDINGS and DESIGN matched by exact text: the operational counts (calls stopped at the
output maximum, observed input tokens, calls per run) whose script of record needs
bucket access and cannot run at a build, and the world's counts the audit records. A
text-matched pin asserts that the report agrees with the recorded passage and does not
rerun anything. A derived pin carries its arithmetic in its note.

The table is built by pure functions over the four inputs; ``load_pins`` is the shell
that reads them from the tree. Names are dotted paths over the registration's own
identifiers (``whole.agent.padded``, ``caps.full_context.tokens``), so a chapter reads as
the record does.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from leaveimpact.results.committed import committed_results
from leaveimpact.results.public import (
    BootstrapInterval,
    CheckComparison,
    CheckEstimate,
    PublicResults,
    WilsonInterval,
)

__all__ = [
    "RECORD_ANCHORS",
    "SOURCES",
    "Pin",
    "RecordAnchor",
    "load_pins",
    "pin_table",
    "record_pins",
    "registration_pins",
    "results_pins",
]

SOURCES = ("results", "registration", "findings", "design")
"""The records a pin may be read from, as its ``source`` names them."""

PICO_PER_USD = Decimal(10) ** 12


@dataclass(frozen=True, slots=True)
class Pin:
    """One figure as the report prints it (``text``), the record it was read from
    (``source``, one of ``SOURCES``) and where in that record, or the arithmetic that
    derived it (``note``)."""

    name: str
    text: str
    source: str
    note: str


@dataclass(frozen=True, slots=True)
class RecordAnchor:
    """A declared passage of a record and the value a pin reads off it: ``anchor`` is
    the exact text, which must occur once in the named ``section`` of the source (the
    whole file when the section is ``None``), and ``text`` the figure the pin states,
    which must appear in the anchor, so a declared value cannot drift from the passage
    it claims to be read from."""

    name: str
    source: str
    section: str | None
    anchor: str
    text: str
    note: str


def _phase_c_row(label: str, cost: str, per_run: str, calls: str, tokens: str, stop: str) -> str:
    return f"| {label} | {cost} | {per_run} | {calls} | {tokens} | {stop} |"


_AGENT_BASE = _phase_c_row(
    "agent, base", "$2.2125", "$0.0738", "4 to 12", "39,678 to 159,172", "0"
)
_AGENT_PADDED = _phase_c_row(
    "agent, padded", "$2.1773", "$0.0726", "4 to 9", "39,678 to 115,610", "0"
)
_FULL_BASE = _phase_c_row(
    "full context, base", "$0.8166", "$0.0272", "1", "10,517 to 10,877", "0"
)
_FULL_PADDED = _phase_c_row(
    "full context, padded", "$2.5618", "$0.0854", "1", "42,232 to 42,592", "24 of 30"
)
_SINGLE_BASE = _phase_c_row(
    "single shot, base", "$0.5178", "$0.0173", "1", "8,755 to 9,765", "0"
)
_SINGLE_PADDED = _phase_c_row(
    "single shot, padded", "$1.6735", "$0.0558", "1", "12,162 to 12,809", "25 of 30"
)
_STOPPED = "the last column of the phase-c cost table: calls that ended at the output maximum"
_TOKENS = "the phase-c cost table's input-token column: the lowest and highest run"
_CALLS = "the phase-c cost table's calls column: the fewest and most calls a run made"
_AUDIT_HEADING = (
    "## measurement-audit — the measurement world accepted: validated under validator "
    "version 2, three scenarios traced by the audit method with a blind model reader, five "
    "filler documents read, the audit sealed (2026-10-15)"
)
_GOLDEN_LINE = (
    "each: seed 16, world start 2026-01-05, 28 people in 5 teams, `plan: golden`, cap 8 (the"
)
_GOLDEN_AUDIT_LINE = (
    "> audit executed the acceptance pass over all thirty scenarios, seventeen deep"
)


def _findings(name: str, section: str, anchor: str, text: str, note: str) -> RecordAnchor:
    return RecordAnchor(name, "findings", section, anchor, text, note)


def _tokens(system: str, level: str, row: str, text: str) -> RecordAnchor:
    return _findings(f"observed_input_tokens.{system}.{level}", "phase-c", row, text, _TOKENS)


RECORD_ANCHORS: tuple[RecordAnchor, ...] = (
    _findings("stopped.full_context.padded", "phase-c", _FULL_PADDED, "24 of 30", _STOPPED),
    _findings("stopped.single_shot.padded", "phase-c", _SINGLE_PADDED, "25 of 30", _STOPPED),
    _tokens("agent", "base", _AGENT_BASE, "39,678 to 159,172"),
    _tokens("agent", "padded", _AGENT_PADDED, "39,678 to 115,610"),
    _tokens("full_context", "base", _FULL_BASE, "10,517 to 10,877"),
    _tokens("full_context", "padded", _FULL_PADDED, "42,232 to 42,592"),
    _tokens("single_shot", "base", _SINGLE_BASE, "8,755 to 9,765"),
    _tokens("single_shot", "padded", _SINGLE_PADDED, "12,162 to 12,809"),
    _findings("calls_per_run.agent.base", "phase-c", _AGENT_BASE, "4 to 12", _CALLS),
    _findings("calls_per_run.agent.padded", "phase-c", _AGENT_PADDED, "4 to 9", _CALLS),
    _findings(
        "forecast.phase_usd",
        "phase-c",
        "Cost $9.9594 over the phase against the about $12 the freeze's forks file",
        "$12",
        "the phase's cost forecast by hand at the freeze, as phase-c restates it",
    ),
    _findings(
        "calibration.padded_level_tokens",
        "step-15-calibration",
        "**The padded level (fork 2): 40,000 by the stated rule.**",
        "40,000",
        "the full-context request size the level-choice rule selected",
    ),
    _findings(
        "runtime_truth.other_pairs_differ",
        "runtime-truth",
        "36 of 32,960 other pairs do, 0 of 1,280 outcomes.",
        "36 of 32,960",
        "pairs the evaluator derives on which the dated and runtime views differ, forty worlds",
    ),
    _findings(
        "crash_matrix.rows",
        "crash-matrix",
        "## crash-matrix — the real worker and the job seam's commands killed at every boundary "
        "their reference runs cross, 469 rows recovering as forecast",
        "469",
        "the crash matrix's rows, the entry's heading",
    ),
    _findings("golden.people", "golden-world", _GOLDEN_LINE, "28", "the golden world's head count"),
    _findings("golden.teams", "golden-world", _GOLDEN_LINE, "5", "the golden world's team count"),
    _findings(
        "audit.measurement.traces",
        "measurement-audit",
        _AUDIT_HEADING,
        "three",
        "the measurement world's traced scenarios, the entry's heading",
    ),
    _findings(
        "audit.measurement.filler_reads",
        "measurement-audit",
        _AUDIT_HEADING,
        "five",
        "the measurement world's filler documents read, the entry's heading",
    ),
    _findings(
        "validator.measurement.exactness",
        "measurement-audit",
        "under validator version 2, verdict `verdicts/38654375403-1.json`: 7 of 7 exactness, "
        "7 of 7",
        "7 of 7",
        "the validator's exactness kinds on the measurement world",
    ),
    _findings(
        "feasibility.random_order.admitted",
        "reservation-book",
        "| 4, the random order | 196 | 0 | 4 (composite 1, seed 1; free-text qualification 2, "
        "seeds 72 and 134; release cardinality 1, seed 85) |",
        "196",
        "seeds of 200 the golden plan constructs on under the random order, run 4",
    ),
    RecordAnchor(
        "golden.audit.acceptance_scenarios",
        "design",
        None,
        _GOLDEN_AUDIT_LINE,
        "thirty",
        "the golden audit's outcome box, DESIGN 'Sealing and the audit'",
    ),
    RecordAnchor(
        "golden.audit.deep_traces",
        "design",
        None,
        _GOLDEN_AUDIT_LINE,
        "seventeen",
        "the golden audit's outcome box, the same line",
    ),
)
"""The record passages the report reads, each checked against its file at every build."""


def results_pins(results: PublicResults) -> tuple[Pin, ...]:
    """The pins the committed results hold: per arm the whole-correct count at the whole
    and at each tier, its Wilson interval, the cell's cost and the cost per run; the run
    and scenario totals; every registered comparison, level contrast and descriptive
    pair as an interval and a two-by-two table; the mechanism's stages per arm and its
    denominator; the headroom per level. Refuses a file whose arms disagree on the
    scenario count."""
    return tuple(_results_pins(results))


def _results_pins(results: PublicResults) -> Iterator[Pin]:
    scenario_counts: set[int] = set()
    total_pico = 0
    total_runs = 0
    per_run_pico: dict[tuple[str, str], Decimal] = {}
    for arm in results.arms:
        place = f"{arm.system}.{arm.level}"
        at = f"the {arm.system} arm at {arm.level}"
        for cell in arm.cells:
            whole = _whole(cell.checks or ())
            if whole is None or cell.stratum.kind not in ("overall", "tier"):
                continue
            if cell.stratum.kind == "tier":
                yield Pin(
                    f"whole.{place}.tier.{cell.stratum.name}",
                    str(int(whole.passed)),
                    "results",
                    f"correct_whole, end to end, {at}, the {cell.stratum.name} tier",
                )
                continue
            scenario_counts.add(cell.accounting.scenarios)
            empty = _empty_reports(cell.checks or ())
            if empty is not None:
                yield Pin(
                    f"empty_reports.{place}",
                    str(empty),
                    "results",
                    f"runs reproduced_whole could not check because the report was empty, {at}",
                )
            total_pico += cell.cost.pico_usd
            total_runs += cell.cost.runs
            yield Pin(f"whole.{place}", str(int(whole.passed)), "results", f"correct_whole, {at}")
            if whole.wilson is not None:
                text = _interval(whole.wilson)
                yield Pin(f"whole.{place}.interval", text, "results", f"Wilson, {at}")
            cost = _usd(cell.cost.pico_usd)
            yield Pin(f"cost.{place}.usd", cost, "results", f"the cell's total, {at}")
            per_run_pico[(arm.system, arm.level)] = Decimal(cell.cost.pico_usd) / cell.cost.runs
            yield Pin(
                f"cost.{place}.per_run_usd",
                _usd(cell.cost.pico_usd, cell.cost.runs),
                "results",
                f"the cell's total divided by its {cell.cost.runs} runs, {at}",
            )
    if len(scenario_counts) != 1:
        raise ValueError(f"the arms disagree on the scenario count: {sorted(scenario_counts)}")
    yield Pin("scenarios.per_arm", str(scenario_counts.pop()), "results", "every arm's accounting")
    yield Pin("runs.total", str(total_runs), "results", "the sum of every arm's run count")
    total_note = f"every arm's cost summed, {total_pico} pico-dollars"
    yield Pin("cost.total_usd", _usd(total_pico), "results", total_note)
    cents = (Decimal(total_pico) / PICO_PER_USD).quantize(Decimal("0.01"))
    yield Pin("cost.total_usd.rounded", f"${cents}", "results", "the same total to cents")
    for level in ("base", "padded"):
        agent, full = per_run_pico.get(("agent", level)), per_run_pico.get(("full_context", level))
        if agent and full:
            ratio = (agent / full).quantize(Decimal("0.1"))
            yield Pin(
                f"cost.ratio.agent_to_full_context.{level}",
                str(ratio),
                "results",
                f"the investigator's per-run cost divided by full context's at {level}, "
                f"{agent:.0f} over {full:.0f} pico-dollars, to one decimal",
            )
    provenance = results.provenance
    for field in (
        "artifact_digest",
        "world_version",
        "registration_digest",
        "registration_commit",
        "evaluator_commit",
    ):
        value = getattr(provenance, field)
        if isinstance(value, str):
            yield Pin(f"provenance.{field}", value, "results", f"provenance.{field}")
    for comparison in (results.primary, *results.secondary):
        first, second = comparison.registered.systems
        level = comparison.registered.level
        yield from _contrast_pins(f"difference.{first}.{second}.{level}", comparison.overall)
    for contrast in results.level_contrasts:
        yield from _contrast_pins(f"level_contrast.{contrast.registered.system}", contrast.overall)
    for pair in results.descriptive:
        first, second = pair.systems
        whole_comparison = _whole_comparison(pair.checks)
        yield from _contrast_pins(f"descriptive.{first}.{second}.{pair.level}", whole_comparison)
    if results.mechanism is not None:
        names = ", ".join(results.mechanism.stages)
        yield Pin("mechanism.stage_names", names, "results", "the registered stage names")
        for arm in results.mechanism.arms:
            stages = [s for s in arm.stages if s.stratum.kind == "overall"]
            if not stages:
                continue
            place = f"mechanism.{arm.system}.{arm.level}"
            counts = ", ".join(str(s.numerator) for s in stages)
            yield Pin(f"{place}.stages", counts, "results", "needed facts reaching each stage")
            yield Pin(
                f"{place}.returned",
                str(stages[0].numerator),
                "results",
                "needed facts whose carrier the run was given, the first stage",
            )
            yield Pin(
                f"{place}.denominator",
                str(stages[0].denominator),
                "results",
                "the needed facts the first stage counts over",
            )
    for row in results.headroom:
        if row.not_passed is not None and row.scenarios is not None:
            yield Pin(
                f"headroom.{row.level}",
                f"{row.not_passed} of {row.scenarios}",
                "results",
                "scenarios the reference system does not pass",
            )


def _empty_reports(checks: tuple[CheckEstimate, ...]) -> int | None:
    """How many runs the reproduced-whole check left unchecked at this cell: a report
    with no claims is outside that check's conditional denominator, so the count is
    the runs that reported nothing."""
    for check in checks:
        if check.check == "reproduced_whole" and check.reading == "conditional":
            return check.not_checked
    return None


def _whole(checks: tuple[CheckEstimate, ...]) -> CheckEstimate | None:
    for check in checks:
        if check.check == "correct_whole" and check.reading == "end_to_end":
            return check
    return None


def _whole_comparison(checks: tuple[CheckComparison, ...]) -> CheckComparison | None:
    for check in checks:
        if (
            check.check == "correct_whole"
            and check.reading == "end_to_end"
            and check.stratum.kind == "overall"
        ):
            return check
    return None


def _contrast_pins(name: str, contrast: CheckComparison | None) -> Iterator[Pin]:
    if contrast is None:
        return
    if contrast.interval is not None:
        note = f"{contrast.first_arm} less {contrast.second_arm}, paired on scenario"
        yield Pin(name, _interval(contrast.interval), "results", note)
        if contrast.first is not None and contrast.second is not None:
            points = round((contrast.first - contrast.second) * 100)
            yield Pin(
                f"{name}.points",
                str(points),
                "results",
                f"the first arm's pass fraction less the second's, times 100, rounded: "
                f"{contrast.first:.4f} less {contrast.second:.4f}",
            )
            low, high = contrast.interval.low * 100, contrast.interval.high * 100
            yield Pin(
                f"{name}.points_interval",
                f"{low:.0f} to {high:.0f}",
                "results",
                "the same interval, times 100, rounded",
            )
    if contrast.two_by_two is not None:
        cells = ", ".join(str(n) for n in contrast.two_by_two)
        note = "both passed, the first only, the second only, neither"
        yield Pin(f"{name}.two_by_two", cells, "results", note)


def _interval(interval: WilsonInterval | BootstrapInterval) -> str:
    return f"{interval.low:.2f} to {interval.high:.2f}"


def _usd(pico: int, runs: int = 1) -> str:
    """Dollars from pico-dollars, to four places as FINDINGS prints a cell; ``$0`` for a
    cell that cost nothing.

    >>> _usd(2_212_500_000_000), _usd(2_212_500_000_000, 30), _usd(0)
    ('$2.2125', '$0.0738', '$0')
    """
    if pico == 0:
        return "$0"
    dollars = Decimal(pico) / PICO_PER_USD / Decimal(runs)
    return f"${dollars.quantize(Decimal('0.0001'))}"


def registration_pins(registration: Mapping[str, object]) -> tuple[Pin, ...]:
    """The pins the bound registration holds: per corpus level the filler documents and
    the registered full-context input range; per system its call and token caps; per
    role its output maximum; the budget's expected and ceiling figures; the confidence
    and resample count."""
    return tuple(_registration_pins(registration))


def _registration_pins(registration: Mapping[str, object]) -> Iterator[Pin]:
    for level in _items(registration, "corpus_levels"):
        name = _text(level, "name")
        filler = _number(_value(level, "filler_documents"))
        where = f"corpus_levels[{name}]"
        yield Pin(f"level.{name}.filler_documents", filler, "registration", where)
        tokens = _mapping(_value(level, "full_context_input_tokens"))
        yield Pin(
            f"level.{name}.full_context_input_tokens",
            f"{_number(tokens['low'])} to {_number(tokens['high'])}",
            "registration",
            f"corpus_levels[{name}].full_context_input_tokens",
        )
    for system in _items(registration, "systems"):
        kind = _text(system, "kind")
        caps = _mapping(system["caps"])
        where = f"systems[{kind}].caps"
        yield Pin(f"caps.{kind}.calls", _number(caps["call_cap"]), "registration", where)
        yield Pin(f"caps.{kind}.tokens", _number(caps["token_cap"]), "registration", where)
        roles = _value(system, "roles") if "roles" in system else None
        if isinstance(roles, list):
            for role in cast("list[object]", roles):
                yield from _role_pins(kind, _mapping(role))
    budget = _mapping(registration["budget"])
    expected = f"${_number(budget['expected_usd'])}"
    yield Pin("budget.expected_usd", expected, "registration", "budget")
    yield Pin("budget.ceiling_usd", f"${_number(budget['ceiling_usd'])}", "registration", "budget")
    statistics = _mapping(registration["statistics"])
    confidence = _number(_value(statistics, "confidence_percent"))
    yield Pin("statistics.confidence_percent", confidence, "registration", "statistics")
    resamples = _number(_value(statistics, "resamples"))
    yield Pin("statistics.resamples", resamples, "registration", "statistics")


def _role_pins(kind: str, role: Mapping[str, object]) -> Iterator[Pin]:
    name = _text(role, "name")
    configuration = _mapping(role["configuration"])
    settings = configuration.get("settings")
    if not isinstance(settings, list):
        return
    for setting in cast("list[object]", settings):
        entry = _mapping(setting)
        if entry.get("name") == "max_tokens":
            yield Pin(
                f"roles.{kind}.{name}.max_tokens",
                _number(entry["value"]),
                "registration",
                f"systems[{kind}].roles[{name}].configuration.settings",
            )


def _items(mapping: Mapping[str, object], key: str) -> Iterator[Mapping[str, object]]:
    value = mapping[key]
    if not isinstance(value, list):
        raise ValueError(f"registration.{key} is not a list")
    for item in cast("list[object]", value):
        yield _mapping(item)


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"expected an object in the registration, found {type(value).__name__}")
    return cast("Mapping[str, object]", value)


def _value(mapping: Mapping[str, object], key: str) -> object:
    """A registration field, unwrapped from the ``{"value": ...}`` form the file uses for
    a value it records beside its basis."""
    value = mapping[key]
    if isinstance(value, dict):
        wrapped = cast("Mapping[str, object]", value)
        if "value" in wrapped:
            return wrapped["value"]
    return value


def _text(mapping: Mapping[str, object], key: str) -> str:
    value = mapping[key]
    if not isinstance(value, str):
        raise ValueError(f"registration field {key!r} is not text")
    return value


def _number(value: object) -> str:
    """An integer with thousands separators, as the report prints a count.

    >>> _number(200000), _number(14)
    ('200,000', '14')
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"expected an integer in the registration, found {value!r}")
    return f"{value:,}"


def record_pins(findings: str, design: str) -> tuple[Pin, ...]:
    """The pins the declared record anchors hold, each checked against the file's text:
    the anchor occurs exactly once in its section (the whole file for DESIGN) and the
    pin's value appears in the anchor. Refuses by pin name otherwise, so a correction
    that moved a figure fails the build before it fails the prose."""
    pins: list[Pin] = []
    for declared in RECORD_ANCHORS:
        if declared.text not in declared.anchor:
            raise ValueError(f"pin {declared.name!r}: its value is not in its declared anchor")
        scope = _scope(declared, findings, design)
        occurrences = scope.count(declared.anchor)
        if occurrences != 1:
            raise ValueError(
                f"pin {declared.name!r}: its anchor occurs {occurrences} times "
                f"in {declared.source} {declared.section or '(whole file)'}, not once"
            )
        pins.append(Pin(declared.name, declared.text, declared.source, declared.note))
    return tuple(pins)


def _scope(declared: RecordAnchor, findings: str, design: str) -> str:
    if declared.source == "design":
        return design
    if declared.source != "findings":
        raise ValueError(f"pin {declared.name!r}: anchors read findings or design")
    heading = f"\n## {declared.section}"
    start = findings.find(heading)
    if start < 0:
        raise ValueError(f"pin {declared.name!r}: FINDINGS has no section {declared.section!r}")
    end = findings.find("\n## ", start + 1)
    return findings[start:] if end < 0 else findings[start:end]


def pin_table(
    results: PublicResults, registration: Mapping[str, object], findings: str, design: str
) -> Mapping[str, Pin]:
    """Every pin by name over the four records; refuses a name two sources both claim."""
    table: dict[str, Pin] = {}
    pins = (
        *results_pins(results),
        *registration_pins(registration),
        *record_pins(findings, design),
    )
    for pin in pins:
        if pin.name in table:
            raise ValueError(f"pin {pin.name!r} is declared twice")
        if pin.source not in SOURCES:
            raise ValueError(f"pin {pin.name!r} names an unknown source {pin.source!r}")
        table[pin.name] = pin
    return table


def load_pins(repository: Path) -> Mapping[str, Pin]:
    """The pin table over the tree: the committed results by package name, the
    registration, FINDINGS and DESIGN by path under ``repository``."""
    registration_path = repository / "preregistration" / "registration.json"
    registration = cast("Mapping[str, object]", json.loads(_read(registration_path)))
    findings = _read(repository / "probes" / "FINDINGS.md")
    design = _read(repository / "DESIGN.md")
    return pin_table(committed_results(), registration, findings, design)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")
