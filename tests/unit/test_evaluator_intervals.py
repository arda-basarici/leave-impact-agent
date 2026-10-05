"""Wilson for a proportion of scenarios; a seeded, stratified percentile bootstrap for a ratio of
sums over scenarios, and for the paired difference of two. Eight of ten is 49 to 94 percent. A
seeded interval reproduces exactly, every replicate keeps each stratum's size, a replicate
with a zero denominator is left out and counted and never read as zero, and a bootstrap that
cannot resolve an interval says which of four reasons holds instead of giving none or one of
no width."""

from collections.abc import Sequence

import pytest

from leaveimpact.evaluator.intervals import (
    QUANTILE_RULE,
    STRATIFICATION,
    BootstrapInterval,
    Cluster,
    Paired,
    Unresolved,
    bootstrap_difference,
    bootstrap_ratio,
    derived_seed,
    percentile_interval,
    wilson,
)

SEED, RESAMPLES = 20_261_002, 2_000


def ratio(
    strata: Sequence[Sequence[Cluster]], seed: int = SEED
) -> BootstrapInterval | Unresolved:
    """The 95 percent interval of ``strata``'s ratio of sums, as every test here draws it."""
    return bootstrap_ratio(strata, confidence=0.95, seed=seed, resamples=RESAMPLES)


def difference(strata: Sequence[Sequence[Paired]]) -> BootstrapInterval | Unresolved:
    return bootstrap_difference(strata, confidence=0.95, seed=SEED, resamples=RESAMPLES)

# Three strata of ten clusters: claims correct of claims made, uneven on purpose.
TIERS: tuple[tuple[Cluster, ...], ...] = (
    tuple((12, 12) for _ in range(8)) + ((9, 12), (11, 12)),
    tuple((value, 14) for value in (14, 12, 9, 14, 7, 13, 10, 14, 11, 8)),
    tuple((value, 20) for value in (6, 15, 9, 20, 4, 12, 17, 8, 10, 13)),
)

PINNED = (0.673913, 0.819565)
"""The interval of ``TIERS`` as ``ratio`` draws it, as first computed."""


def test_eight_of_ten_scenarios_is_forty_nine_to_ninety_four_percent() -> None:
    interval = wilson(8, 10, 0.95)
    assert interval is not None
    assert (round(interval.low, 3), round(interval.high, 3)) == (0.490, 0.943)
    assert interval.confidence == 0.95


def test_wilson_keeps_width_at_the_ends_and_narrows_with_more_scenarios() -> None:
    none, every = wilson(0, 10, 0.95), wilson(10, 10, 0.95)
    assert none is not None and every is not None
    # Ten of ten is not certainty: the rate could be as low as 72 percent.
    assert (none.low, round(none.high, 2)) == (0.0, 0.28)
    assert (round(every.low, 2), every.high) == (0.72, 1.0)
    ten, thirty = wilson(8, 10, 0.95), wilson(24, 30, 0.95)
    assert ten is not None and thirty is not None
    assert thirty.high - thirty.low < ten.high - ten.low
    cautious = wilson(8, 10, 0.99)
    assert cautious is not None and cautious.low < ten.low and cautious.high > ten.high


def test_wilson_has_nothing_to_say_of_no_trial_and_refuses_an_impossible_count() -> None:
    assert wilson(0, 0, 0.95) is None
    with pytest.raises(ValueError, match="within the trials"):
        wilson(11, 10, 0.95)
    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        wilson(8, 10, 95)


def test_a_percentile_is_interpolated_between_order_statistics() -> None:
    assert percentile_interval(range(101), 0.5) == (25, 75)
    assert percentile_interval(range(101), 0.95) == pytest.approx((2.5, 97.5))
    assert percentile_interval([3.0, 1.0, 2.0], 0.5) == (1.5, 2.5)  # sorted first
    assert percentile_interval([4.0], 0.95) == (4, 4)


