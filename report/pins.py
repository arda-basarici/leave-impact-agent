"""The report's pins: every figure a chapter may state, by name, read from the record that
holds it, so the prose cannot carry a number the build did not read.

Three sources, each named on its pin. ``results`` is the committed public results file
through the package's own reader, which holds every statistical figure and every cell's
cost. ``registration`` is the bound registration file, which holds the corpus levels, the
caps and the budget. ``findings`` is a row of FINDINGS ``phase-c`` matched by its exact
text, which holds the operational counts (calls stopped at the output maximum, observed
input tokens, calls per run) whose script of record needs bucket access and cannot run at
a build; a findings pin asserts that the report agrees with the recorded row and does not
rerun that script. A derived pin carries its arithmetic in its note.

The table is built by pure functions over the three inputs; ``load_pins`` is the shell
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
    "FINDINGS_ROWS",
    "FindingsRow",
    "Pin",
    "findings_pins",
    "load_pins",
    "pin_table",
    "registration_pins",
    "results_pins",
]

SOURCES = ("results", "registration", "findings")
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
class FindingsRow:
    """A declared row of FINDINGS ``phase-c`` and the value a pin reads off it: ``row`` is
    the exact table line, ``text`` the cell the pin states, which must appear in the
    row, so a declared value cannot drift from the row it claims to be read from."""

    name: str
    row: str
    text: str
    note: str


def _phase_c_row(label: str, cost: str, per_run: str, calls: str, tokens: str, stopped: str) -> str:
    return f"| {label} | {cost} | {per_run} | {calls} | {tokens} | {stopped} |"


_AGENT_BASE = _phase_c_row("agent, base", "$2.2125", "$0.0738", "4 to 12", "39,678 to 159,172", "0")
_AGENT_PADDED = _phase_c_row(
    "agent, padded", "$2.1773", "$0.0726", "4 to 9", "39,678 to 115,610", "0"
)
_FULL_BASE = _phase_c_row("full context, base", "$0.8166", "$0.0272", "1", "10,517 to 10,877", "0")
_FULL_PADDED = _phase_c_row(
    "full context, padded", "$2.5618", "$0.0854", "1", "42,232 to 42,592", "24 of 30"
)
_SINGLE_BASE = _phase_c_row("single shot, base", "$0.5178", "$0.0173", "1", "8,755 to 9,765", "0")
_SINGLE_PADDED = _phase_c_row(
    "single shot, padded", "$1.6735", "$0.0558", "1", "12,162 to 12,809", "25 of 30"
)
_STOPPED = "the last column of the phase-c cost table: calls that ended at the output maximum"
_TOKENS = "the phase-c cost table's input-token column: the lowest and highest run"
_CALLS = "the phase-c cost table's calls column: the fewest and most calls a run made"

FINDINGS_ROWS: tuple[FindingsRow, ...] = (
    FindingsRow("stopped.full_context.padded", _FULL_PADDED, "24 of 30", _STOPPED),
    FindingsRow("stopped.single_shot.padded", _SINGLE_PADDED, "25 of 30", _STOPPED),
    FindingsRow("observed_input_tokens.agent.base", _AGENT_BASE, "39,678 to 159,172", _TOKENS),
    FindingsRow("observed_input_tokens.agent.padded", _AGENT_PADDED, "39,678 to 115,610", _TOKENS),
    FindingsRow("observed_input_tokens.full_context.base", _FULL_BASE, "10,517 to 10,877", _TOKENS),
    FindingsRow(
        "observed_input_tokens.full_context.padded", _FULL_PADDED, "42,232 to 42,592", _TOKENS
    ),
    FindingsRow("observed_input_tokens.single_shot.base", _SINGLE_BASE, "8,755 to 9,765", _TOKENS),
    FindingsRow(
        "observed_input_tokens.single_shot.padded", _SINGLE_PADDED, "12,162 to 12,809", _TOKENS
    ),
    FindingsRow("calls_per_run.agent.base", _AGENT_BASE, "4 to 12", _CALLS),
    FindingsRow("calls_per_run.agent.padded", _AGENT_PADDED, "4 to 9", _CALLS),
)
"""The FINDINGS rows the report reads, each checked against the file at every build."""

_FINDINGS_SECTION = "\n## phase-c"


def results_pins(results: PublicResults) -> tuple[Pin, ...]:
    """The pins the committed results hold: per arm the whole-correct count, its Wilson
    interval, the cell's cost and the cost per run; the run and scenario totals; every
    registered comparison, level contrast and descriptive pair as an interval and a
    two-by-two table; the mechanism's stages per arm and its denominator; the headroom
    per level. Refuses a file whose arms disagree on the scenario count."""
    return tuple(_results_pins(results))


def _results_pins(results: PublicResults) -> Iterator[Pin]:
    scenario_counts: set[int] = set()
    total_pico = 0
    total_runs = 0
    for arm in results.arms:
        (cell,) = [c for c in arm.cells if c.stratum.kind == "overall"]
        place = f"{arm.system}.{arm.level}"
        at = f"the {arm.system} arm at {arm.level}, the overall stratum"
        scenario_counts.add(cell.accounting.scenarios)
        total_pico += cell.cost.pico_usd
        total_runs += cell.cost.runs
        whole = _whole(cell.checks or ())
        if whole is not None:
            yield Pin(
                f"whole.{place}",
                str(int(whole.passed)),
                "results",
                f"correct_whole, end to end, {at}",
            )
            if whole.wilson is not None:
                yield Pin(
                    f"whole.{place}.interval", _wilson(whole.wilson), "results", f"Wilson at {at}"
                )
        yield Pin(
            f"cost.{place}.usd", _usd(cell.cost.pico_usd), "results", f"the cell's total, {at}"
        )
        yield Pin(
            f"cost.{place}.per_run_usd",
            _usd(cell.cost.pico_usd, cell.cost.runs),
            "results",
            f"the cell's total divided by its {cell.cost.runs} runs, {at}",
        )
    if len(scenario_counts) != 1:
        raise ValueError(f"the arms disagree on the scenario count: {sorted(scenario_counts)}")
    yield Pin(
        "scenarios.per_arm", str(scenario_counts.pop()), "results", "every arm's overall accounting"
    )
    yield Pin("runs.total", str(total_runs), "results", "the sum of every arm's overall run count")
    yield Pin(
        "cost.total_usd",
        _usd(total_pico),
        "results",
        f"the sum of every arm's cost, {total_pico} pico-dollars",
    )
    for comparison in (results.primary, *results.secondary):
        first, second = comparison.registered.systems
        yield from _contrast_pins(
            f"difference.{first}.{second}.{comparison.registered.level}", comparison.overall
        )
    for contrast in results.level_contrasts:
        yield from _contrast_pins(f"level_contrast.{contrast.registered.system}", contrast.overall)
    for pair in results.descriptive:
        first, second = pair.systems
        yield from _contrast_pins(
            f"descriptive.{first}.{second}.{pair.level}", _whole_comparison(pair.checks)
        )
    if results.mechanism is not None:
        yield Pin(
            "mechanism.stage_names",
            ", ".join(results.mechanism.stages),
            "results",
            "the registered stage names",
        )
        for arm in results.mechanism.arms:
            stages = [s for s in arm.stages if s.stratum.kind == "overall"]
            if not stages:
                continue
            place = f"mechanism.{arm.system}.{arm.level}"
            yield Pin(
                f"{place}.stages",
                ", ".join(str(s.numerator) for s in stages),
                "results",
                "needed facts reaching each stage, the overall stratum",
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
        yield Pin(
            name,
            _bootstrap(contrast.interval),
            "results",
            f"{contrast.first_arm} less {contrast.second_arm}, paired on scenario",
        )
    if contrast.two_by_two is not None:
        yield Pin(
            f"{name}.two_by_two",
            ", ".join(str(n) for n in contrast.two_by_two),
            "results",
            "both passed, the first only, the second only, neither",
        )


def _wilson(interval: WilsonInterval) -> str:
    return f"{interval.low:.2f} to {interval.high:.2f}"


def _bootstrap(interval: BootstrapInterval) -> str:
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
    the registered full-context input range; per system its call and token caps; the
    budget's expected and ceiling figures; the confidence and resample count."""
    return tuple(_registration_pins(registration))


