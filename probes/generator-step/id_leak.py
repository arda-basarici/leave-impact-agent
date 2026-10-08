"""How far an identifier predicts a scenario's tier, under three construction orders.

The generator step's measurement (2026-10-08), model-free. ``tree`` is the order the tree
draws, ``plan`` the plan's own row order and ``random`` a shuffle from a generator of the
probe's own, the last two patched in at the module seam; the result is `id_leak_tree.md`,
which FINDINGS, ``generator-step``, reads. `id_leak_group0.md` beside it is the earlier
comparison this script's first form made before the tier-shuffle ruling, on the tree at
`a6c40ef`, where the order was scarcity first and a function of the organization and the
plan: that column cannot be regenerated on a tree that no longer holds the order, and
that run's sample read no pending prose identifier (the close's review), so it stands
as recorded and is read beside the table this script writes.

For each seed the golden plan is assembled three ways: the tree's scarcity-first order, plain
plan order, and a seeded random order (the order patched at the module seam). For each
successful assembly the probe asks, per identifier kind the model can see, how well the id's
number predicts the scenario's tier: the best accuracy of a two-threshold classifier over
the id numbers with tiers ordered by their median id, and whether the three tiers' id
ranges are pairwise disjoint. The window's start date is measured the same way as the
baseline the slot permutation removes. Failures are counted by exception type.

Run from the repository root:
``PYTHONPATH=. uv run python <this file> [--seeds N] [--out DIR]``.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from random import Random

from leaveimpact.world import assembly
from leaveimpact.world.assembly import assemble_semantic_world
from leaveimpact.world.briefs import SectionTarget
from leaveimpact.world.org import DEFAULT_PARAMS
from leaveimpact.world.scenario import Tier

WORLD_START = date(2026, 1, 1)
PLAN = "golden"
TIERS = (Tier.STRUCTURED, Tier.FRAGMENTED, Tier.ADVERSARIAL)


def number_of(id: str) -> int:
    return int(id.rsplit("_", 1)[1])


def observations(world) -> dict[str, list[tuple[int, str]]]:  # noqa: ANN001
    """Per identifier kind, (number, tier) for every id a run over that scenario could see."""
    tier_of = {row.scenario_id: row.tier.value for row in world.plan}
    seen: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for scenario in world.scenarios:
        tier = tier_of[scenario.spec.id]
        seen["leave (investigated)"].append((number_of(scenario.spec.leave_id), tier))
        seen["window start (ordinal)"].append((scenario.spec.window.start.toordinal(), tier))
        owned = scenario.owned
        for planted in owned.leaves:
            seen["leave (owned)"].append((number_of(planted.entity.id), tier))
            seen["employee (on leave)"].append((number_of(planted.entity.employee_id), tier))
        for planted in owned.work_items:
            seen["work item"].append((number_of(planted.entity.id), tier))
            for comment in planted.entity.comments:
                seen["comment"].append((number_of(comment.id), tier))
        for planted in owned.events:
            seen["event"].append((number_of(planted.entity.id), tier))
        for planted in owned.documents:
            seen["document"].append((number_of(planted.entity.id), tier))
            for section in planted.entity.sections:
                seen["clause"].append((number_of(section.id), tier))
        # The semantic world holds a pending section or comment as a brief, not as a record
        # of its document or work item; a run sees its id all the same once prose is
        # composed, so the sample reads the briefs' targets too (the close's review found
        # the first form counting 17 clauses and no comments of 26 and 3 on seed 6).
        for brief in scenario.briefs:
            kind = "clause" if isinstance(brief.target, SectionTarget) else "comment"
            seen[kind].append((number_of(brief.target.id), tier))
    return seen


def threshold_accuracy(rows: list[tuple[int, str]]) -> float:
    """The best two-threshold classifier's accuracy, tiers ordered by their median number."""
    by_tier = defaultdict(list)
    for number, tier in rows:
        by_tier[tier].append(number)
    present = [t for t in TIERS if by_tier.get(t.value)]
    if len(present) < 2:
        return 1.0
    order = sorted(present, key=lambda t: statistics.median(by_tier[t.value]))
    numbers = sorted({n for n, _ in rows})
    cuts = [float("-inf"), *[(a + b) / 2 for a, b in zip(numbers, numbers[1:])], float("inf")]
    best = 0
    if len(order) == 2:
        for c in cuts:
            hit = sum((n <= c) == (t == order[0].value) for n, t in rows)
            best = max(best, hit)
    else:
        for i, c1 in enumerate(cuts):
            for c2 in cuts[i:]:
                hit = 0
                for n, t in rows:
                    predicted = order[0] if n <= c1 else order[1] if n <= c2 else order[2]
                    hit += predicted.value == t
                best = max(best, hit)
    return best / len(rows)


