"""Runtime truth on the sealed golden world: how many graded items rest on the choice of view.

The forty-seed measurement beside this file (`probe.py`) counts, over throwaway worlds, how
often the dated view and runtime truth judge a candidate differently. This asks the one
world the results are reported on, through the evaluator's own code: the world is loaded
as the evaluator loads it (the three sealed files joined, every sealed key reproduced by
today's rules) and `compare_views` puts the oracle's question to both views, under the
normal condition and under each single-source outage, and compares the two answers part
by part: whether the leave is readable, the impacts the rules ground, every organization
member's verdict and reasons for each impact both views expect, the open questions behind
an unknown verdict, the requirements, the outcomes, the expected constraints, conflicts
and unknowns.

Two runs, two captures. Run 01 (`golden-world.json`, at `23cf13f`) compared verdicts,
reasons and outcomes for the sealed impacts and nothing else, and found none differing;
its entry in FINDINGS first read that as "no graded item rests on the view", which the
comparison did not show under an outage (the batch review of 2026-10-01). Run 02
(`golden-world-run-02.json`, at `60b23e4`) made the complete comparison and found no part
differing under any condition. After it, a corpus outage was ruled to leave no claim-level
answer (the policy is unreadable, as the leave is with Frappe down), so a later run
compares nothing under that condition where run 02 compared thirty scenarios; a third
run, if made, writes `golden-world-run-03.json` and never over an earlier capture.

Declared, for run 02 and any later one:

- the world loads, which is the reproduction of its thirty sealed keys;
- under the normal condition every part the sealed key proves agrees between the views:
  the leave's readability, the impact sets, the must-assess verdicts, the requirements,
  the outcomes, the constraints, the conflicts and the unknowns, hence the open questions
  too. World assembly proved the key under both views before the world was sealed, so a
  difference there fails the probe. A verdict outside the must-assess set may differ and
  is recorded.

Everything under an outage is a count to record, with no criterion: nothing was proven
there. On six throwaway worlds the complete comparison found, under a Jira outage, two
must-assess verdicts and two unknown sets differing, and under a calendar outage four
other verdicts; so a difference here would be a finding about this world, and none would
be the sentence run 01 could not support.

The capture holds counts per condition and per part and no candidate, artifact or scenario
id: what `compare_views` returns names them, and they are the benchmark's private truth.

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
        rows.append(
            {
                "condition": name,
                "scenarios": comparison.scenarios,
                "answerable_in_both_views": comparison.answerable,
                "impacts_expected_in_both_views": comparison.impacts,
                "must_assess_pairs": comparison.probed_pairs,
                "other_pairs": comparison.other_pairs,
                "differing": comparison.counts(),
                "other_verdicts_that_flip": sum(
                    difference.flips
                    for difference in comparison.verdict_differences
                    if not difference.probed
                ),
                "scenarios_with_a_difference": len(comparison.scenarios_differing),
            }
        )

    normal = rows[0]
    proven = {part: n for part, n in normal["differing"].items() if part != "other verdicts"}
    holds = not any(proven.values())
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
        "run": 3,
        "declared": {
            "the world loads and its sealed keys are reproduced": True,
            "normal condition: every part the sealed key proves agrees between the views": holds,
        },
        "conditions": rows,
    }
    CAPTURES.mkdir(parents=True, exist_ok=True)
    out = CAPTURES / "golden-world-run-03.json"
    out.write_text(json.dumps(capture, indent=2) + "\n", encoding="utf-8")

    print(f"golden world {version[:8]}…, {len(world.scenarios)} scenarios, "
          f"organization of {len(world.org.employees)}, sealed keys reproduced")
    for row in rows:
        differing = {part: n for part, n in row["differing"].items() if n}
        print(
            f"{row['condition']:<15}answerable {row['answerable_in_both_views']:>2} of "
            f"{row['scenarios']}, impacts compared {row['impacts_expected_in_both_views']:>2}, "
            f"pairs {row['must_assess_pairs']} must-assess + {row['other_pairs']} other | "
            f"differing: {differing or 'nothing'} | scenarios with a difference "
            f"{row['scenarios_with_a_difference']}"
        )
    print(f"declared, normal condition: {'HOLDS' if holds else 'FAILS'}; capture {out}")
    return 0 if holds else 1


if __name__ == "__main__":
    sys.exit(main())
