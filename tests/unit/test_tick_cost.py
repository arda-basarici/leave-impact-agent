"""The tick-cost probe's committed captures (`probes/captures/tick-cost/`, the live pages
step) and what was written from them: the stream module's docstring and DESIGN's memory
passage cite the whole-tick, idle-tick and per-event figures the probe measured, and this
test recomputes each from the captures through the probe's own reducer, so a figure in
either text has the capture behind it and neither moves alone (the memory baseline's test
is the precedent)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from leaveimpact.app import stream

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "probes" / "tick-cost"
CAPTURES = ROOT / "probes" / "captures" / "tick-cost"
FIRST = CAPTURES / "2026-10-30" / "host.out.txt"
SECOND = CAPTURES / "2026-10-30-idle" / "reading.json"
"""The second run's stdout was cut at SSM's limit; the reading fetched whole sits beside it."""


@pytest.fixture(scope="module")
def reduce() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tick_cost_reduce", PROBE / "reduce.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def readings(reduce: ModuleType) -> tuple[dict[str, Any], dict[str, Any]]:
    return reduce.reading_of(FIRST), reduce.reading_of(SECOND)


def test_both_runs_measured_every_attempt_of_the_replay_set(
    readings: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    for reading in readings:
        assert reading["attempts_measured"] == 30 == len(reading["attempts"])
        assert reading["ledger"] == "ledger-demo" and reading["repetitions"] == 20


def test_the_cited_figures_are_the_captures(
    readings: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    """The whole-tick range over both runs, the idle-tick range over the second, the per-event
    range over both, each as the texts spell it."""
    attempts = [a for reading in readings for a in reading["attempts"]]
    whole = [a["whole_cpu"]["p95"] for a in attempts]
    idle = [a["idle_cpu"]["p95"] for a in readings[1]["attempts"]]
    per_event = [a["fold_cpu"]["median"] / a["events"] * 1000 for a in attempts]
    whole_text = f"{min(whole):.2f} to {max(whole):.2f} s"
    idle_text = f"{min(idle) * 1000:.1f} to {max(idle) * 1000:.1f} ms"
    event_text = f"{min(per_event):.1f} to {max(per_event):.1f} ms"
    assert (whole_text, idle_text, event_text) == (
        "0.12 to 0.69 s",
        "6.5 to 11.1 ms",
        "1.8 to 5.2 ms",
    )
    docstring = stream.__doc__ or ""
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    for text in (whole_text, idle_text, event_text):
        assert text in docstring, f"the stream module does not cite {text!r}"
        assert text in design, f"DESIGN does not cite {text!r}"
    events = [a["events"] for a in attempts]
    assert f"{min(events)} to {max(events)} events" in docstring


def test_the_rule_landed_on_its_third_branch(
    readings: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    """Both runs: eight whole ticks a second exceed the budget and so does one, which is what
    sent the step to the incremental tick rather than the shared fold."""
    for reading in readings:
        rule = reading["rule"]
        assert rule["c_seconds"] > rule["budget_seconds"] < rule["eight_c_seconds"]
        assert rule["branch"].startswith("undecided")
