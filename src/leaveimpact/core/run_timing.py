"""How long a run took, from what the log holds: segments, two durations, and whether they
are whole.

Format 1 held one duration from one process's monotonic clock and one harness commit, and
a run that is killed and recovered has neither (the acceptance spike's measurement). A run
executes in *segments*, one per process that worked on it. Each segment has its own
monotonic clock, starting at zero, and its own harness revision. A run is in one of three
states at any moment: executing, waiting for an approval, stopped. The contract step's
ruling on time gives two durations over them, and they answer different questions:

- *Evidenced active time* is execution the log can show. Each segment contributes the
  offset of its last durable event, less the part of the approval wait that fell inside
  it. Stopped time is never on any segment's clock, so it needs no subtraction.
- *Elapsed time* is the wall clock from admission to the terminal event, downtime and
  waiting included.

A segment whose end was never recorded was killed, and what its process did after its last
durable event is unknowable from the stores: its contribution is a lower bound, and the
run's timing is *incomplete*. A latency table marks that, with the number of segments
beside it, so an interrupted run never reads as an unusually fast one.

The record holds the inputs only (the segments, the two wall-clock instants, where the
approval was requested and where the worker resumed) and the durations are functions over
them, so no stored duration can disagree with the segments it was summed from. A *stamp*
is where a worker's event sits: its segment, its offset on that segment's clock and its
position in the attempt's event order. An event produced outside a worker (an operator's
approval, an abandonment) has no stamp; the worker stamps its own transition when it
resumes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import cast

from leaveimpact.core.enums import require_member
from leaveimpact.core.run_trace import require_integer

GIT_SHA_LENGTH = 40


def require_commit(value: str, what: str) -> str:
    """``value`` if it is a full lower-case git commit SHA."""
    if len(value) != GIT_SHA_LENGTH or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{what} is a forty-hex git commit, got {value!r}")
    return value


class TreeState(StrEnum):
    """Whether the harness ran from the commit it names or from uncommitted changes over it."""

    CLEAN = "clean"
    DIRTY = "dirty"


@dataclass(frozen=True, slots=True)
class HarnessRevision:
    """The harness commit and the state of the tree it ran from; dirty is refused at reporting."""

    commit: str
    tree: TreeState

    def __post_init__(self) -> None:
        require_commit(self.commit, "the harness commit")
        require_member(self.tree, TreeState, "the tree state")


@dataclass(frozen=True, slots=True)
class Stamp:
    """Where a worker's event sits: its segment, its offset on that segment's monotonic
    clock, and its position in the attempt's event order."""

    segment: int
    offset_ms: int
    position: int

    def __post_init__(self) -> None:
        require_integer(self.segment, "a segment number", minimum=1)
        require_integer(self.offset_ms, "an offset in ms")
        require_integer(self.position, "a position", minimum=1)


@dataclass(frozen=True, slots=True)
class Segment:
    """One process's work on a run: the revision it ran, the offset of its last durable
    event, and whether its end was recorded (a pause or the terminal event) or it was
    killed with an unknown tail."""

    number: int
    harness: HarnessRevision
    last_offset_ms: int
    end_recorded: bool

    def __post_init__(self) -> None:
        require_integer(self.number, "a segment number", minimum=1)
        require_integer(self.last_offset_ms, "a segment's last offset in ms")
        if not isinstance(cast(object, self.end_recorded), bool):
            raise ValueError(f"end_recorded is a boolean, got {self.end_recorded!r}")