def ranges_disjoint(rows: list[tuple[int, str]]) -> bool:
    spans = {}
    for tier in TIERS:
        numbers = [n for n, t in rows if t == tier.value]
        if numbers:
            spans[tier] = (min(numbers), max(numbers))
    items = list(spans.values())
    return all(a[1] < b[0] or b[1] < a[0] for i, a in enumerate(items) for b in items[i + 1 :])


def random_order(seed: int):  # noqa: ANN202
    """A shuffle from a generator of the probe's own, so it is not the tree's draw."""

    def order(rng, count):  # noqa: ANN001
        indices = list(range(count))
        Random(seed ^ 0x5EED).shuffle(indices)
        return tuple(indices)

    return order


def plan_order(rng, count):  # noqa: ANN001
    return tuple(range(count))


def assemble(seed: int, variant: str):  # noqa: ANN202
    """``tree`` assembles as the tree does; ``plan`` and ``random`` patch the order at the
    module seam, which takes ``(rng, count)`` since generator version 17."""
    original = assembly.construction_order
    if variant == "random":
        assembly.construction_order = random_order(seed)
    elif variant == "plan":
        assembly.construction_order = plan_order
    try:
        started = time.perf_counter()
        world = assemble_semantic_world(seed, DEFAULT_PARAMS, WORLD_START, PLAN)
        return world, None, time.perf_counter() - started
    except Exception as exc:  # noqa: BLE001 - the probe counts every failure by type
        return None, type(exc).__name__, time.perf_counter() - started
    finally:
        assembly.construction_order = original


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    seeds = list(range(101, 101 + args.seeds))

    results: dict[str, dict] = {}
    for variant in ("tree", "plan", "random"):
        failures: Counter[str] = Counter()
        times: list[float] = []
        accuracy: dict[str, list[float]] = defaultdict(list)
        disjoint: Counter[str] = Counter()
        for seed in seeds:
            world, failure, seconds = assemble(seed, variant)
            times.append(seconds)
            if world is None:
                failures[failure or "?"] += 1
                print(f"{variant} seed {seed}: {failure} ({seconds:.1f}s)", flush=True)
                continue
            for kind, rows in observations(world).items():
                accuracy[kind].append(threshold_accuracy(rows))
                disjoint[kind] += ranges_disjoint(rows)
            print(f"{variant} seed {seed}: ok ({seconds:.1f}s)", flush=True)
        built = len(seeds) - sum(failures.values())
        results[variant] = {
            "built": built,
            "failures": dict(failures),
            "seconds_mean": statistics.mean(times),
            "seconds_max": max(times),
            "leak": {
                kind: {
                    "accuracy_mean": statistics.mean(values),
                    "accuracy_min": min(values),
                    "ranges_disjoint_in": disjoint[kind],
                    "of": built,
                }
                for kind, values in sorted(accuracy.items())
            },
        }

    lines = ["# Id leak and construction-order feasibility", "",
             f"Seeds {seeds[0]} to {seeds[-1]}, plan `{PLAN}`, world start {WORLD_START}.", ""]
    for variant, r in results.items():
        lines += [f"## {variant} order: built {r['built']} of {len(seeds)}, failures {r['failures']}, "
                  f"{r['seconds_mean']:.1f}s mean, {r['seconds_max']:.1f}s max", "",
                  "| identifier kind | accuracy mean | accuracy min | tier ranges disjoint |",
                  "|---|---|---|---|"]
        for kind, v in r["leak"].items():
            lines.append(f"| {kind} | {v['accuracy_mean']:.2f} | {v['accuracy_min']:.2f} | "
                         f"{v['ranges_disjoint_in']} of {v['of']} |")
        lines.append("")
    report = "\n".join(lines)
    print(report)
    (args.out / "id_leak_tree.md").write_text(report, encoding="utf-8")
    (args.out / "id_leak_tree.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
