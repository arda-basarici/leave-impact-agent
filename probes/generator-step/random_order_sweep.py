"""The feasibility sweep of the golden plan under the random construction order, model-free.

The generator step's measurement after its tier-shuffle ruling (2026-10-08); FINDINGS,
``reservation-book``, run 4, holds the result (`random_order_sweep.md`).

The golden plan is assembled over seeds 1 to 200 on the tree as built (the order drawn from
the world's generator after the row seeds), as the 15.5 sweep recorded the scarcity-first
order (FINDINGS, ``reservation-book``, run 3: 199 admitted, 1 exhausted). Outcomes are
counted by exception type, and a reservation exhaustion by the class refused; the seeds
refused are listed so the record names them.

Run from the repository root:
``PYTHONPATH=. uv run python <this file> [--first 1] [--last 200] [--out DIR]``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

from leaveimpact.world.assembly import assemble_semantic_world
from leaveimpact.world.construction import ReservationExhausted
from leaveimpact.world.org import DEFAULT_PARAMS

WORLD_START = date(2026, 1, 1)
PLAN = "golden"


def attempt(seed: int) -> dict[str, object]:
    started = time.perf_counter()
    try:
        assemble_semantic_world(seed, DEFAULT_PARAMS, WORLD_START, PLAN)
        outcome: dict[str, object] = {"seed": seed, "outcome": "admitted"}
    except ReservationExhausted as exc:
        outcome = {
            "seed": seed,
            "outcome": "exhausted",
            "class": exc.who,
            "scenario": str(exc.scenario_id),
            "universe": exc.universe,
            "eliminated": exc.eliminated,
        }
    except Exception as exc:  # noqa: BLE001 - the sweep counts every failure by type
        outcome = {"seed": seed, "outcome": type(exc).__name__, "message": str(exc)[:200]}
    outcome["seconds"] = round(time.perf_counter() - started, 2)
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--last", type=int, default=200)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    seeds = range(args.first, args.last + 1)
    started = time.perf_counter()
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(attempt, seeds))
    elapsed = time.perf_counter() - started
    outcomes = Counter(str(row["outcome"]) for row in rows)
    exhausted = [row for row in rows if row["outcome"] == "exhausted"]
    by_class = Counter(str(row["class"]) for row in exhausted)
    refused = [row for row in rows if row["outcome"] != "admitted"]
    mean_seconds = sum(float(row["seconds"]) for row in rows) / len(rows)
    lines = [
        f"# The golden plan under the random construction order, seeds {seeds.start} to "
        f"{seeds.stop - 1}",
        "",
        f"Wall {elapsed:.0f} s across processes, {mean_seconds:.1f} s a world.",
        "",
        "| outcome | seeds |",
        "|---|---|",
        *(f"| {name} | {count} |" for name, count in sorted(outcomes.items())),
        "",
        "Exhaustions by class: "
        + (", ".join(f"{name} {count}" for name, count in sorted(by_class.items())) or "none"),
        "",
        "Refused seeds: "
        + (", ".join(f"{row['seed']} ({row['outcome']}" + (f", {row['class']}" if "class" in row else "") + ")" for row in refused) or "none"),
    ]
    (args.out / "random_order_sweep.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (args.out / "random_order_sweep.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
