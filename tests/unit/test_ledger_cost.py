"""The ledger-cost probe's committed capture (`probes/captures/ledger-cost/`, the live pages
step's ledger page) and what was written from it: the page's replay-set constants, the fold
rate the page module and the store cite, and the rule's branch, each recomputed from the
capture through the probe's own reducer so that a figure in a text has the capture behind
it and neither moves alone (the tick-cost test is the precedent)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from leaveimpact.agent import log_store
from leaveimpact.app import ledger_page
from leaveimpact.app.amounts import dollars
from leaveimpact.app.ledger_page import (
    REPLAY_SET_MEAN_CHARGE_PICO_USD,
    REPLAY_SET_RUNS,
    REPLAY_SET_TOTAL_PICO_USD,
)

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "probes" / "ledger-cost"
FIRST = ROOT / "probes" / "captures" / "ledger-cost" / "2026-10-31" / "host.out.txt"


@pytest.fixture(scope="module")
def reduce() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ledger_cost_reduce", PROBE / "reduce.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def reading(reduce: ModuleType) -> dict[str, Any]:
    return reduce.reading_of(FIRST)


def test_the_run_measured_every_settled_attempt_and_every_check_passed(
    reading: dict[str, Any],
) -> None:
    assert reading["ledger"] == "ledger-demo"
    assert reading["attempts_measured"] == 30 == len(reading["attempts"])
    assert reading["entries_by_kind"]["settled"] == 30 and reading["checks"]["passed"]
    assert reading["charges"]["kept"] == 0 and reading["charges"]["retained_sum_pico_usd"] == 0


def test_the_pages_replay_set_constants_are_the_captures_charges(reading: dict[str, Any]) -> None:
    """The charge forecast the page quotes until a visitor run settles: the mean and the count
    over the replay set's thirty, and the total the FINDINGS entry records to the cent."""
    charges = reading["charges"]
    assert charges["count"] == REPLAY_SET_RUNS == 30
    assert charges["sum_pico_usd"] == REPLAY_SET_TOTAL_PICO_USD
    assert charges["mean_pico_usd"] == REPLAY_SET_MEAN_CHARGE_PICO_USD
    assert round(charges["sum_pico_usd"] / charges["count"]) == REPLAY_SET_MEAN_CHARGE_PICO_USD
    assert dollars(REPLAY_SET_TOTAL_PICO_USD) == "$2.0967"
    assert dollars(REPLAY_SET_MEAN_CHARGE_PICO_USD) == "$0.0699"
    findings = (ROOT / "probes" / "FINDINGS.md").read_text(encoding="utf-8")
    assert "$2.0967" in findings and "$0.0699" in findings


def test_the_cited_fold_rate_and_branch_are_the_captures(reading: dict[str, Any]) -> None:
    """The page module and the store cite the fold's cost per attempt and over the replay
    set, and the rule's branch that sent the memo to the settlements read."""
    cold = reading["cold"]
    rate_text = f"{cold['mean_per_attempt_cpu_s'] * 1000:.0f} ms an attempt"
    pass_text = f"{cold['pass_cpu_s']:.1f} s of CPU"
    forecast_text = f"{cold['forecast_cpu_s']:.0f} s"
    assert (rate_text, pass_text, forecast_text) == ("129 ms an attempt", "3.9 s of CPU", "19 s")
    assert cold["forecast_cpu_s"] > cold["budget_seconds"] == 5.0
    assert cold["branch"].startswith("warm the memo")
    page_doc = ledger_page.__doc__ or ""
    store_doc = log_store.__doc__ or ""
    assert rate_text in page_doc and pass_text in page_doc
    assert f"{forecast_text} forecast" in page_doc
    assert rate_text in store_doc and "3.9 s over the replay set" in store_doc
