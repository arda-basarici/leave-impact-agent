"""The released golden world under ``docs/golden-world``, as CI holds it without bucket
access: the three committed files are the world the demo serves, by content.

The world version is the digest over the three files' canonical bytes, so the evaluator's
own loader proves the release without reading a bucket: it decodes the world spec, checks
the digests it cites against the other two files, recomputes the version and requires it
to be the one named. The test names the version the demo configuration serves, so a
release of another world, a file edited after the fact, or a configuration moved to a
world whose files are not released is a failure here. The index beside the files states
their digests and the version; the test holds the index to the files. The comparison with
the buckets' bytes is the offline acceptance script's, under the administrator profile.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from leaveimpact.adapters.object_store.read import StoredObject
from leaveimpact.app.config import committed_configuration
from leaveimpact.core.ids import WorldVersion
from leaveimpact.evaluator.sealed_world import SealedWorld, join_sealed_world
from leaveimpact.world.artifacts import SCENARIO_SPECS, TRUTH_MANIFEST, WORLD_SPEC
from leaveimpact.world.disclosure import Disclosure

RELEASE = Path(__file__).resolve().parents[2] / "docs" / "golden-world"
FILES = (WORLD_SPEC, SCENARIO_SPECS, TRUTH_MANIFEST)
HEX64 = re.compile(r"[0-9a-f]{64}")


def released(name: str) -> StoredObject:
    return StoredObject(name, (RELEASE / name).read_bytes(), "committed")


def joined() -> SealedWorld:
    served = WorldVersion(committed_configuration().served_world_version)
    return join_sealed_world(served, *(released(name) for name in FILES))


def test_the_released_files_are_the_served_world_by_content() -> None:
    world = joined()
    assert world.version == committed_configuration().served_world_version
    assert world.disclosure is Disclosure.OPEN
    assert len(world.scenarios) == 30
    assert world.generator_version == "14"


def test_the_index_states_the_files_digests_and_the_version() -> None:
    index = (RELEASE / "README.md").read_text(encoding="utf-8")
    stated = set(HEX64.findall(index))
    digests = {hashlib.sha256((RELEASE / name).read_bytes()).hexdigest() for name in FILES}
    world = joined()
    assert digests <= stated
    assert world.version in stated
    assert world.semantic_digest in stated
    for name in FILES:
        assert f"`{name}`" in index
        size = f"{len((RELEASE / name).read_bytes()):,}"
        assert size in index, f"the index states {name}'s size"


def test_every_scenario_carries_its_key() -> None:
    world = joined()
    ids = sorted(scenario.spec.id for scenario in world.scenarios)
    assert ids == [f"scenario_{n:03d}" for n in range(1, 31)]
    for scenario in world.scenarios:
        assert scenario.key.impacts, f"{scenario.spec.id} has an expected impact"
