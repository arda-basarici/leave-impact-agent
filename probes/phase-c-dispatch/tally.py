"""The phase C operational tally: per cell, what the runs cost and how their calls ended.

FINDINGS cites the phase's operational numbers (cost per cell against the freeze's basis,
calls and tokens per run, how many one-call runs stopped at the output maximum, endings
and recoveries) and a number cited needs a script in the tree behind it. This reads the
ledger `dispatch.py` wrote, fetches each finished run's export from the world bucket by
the object identity the job log printed, and prints one row per cell. Nothing here is a
correctness measure: the evaluator's artifact under the bound registration is the only
reading of the runs' answers, and this script never opens a claim or a stated fact.

A total is printed only over complete costs: a run that made a model call and records
no cost, or a cost the record marks incomplete (a lower bound), is refused by run id
rather than summed as zero or as the bound, since a silent zero in one row is a wrong
total in the last (the external read of 2026-10-17). A rules-only run records no cost
and made no call, and counts as zero.

Usage, from the repository root with `gh` logged in and the SSO profile valid:

    uv run python probes/phase-c-dispatch/tally.py

The exports are cached under `data/phase-c-dispatch/exports/` (git-ignored) so a rerun
costs no bucket reads.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
LEDGER_FILE = HERE / "ledger.jsonl"
CACHE = REPOSITORY / "data" / "phase-c-dispatch" / "exports"
BUCKET = "leave-impact-world-445743457479"
PROFILE = "leave-impact"
OBJECT_IDENTITY = re.compile(r"object_identity=(\S+)")


def export_of(run_id: int) -> dict:
    cached = CACHE / f"{run_id}.json"
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    log = subprocess.run(
        ["gh", "run", "view", str(run_id), "--log"], capture_output=True, text=True, check=True
    ).stdout
    match = OBJECT_IDENTITY.search(log)
    if match is None:
        raise RuntimeError(f"run {run_id}: the job log prints no object identity")
    body = subprocess.run(
        ["aws", "s3", "cp", f"s3://{BUCKET}/{match.group(1)}", "-", "--profile", PROFILE],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(body, encoding="utf-8")
    return json.loads(body)


def complete_cost_usd(export: dict, run_id: int) -> float:
    record = export["record"]
    cost = record["cost"]
    if cost is None:
        if record["usage"]["model_calls"]:
            raise RuntimeError(f"{run_id}: model calls were made and no cost is recorded")
        return 0.0
    if not cost["complete"]:
        raise RuntimeError(f"{run_id}: the recorded cost is a lower bound, not a total")
    return cost["pico_usd"] / 1e12


def row_of(export: dict, run_id: int) -> dict:
    record = export["record"]
    counters = {c["name"]: c["value"] for c in record["usage"]["counters"]}
    calls = export["trace"]["model_calls"]
    saturated = any(
        d["observation"].get("stop_reason") == "max_tokens" for c in calls for d in c["dispatches"]
    )
    unparsed = any(b["kind"] != "parsed" for c in calls for b in c["answer"]["fact_batches"])
    return {
        "calls": record["usage"]["model_calls"],
        "input": counters.get("input_tokens", 0),
        "output": counters.get("output_tokens", 0),
        "cost": complete_cost_usd(export, run_id),
        "saturated": saturated,
        "unparsed": unparsed,
        "operations": len(export["trace"]["operations"]),
    }


def main() -> int:
    records = [
        json.loads(line)
        for line in LEDGER_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    finished = [r for r in records if r["kind"] == "finished"]
    cells: dict[str, list[dict]] = {}
    for r in finished:
        system, level, _ = r["key"].split("/")
        row = row_of(export_of(r["run_id"]), r["run_id"])
        row["ending"] = r["markers"]["work.detail"]
        row["recoveries"] = int(r["markers"]["status.recoveries"] or 0)
        cells.setdefault(f"{system}/{level}", []).append(row)
    header = (
        f"{'cell':<22}{'runs':>5}{'cost $':>9}{'mean $':>8}{'calls':>9}{'input tokens':>18}"
        f"{'saturated':>10}{'unparsed':>9}{'completed':>10}{'recov':>6}"
    )
    print(header)
    total = 0.0
    for cell, rows in cells.items():
        cost = sum(r["cost"] for r in rows)
        total += cost
        calls = [r["calls"] for r in rows]
        inputs = [r["input"] for r in rows]
        print(
            f"{cell:<22}{len(rows):>5}{cost:>9.4f}{cost / len(rows):>8.4f}"
            f"{f'{min(calls)}-{max(calls)}':>9}{f'{min(inputs):,}-{max(inputs):,}':>18}"
            f"{sum(r['saturated'] for r in rows):>10}{sum(r['unparsed'] for r in rows):>9}"
            f"{sum(r['ending'] == 'completed' for r in rows):>10}"
            f"{sum(r['recoveries'] for r in rows):>6}"
        )
    print(f"{'all':<22}{len(finished):>5}{total:>9.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
