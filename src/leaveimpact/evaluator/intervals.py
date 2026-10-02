"""Intervals for the two kinds of number an evaluation reports, and nothing about claims.

A result with no error bar is not a result yet, and the wrong error bar is worse than
none. Two kinds of metric come out of a set of graded runs, and each has its own interval
(the investigator milestone's fourth build step, ruling 6):

- *A scenario-level proportion*: x of n scenarios pass a yes-or-no check. The scenario is
  the trial, the trials are roughly independent, and the interval is Wilson's. Wilson and
  not the textbook one because n is ten: at 10 of 10 the textbook interval has no width,
  and Wilson still says the true rate could be as low as 72 percent.
- *A claim-level ratio*: precision, recall, a grounded share. The claims of one scenario
  are not independent trials: they share its people, its leave and its documents, and a
  system that misreads one clause gets a dozen claims wrong together. Counting each claim
  as a trial would make the interval far too narrow. So the scenario stays the unit: the
  ratio is the sum of the numerators over the sum of the denominators, and its interval
  comes from resampling whole scenarios with replacement and recomputing that ratio of
  sums each time (a cluster bootstrap, percentile interval).

The resampling is *stratified*: scenarios are drawn within their stratum, so every
replicate keeps the design's allocation (ten scenarios per tier) and no replicate is
mostly one tier by chance.

A replicate whose denominator is zero has no ratio. It is never read as zero: it is left
out and counted, and an interval over the ones that remain says how many there were
(``valid`` against ``resamples``), which makes it an interval conditional on a positive
denominator. An observed zero denominator has no interval at all.

A *paired* difference between two systems resamples the same scenarios for both and
recomputes each system's ratio of sums, then subtracts. The mean of per-scenario ratio
differences is a different quantity and is not computed: a ratio of sums is not a mean of
per-scenario ratios.

Reproducible by construction. Draws come from ``random.Random(seed).random()`` alone, the
one method whose sequence the language guarantees for a seed across versions, and each
interval is given its own seed, derived from the plan's seed and the names of what is
being estimated (``derived_seed``), so a number does not depend on the order tables were
computed in. Every interval carries what produced it: the confidence level, the seed, the
resamples asked for and the valid ones, the quantile rule and the stratification.

Limits, which a table states beside its intervals: ten scenarios per tier is very few
clusters, and a percentile interval's coverage there can be poor and visibly discrete; no
correction is applied. Resampling scenarios of one organization says nothing about another
organization.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import floor, sqrt
from statistics import NormalDist

QUANTILE_RULE = "linear interpolation between order statistics"
"""How a percentile is read off the sorted replicates: position ``(m - 1) * q`` among ``m``
values, interpolated between its neighbours."""

STRATIFICATION = "clusters resampled with replacement within each stratum"

Cluster = tuple[float, float]
"""One scenario's contribution to a ratio: its numerator and its denominator."""

Paired = tuple[Cluster, Cluster]
"""One scenario's contribution to a comparison: the first system's cluster and the second's."""


@dataclass(frozen=True, slots=True)
class WilsonInterval:
    """The Wilson score interval of a proportion at ``confidence``."""

    low: float
    high: float
    confidence: float


@dataclass(frozen=True, slots=True)
class BootstrapInterval:
    """A percentile interval from resampled clusters, with everything that produced it.

    ``resamples`` were asked for and ``valid`` of them had a statistic; the interval is
    over those.
    """

    low: float
    high: float
    confidence: float
    seed: int
    resamples: int
    valid: int
    quantile_rule: str = QUANTILE_RULE
    stratification: str = STRATIFICATION

    @property
    def conditional(self) -> bool:
        """Whether some replicates had a zero denominator and were left out: the interval is
        then conditional on a positive one."""
        return self.valid < self.resamples


def wilson(successes: int, trials: int, confidence: float) -> WilsonInterval | None:
    """The Wilson interval of ``successes`` in ``trials``, or ``None`` with no trial.

    >>> eight_of_ten = wilson(8, 10, 0.95)
    >>> round(eight_of_ten.low, 2), round(eight_of_ten.high, 2)
    (0.49, 0.94)
    >>> wilson(0, 0, 0.95) is None
    True
    """
    _require_confidence(confidence)
    if not 0 <= successes <= trials:
        raise ValueError(
            f"a count of successes lies within the trials, got {successes} of {trials}"
        )
    if trials == 0:
        return None
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    share = successes / trials
    spread = 1 + z * z / trials
    centre = (share + z * z / (2 * trials)) / spread
    half = z * sqrt(share * (1 - share) / trials + z * z / (4 * trials * trials)) / spread
    # At no success the lower end is zero and at every success the upper end is one, exactly;
    # the arithmetic lands a rounding error away from each.
    low = 0.0 if successes == 0 else max(0.0, centre - half)
    high = 1.0 if successes == trials else min(1.0, centre + half)
    return WilsonInterval(low, high, confidence)