def _registration_pins(registration: Mapping[str, object]) -> Iterator[Pin]:
    for level in _items(registration, "corpus_levels"):
        name = _text(level, "name")
        yield Pin(
            f"level.{name}.filler_documents",
            _number(_value(level, "filler_documents")),
            "registration",
            f"corpus_levels[{name}].filler_documents",
        )
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
        yield Pin(
            f"caps.{kind}.calls",
            _number(caps["call_cap"]),
            "registration",
            f"systems[{kind}].caps.call_cap",
        )
        yield Pin(
            f"caps.{kind}.tokens",
            _number(caps["token_cap"]),
            "registration",
            f"systems[{kind}].caps.token_cap",
        )
    budget = _mapping(registration["budget"])
    yield Pin(
        "budget.expected_usd",
        f"${_number(budget['expected_usd'])}",
        "registration",
        "budget.expected_usd",
    )
    yield Pin(
        "budget.ceiling_usd",
        f"${_number(budget['ceiling_usd'])}",
        "registration",
        "budget.ceiling_usd",
    )
    statistics = _mapping(registration["statistics"])
    yield Pin(
        "statistics.confidence_percent",
        _number(_value(statistics, "confidence_percent")),
        "registration",
        "statistics.confidence_percent",
    )
    yield Pin(
        "statistics.resamples",
        _number(_value(statistics, "resamples")),
        "registration",
        "statistics.resamples",
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


def findings_pins(findings: str) -> tuple[Pin, ...]:
    """The pins the declared FINDINGS rows hold, each checked against ``findings`` (the
    file's text): the row occurs exactly once in the ``phase-c`` section and the pin's
    value appears in the row. Refuses by pin name otherwise, so a FINDINGS correction
    that moved a figure fails the build before it fails the prose."""
    start = findings.find(_FINDINGS_SECTION)
    if start < 0:
        raise ValueError("FINDINGS has no phase-c section")
    end = findings.find("\n## ", start + 1)
    section = findings[start:] if end < 0 else findings[start:end]
    pins: list[Pin] = []
    for declared in FINDINGS_ROWS:
        if declared.text not in declared.row:
            raise ValueError(
                f"findings pin {declared.name!r}: its value is not in its declared row"
            )
        occurrences = section.count("\n" + declared.row + "\n")
        if occurrences != 1:
            raise ValueError(
                f"findings pin {declared.name!r}: its row occurs {occurrences} times "
                "in phase-c, not once"
            )
        pins.append(Pin(declared.name, declared.text, "findings", declared.note))
    return tuple(pins)


def pin_table(
    results: PublicResults, registration: Mapping[str, object], findings: str
) -> Mapping[str, Pin]:
    """Every pin by name over the three records; refuses a name two sources both claim."""
    table: dict[str, Pin] = {}
    for pin in (*results_pins(results), *registration_pins(registration), *findings_pins(findings)):
        if pin.name in table:
            raise ValueError(f"pin {pin.name!r} is declared twice")
        if pin.source not in SOURCES:
            raise ValueError(f"pin {pin.name!r} names an unknown source {pin.source!r}")
        table[pin.name] = pin
    return table


def load_pins(repository: Path) -> Mapping[str, Pin]:
    """The pin table over the tree: the committed results by package name, the
    registration and FINDINGS by path under ``repository``."""
    registration = cast(
        "Mapping[str, object]",
        json.loads(
            (repository / "preregistration" / "registration.json").read_text(encoding="utf-8")
        ),
    )
    findings = (repository / "probes" / "FINDINGS.md").read_text(encoding="utf-8")
    return pin_table(committed_results(), registration, findings)
