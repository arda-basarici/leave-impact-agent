"""Money and token amounts as a page states them, with absence and partiality kept apart
from totals.

The record keeps costs in integer pico-dollars with a completeness flag, usage counters as
sums over the dispatches that reported them, and token counts as established or a floor
(the contract step's rulings on absent and partial amounts). A page that printed a floor
as a total, or a missing counter as zero, would state more than the run recorded; so every
amount here renders with its qualification, and the one rounding a floor gets is downward,
since a lower bound rounded up is no longer a lower bound (the demo milestone's report
step, after its external read). Pure functions, doctested; the templates call these and
format nothing themselves.
"""

from __future__ import annotations

from leaveimpact.core.run_trace import Cost
from leaveimpact.core.token_counting import TokenCount

PICO_PER_DOLLAR = 10**12
"""The record's unit: pico-dollars per dollar."""
_PICO_PER_UNIT = PICO_PER_DOLLAR // 10_000
"""Pico-dollars per ten-thousandth of a dollar, the page's last shown place."""


def dollars(pico_usd: int, *, floor: bool = False) -> str:
    """``pico_usd`` as dollars to four places; a complete amount rounds to the nearest place
    and a floor is truncated, so a lower bound shown is still a lower bound.

    >>> dollars(123_456_789_012)
    '$0.1235'
    >>> dollars(123_456_789_012, floor=True)
    '$0.1234'
    >>> dollars(1_234 * 10**12)
    '$1,234.0000'
    >>> dollars(-1)
    Traceback (most recent call last):
    ...
    ValueError: an amount in pico-dollars is not negative, got -1
    """
    if pico_usd < 0:
        raise ValueError(f"an amount in pico-dollars is not negative, got {pico_usd}")
    units = (
        pico_usd // _PICO_PER_UNIT if floor else (pico_usd + _PICO_PER_UNIT // 2) // _PICO_PER_UNIT
    )
    whole, fraction = divmod(units, 10_000)
    return f"${whole:,}.{fraction:04d}"


def cost_label(cost: Cost | None) -> str:
    """``cost`` as the page says it: a complete amount plainly, an incomplete one as a floor,
    and no cost as "not priced", never zero.

    >>> cost_label(None)
    'not priced'
    >>> cost_label(Cost(250_000_000_000, True))
    '$0.2500'
    >>> cost_label(Cost(250_099_999_999, False))
    'at least $0.2500'
    """
    if cost is None:
        return "not priced"
    if cost.complete:
        return dollars(cost.pico_usd)
    return f"at least {dollars(cost.pico_usd, floor=True)}"


def counter_label(name: str, value: int, reported: int, dispatches: int) -> str:
    """A usage counter's sum with its coverage when the sum is partial: ``reported`` of
    ``dispatches`` reported it.

    >>> counter_label("input_tokens", 12_500, 4, 4)
    '12,500 input tokens'
    >>> counter_label("cache_read_input_tokens", 900, 3, 4)
    '900 cache read input tokens (3 of 4 dispatches reported)'
    """
    label = f"{value:,} {name.replace('_', ' ')}"
    if reported < dispatches:
        label += f" ({reported} of {dispatches} dispatches reported)"
    return label


def token_label(count: TokenCount | None) -> str:
    """A token count as the page says it: established plainly, a floor as one, and no count
    as "not counted".

    >>> token_label(TokenCount(4_250, True))
    '4,250 tokens'
    >>> token_label(TokenCount(4_250, False))
    'at least 4,250 tokens'
    >>> token_label(None)
    'not counted'
    """
    if count is None:
        return "not counted"
    if count.established:
        return f"{count.tokens:,} tokens"
    return f"at least {count.tokens:,} tokens"


__all__ = ["PICO_PER_DOLLAR", "cost_label", "counter_label", "dollars", "token_label"]
