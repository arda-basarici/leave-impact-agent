"""The measurement world's acceptance draw: the scenarios traced and the filler documents read.

PROTOCOL ("How the measurement world is accepted") fixes two samples before the world is
bound: one scenario per tier traced by the audit method, and five filler documents read by
a model of another family than the writer's. Both are "drawn by the same rule" as the
development draw the prompt check used (`probes/prompt-check/development_world.py`): a
stream derived from the frozen registration's statistics seed, the draw's name and, for
the scenarios, the tier's name; each population's ids sorted first, then sampled. The rule
is mechanical and fixed by the frozen file, so nobody chooses what is read, and it is
rerunnable: the same world and the same registration give the same draw.

The draw is written to the git-ignored audit directory as a small JSON object the filler
read and the rulings record cite, with each scenario's tier beside its id, because the
records are private; the public FINDINGS entry lists the three scenarios as bare ids, as
the development six are listed, since a scenario's tier is sealed. Nothing of the seed or
the semantic digest is read or printed here.

Usage: ``python probes/measurement-acceptance/draw.py <world_version>`` with
``AWS_PROFILE`` set to a principal that reads both buckets.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from random import Random

import boto3

from leaveimpact.adapters.object_store.s3 import S3ObjectReader
from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.registration_json import decode_registration_bytes
from leaveimpact.evaluator.intervals import derived_seed
from leaveimpact.evaluator.sealed_world import SealedWorld, load_sealed_world
from leaveimpact.world.scenario import Tier

REPOSITORY = Path(__file__).resolve().parents[2]
REGISTRATION_FILE = REPOSITORY / "preregistration" / "registration.json"
OUT_DIR = REPOSITORY / "data" / "audit"
REGION = "eu-central-1"
TRUTH_BUCKET = "leave-impact-truth-445743457479"
WORLD_BUCKET = "leave-impact-world-445743457479"

TRACES_PER_TIER = 1
FILLER_DOCUMENTS = 5
TRACE_DRAW = "acceptance-traces"
FILLER_DRAW = "acceptance-filler"


def require_ignored(path: Path) -> None:
    """The draw names sealed tiers: it is written where git ignores it and nowhere else."""
    done = subprocess.run(
        ["git", "-C", str(REPOSITORY), "check-ignore", "-q", str(path)],
        capture_output=True,
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(f"{path} is not git-ignored; the draw is private and stays unwritten")


def sealed_world(version: WorldVersion) -> SealedWorld:
    s3 = boto3.Session(region_name=REGION).client("s3")
    return load_sealed_world(
        version, S3ObjectReader(s3, TRUTH_BUCKET), S3ObjectReader(s3, WORLD_BUCKET)
    )


def trace_draw(world: SealedWorld, seed: int) -> dict[ScenarioId, str]:
    """One scenario per tier: each tier's ids sorted and sampled by its own derived stream."""
    drawn: dict[ScenarioId, str] = {}
    for tier in Tier:
        ids = sorted(s.spec.id for s in world.scenarios if s.key.tier is tier)
        if len(ids) < TRACES_PER_TIER:
            raise ValueError(f"the {tier.value} tier has {len(ids)} scenarios, fewer than drawn")
        for scenario_id in Random(derived_seed(seed, TRACE_DRAW, tier.value)).sample(
            ids, TRACES_PER_TIER
        ):
            drawn[scenario_id] = tier.value
    return dict(sorted(drawn.items()))


def filler_draw(world: SealedWorld, seed: int) -> list[str]:
    """Five documents of the sealed filler pool, ids sorted and sampled by one derived stream."""
    ids = sorted(ref.id for ref in world.filler)
    if len(ids) < FILLER_DOCUMENTS:
        raise ValueError(f"the filler pool holds {len(ids)} documents, fewer than drawn")
    return sorted(Random(derived_seed(seed, FILLER_DRAW)).sample(ids, FILLER_DOCUMENTS))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: draw.py <world_version>", file=sys.stderr)
        return 2
    version = WorldVersion(sys.argv[1])
    path = OUT_DIR / f"acceptance_draw_{version[:8]}.json"
    require_ignored(path)
    seed = decode_registration_bytes(REGISTRATION_FILE.read_bytes()).statistics.seed
    world = sealed_world(version)
    traces = trace_draw(world, seed)
    filler = filler_draw(world, seed)
    record = {
        "world_version": version,
        "rule": (
            "Random(derived_seed(statistics.seed, name[, tier])).sample over sorted ids; "
            "the seed is preregistration/registration.json's statistics.seed"
        ),
        "statistics_seed": seed,
        "traces": {"name": TRACE_DRAW, "per_tier": TRACES_PER_TIER, "scenarios": traces},
        "filler": {
            "name": FILLER_DRAW,
            "count": FILLER_DOCUMENTS,
            "pool_size": len(world.filler),
            "documents": filler,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"statistics seed {seed}; filler pool {len(world.filler)}")
    for scenario_id, tier in traces.items():
        print(f"trace {scenario_id} ({tier})")
    print("filler " + " ".join(filler))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
