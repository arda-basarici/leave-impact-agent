"""Stopped calls against failed scenarios, and output tokens per cell, for the phase C runs.

The reported evaluation records 24 of full context's 30 padded calls and 25 of single
shot's stopping at the output maximum, and 16 and 12 scenarios failed; nothing recorded
how the two overlap, and the M2 report's external readers asked. This joins, per run,
the graded outcome the evaluation artifact lists (`listing[].run.outcome`) with the
run's export (the stop reason of each dispatch, the usage counters), both held locally:
the artifact copy the phase-C runbook fetches and the exports `tally.py` caches.

Correct whole is read here by hand from the listed rows, the reading `grading.py`'s
`correct_whole` states (structurally valid, every required row reported, every reported
row's payload right, no unexpected row, no plan finding against the oracle), because the
artifact has no decoder into the evaluator's types. The reading is validated before any
cross-tab is printed: it must reproduce the eight whole-correct counts FINDINGS
`phase-c` records (24, 24, 30, 14, 22, 10, 10, 10), and the script refuses otherwise.
A stopped call is `tally.py`'s rule: a dispatch whose stop reason is `max_tokens`.

Usage, from the repository root, with the cached exports present::

    uv run python probes/phase-c-dispatch/stops_by_scenario.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
ARTIFACT = REPOSITORY / "data" / "phase-c-dispatch" / "evaluation-39061375799-1.json"
CACHE = REPOSITORY / "data" / "phase-c-dispatch" / "exports"
EXPECTED_WHOLE = {
    ("agent", "base"): 24,
    ("agent", "padded"): 24,
    ("full_context", "base"): 30,
    ("full_context", "padded"): 14,
    ("single_shot", "base"): 22,
    ("single_shot", "padded"): 10,
    ("rules_only", "base"): 10,
    ("rules_only", "padded"): 10,
}
ROW_KINDS = ("impacts", "constraints", "assessments", "actions", "conflicts", "unknowns")


def correct_whole(outcome: dict) -> bool:
    """The hand reading of the graded rows; see the module docstring for its validation."""
    rows = outcome["rows"]
    if rows["structural_problems"] or outcome["oracle_findings"]:
        return False
    for kind in ROW_KINDS:
        for row in rows[kind]:
            expectation, claim = row["expectation"], row["claim_id"]
            if expectation == "required" and claim is None:
                return False
            if expectation not in ("required", "optional"):
                return False
            if claim is not None and "expected" in row and row["expected"] != row["reported"]:
                return False
            for flag in ("verdict_matches", "reasons_match", "value_matches", "rule_matches",
                         "observations_hold", "reason_matches"):
                if claim is not None and row.get(flag) is False:
                    return False
    return True


def run_rows() -> list[dict]:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    rows = []
    for entry in artifact["listing"]:
        run = entry["run"]
        header = run["outcome"]["header"]
        run_id = int(header["run_id"].removeprefix("run-"))
        export = json.loads((CACHE / f"{run_id}.json").read_text(encoding="utf-8"))
        calls = export["trace"]["model_calls"]
        stopped = any(
            d["observation"].get("stop_reason") == "max_tokens"
            for c in calls
            for d in c["dispatches"]
        )
        counters = {c["name"]: c["value"] for c in export["record"]["usage"]["counters"]}
        rows.append(
            {
                "system": header["system"]["kind"],
                "level": run["level"],
                "scenario": header["scenario_id"],
                "whole": correct_whole(run["outcome"]),
                "stopped": stopped,
                "output": counters.get("output_tokens", 0),
                "input": counters.get("input_tokens", 0),
            }
        )
    return rows


def main() -> int:
    rows = run_rows()
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        cells[(row["system"], row["level"])].append(row)
    for key, expected in EXPECTED_WHOLE.items():
        found = sum(r["whole"] for r in cells[key])
        if found != expected:
            raise SystemExit(f"the hand reading of correct whole gives {found} at {key}, FINDINGS records {expected}")
    print("the hand reading reproduces every whole-correct count FINDINGS records\n")
    print(f"{'cell':<22}{'runs':>5}{'output tokens':>16}{'per run':>18}{'stopped':>9}{'failed':>8}"
          f"{'stop&fail':>11}{'stop&pass':>11}{'go&fail':>9}{'go&pass':>9}")
    for key in EXPECTED_WHOLE:
        cell = cells[key]
        outputs = [r["output"] for r in cell]
        stopped_failed = sum(r["stopped"] and not r["whole"] for r in cell)
        stopped_passed = sum(r["stopped"] and r["whole"] for r in cell)
        went_failed = sum(not r["stopped"] and not r["whole"] for r in cell)
        went_passed = sum(not r["stopped"] and r["whole"] for r in cell)
        print(
            f"{key[0] + ', ' + key[1]:<22}{len(cell):>5}{sum(outputs):>16,}"
            f"{f'{min(outputs):,} to {max(outputs):,}':>18}{sum(r['stopped'] for r in cell):>9}"
            f"{sum(not r['whole'] for r in cell):>8}{stopped_failed:>11}{stopped_passed:>11}"
            f"{went_failed:>9}{went_passed:>9}"
        )
    for key in (("full_context", "padded"), ("single_shot", "padded")):
        failed = sorted(r["scenario"] for r in cells[key] if not r["whole"])
        unstopped_failed = sorted(r["scenario"] for r in cells[key] if not r["whole"] and not r["stopped"])
        print(f"\n{key[0]}, {key[1]}: failed {failed}")
        print(f"  failed without a stopped call: {unstopped_failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