def bootstrap_ratio(
    strata: Sequence[Sequence[Cluster]], *, confidence: float, seed: int, resamples: int
) -> BootstrapInterval | None:
    """The interval of the ratio of sums over ``strata``, each a group of clusters resampled
    within itself. ``None`` when the observed denominator is zero: nothing to estimate."""
    if sum(denominator for stratum in strata for _, denominator in stratum) <= 0:
        return None
    return _bootstrap(strata, _ratio, confidence, seed, resamples)


def bootstrap_difference(
    strata: Sequence[Sequence[Paired]], *, confidence: float, seed: int, resamples: int
) -> BootstrapInterval | None:
    """The interval of the first system's ratio of sums less the second's, the same clusters
    resampled for both. ``None`` when either observed denominator is zero."""
    flat = [(*first, *second) for stratum in strata for first, second in stratum]
    if sum(row[1] for row in flat) <= 0 or sum(row[3] for row in flat) <= 0:
        return None
    joined = [[(*first, *second) for first, second in stratum] for stratum in strata]
    return _bootstrap(joined, _difference, confidence, seed, resamples)


def percentile_interval(values: Sequence[float], confidence: float) -> tuple[float, float]:
    """The central ``confidence`` share of ``values`` by the quantile rule.

    >>> percentile_interval(range(101), 0.5)
    (25.0, 75.0)
    """
    _require_confidence(confidence)
    if not values:
        raise ValueError("a percentile is read off at least one value")
    ordered = sorted(values)
    tail = (1 - confidence) / 2
    return _quantile(ordered, tail), _quantile(ordered, 1 - tail)


def derived_seed(seed: int, *names: str) -> int:
    """The seed of one interval's own stream: the plan's ``seed`` and the names of what is
    estimated, hashed, so an interval's draws depend on nothing computed before it.

    >>> derived_seed(7, "agent", "normal", "recall") == derived_seed(7, "agent", "normal", "recall")
    True
    >>> derived_seed(7, "agent", "normal", "recall") == derived_seed(7, "agent", "recall", "normal")
    False
    """
    text = "\x1f".join((str(seed), *names))
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def _bootstrap(
    strata: Sequence[Sequence[tuple[float, ...]]],
    statistic: Callable[[Sequence[float]], float | None],
    confidence: float,
    seed: int,
    resamples: int,
) -> BootstrapInterval | None:
    """The percentile interval of ``statistic`` over the sums of resampled clusters."""
    _require_confidence(confidence)
    if resamples < 1:
        raise ValueError(f"a bootstrap draws at least one resample, got {resamples}")
    held = [stratum for stratum in strata if stratum]
    if not held:
        return None
    width = len(held[0][0])
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(resamples):
        sums = [0.0] * width
        for stratum in held:
            size = len(stratum)
            for _ in range(size):
                # random() alone: its sequence is the one the language guarantees per seed.
                drawn = stratum[int(rng.random() * size)]
                for position in range(width):
                    sums[position] += drawn[position]
        value = statistic(sums)
        if value is not None:
            values.append(value)
    if not values:
        return None
    low, high = percentile_interval(values, confidence)
    return BootstrapInterval(low, high, confidence, seed, resamples, len(values))


def _ratio(sums: Sequence[float]) -> float | None:
    numerator, denominator = sums
    return numerator / denominator if denominator > 0 else None


def _difference(sums: Sequence[float]) -> float | None:
    first, first_of, second, second_of = sums
    if first_of <= 0 or second_of <= 0:
        return None
    return first / first_of - second / second_of


def _quantile(ordered: Sequence[float], share: float) -> float:
    position = (len(ordered) - 1) * share
    below = floor(position)
    if below + 1 >= len(ordered):
        return float(ordered[-1])
    return ordered[below] + (position - below) * (ordered[below + 1] - ordered[below])


def _require_confidence(confidence: float) -> None:
    if not 0 < confidence < 1:
        raise ValueError(f"a confidence level lies strictly between 0 and 1, got {confidence}")


__all__ = [
    "QUANTILE_RULE",
    "STRATIFICATION",
    "BootstrapInterval",
    "Cluster",
    "Paired",
    "WilsonInterval",
    "bootstrap_difference",
    "bootstrap_ratio",
    "derived_seed",
    "percentile_interval",
    "wilson",
]
