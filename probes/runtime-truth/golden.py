"""Runtime truth on the sealed golden world: how many graded items rest on the choice of view.

The forty-seed measurement beside this file (`probe.py`) counts, over throwaway worlds, how
often the dated view and runtime truth judge a candidate differently. This asks the same of
the one world the results are reported on, through the evaluator's own code: the world is
loaded as the evaluator loads it (the three sealed files joined, every sealed key
reproduced by today's rules) and `compare_views` is run under the normal condition and
under each single-source outage.

Declared before the first run:

- the world loads, which is the reproduction of its thirty sealed keys;
- under the normal condition no must-assess pair and no outcome differs between the
  views, since world assembly proved every key under both before the world was sealed. A
  difference there fails the probe.

Everything else is a count to record, with no criterion: the pairs outside the must-assess
set that differ under each condition, how many of them flip the verdict, how many scenarios
hold one. On forty throwaway worlds twenty-three held at least one such pair under the
normal condition, so one is expected here and none would not be a failure.

The capture holds counts per condition and no candidate, artifact or scenario id: what
`compare_views` returns names them, and they are the benchmark's private truth.

Read-only: three objects are read by key through the object-store reader, nothing is
listed or written to a bucket. It runs from a workstation under the administrative
`leave-impact` profile, the one identity that reads both buckets; the inventory is the
stream's fixed record, handed in through `LEAVE_IMPACT_SEALED_INVENTORY`, and names the
golden world's version and the two buckets.

Run: `uv run python probes/runtime-truth/golden.py` with the profile and the inventory
variable set. Exit 0 only when both declarations hold and the capture was written.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from leaveimpact.adapters.object_store.s3 import S3ObjectReader, s3_client
from leaveimpact.core.enums import Source
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.ids import WorldVersion
from leaveimpact.evaluator.characterization import compare_views
from leaveimpact.evaluator.sealed_world import SealedWorldRefused, load_sealed_world

INVENTORY_VARIABLE = "LEAVE_IMPACT_SEALED_INVENTORY"
CAPTURES = Path(__file__).resolve().parent.parent / "captures" / "runtime-truth"
NORMAL = RunCondition.all_reachable()
CONDITIONS = {"normal": NORMAL} | {
    f"{source.value}_down": NORMAL.without(source) for source in Source
}


def main() -> int:
    path = os.environ.get(INVENTORY_VARIABLE)
    if path is None:
        print(f"{INVENTORY_VARIABLE} is not set; the inventory lives in the private stream")
        return 2
    inventory = json.loads(Path(path).read_text(encoding="utf-8"))
    version = WorldVersion(inventory["golden_chain"]["world_version"])
    client = s3_client(inventory.get("region", "eu-central-1"))
    truth = S3ObjectReader(client, inventory["buckets"]["truth"])
    world_store = S3ObjectReader(client, inventory["buckets"]["world"])
    try:
        world = load_sealed_world(version, truth, world_store)
    except SealedWorldRefused as refused:
        # The message is content-free by construction; the findings are not printed.
        print(f"the world did not load: {refused}")
        return 1

    rows = []
    for name, condition in CONDITIONS.items():
        comparison = compare_views(world, condition)
        differences = comparison.verdict_differences
        probed = [difference for difference in differences if difference.probed]
        other = [difference for difference in differences if not difference.probed]
        rows.append(
            {
                "condition": name,
                "impacts": comparison.impacts,
                "must_assess_pairs": comparison.probed_pairs,
                "must_assess_differ": len(probed),
                "other_pairs": comparison.other_pairs,
                "other_differ": len(other),
                "other_differ_verdict_flips": sum(difference.flips for difference in other),
                "outcomes_differ": len(comparison.outcome_differences),
                "scenarios_with_a_difference": len(
                    {difference.scenario_id for difference in differences}
                    | {scenario_id for scenario_id, _ in comparison.outcome_differences}
                ),
            }
        )

    normal = rows[0]
    holds = normal["must_assess_differ"] == 0 and normal["outcomes_differ"] == 0
    capture = {
        "probe": "runtime-truth, the golden world",
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "world_version": version,
        "generator_version": world.generator_version,
        "scenarios": len(world.scenarios),
        "organization": len(world.org.employees),
        "sources": {
            name: {"key": source.key, "version_id": source.version_id, "sha256": source.digest}
            for name, source in (
                ("world_spec", world.world_spec),
                ("scenario_specs", world.scenario_specs),
                ("truth_manifest", world.truth_manifest),
            )
        },
        "declared": {
            "the world loads and its sealed keys are reproduced": True,
            "normal condition: no must-assess pair and no outcome differs": holds,
        },
        "conditions": rows,
    }
    CAPTURES.mkdir(parents=True, exist_ok=True)
    out = CAPTURES / "golden-world.json"
    out.write_text(json.dumps(capture, indent=2) + "\n", encoding="utf-8")

    print(f"golden world {version[:8]}…, {len(world.scenarios)} scenarios, "
          f"organization of {len(world.org.employees)}, sealed keys reproduced")
    print(f"{'condition':<15}{'must-assess differ':>22}{'other differ (flips)':>26}"
          f"{'outcomes differ':>18}{'scenarios':>11}")
    for row in rows:
        print(
            f"{row['condition']:<15}"
            f"{row['must_assess_differ']:>8} of {row['must_assess_pairs']:<10}"
            f"{row['other_differ']:>8} ({row['other_differ_verdict_flips']}) of "
            f"{row['other_pairs']:<8}"
            f"{row['outcomes_differ']:>8} of {row['impacts']:<6}"
            f"{row['scenarios_with_a_difference']:>8}"
        )
    print(f"declared, normal condition: {'HOLDS' if holds else 'FAILS'}; capture {out}")
    return 0 if holds else 1


if __name__ == "__main__":
    sys.exit(main())
