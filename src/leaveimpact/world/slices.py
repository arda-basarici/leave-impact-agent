"""Scenario time: disjoint slices, the leave inside one, ``now`` before it, the stable-now interval.

A scenario owns a fourteen-day slice of world state and slices never overlap — the
cheapest write isolation, and thirty of them spread believably over about fourteen
months of shared calendars (DESIGN, "A scenario owns a disjoint fourteen-day slice").
Slices are dealt in scenario order from the world's start with a small random gap
between them, so month boundaries and slice boundaries drift apart instead of lining up.

Inside a slice the leave starts around the middle and runs a few days, which leaves
room before it for "a meeting the day before" and room after for "the day after"
without a two-week absence. ``now`` sits a few days before the leave, at the start of a
working day in the reference timezone, because a manager plans cover shortly before an
absence, not months out.

The stable-now interval is derived, never authored, and around ``now`` rather than up to
it: it is the maximal run of days before the leave over which the set of observable
answer-relevant facts is unchanged. A fact observable from day four is admissible for
every ``now`` from day four on, so the latest fact the key needs sets the interval's
lower bound, and the next fact whose arrival would change the answer sets its upper
bound, capped at the day before the leave. The derivation reads the planted
observability dates, not the rules: construction stays independent of the rule
implementation, and the validator's two-instant check inside the interval is the
independent verification (the stable-interval ruling at the scenario-framework step).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from random import Random

from leaveimpact.core.worldtime import DateSpan, zone

SLICE_DAYS = 14
# The gap between consecutive slices, in days; zero keeps two slices adjacent.
MAX_GAP_DAYS = 3
# Zero-based offsets into the slice: the leave starts on day five to nine of fourteen.
LEAVE_START_OFFSET_DAYS = (4, 8)
LEAVE_LENGTH_DAYS = (2, 5)
# How many days before the leave starts the run's ``now`` falls.
NOW_LEAD_DAYS = (2, 4)
NOW_LOCAL_TIME = time(9, 0)


def allocate_slices(rng: Random, count: int, world_start: date) -> tuple[DateSpan, ...]:
    """``count`` disjoint fourteen-day slices in order from ``world_start``, gaps from ``rng``.

    >>> slices = allocate_slices(Random(1), 3, date(2026, 1, 1))
    >>> [span.days for span in slices]
    [14, 14, 14]
    >>> all(later.start > earlier.end for earlier, later in zip(slices, slices[1:]))
    True
    """
    slices: list[DateSpan] = []
    start = world_start
    for _ in range(count):
        slices.append(DateSpan(start, start + timedelta(days=SLICE_DAYS - 1)))
        start = slices[-1].end + timedelta(days=1 + rng.randint(0, MAX_GAP_DAYS))
    return tuple(slices)


def place_leave(rng: Random, window: DateSpan) -> DateSpan:
    """The leave's inclusive days inside ``window``: starting mid-slice, a few days long.

    >>> window = DateSpan(date(2026, 3, 1), date(2026, 3, 14))
    >>> leave = place_leave(Random(1), window)
    >>> window.contains(leave.start) and window.contains(leave.end)
    True
    """
    if window.days != SLICE_DAYS:
        raise ValueError(
            f"a leave is placed inside a {SLICE_DAYS}-day slice, got {window.days} days"
        )
    start = window.start + timedelta(days=rng.randint(*LEAVE_START_OFFSET_DAYS))
    end = start + timedelta(days=rng.randint(*LEAVE_LENGTH_DAYS) - 1)
    return DateSpan(start, end)


def place_now(rng: Random, leave: DateSpan, reference_timezone: str) -> datetime:
    """The run's ``now``: a few days before the leave, at the start of a working day in the zone.

    >>> now = place_now(Random(1), DateSpan(date(2026, 3, 6), date(2026, 3, 8)), "Europe/Istanbul")
    >>> now.tzinfo is not None and now.date() < date(2026, 3, 6)
    True
    """
    day = leave.start - timedelta(days=rng.randint(*NOW_LEAD_DAYS))
    return datetime.combine(day, NOW_LOCAL_TIME, tzinfo=zone(reference_timezone))


def stable_interval(
    window: DateSpan, leave: DateSpan, today: date, observability: Iterable[date]
) -> DateSpan:
    """The days around ``today`` over which the observable answer-relevant facts are unchanged.

    ``observability`` is every planted answer-relevant fact's ``observable_from``. Facts
    on or before ``today`` bound the interval from below by the latest of them; facts
    after ``today`` bound it from above by the earliest of them, less a day; the window
    start and the day before the leave cap both ends. ``today`` always lies inside.

    >>> window = DateSpan(date(2026, 3, 1), date(2026, 3, 14))
    >>> leave = DateSpan(date(2026, 3, 10), date(2026, 3, 12))
    >>> stable_interval(window, leave, date(2026, 3, 6), [date(2026, 3, 4), date(2026, 3, 8)])
    DateSpan(start=datetime.date(2026, 3, 4), end=datetime.date(2026, 3, 7))
    """
    if not window.start <= today < leave.start:
        raise ValueError(
            f"the stable interval is derived for a now before the leave and inside the window, "
            f"got {today} against window {window.start}..{window.end} and leave from {leave.start}"
        )
    dates = tuple(observability)
    lower = max([window.start, *(day for day in dates if day <= today)])
    day_before = timedelta(days=1)
    upper = min([leave.start - day_before, *(day - day_before for day in dates if day > today)])
    return DateSpan(lower, upper)