def test_a_seeded_interval_reproduces_exactly_and_records_what_produced_it() -> None:
    first = ratio(TIERS)
    again = ratio(TIERS)
    assert isinstance(first, BootstrapInterval) and first == again
    assert first == BootstrapInterval(
        first.low, first.high, 0.95, 20_261_002, 2_000, 2_000, QUANTILE_RULE, STRATIFICATION
    )
    assert not first.conditional
    # Pinned: the draws rest on random(), whose sequence the language guarantees per seed.
    assert (round(first.low, 6), round(first.high, 6)) == PINNED
    observed = sum(n for tier in TIERS for n, _ in tier) / sum(d for tier in TIERS for _, d in tier)
    assert first.low < observed < first.high
    other = ratio(TIERS, seed=1)
    assert isinstance(other, BootstrapInterval)
    assert (other.low, other.high) != (first.low, first.high)


def test_every_replicate_keeps_each_stratums_size() -> None:
    # One stratum always right, one always wrong: stratified, every replicate is ten of each
    # and the ratio is one half exactly, so no resample differs from another. Drawn from
    # the twenty together it would wander.
    right, wrong = tuple((1, 1) for _ in range(10)), tuple((0, 1) for _ in range(10))
    assert ratio((right, wrong)) is Unresolved.EVERY_RESAMPLE_EQUAL
    pooled = ratio(((*right, *wrong),))
    assert isinstance(pooled, BootstrapInterval) and pooled.low < 0.5 < pooled.high
    # An empty stratum contributes nothing and breaks nothing.
    uneven = ((*right[:9], (0, 1)), wrong)
    assert ratio((uneven[0], (), uneven[1])) == ratio(uneven)
    assert isinstance(ratio(uneven), BootstrapInterval)


def test_a_replicate_with_a_zero_denominator_is_left_out_and_counted_never_read_as_zero() -> None:
    # Three scenarios, one of which made no claim of the kind: the replicates that draw it
    # three times have no ratio, one in twenty-seven.
    sparse = (((3, 3), (1, 3), (0, 0)),)
    interval = ratio(sparse)
    assert isinstance(interval, BootstrapInterval)
    assert interval.conditional
    assert 0.02 < 1 - interval.valid / interval.resamples < 0.06
    # Read as zero, the silent scenario would pull the low end to zero.
    assert interval.low >= 1 / 3


def test_each_reason_a_bootstrap_resolves_no_interval() -> None:
    assert ratio(((), ())) is Unresolved.NO_ELIGIBLE_SCENARIO
    assert ratio(()) is Unresolved.NO_ELIGIBLE_SCENARIO
    assert ratio((((0, 0), (0, 0)),)) is Unresolved.ZERO_DENOMINATOR
    assert ratio((((2, 3),),)) is Unresolved.FEWER_THAN_TWO_ELIGIBLE_SCENARIOS
    # Ten scenarios that all pass: every resample is 1.0, and "[1.0, 1.0]" would read as
    # certainty where Wilson still allows a rate of 72 percent.
    assert ratio((tuple((1, 1) for _ in range(10)),)) is Unresolved.EVERY_RESAMPLE_EQUAL
    # The order the reasons are tried in: a lone scenario with nothing to divide by has no
    # statistic at all, which says more than that it is alone.
    assert ratio((((0, 0),),)) is Unresolved.ZERO_DENOMINATOR
    # Two scenarios in two strata are two scenarios, and each stratum resamples to itself.
    assert ratio((((1, 2),), ((2, 2),))) is Unresolved.EVERY_RESAMPLE_EQUAL
    assert [reason.value for reason in Unresolved] == [
        "no_eligible_scenario",
        "zero_denominator",
        "fewer_than_two_eligible_scenarios",
        "every_resample_equal",
    ]


