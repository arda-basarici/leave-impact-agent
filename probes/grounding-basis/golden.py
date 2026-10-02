"""The grounding replay's basis on the sealed golden world: does the world index build, and does
every requirement clause's text name its scope.

The twenty-seed measurement beside this file (`probe.py`) found, on throwaway worlds of
generator version 15, that every requirement clause names its sealed target once the
titles contained in a longer found title are set aside. The evaluator is about to refuse,
at loading, a world where that does not hold (the investigator milestone's fourth build
step, ruling 3's fourth property), and the one world the results are reported on was sealed
at generator version 14 and has never been asked. This asks it first, with counts and no
refusal, so that a failure arrives as a finding to rule and never as a load that stops.

The world is loaded as the evaluator loads it today (the three sealed files joined, every
sealed key reproduced by today's rules), then indexed by the evaluator's own
`index_world`, the function the loader will call. Unlike the throwaway worlds, this one
holds its real prose: the sections and comments a model wrote and the record accepted.

Declared before the run:

- the world loads, which is the reproduction of its thirty sealed keys;
- the index reports no problem of any kind: no record or part sealed twice, every authored
  fact's carrier in a sealed record, every requirement clause scoped exactly once and by a
  pairing that names it, every section-kind target in a document of one section, and every
  requirement clause's text resolving to its sealed target.

Recorded with no criterion: how many records, parts, carriers and statements the world
holds; the statements by the number of carriers stating them; the scoped clauses by the
kind of their target; and in how many clauses plain containment finds more than one
title, the case the longest-title rule exists for.

The capture holds counts and the problem kinds, and no record, clause or scenario id: a
problem's detail names ids, which are the benchmark's private truth, and is not written.

Read-only: three objects are read by key through the object-store reader, nothing is
listed or written to a bucket. It runs from a workstation under the administrative
`leave-impact` profile, the one identity that reads both buckets; the inventory is the
stream's fixed record, handed in through `LEAVE_IMPACT_SEALED_INVENTORY`, and names the
golden world's version and the two buckets.

Run: `uv run python probes/grounding-basis/golden.py` with the profile and the inventory
variable set. Exit 0 only when both declarations hold and the capture was written.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from leaveimpact.adapters.object_store.s3 import S3ObjectReader, s3_client
from leaveimpact.core.entities import CalendarEvent, Document, WorkItem
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.refs import clause_ref
from leaveimpact.evaluator.sealed_world import SealedWorld, SealedWorldRefused, load_sealed_world
from leaveimpact.evaluator.world_index import index_world

INVENTORY_VARIABLE = "LEAVE_IMPACT_SEALED_INVENTORY"
CAPTURES = Path(__file__).resolve().parent.parent / "captures" / "grounding-basis"


def measure(world: SealedWorld) -> dict:
    """The index's counts and its problems by kind, for ``world``: no id, no content."""
    index, problems = index_world(world.org, world.scenarios)
    titles = [
        record.title
        for record in index.records.values()
        if isinstance(record, WorkItem | CalendarEvent | Document)
    ]
    titles_found: Counter = Counter()
    for clause in index.scope:
        sealed = index.parts.get(clause_ref(clause))
        text = "" if sealed is None else sealed.content.text
        titles_found[len({title for title in titles if title in text})] += 1
    return {
        "records": len(index.records),
        "parts": len(index.parts),
        "carriers": len(index.carried),
        "authored_facts": sum(len(facts) for facts in index.carried.values()),
        "statements": len(index.statements),
        "statements_by_carriers": dict(
            sorted(Counter(len(carriers) for carriers in index.statements.values()).items())
        ),
        "scoped_clauses": len(index.scope),
        "scoped_clauses_by_target_kind": dict(
            sorted(Counter(target.kind.value for target in index.scope.values()).items())
        ),
        "scoped_clauses_by_titles_found_in_their_text": dict(sorted(titles_found.items())),
        "problems": dict(sorted(Counter(problem.kind.value for problem in problems).items())),
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

    measured = measure(world)
    holds = not measured["problems"]
    capture = {
        "probe": "grounding-basis, the golden world",
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "world_version": version,
        "generator_version": world.generator_version,
        "scenarios": len(world.scenarios),
        "sources": {
            name: {"key": source.key, "version_id": source.version_id, "sha256": source.digest}
            for name, source in (
                ("world_spec", world.world_spec),
                ("scenario_specs", world.scenario_specs),
                ("truth_manifest", world.truth_manifest),
            )
        },
        "run": 1,
        "declared": {
            "the world loads and its sealed keys are reproduced": True,
            "the index reports no problem of any kind": holds,
        },
        "index": measured,
    }
    CAPTURES.mkdir(parents=True, exist_ok=True)
    out = CAPTURES / "golden-world.json"
    out.write_text(json.dumps(capture, indent=2) + "\n", encoding="utf-8")

    print(
        f"golden world {version[:8]}..., {len(world.scenarios)} scenarios, sealed keys reproduced"
    )
    for name, value in measured.items():
        print(f"  {name:<46}{value or 'none'}")
    print(f"declared, no problem of any kind: {'HOLDS' if holds else 'FAILS'}; capture {out}")
    return 0 if holds else 1


if __name__ == "__main__":
    sys.exit(main())
