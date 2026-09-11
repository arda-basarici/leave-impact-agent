"""Two questions about IANA zones the world asks: how far apart are two zones at an instant,
and does that distance hold all year.

Both exist for the timezone affordance (the step 8 ruling): the organization guarantees
one employee whose zone is at least a fixed number of hours from the reference zone at
every instant of a full year — DST-aware and date-free, so the org generator can check
it without knowing what any scenario plans — and the timezone-boundary modifier then
reads the gap at the instant it plants, never as a city-to-city constant. A gap is the
absolute difference of the two UTC offsets, so a zone ahead and a zone behind qualify
alike; which side a zone is on is the modifier's question, asked with ``offset_of``.

"All year" is sampled hourly over a fixed rules year rather than read from transition
tables, which ``zoneinfo`` does not expose: transitions fall on hour boundaries in every
zone the vocabulary lists, and an hourly sweep of a leap-year-sized span crosses every
DST state the fourteen-month world can meet. The year is a constant of the generator, so
the guarantee does not drift with the wall clock.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import cache

from leaveimpact.core.worldtime import zone

RULES_YEAR = 2026
"""The calendar year whose DST rules the all-year check sweeps; generator semantics."""

_YEAR_HOURS = 366 * 24


def offset_of(timezone: str, instant: datetime) -> timedelta:
    """The UTC offset ``timezone`` has at ``instant`` (an aware datetime)."""
    offset = instant.astimezone(zone(timezone)).utcoffset()
    assert offset is not None
    return offset


def gap_at(timezone: str, reference: str, instant: datetime) -> timedelta:
    """How far apart ``timezone`` and ``reference`` are at ``instant``, as a non-negative duration.

    >>> gap_at("America/Toronto", "Europe/Istanbul", datetime(2026, 1, 15, 12, tzinfo=UTC))
    datetime.timedelta(seconds=28800)
    >>> gap_at("America/Toronto", "Europe/Istanbul", datetime(2026, 7, 15, 12, tzinfo=UTC))
    datetime.timedelta(seconds=25200)
    """
    return abs(offset_of(timezone, instant) - offset_of(reference, instant))


@cache
def gap_holds_all_year(timezone: str, reference: str, hours: int) -> bool:
    """Whether the two zones are at least ``hours`` apart at every hour of the rules year.

    Cached: pure in its three arguments, and asked once per city by every organization
    generated and every parameter record validated.

    >>> gap_holds_all_year("America/Toronto", "Europe/Istanbul", 6)
    True
    >>> gap_holds_all_year("Asia/Kolkata", "Europe/Istanbul", 6)
    False
    """
    least = timedelta(hours=hours)
    start = datetime(RULES_YEAR, 1, 1, tzinfo=UTC)
    return all(
        gap_at(timezone, reference, start + timedelta(hours=hour)) >= least
        for hour in range(_YEAR_HOURS)
    )
