"""A throwaway world assembled in process and sealed into in-memory stores: what the evaluator's
tests grade against.

Test infrastructure, like the in-memory ports beside it. The world is the reference seed
under a named plan, composed with stand-in prose and a record that accepts it, so it has
every shape a sealed world has (keys of all three tiers under the golden plan, briefs, a
record) and costs no model call; nothing here is sealed to a bucket, scored or projected.
The stores hold the three files under the keys the layout gives them, the world spec and
the truth manifest in the truth store and the scenario specs in the world store, which is
where the evaluator's loader looks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import cache

from leaveimpact.adapters.object_store.layout import (
    scenario_specs_key,
    truth_manifest_key,
    world_spec_key,
)
from leaveimpact.evaluator.sealed_world import SealedWorld, load_sealed_world
from leaveimpact.world import (
    DEFAULT_PARAMS,
    Bundle,
    WorldSpec,
    assemble_semantic_world,
    bundle,
    compose,
)
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.prose_fixture import record_for

WORLD_START = date(2026, 1, 1)
# Seed 6 since generator version 17 (the tier shuffle), seed 7 before it: the evaluator tests
# assert properties this world must hold (a target planted by another scenario, a candidate
# whose verdict the two views flip, a clause whose target's title contains another ticket's),
# and a version that moves the worlds moves them; the seed is the smallest holding every one
# on the tree as built (the generator step's group 3 probe over seeds 2 to 40: six of
# thirty-nine held the set), never a seed chosen for a count.
REFERENCE_SEED = 6


@dataclass(frozen=True)
class SealedStores:
    """The two buckets a sealed world lives in, as the loader is handed them."""

    truth: InMemoryObjectStore
    world: InMemoryObjectStore


@cache
def composed_world(plan_name: str = "golden", seed: int = REFERENCE_SEED) -> WorldSpec:
    """The world ``seed`` produces under ``plan_name``, every pending text a stand-in.

    Assembled once per process and shared: the world is immutable, a golden-plan assembly
    is the slowest thing these tests do, and several test modules grade against the same one.
    """
    semantic = assemble_semantic_world(seed, DEFAULT_PARAMS, WORLD_START, plan_name)
    bodies = {
        brief.id: f"Stand-in text for {brief.id}."
        for scenario in semantic.scenarios
        for brief in scenario.briefs
    }
    return compose(semantic, bodies, record_for(bodies) if bodies else None)


def sealed_stores(sealed: Bundle) -> SealedStores:
    """``sealed``'s three files under their keys, in the bucket each lives in."""
    stores = SealedStores(InMemoryObjectStore(), InMemoryObjectStore())
    version = sealed.world_version
    stores.truth.put_if_absent(world_spec_key(version), sealed.world_spec.content)
    stores.truth.put_if_absent(truth_manifest_key(version), sealed.truth_manifest.content)
    stores.world.put_if_absent(scenario_specs_key(version), sealed.scenario_specs.content)
    return stores


@cache
def loaded_world(plan_name: str = "golden", seed: int = REFERENCE_SEED) -> SealedWorld:
    """``composed_world`` sealed and loaded as the evaluator loads it, once per process.

    Loading runs the whole-world verification, seconds for a golden plan, so the tests that
    only read a loaded world share one.
    """
    sealed = bundle(composed_world(plan_name, seed))
    stores = sealed_stores(sealed)
    return load_sealed_world(sealed.world_version, stores.truth, stores.world)


__all__ = [
    "REFERENCE_SEED",
    "WORLD_START",
    "SealedStores",
    "composed_world",
    "composed_world_with_filler",
    "loaded_world",
    "loaded_world_with_filler",
    "sealed_stores",
]


@cache
def composed_world_with_filler(
    count: int = 3, plan_name: str = "golden", seed: int = REFERENCE_SEED
) -> WorldSpec:
    """``composed_world`` carrying ``count`` stand-in filler documents and the base and padded
    levels over them; the pool's content is the generator's to write, the shapes are here."""
    from tests.unit.filler_fixture import padded_world, stand_in_bodies

    semantic = padded_world(
        assemble_semantic_world(seed, DEFAULT_PARAMS, WORLD_START, plan_name), count
    )
    bodies = stand_in_bodies(semantic)
    return compose(semantic, bodies, record_for(bodies) if bodies else None)


@cache
def loaded_world_with_filler(
    count: int = 3, plan_name: str = "golden", seed: int = REFERENCE_SEED
) -> SealedWorld:
    """``composed_world_with_filler`` sealed and loaded as the evaluator loads it."""
    sealed = bundle(composed_world_with_filler(count, plan_name, seed))
    stores = sealed_stores(sealed)
    return load_sealed_world(sealed.world_version, stores.truth, stores.world)
