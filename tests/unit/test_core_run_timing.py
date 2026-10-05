"""A run's two durations from its segments: evidenced active time less the approval wait
that fell on each segment's own clock, elapsed time on the wall clock, and completeness
lost to a killed segment."""

from datetime import UTC, datetime, timedelta

import pytest

from leaveimpact.core.run_timing import (
    HarnessRevision,
    Segment,
    Stamp,
    Timing,
    TreeState,
    approval_wait_ms,
    elapsed_ms,
    evidenced_active_ms,
    signed_elapsed_ms,
    timing_complete,
)

REVISION = HarnessRevision("a" * 40, TreeState.CLEAN)
ADMITTED = datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)


def segments(*last_offsets: int, killed: tuple[int, ...] = ()) -> tuple[Segment, ...]:
    return tuple(
        Segment(number, REVISION, last_offset, number not in killed)
        for number, last_offset in enumerate(last_offsets, start=1)
    )


def timing(
    held: tuple[Segment, ...],
    requested: Stamp | None = None,
    resumed: Stamp | None = None,
    elapsed: timedelta = timedelta(seconds=30),
) -> Timing:
    return Timing(held, ADMITTED, ADMITTED + elapsed, requested, resumed)


def test_one_uninterrupted_segment_with_an_automatic_approval() -> None:
    run = timing(segments(9_334), Stamp(1, 9_000, 14), Stamp(1, 9_004, 15))
    assert evidenced_active_ms(run) == 9_330
    assert timing_complete(run)
    assert elapsed_ms(run) == 30_000


def test_a_killed_segment_makes_the_active_time_a_lower_bound() -> None:
    run = timing(segments(4_200, 5_100, killed=(1,)), elapsed=timedelta(minutes=3))
    assert evidenced_active_ms(run) == 9_300
    assert not timing_complete(run)
    assert elapsed_ms(run) == 180_000


def test_an_approval_wait_across_a_restart_is_taken_from_each_segments_own_clock() -> None:
    """Requested at 7,000 of a segment whose last durable offset is 7,900; a second segment
    that began and died inside the wait (600); resumed at 50 of the third, which then ran to
    2,050. Waiting: 900, 600 and 50. Active: 7,000, 0 and 2,000."""
    held = segments(7_900, 600, 2_050, killed=(2,))
    run = timing(held, Stamp(1, 7_000, 11), Stamp(3, 50, 14), elapsed=timedelta(hours=2))
    assert [approval_wait_ms(run, segment) for segment in held] == [900, 600, 50]
    assert evidenced_active_ms(run) == 9_000
    assert elapsed_ms(run) == 7_200_000
    assert not timing_complete(run)


def test_a_wait_never_resumed_runs_to_the_end_of_every_segment_after_its_request() -> None:
    held = segments(5_000, 800)
    run = timing(held, Stamp(1, 4_500, 9))
    assert [approval_wait_ms(run, segment) for segment in held] == [500, 800]
    assert evidenced_active_ms(run) == 4_500


def test_elapsed_time_is_whole_milliseconds_of_the_wall_clock() -> None:
    run = timing(segments(10), elapsed=timedelta(days=1, seconds=2, microseconds=3_999))
    assert elapsed_ms(run) == 86_402_003


def test_the_segments_revisions_are_listed_so_a_mismatch_can_be_found() -> None:
    other = HarnessRevision("b" * 40, TreeState.DIRTY)
    run = timing((Segment(1, REVISION, 100, False), Segment(2, other, 200, True)))
    assert run.harness_revisions == {REVISION, other}
    assert timing(segments(100, 200)).harness_revisions == {REVISION}


def test_timing_refuses_what_no_log_could_hold() -> None:
    with pytest.raises(ValueError, match="numbered from one without a gap"):
        timing((Segment(2, REVISION, 100, True),))
    with pytest.raises(ValueError, match="timezone-aware"):
        Timing(segments(1), datetime(2026, 10, 4), ADMITTED, None, None)
    with pytest.raises(ValueError, match="only after requesting one"):
        timing(segments(100), None, Stamp(1, 50, 3))
    with pytest.raises(ValueError, match="requested in segment 2, not held"):
        timing(segments(100), Stamp(2, 0, 3))
    with pytest.raises(ValueError, match="after its segment's last durable offset"):
        timing(segments(100), Stamp(1, 101, 3))
    with pytest.raises(ValueError, match="resumed after it is requested"):
        timing(segments(100), Stamp(1, 60, 5), Stamp(1, 70, 4))
    with pytest.raises(ValueError, match="resumed after it is requested"):
        timing(segments(100), Stamp(1, 60, 5), Stamp(1, 50, 6))
    with pytest.raises(ValueError, match="resumed after it is requested"):
        timing(segments(100, 100), Stamp(2, 60, 5), Stamp(1, 70, 6))
    with pytest.raises(ValueError, match="forty-hex git commit"):
        HarnessRevision("abc", TreeState.CLEAN)
    with pytest.raises(ValueError, match="end_recorded is a boolean"):
        Segment(1, REVISION, 100, 1)  # type: ignore[arg-type]


def test_no_segment_is_the_never_claimed_attempt_with_a_complete_timing() -> None:
    """An attempt admitted and closed by an abandon command before any claim (the event log
    step's ruling on admission): nothing ran, no tail is missing, and the elapsed time runs
    from the admission to the command."""
    never = timing((), elapsed=timedelta(hours=2))
    assert never.segments == ()
    assert (evidenced_active_ms(never), timing_complete(never)) == (0, True)
    assert (elapsed_ms(never), signed_elapsed_ms(never)) == (7_200_000, 7_200_000)
    assert never.harness_revisions == frozenset()
    with pytest.raises(ValueError, match="requested in segment 1, not held"):
        timing((), Stamp(1, 0, 3))


def test_a_terminal_instant_before_the_admission_is_kept_and_gives_no_elapsed_duration() -> None:
    """The log's clock can step back between the two events (the event log step's ruling on
    an export that will not construct): both instants are kept as logged, the signed
    difference is a function of them, and the elapsed duration is unavailable, never
    clamped or made absolute."""
    stepped = timing(segments(1_200), elapsed=timedelta(milliseconds=-300))
    assert stepped.terminal_at < stepped.admitted_at
    assert signed_elapsed_ms(stepped) == -300
    assert elapsed_ms(stepped) is None
    assert evidenced_active_ms(stepped) == 1_200
    assert signed_elapsed_ms(timing(segments(1), elapsed=timedelta(microseconds=-1_500))) == -2
    assert elapsed_ms(timing(segments(1), elapsed=timedelta(0))) == 0
