"""The tick-cost probe's reading as a table (the demo milestone's step 15): the capture's
JSON read out of the host's stdout, one row per attempt with the paired timings' summaries
and its durations, then the figures the step cites, each printed here so a number in the
record has this script behind it.

Usage: ``python probes/tick-cost/reduce.py probes/captures/tick-cost/<date>/host.out.txt``.
The capture is read as the sender saved it (a UTF-8 BOM from PowerShell's ``Out-File``,
CRLF), so the same file decodes on both checkouts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def reading_of(capture: Path) -> dict[str, Any]:
    """The probe's JSON object: out of the host's stdout, between its markers, or the file
    itself when the capture is the reading fetched whole from the host's work directory
    (the second run's stdout was cut at SSM's limit once the idle figures joined it)."""
    text = capture.read_text(encoding="utf-8-sig")
    if text.lstrip().startswith("{"):
        return json.loads(text)
    start = text.index("== reading") + len("== reading")
    end = text.index("== stderr")
    return json.loads(text[start:end])


def table(reading: dict[str, Any]) -> list[str]:
    rows = [
        f"{'attempt':>7} {'events':>6} {'load cpu med':>12} {'fold cpu med':>12} "
        f"{'whole cpu p95':>13} {'whole wall p95':>14} {'adm->req s':>10} {'adm->close s':>12}"
    ]
    for a in reading["attempts"]:
        d = a["durations_s"]
        rows.append(
            f"{a['attempt']:>7} {a['events']:>6} {a['load_cpu']['median']:>12.3f} "
            f"{a['fold_cpu']['median']:>12.3f} {a['whole_cpu']['p95']:>13.3f} "
            f"{a['whole_wall']['p95']:>14.3f} {d['admission_to_request']!s:>10} "
            f"{d['admission_to_close']!s:>12}"
        )
    return rows


def figures(reading: dict[str, Any]) -> list[str]:
    attempts = reading["attempts"]
    events = [a["events"] for a in attempts]
    fold_per_event_ms = [a["fold_cpu"]["median"] / a["events"] * 1000 for a in attempts]
    load_per_event_ms = [a["load_cpu"]["median"] / a["events"] * 1000 for a in attempts]
    whole_p95 = [a["whole_cpu"]["p95"] for a in attempts]
    rule = reading["rule"]
    durations = reading["durations_s"]
    request = durations["admission_to_request"]
    close = durations["admission_to_close"]
    idle: list[str] = []
    if all("idle_cpu" in a for a in attempts):
        # The second capture's figure: the fixed cost of a tick that finds nothing new.
        idle_p95 = [a["idle_cpu"]["p95"] for a in attempts]
        idle_wall = [a["idle_wall"]["p95"] for a in attempts]
        idle = [
            f"idle-tick cpu p95 (connect, version check, row read, close): "
            f"{min(idle_p95):.4f} to {max(idle_p95):.4f} s; eight a second at the highest "
            f"{8 * max(idle_p95):.3f} s",
            f"idle-tick wall p95: {min(idle_wall):.4f} to {max(idle_wall):.4f} s",
        ]
    return [
        f"attempts measured: {reading['attempts_measured']}, repetitions "
        f"{reading['repetitions']} after {reading['warmup']} warm-up, python "
        f"{reading['python']}, cpus {reading['cpu_count']}",
        f"events per attempt: {min(events)} to {max(events)}",
        f"whole-tick cpu p95: {min(whole_p95):.3f} to {max(whole_p95):.3f} s; the highest is "
        f"attempt {rule['highest_attempt']}, c = {rule['c_seconds']:.3f} s, "
        f"8c = {rule['eight_c_seconds']:.3f} s against the budget of {rule['budget_seconds']} s",
        f"rule's branch: {rule['branch']}",
        f"fold cpu per event (median tick / events): {min(fold_per_event_ms):.2f} to "
        f"{max(fold_per_event_ms):.2f} ms",
        f"load cpu per event (median tick / events): {min(load_per_event_ms):.2f} to "
        f"{max(load_per_event_ms):.2f} ms",
        f"admission to the approval request, s: median {request['median']}, "
        f"p95 {request['p95']}, max {request['max']}",
        f"admission to close, s: median {close['median']}, p95 {close['p95']}, "
        f"max {close['max']}",
        *idle,
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
