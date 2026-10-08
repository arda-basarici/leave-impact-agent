"""The tier shuffle (the generator step's ruling 4): a scenario's window and the ids a run
sees are not a function of its tier by construction. The windows are the forward dealing's
slices dealt out to positions by a seeded permutation, and rows are constructed in a seeded
random order, so the tiers' window-start ranges overlap and no tier's scenarios are one
block of the construction order. Under the orders this replaced, plan order (the tiers
concatenated) and scarcest class first (tiered), the window-start ranges were disjoint on
every seed and the leave id read the tier at 1.00 and 0.71 (group 0's id-leak probe). The
claim is structural, so the tests read the mechanism off the assembled world; the
classifier that measured the leak is the probe's, rerun and recorded, not a test. Five seeds
in the suite, twenty under the slow marker (ruling 9 as amended)."""

from datetime import date

import pytest

from leaveimpact.world import DEFAULT_PARAMS, SCENARIO_CLASSES, SemanticWorld, Tier
from leaveimpact.world.assembly import assemble_semantic_world
from leaveimpact.world.construction import ReservationExhausted

WORLD_START = date(2026, 1, 1)
TIERS = (Tier.STRUCTURED, Tier.FRAGMENTED, Tier.ADVERSARIAL)
# The claims are about assembled worlds, and the reservation book refuses seed 1 under this
# order (the group 3 sweep: 4 of 200 refused, seeds 1, 72, 85 and 134; one under the
# scarcity-first order it replaced; FINDINGS, ``reservation-book``). The refusal is pinned
# below so that a change in the order shows; the seeds here are the next ones.
SUITE_SEEDS = range(2, 7)
SWEEP_SEEDS = range(2, 22)


def golden(seed: int) -> SemanticWorld:
    return assemble_semantic_world(seed, DEFAULT_PARAMS, WORLD_START, "golden")


def rows_of(world: SemanticWorld, tier: Tier) -> list[int]:
    return [index for index, row in enumerate(world.plan) if row.tier is tier]


def id_number(identifier: str) -> int:
    return int(identifier.rsplit("_", 1)[1])


def construction_order_of(world: SemanticWorld) -> list[int]:
    """The order the rows were constructed in, read off the world: the minting book numbers
    ids in the order constructions ask, and a construction mints its investigated leave
    before the next construction begins, so the leave ids rank the rows."""
    return sorted(
        range(len(world.scenarios)),
        key=lambda index: id_number(world.scenarios[index].spec.leave_id),
    )


def scarcity_order_of(world: SemanticWorld) -> list[int]:
    """The order the 15.5 rulings constructed in, scarcest class first with ties in plan
    order, which the random order replaced."""
    scarcity = {
        name: len(SCENARIO_CLASSES[name].admissible(world.org))
        for name in {row.scenario_class for row in world.plan}
    }
    return sorted(
        range(len(world.plan)),
        key=lambda index: (scarcity[world.plan[index].scenario_class], index),
    )


def tier_window_ranges_overlap(world: SemanticWorld) -> None:
    ranges: dict[Tier, tuple[date, date]] = {}
    for tier in TIERS:
        starts = [world.scenarios[index].spec.window.start for index in rows_of(world, tier)]
        ranges[tier] = (min(starts), max(starts))
    for first in TIERS:
        for second in TIERS:
            if first is second:
                continue
            (low, high), (other_low, other_high) = ranges[first], ranges[second]
            assert not (high < other_low or other_high < low), (first, second, ranges)


def no_tier_is_one_block_of_the_construction_order(world: SemanticWorld) -> None:
    rank = {index: position for position, index in enumerate(construction_order_of(world))}
    for tier in TIERS:
        positions = sorted(rank[index] for index in rows_of(world, tier))
        assert positions[-1] - positions[0] + 1 != len(positions), (tier, positions)


@pytest.mark.parametrize("seed", SUITE_SEEDS)
def test_the_tiers_window_start_ranges_overlap(seed: int) -> None:
    tier_window_ranges_overlap(golden(seed))


@pytest.mark.parametrize("seed", SUITE_SEEDS)
def test_no_tier_is_one_block_of_the_construction_order(seed: int) -> None:
    no_tier_is_one_block_of_the_construction_order(golden(seed))


@pytest.mark.parametrize("seed", SUITE_SEEDS)
def test_the_construction_order_is_neither_plan_order_nor_scarcest_first(seed: int) -> None:
    world = golden(seed)
    order = construction_order_of(world)
    assert sorted(order) == list(range(len(world.plan)))
    assert order != list(range(len(world.plan)))
    assert order != scarcity_order_of(world)


def test_the_sweeps_refusal_on_seed_one_reproduces() -> None:
    """The feasibility datum the suite can hold: under the random order seed 1 is refused by
    the reservation book at the composite row, every construction crossing a standing-owner
    rule. A seed 1 that builds, or refuses elsewhere, is an order that moved."""
    with pytest.raises(ReservationExhausted) as refused:
        golden(1)
    assert refused.value.who == "adversarial_composite"
    assert all(
        "standing owner" in rule or "leave subject" in rule for rule in refused.value.eliminated
    )


@pytest.mark.slow
@pytest.mark.parametrize("seed", SWEEP_SEEDS)
def test_twenty_seeds_hold_the_two_tier_independence_claims(seed: int) -> None:
    world = golden(seed)
    tier_window_ranges_overlap(world)
    no_tier_is_one_block_of_the_construction_order(world)
