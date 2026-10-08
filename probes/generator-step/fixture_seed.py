"""The throwaway world's properties by seed, so a fixture seed is read off a table.

The generator step's measurement after version 17 moved every world (2026-10-08);
FINDINGS, ``generator-step``, holds the result (`fixture_seed.md`).

Generator version 17 moved every world, and four evaluator tests assert a property the
throwaway world of seed 7 no longer holds (a candidate whose verdict the two views flip, a
target planted by another scenario, the Jira-outage split of seed 10, a clause whose target's
title contains another ticket's). The tests say a bump that moves the property needs another
seed; this probe says which seeds hold which, over a range, on the tree as built, so the
choice is a reading of a table and not a guess, and so the rate at which the properties occur
is known (a property present on no seed would be structural, not chance).

Run from the repository root:
``PYTHONPATH=. uv run python <this file> [--first 2] [--last 40] [--out DIR]``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from leaveimpact.core import EntityKind, RunCondition, Source, Verdict
from leaveimpact.core.entities import CalendarEvent, Document, WorkItem
from leaveimpact.evaluator.characterization import compare_views
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.retrieval_targets import retrieval_targets
from leaveimpact.evaluator.world_index import index_world, statement_of
from leaveimpact.world.construction import ConstructionError
from tests.unit.throwaway_world import composed_world, loaded_world

NORMAL = RunCondition.all_reachable()
JIRA_DOWN = NORMAL.without(Source.JIRA)
CALENDAR_DOWN = NORMAL.without(Source.CALENDAR)


def foreign_targets(world, condition) -> tuple[int, int]:  # noqa: ANN001
    own = foreign = 0
    for scenario in world.scenarios:
        oracle = oracle_for(world, scenario, condition)
        if not isinstance(oracle, Answerable):
            continue
        planted = {statement_of(fact) for fact in scenario.authored_facts}
        for target in retrieval_targets(world, oracle):
            if target.statement in planted:
                own += 1
            else:
                foreign += 1
    return own, foreign


def jira_split_holds(world) -> bool:  # noqa: ANN001
    if compare_views(world, NORMAL).counts()["must-assess verdicts"] != 0:
        return False
    down = compare_views(world, JIRA_DOWN)
    probed = [d for d in down.verdict_differences if d.probed]
    if len(probed) != 1:
        return False
    [split] = probed
    return (
        split.dated == (Verdict.UNKNOWN, ())
        and split.runtime == (Verdict.VIABLE, ())
        and down.unknown_differences == (split.scenario_id,)
        and down.scenarios_differing == {split.scenario_id}
    )


def qualified_title_shape_holds(seed: int) -> bool:
    world = composed_world("golden", seed)
    index, problems = index_world(world.org, world.scenarios)
    if problems:
        return False
    titles = {}
    for ref, record in index.records.items():
        if ref.kind is EntityKind.WORK_ITEM and isinstance(record, WorkItem | CalendarEvent | Document):
            titles[ref] = record.title
    return any(
        ref != target and title in titles[target]
        for target in index.scope.values()
        if target.kind is EntityKind.WORK_ITEM
        for ref, title in titles.items()
    )


def probe(seed: int) -> dict[str, object]:
    started = time.perf_counter()
    try:
        world = loaded_world("golden", seed)
    except ConstructionError as exc:
        return {"seed": seed, "builds": False, "refusal": type(exc).__name__}
    normal = compare_views(world, NORMAL)
    counts = normal.counts()
    row: dict[str, object] = {
        "seed": seed,
        "builds": True,
        "foreign_normal": foreign_targets(world, NORMAL)[1],
        "foreign_calendar_down": foreign_targets(world, CALENDAR_DOWN)[1],
        "differing_parts": sorted(part for part, count in counts.items() if count),
        "verdict_differences": len(normal.verdict_differences),
        "flips": sum(1 for d in normal.verdict_differences if d.flips),
        "jira_split": jira_split_holds(world),
        "qualified_title": qualified_title_shape_holds(seed),
        "seconds": round(time.perf_counter() - started, 1),
    }
    row["holds_seed_7_set"] = bool(
        row["foreign_normal"]
        and row["flips"]
        and row["differing_parts"] == ["other verdicts"]
        and row["qualified_title"]
    )
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=int, default=2)
    parser.add_argument("--last", type=int, default=40)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    seeds = range(args.first, args.last + 1)
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(probe, seeds))
    header = (
        "| seed | builds | foreign (normal) | foreign (calendar down) | differing parts | "
        "verdict differences | flips | jira split | qualified title | seed-7 set |"
    )
    lines = [
        f"# The throwaway world's properties by seed, {seeds.start} to {seeds.stop - 1}, "
        "generator version 17",
        "",
        header,
        "|" + "---|" * 10,
    ]
    for row in rows:
        if not row["builds"]:
            lines.append(f"| {row['seed']} | refused: {row['refusal']} | | | | | | | | |")
            continue
        lines.append(
            f"| {row['seed']} | yes | {row['foreign_normal']} | {row['foreign_calendar_down']} | "
            f"{', '.join(row['differing_parts']) or 'none'} | {row['verdict_differences']} | "
            f"{row['flips']} | {row['jira_split']} | {row['qualified_title']} | "
            f"{row['holds_seed_7_set']} |"
        )
    built = [row for row in rows if row["builds"]]
    lines += [
        "",
        f"Built {len(built)} of {len(rows)}; with a foreign target {sum(1 for r in built if r['foreign_normal'])}; "
        f"with a flip {sum(1 for r in built if r['flips'])}; with the Jira split "
        f"{sum(1 for r in built if r['jira_split'])}; with the qualified-title shape "
        f"{sum(1 for r in built if r['qualified_title'])}; holding seed 7's whole set "
        f"{sum(1 for r in built if r['holds_seed_7_set'])}.",
    ]
    (args.out / "fixture_seed.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (args.out / "fixture_seed.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
