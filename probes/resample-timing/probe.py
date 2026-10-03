"""How long the registered resample count takes: the tier-stratified scenario bootstrap timed
at the sizes the registered analysis runs it.

A measurement, not a pass-or-fail probe. The preregistration draft registers 10,000
resamples, and the registered analysis draws that many for every interval and every paired
difference it estimates by bootstrap; the count was registered on the condition that its
cost be measured before the analysis is written, and any reduction settled before a
measurement (the investigator milestone's sixth build step, ruling 4). The count buys
simulation precision and nothing else: it does nothing for ten scenarios a tier.

Timed here, on synthetic clusters of the real shape (three tiers, a ratio's numerator and
denominator per scenario): one interval of a ratio and one paired difference, over the
full set (ten scenarios a tier) and over the primary set (eight a tier), the median of
five runs each. Then the arithmetic for the descriptive comparisons the draft registers on
measures, which are always bootstraps: three pairs of systems, three answer-quality
conditions, four strata (the whole and three tiers), two scenario sets, four measures.
The whole costs a full draw and a tier a third of one, so a set's four strata cost two
full draws.

The seconds are this machine's on the day of the run and are not reproducible to the
digit; the capture is dated. The draws themselves are seeded and are the ones the
evaluator makes.

    uv run python probes/resample-timing/probe.py
"""

from __future__ import annotations

import platform
import random
import statistics
import time

from leaveimpact.evaluator.intervals import bootstrap_difference, bootstrap_ratio

RESAMPLES = 10_000
CONFIDENCE = 0.95
SEED = 20261003
RUNS = 5
TIERS = 3
PAIRS, CONDITIONS, MEASURES = 3, 3, 4


def clusters(per_tier: int, seed: int) -> list[list[tuple[float, float]]]:
    """Synthetic scenarios: a denominator of 5 to 40 claims and a numerator within it."""
    rng = random.Random(seed)
    tiers: list[list[tuple[float, float]]] = []
    for _ in range(TIERS):
        tier: list[tuple[float, float]] = []
        for _ in range(per_tier):
            denominator = rng.randint(5, 40)
            tier.append((float(rng.randint(0, denominator)), float(denominator)))
        tiers.append(tier)
    return tiers


def timed(call: object) -> float:
    assert callable(call)
    seconds: list[float] = []
    for _ in range(RUNS):
        started = time.perf_counter()
        assert call() is not None
        seconds.append(time.perf_counter() - started)
    return statistics.median(seconds)


def main() -> None:
    print(f"python {platform.python_version()}, {platform.machine()}, {platform.system()}")
    print(f"{RESAMPLES} resamples, median of {RUNS} runs, seconds")
    per_difference: dict[str, float] = {}
    for name, per_tier in (("full set, 10 a tier", 10), ("primary set, 8 a tier", 8)):
        first, second = clusters(per_tier, 1), clusters(per_tier, 2)
        paired = [list(zip(a, b, strict=True)) for a, b in zip(first, second, strict=True)]
        ratio = timed(
            lambda first=first: bootstrap_ratio(
                first, confidence=CONFIDENCE, seed=SEED, resamples=RESAMPLES
            )
        )
        difference = timed(
            lambda paired=paired: bootstrap_difference(
                paired, confidence=CONFIDENCE, seed=SEED, resamples=RESAMPLES
            )
        )
        per_difference[name] = difference
        print(f"  {name}: one ratio {ratio:.3f}, one paired difference {difference:.3f}")
    # The whole is one full draw and each of three tiers a third of one: two per set.
    full_draws = PAIRS * CONDITIONS * MEASURES * 2
    total = sum(full_draws * seconds for seconds in per_difference.values())
    print(
        f"descriptive measure comparisons: {PAIRS} pairs x {CONDITIONS} conditions x "
        f"{MEASURES} measures x 4 strata x 2 sets = {PAIRS * CONDITIONS * MEASURES * 4 * 2} "
        f"bootstraps, {full_draws} full draws a set"
    )
    print(f"  estimated {total:.0f} seconds in all, single-threaded")


if __name__ == "__main__":
    main()