@dataclass(frozen=True, slots=True)
class Timing:
    """The inputs of a run's two durations; see the module.

    Segments are numbered from one without a gap. ``approval_requested`` is the stamp of the
    worker's request for approval and ``approval_resumed`` the stamp of its own transition
    once the approval was delivered; a resume exists only after a request, later in
    position and never in an earlier segment, and both sit inside their segments' evidenced
    offsets. The two instants are timezone-aware and the terminal one is not before the
    admission.
    """

    segments: tuple[Segment, ...]
    admitted_at: datetime
    terminal_at: datetime
    approval_requested: Stamp | None
    approval_resumed: Stamp | None

    def __post_init__(self) -> None:
        if not self.segments:
            raise ValueError("a run that executed has at least one segment")
        numbers = [segment.number for segment in self.segments]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(f"segments are numbered from one without a gap, got {numbers}")
        for what, instant in (("admitted_at", self.admitted_at), ("terminal_at", self.terminal_at)):
            if instant.utcoffset() is None:
                raise ValueError(f"{what} is a timezone-aware instant, got {instant!r}")
        if self.terminal_at < self.admitted_at:
            raise ValueError("the terminal event is not before the admission")
        requested, resumed = self.approval_requested, self.approval_resumed
        if resumed is not None and requested is None:
            raise ValueError("a worker resumes from an approval only after requesting one")
        for what, stamp in (("requested", requested), ("resumed", resumed)):
            if stamp is None:
                continue
            if stamp.segment > len(self.segments):
                raise ValueError(f"the approval was {what} in segment {stamp.segment}, not held")
            if stamp.offset_ms > self.segments[stamp.segment - 1].last_offset_ms:
                raise ValueError(f"the approval was {what} after its segment's last durable offset")
        if requested is not None and resumed is not None:
            if resumed.position <= requested.position or resumed.segment < requested.segment:
                raise ValueError("an approval is resumed after it is requested")
            if resumed.segment == requested.segment and resumed.offset_ms < requested.offset_ms:
                raise ValueError("an approval is resumed after it is requested")

    @property
    def harness_revisions(self) -> frozenset[HarnessRevision]:
        """The distinct revisions the segments ran; one for a run a report may use."""
        return frozenset(segment.harness for segment in self.segments)


def approval_wait_ms(timing: Timing, segment: Segment) -> int:
    """The part of the approval wait that fell on ``segment``'s clock.

    From the request to the resume when both sit in the segment; from the request to the
    segment's last offset when the wait outlived it; the whole of a segment that began and
    ended inside the wait; from the segment's start to the resume in the segment that
    resumed. A wait never resumed runs to the end of every segment from its request on.

    >>> from datetime import UTC, datetime
    >>> at = datetime(2026, 10, 4, tzinfo=UTC)
    >>> revision = HarnessRevision("a" * 40, TreeState.CLEAN)
    >>> first, second = Segment(1, revision, 900, True), Segment(2, revision, 400, True)
    >>> timing = Timing((first, second), at, at, Stamp(1, 700, 5), Stamp(2, 50, 7))
    >>> approval_wait_ms(timing, first), approval_wait_ms(timing, second)
    (200, 50)
    """
    requested, resumed = timing.approval_requested, timing.approval_resumed
    if requested is None or segment.number < requested.segment:
        return 0
    if resumed is not None and segment.number > resumed.segment:
        return 0
    start = requested.offset_ms if segment.number == requested.segment else 0
    end = (
        resumed.offset_ms
        if resumed is not None and segment.number == resumed.segment
        else segment.last_offset_ms
    )
    return end - start


def evidenced_active_ms(timing: Timing) -> int:
    """Execution the log can show: each segment's last durable offset less its share of the
    approval wait. A lower bound when the timing is incomplete."""
    return sum(
        segment.last_offset_ms - approval_wait_ms(timing, segment) for segment in timing.segments
    )


def elapsed_ms(timing: Timing) -> int:
    """The wall clock from admission to the terminal event, in whole milliseconds."""
    delta = timing.terminal_at - timing.admitted_at
    return delta.days * 86_400_000 + delta.seconds * 1_000 + delta.microseconds // 1_000


def timing_complete(timing: Timing) -> bool:
    """Whether every segment's end was recorded; if not, a killed segment's tail is missing
    and the evidenced active time is a lower bound."""
    return all(segment.end_recorded for segment in timing.segments)


__all__ = [
    "GIT_SHA_LENGTH",
    "HarnessRevision",
    "Segment",
    "Stamp",
    "Timing",
    "TreeState",
    "approval_wait_ms",
    "elapsed_ms",
    "evidenced_active_ms",
    "require_commit",
    "timing_complete",
]
