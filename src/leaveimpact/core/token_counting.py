"""The counting rules: which tokens a run's token cap counts, and when a count is established.

A run stops at its token cap, and that stop is graded, so which token classes count toward
the cap is a registered condition and not something a harness may decide as it goes (the
event log step's ruling on counting rules). A rule is a name in the closed registry here,
standing for the usage counters it sums. A cap that names anything else is refused where
it is constructed, so a record and a registration can only hold a rule this code gives a
meaning to.

One rule exists: every reported class counts, the two cache classes included. The usage
reader takes the input counter as the non-cached part and the reported total as the sum of
the four (``usage.read_usage``, written against what the supported configurations
returned), so the rule's sum is the provider's own total wherever all four are reported.

A count is *established* when it can replace a dispatch's worst-case allocation: every
counter the rule names was reported, or was absent under a configuration where absence is
proven to mean no token of that class, and the usage held nothing the reader could not
take as declared, since a field nobody understood may be a counted class. Otherwise the
sum of what was reported is a floor, and the allocation it would have replaced is kept.
Which absences are proven is the caller's to supply, from the one place that fact is
recorded (the price table's policy for an unreported counter, ``pricing.absent_as_zero``).
A price says nothing here: a class billed at zero, or a charge that was waived, still
consumed its tokens.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass
from types import MappingProxyType

from leaveimpact.core.run_trace import USAGE_COUNTER_NAMES, require_integer
from leaveimpact.core.usage import ReportedUsage

INPUT_PLUS_OUTPUT_CACHED_INCLUDED = "input_plus_output_cached_included"
"""Every class a provider reports counts: input, output, cache reads and cache writes."""

COUNTING_RULES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {INPUT_PLUS_OUTPUT_CACHED_INCLUDED: USAGE_COUNTER_NAMES}
)
"""Each registered rule with the usage counters it sums. Closed: a rule is added here, with
a name of its own, and never by changing what an existing name sums."""


def require_counting_rule(name: str, what: str) -> str:
    """``name`` if the registry holds it; ``ValueError`` otherwise.

    >>> require_counting_rule("input_output", "the counting rule")
    Traceback (most recent call last):
    ...
    ValueError: the counting rule is a registered one (input_plus_output_cached_included), \
got 'input_output'
    """
    if name not in COUNTING_RULES:
        raise ValueError(f"{what} is a registered one ({', '.join(COUNTING_RULES)}), got {name!r}")
    return name


@dataclass(frozen=True, slots=True)
class TokenCount:
    """Tokens counted under a rule, and whether the count is established or a floor.

    The token-side twin of a cost and its completeness: ``established`` is false when a
    counter the rule names was not accounted for or the usage held an anomaly, and the
    amount is then what is known to have been used at least.
    """

    tokens: int
    established: bool

    def __post_init__(self) -> None:
        require_integer(self.tokens, "a token count")


def count_tokens(rule: str, reported: ReportedUsage, absent_as_zero: Set[str]) -> TokenCount:
    """What ``reported`` counts for under ``rule``, established or a floor.

    ``absent_as_zero`` names the counters whose absence, under the configuration that
    answered, is proven to mean no token of that class.

    >>> rule = INPUT_PLUS_OUTPUT_CACHED_INCLUDED
    >>> usage = ReportedUsage({"inputTokens": 120, "outputTokens": 30})
    >>> count_tokens(rule, usage, frozenset())
    TokenCount(tokens=150, established=False)
    >>> cache = frozenset({"cache_read_input_tokens", "cache_write_input_tokens"})
    >>> count_tokens(rule, usage, cache)
    TokenCount(tokens=150, established=True)
    """
    counters = reported.counters
    total = 0
    accounted = True
    for name in COUNTING_RULES[require_counting_rule(rule, "a counting rule")]:
        value = counters.value(name)
        if value is None:
            accounted = accounted and name in absent_as_zero
        else:
            total += value
    return TokenCount(total, accounted and reported.complete)


__all__ = [
    "COUNTING_RULES",
    "INPUT_PLUS_OUTPUT_CACHED_INCLUDED",
    "TokenCount",
    "count_tokens",
    "require_counting_rule",
]
