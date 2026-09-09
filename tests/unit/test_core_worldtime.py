"""World time: naive instants are refused, the two interval conventions hold at their ends,
and a run's ``today`` is read in the reference zone — the timezone-boundary case."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.worldtime import DateSpan, InstantSpan, RunContext, local_date

SCENARIO = ScenarioId("scenario_003")
WORLD = WorldVersion("4f2c")


def _utc(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=UTC)


def test_a_naive_now_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="now must be timezone-aware"):
        RunContext(SCENARIO, WORLD, datetime(2026, 9, 14, 9, 0), "Europe/Istanbul")


def test_an_unknown_reference_zone_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="Mars/Olympus"):
        RunContext(SCENARIO, WORLD, _utc(14, 9), "Mars/Olympus")


def test_today_is_read_in_the_reference_zone_not_utc() -> None:
    late_utc = _utc(14, 22, 30)
    assert RunContext(SCENARIO, WORLD, late_utc, "Europe/Istanbul").today == date(2026, 9, 15)
    assert RunContext(SCENARIO, WORLD, late_utc, "Europe/London").today == date(2026, 9, 14)


def test_local_date_refuses_a_naive_instant() -> None:
    with pytest.raises(ValueError, match="instant must be timezone-aware"):
        local_date(datetime(2026, 9, 14, 9, 0), "Europe/Istanbul")


def test_date_spans_are_inclusive_at_both_ends() -> None:
    leave = DateSpan(date(2026, 9, 10), date(2026, 9, 12))
    assert leave.contains(date(2026, 9, 10))
    assert leave.contains(date(2026, 9, 12))
    assert not leave.contains(date(2026, 9, 13))
    assert leave.days == 3
    assert DateSpan(date(2026, 9, 10), date(2026, 9, 10)).days == 1


def test_date_spans_touching_on_a_day_overlap() -> None:
    leave = DateSpan(date(2026, 9, 10), date(2026, 9, 12))
    assert leave.overlaps(DateSpan(date(2026, 9, 12), date(2026, 9, 14)))
    assert not leave.overlaps(DateSpan(date(2026, 9, 13), date(2026, 9, 14)))


def test_a_date_span_ending_before_it_starts_is_refused() -> None:
    with pytest.raises(ValueError, match="ends on or after it starts"):
        DateSpan(date(2026, 9, 12), date(2026, 9, 10))


def test_instant_spans_are_half_open() -> None:
    meeting = InstantSpan(_utc(14, 9), _utc(14, 10))
    assert meeting.contains(_utc(14, 9))
    assert meeting.contains(_utc(14, 9, 59))
    assert not meeting.contains(_utc(14, 10))


def test_back_to_back_instant_spans_do_not_overlap() -> None:
    first = InstantSpan(_utc(14, 9), _utc(14, 10))
    assert not first.overlaps(InstantSpan(_utc(14, 10), _utc(14, 11)))
    assert first.overlaps(InstantSpan(_utc(14, 9, 30), _utc(14, 11)))


def test_an_empty_or_reversed_instant_span_is_refused() -> None:
    with pytest.raises(ValueError, match="ends after it starts"):
        InstantSpan(_utc(14, 10), _utc(14, 10))
    with pytest.raises(ValueError, match="span start must be timezone-aware"):
        InstantSpan(datetime(2026, 9, 14, 9), _utc(14, 10))


def test_an_instant_span_crossing_midnight_in_one_zone_only() -> None:
    late_evening_london = InstantSpan(_utc(14, 22), _utc(14, 23))
    assert late_evening_london.local_dates("Europe/London") == DateSpan(
        date(2026, 9, 14), date(2026, 9, 14)
    )
    assert late_evening_london.local_dates("Europe/Istanbul") == DateSpan(
        date(2026, 9, 15), date(2026, 9, 15)
    )


def test_a_span_ending_exactly_at_local_midnight_stays_on_the_earlier_day() -> None:
    until_midnight_istanbul = InstantSpan(_utc(14, 20), _utc(14, 21))
    assert until_midnight_istanbul.local_dates("Europe/Istanbul") == DateSpan(
        date(2026, 9, 14), date(2026, 9, 14)
    )


LONDON = ZoneInfo("Europe/London")


def test_duration_across_a_spring_forward_is_elapsed_time_not_wall_clock() -> None:
    # 2026-03-29 01:00 UTC: London jumps from 01:00 GMT to 02:00 BST.
    span = InstantSpan(
        datetime(2026, 3, 29, 0, 30, tzinfo=LONDON), datetime(2026, 3, 29, 2, 30, tzinfo=LONDON)
    )
    assert span.duration == timedelta(hours=1)


def test_the_two_readings_of_a_fall_back_hour_are_distinct_ordered_instants() -> None:
    # 2026-10-25 01:00 UTC: London reads 01:30 twice; fold tells the readings apart.
    first, second = (
        datetime(2026, 10, 25, 1, 30, tzinfo=LONDON, fold=fold) for fold in (0, 1)
    )
    span = InstantSpan(first, second)
    assert span.duration == timedelta(hours=1)
    assert span.contains(first)
    assert not span.contains(second)


def test_local_dates_of_a_span_ending_at_midnight_after_a_fall_back() -> None:
    # Ends at local midnight of the 26th, one wall-clock hour longer than it looks.
    span = InstantSpan(
        datetime(2026, 10, 25, 23, 0, tzinfo=LONDON), datetime(2026, 10, 26, 0, 0, tzinfo=LONDON)
    )
    assert span.local_dates("Europe/London") == DateSpan(date(2026, 10, 25), date(2026, 10, 25))
