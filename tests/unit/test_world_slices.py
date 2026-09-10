"""Scenario time: slices disjoint and dealt in order, the leave mid-slice with room on both
sides, ``now`` shortly before it, and the stable interval derived around ``today`` from
the planted observability dates — latest earlier fact below, earliest later fact above."""

from datetime import date, timedelta
from random import Random

import pytest

from leaveimpact.core import DateSpan
from leaveimpact.world.slices import (
    LEAVE_LENGTH_DAYS,
    LEAVE_START_OFFSET_DAYS,
    MAX_GAP_DAYS,
    NOW_LEAD_DAYS,
    SLICE_DAYS,
    allocate_slices,
    place_leave,
    place_now,
    stable_interval,
)

WORLD_START = date(2026, 1, 1)
WINDOW = DateSpan(date(2026, 3, 1), date(2026, 3, 14))
LEAVE = DateSpan(date(2026, 3, 10), date(2026, 3, 12))


def test_slices_are_disjoint_ordered_fourteen_day_runs_with_bounded_gaps() -> None:
    slices = allocate_slices(Random(3), 30, WORLD_START)
    assert len(slices) == 30 and slices[0].start == WORLD_START
    for earlier, later in zip(slices, slices[1:], strict=False):
        assert earlier.days == SLICE_DAYS
        gap = (later.start - earlier.end).days - 1
        assert 0 <= gap <= MAX_GAP_DAYS, (earlier, later)
    assert slices[-1].days == SLICE_DAYS


def test_thirty_slices_span_about_fourteen_months() -> None:
    slices = allocate_slices(Random(3), 30, WORLD_START)
    months = (slices[-1].end - slices[0].start).days / 30
    assert 13 <= months <= 17, months


def test_same_seed_same_slices() -> None:
    first = allocate_slices(Random(9), 30, WORLD_START)
    assert first == allocate_slices(Random(9), 30, WORLD_START)


@pytest.mark.parametrize("seed", range(1, 41))
def test_the_leave_sits_mid_slice_with_room_before_and_after(seed: int) -> None:
    leave = place_leave(Random(seed), WINDOW)
    offset = (leave.start - WINDOW.start).days
    assert LEAVE_START_OFFSET_DAYS[0] <= offset <= LEAVE_START_OFFSET_DAYS[1]
    assert LEAVE_LENGTH_DAYS[0] <= leave.days <= LEAVE_LENGTH_DAYS[1]
    assert leave.end < WINDOW.end, "a day after the leave stays inside the slice"


def test_a_leave_is_only_placed_inside_a_full_slice() -> None:
    with pytest.raises(ValueError, match="14-day slice"):
        place_leave(Random(1), DateSpan(date(2026, 3, 1), date(2026, 3, 10)))


@pytest.mark.parametrize("seed", range(1, 41))
def test_now_falls_a_few_days_before_the_leave_at_the_start_of_a_working_day(seed: int) -> None:
    now = place_now(Random(seed), LEAVE, "Europe/Istanbul")
    lead = (LEAVE.start - now.date()).days
    assert NOW_LEAD_DAYS[0] <= lead <= NOW_LEAD_DAYS[1]
    assert now.tzinfo is not None and str(now.tzinfo) == "Europe/Istanbul"
    assert (now.hour, now.minute) == (9, 0)
    assert now.date() >= WINDOW.start


def test_without_planted_facts_the_interval_spans_window_start_to_before_the_leave() -> None:
    interval = stable_interval(WINDOW, LEAVE, date(2026, 3, 6), [])
    assert interval == DateSpan(WINDOW.start, LEAVE.start - timedelta(days=1))


def test_the_latest_fact_already_observable_sets_the_lower_bound() -> None:
    facts = [date(2026, 3, 2), date(2026, 3, 4)]
    interval = stable_interval(WINDOW, LEAVE, date(2026, 3, 6), facts)
    assert interval.start == date(2026, 3, 4)
    assert interval.end == date(2026, 3, 9)


def test_a_fact_arriving_after_today_sets_the_upper_bound_to_the_day_before_it() -> None:
    interval = stable_interval(WINDOW, LEAVE, date(2026, 3, 6), [date(2026, 3, 8)])
    assert interval == DateSpan(WINDOW.start, date(2026, 3, 7))


def test_a_fact_observable_today_or_after_the_leave_does_not_narrow_the_wrong_side() -> None:
    facts = [date(2026, 3, 6), date(2026, 3, 13)]
    interval = stable_interval(WINDOW, LEAVE, date(2026, 3, 6), facts)
    assert interval == DateSpan(date(2026, 3, 6), LEAVE.start - timedelta(days=1))


def test_today_always_lies_inside_the_derived_interval() -> None:
    for seed in range(1, 41):
        rng = Random(seed)
        leave = place_leave(rng, WINDOW)
        today = place_now(rng, leave, "Europe/Istanbul").date()
        dates = [WINDOW.start + timedelta(days=rng.randint(0, 13)) for _ in range(4)]
        interval = stable_interval(WINDOW, leave, today, dates)
        assert interval.contains(today), (today, interval, dates)


def test_the_interval_is_only_derived_for_a_now_before_the_leave() -> None:
    with pytest.raises(ValueError, match="before the leave"):
        stable_interval(WINDOW, LEAVE, LEAVE.start, [])