def test_equal_differences_resolve_no_interval_whatever_fractions_they_are_between() -> None:
    # Ten scenarios of ten repeats, the first system passing n of them and the second n - 1:
    # every scenario's gain is exactly one in ten, so every resample is the same difference.
    # Summed as floats the resamples differed by rounding, and the noise came back as an
    # interval 3e-16 wide that resolved a positive difference (the external read's case).
    gains = (tuple(((n, 10), (n - 1, 10)) for n in range(1, 11)),)
    found = bootstrap_difference(gains, confidence=0.95, seed=20_261_003, resamples=10_000)
    assert found is Unresolved.EVERY_RESAMPLE_EQUAL
    # The same gain over other denominators is the same difference.
    thirds = tuple(((3 * n, 30), (3 * n - 3, 30)) for n in range(1, 6))
    mixed = ((*thirds, *gains[0][5:]),)
    assert difference(mixed) is Unresolved.EVERY_RESAMPLE_EQUAL
    # One scenario gaining two in ten is variation, and resolves.
    uneven = (((*gains[0][:9], ((10, 10), (8, 10)))),)
    resolved = difference(uneven)
    assert isinstance(resolved, BootstrapInterval) and 0.1 <= resolved.low < resolved.high


def test_a_cluster_holds_whole_numbers() -> None:
    with pytest.raises(ValueError, match=r"a cluster's count is an integer, got 0\.5"):
        ratio((((0.5, 1), (1, 1)),))  # pyright: ignore[reportArgumentType]
    with pytest.raises(ValueError, match="a cluster's count is an integer, got True"):
        ratio((((True, 1), (1, 1)),))


def test_a_system_compared_with_itself_resolves_no_interval() -> None:
    paired = tuple(tuple((cluster, cluster) for cluster in tier) for tier in TIERS)
    assert difference(paired) is Unresolved.EVERY_RESAMPLE_EQUAL


def test_a_paired_difference_resamples_the_same_scenarios_for_both_systems() -> None:
    # The second system gets one claim fewer right in every other scenario. One fewer in
    # every scenario would be the same loss in every resample, each tier's denominators
    # being equal, and no interval: this test once passed on that case's rounding noise.
    behind = tuple(
        tuple(
            (cluster, (max(cluster[0] - position % 2, 0), cluster[1]))
            for position, cluster in enumerate(tier)
        )
        for tier in TIERS
    )
    even = tuple(tuple((c, (max(c[0] - 1, 0), c[1])) for c in tier) for tier in TIERS[1:])
    assert difference(even) is Unresolved.EVERY_RESAMPLE_EQUAL
    ahead = difference(behind)
    assert isinstance(ahead, BootstrapInterval) and 0 < ahead.low < ahead.high
    # Paired, the scenario-to-scenario spread the two systems share cancels: the interval
    # of the difference is far narrower than either system's own.
    alone = ratio(TIERS)
    assert isinstance(alone, BootstrapInterval)
    assert ahead.high - ahead.low < (alone.high - alone.low) / 5
    # Either side with nothing to divide by: no comparison.
    silent = tuple(tuple((cluster, (0, 0)) for cluster in tier) for tier in TIERS)
    assert difference(silent) is Unresolved.ZERO_DENOMINATOR


def test_an_intervals_seed_depends_on_its_names_and_on_nothing_computed_before() -> None:
    recall = derived_seed(7, "agent", "normal", "overall", "recall")
    assert recall == derived_seed(7, "agent", "normal", "overall", "recall")
    assert recall != derived_seed(7, "agent", "normal", "overall", "precision")
    assert recall != derived_seed(8, "agent", "normal", "overall", "recall")
    # Names are kept apart: joined differently they are different names.
    assert derived_seed(7, "ab", "c") != derived_seed(7, "a", "bc")
    assert 0 <= recall < 2**64


def test_a_bootstrap_refuses_no_resample_and_a_confidence_that_is_not_one() -> None:
    with pytest.raises(ValueError, match="at least one resample"):
        bootstrap_ratio(TIERS, confidence=0.95, seed=1, resamples=0)
    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        bootstrap_ratio(TIERS, confidence=1.0, seed=1, resamples=10)
