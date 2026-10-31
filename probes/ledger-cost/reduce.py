"""The ledger-cost probe's reading as a table (the demo milestone's step 15, the ledger
page): the capture's JSON read out of the host's stdout, one row per settled attempt with
its figures and its cold load, then the figures the step cites, each printed here so a
number in the record has this script behind it.

Usage: ``python probes/ledger-cost/reduce.py probes/captures/ledger-cost/<date>/host.out.txt``.
The capture is read as the sender saved it (a UTF-8 BOM from PowerShell's ``Out-File``,
CRLF), so the same file decodes on both checkouts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PICO_PER_USD = 10**12


def reading_of(capture: Path) -> dict[str, Any]:
    """The probe's JSON object: out of the host's stdout, between its markers, or the file
    itself when the capture is the reading fetched whole from the host's work directory."""
    text = capture.read_text(encoding="utf-8-sig")
    if text.lstrip().startswith("{"):
        return json.loads(text)
    start = text.index("== reading") + len("== reading")
    end = text.index("== stderr")
    return json.loads(text[start:end])


def usd(pico: int | None) -> str:
    return "none" if pico is None else f"${pico / PICO_PER_USD:.4f}"


def table(reading: dict[str, Any]) -> list[str]:
    rows = [
        f"{'attempt':>7} {'events':>6} {'state':>10} {'charged':>9} {'known':>9} "
        f"{'retained':>9} {'cold load cpu s':>15} {'cold load wall s':>16} {'load cpu med':>12}"
    ]
    for a in reading["attempts"]:
        rows.append(
            f"{a['attempt']:>7} {a['events']:>6} {a['settlement_state']:>10} "
            f"{usd(a['charged_pico_usd']):>9} {usd(a['known_pico_usd']):>9} "
            f"{usd(a['retained_pico_usd']):>9} {a['cold']['load_cpu']:>15.3f} "
            f"{a['cold']['load_wall']:>16.3f} {a['load_cpu']['median']:>12.3f}"
        )
    return rows


def figures(reading: dict[str, Any]) -> list[str]:
    charges = reading["charges"]
    cold = reading["cold"]
    head = reading["head"]
    per = cold["per_attempt_cpu_ms"]
    checks = reading["checks"]
    return [
        f"attempts measured: {reading['attempts_measured']}, repetitions "
        f"{reading['repetitions']} after {reading['warmup']} warm-up, python "
        f"{reading['python']}, cpus {reading['cpu_count']}",
        f"ledger {reading['ledger']}: head total {usd(head['total_pico_usd'])} at revision "
        f"{head['revision']} under the threshold {usd(head['threshold_pico_usd'])}; entries by "
        f"kind {reading['entries_by_kind']}",
        f"charges: {charges['count']} settled, sum {usd(charges['sum_pico_usd'])} "
        f"({charges['sum_pico_usd']} pico), mean {usd(charges['mean_pico_usd'])} "
        f"({charges['mean_pico_usd']} pico); known {usd(charges['known_sum_pico_usd'])}, "
        f"retained {usd(charges['retained_sum_pico_usd'])}; {charges['reconciled']} "
        f"reconciled, {charges['kept']} kept",
        f"cold pass (one load per settled attempt): {cold['pass_cpu_s']:.3f} s of CPU, "
        f"{cold['pass_wall_s']:.3f} s of wall; per attempt {per['median']:.1f} ms median, "
        f"{per['p95']:.1f} ms p95, {per['max']:.1f} ms max; mean "
        f"{cold['mean_per_attempt_cpu_s'] * 1000:.1f} ms",
        f"forecast: {cold['forecast_days']} days at {cold['daily_admissions']} a day is "
        f"{cold['forecast_attempts']} attempts, {cold['forecast_cpu_s']:.2f} s of CPU on the "
        f"first view, against the budget of {cold['budget_seconds']} s",
        f"rule's branch (the fold as the memo's fill): {cold['branch']}",
        *settlements_lines(reading),
        f"checks: {'passed' if checks['passed'] else 'FAILED'}"
        + ("" if checks["passed"] else "; " + "; ".join(checks["failures"])),
    ]


def settlements_lines(reading: dict[str, Any]) -> list[str]:
    """The settlements read's figures, the memo's fill after fork G4-4; absent on a capture
    taken before the read existed."""
    read = reading.get("settlements_read")
    if read is None:
        return ["settlements read: not in this capture (the image predates the read)"]
    cold = reading["cold"]
    forecast = cold["forecast_settlements_read_cpu_s"]
    verdict = (
        "no settled attempt to forecast from"
        if forecast is None
        else (
            f"{forecast:.2f} s of CPU on the first view, against the budget of "
            f"{cold['budget_seconds']} s" + ("" if forecast <= cold["budget_seconds"] else "; OVER")
        )
    )
    return [
        f"settlements read (one statement, {read['rows']} rows): cold "
        f"{read['cold_cpu_s'] * 1000:.1f} ms of CPU, {read['cold_wall_s'] * 1000:.1f} ms of wall; "
        f"warm cpu median {read['cpu']['median'] * 1000:.1f} ms, p95 "
        f"{read['cpu']['p95'] * 1000:.1f} ms",
        f"forecast under the settlements read: {cold['forecast_attempts']} attempts, {verdict}",
    ]


def main(argv: list[str]) -> int:
    capture = Path(argv[1])
    reading = reading_of(capture)
    print("\n".join(table(reading)))
    print()
    print("\n".join(figures(reading)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
