"""The narration stream: an attempt's lines as server-sent events, one subscription per
explicitly named attempt, built as an asynchronous generator that awaits between ticks and
runs each short synchronous read on the thread pool (the demo milestone's entry ruling on
narration from the log, as the narration step's forks shaped it).

Each tick is one synchronous read on the thread pool in a session of its own, opened and
closed inside it, so a waiting stream holds no thread, no connection and no transaction
between ticks. A subscription's first tick loads the attempt whole and narrates it; every
later tick reads only the events past the position the subscription holds and extends its
state and lines through the transition one event at a time (``narration.extend``), so a
tick costs the new events and not the log's length (the live pages step: the first shape
re-folded the whole log every tick, and the measurement below is what changed it). The
generator sends the lines past its cursor. The cursor is a position: the
page's first connection says where its server-rendered lines ended through the ``after``
query parameter, a browser's reconnection says it through ``Last-Event-ID``, which wins
when both are present, and the client keys what it shows by attempt and position, so a
stale reconnection cannot duplicate a line. A cursor below the attempt's terminal position
receives the remainder and then the closing frame; one equal to it receives HTTP 204, which
stops a browser's reconnection; one that is not a non-negative integer or lies beyond the
last committed position is a 400, answered after admission, so an unpublished name stays
the one not-found page whatever cursor it carries, and a browser stops on it as on a 204,
which is right, since the client's position is wrong and a reload repairs it.

The wire form: ordinary frames are ``event: line`` with the position as the id and the
line's fields as JSON, since a named event does not reach a browser's ``onmessage`` and the
kind travels inside the data; the terminal event is the ``closed`` frame, the same fields
with the ending's status beside them, so a live visitor reads the same terminal line a
replay shows; a tick that finds the store unavailable ends the stream with an
``unavailable`` frame rather than silence, and the client stops on it; a comment line is the
heartbeat while nothing arrives. The lines are built once by the narration module and the
client places them as text content, never markup, so the pages' escaping discipline holds
on the client by construction.

**Subscription ownership.** Concurrent streams are bounded per process; the route acquires
a slot before the response starts and answers 503 beyond the bound, and the slot is released
in the generator's ``finally`` and again, idempotently, by the response's background task,
so every exit releases it: a normal close, the unavailable ending, a cancellation, and a
disconnection before the first frame, when the generator may never have started. The
disconnect mechanism was probed on the pinned stack before this shape was chosen: under
Uvicorn 0.54, which declares ASGI spec 2.3, Starlette's streaming response listens for the
disconnect in a task group and cancels the body generator at its next await, and the test
client's early close cancels the application's scope the same way; in both the generator
received ``CancelledError`` within a millisecond of the client going away and its
``finally`` ran. No disconnect polling is done, since under that spec the listener owns the
receive channel. A tick's thread is not abandoned on cancellation (anyio's default), so the
session is closed by the tick function before the cancellation lands.

Cost per tick, measured on the instance (the live pages step, ``probes/tick-cost``, two
runs on 2026-10-30 over the replay set's thirty closed attempts of 32 to 63 events): a tick
that folds the whole log, a subscription's first, cost 0.12 to 0.69 s of CPU at the 95th
percentile, the store's load and the narration's own replay about equal halves of it; a
tick that finds nothing new (the connect, the version check, the row read, the close)
6.5 to 11.1 ms; and an event folded 1.8 to 5.2 ms. So a subscription pays the whole fold
once and then the new events, about 0.02 s of CPU a second at a run's worst rates (1.3 events a
second), and eight subscriptions on one open attempt about 0.14 s of the one interpreter's
second, under the step's budget of a fifth; that forecast is checked on the first public
attempt at the live path's acceptance step, where the shared fold is the move if it
misses. Each statement runs under the store's three-second bound and the connect under its
own, so a wedged tick can take twelve seconds, under the heartbeat interval. The pacing
constants are the process's; the subscription bound was set by the instance's memory
baseline (the demo milestone's step 10, ``probes/memory-baseline``): memory did not move
with loopers (218 to 232 MiB at one, four and eight), the thread pool did not bind (27 of
40 threads at the heaviest level), and throughput stayed flat at about 2.2 whole-stream
fetches a second from one client upward, read then as the single worker's CPU and since
measured as the whole fold's; the bound stays at eight under that rule.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Protocol

import anyio

from leaveimpact.agent.log_ending import ending_of
from leaveimpact.agent.log_events import LoggedEvent
from leaveimpact.agent.log_store import LogStoreInvariantBroken, LogStoreUnavailable
from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.app.narration import Line, extend, narration
from leaveimpact.core.run_record import TerminalStatus

TICK_SECONDS = 1.0
"""About how often a stream over a running attempt reads the log."""
HEARTBEAT_SECONDS = 15.0
"""The longest silence before a comment line keeps the connection alive."""
SUBSCRIPTION_BOUND = 8
"""Concurrent streams one process serves; the next is refused. Held to the memory
baseline's committed reading by ``tests/unit/test_memory_baseline.py``."""

MEDIA_TYPE = "text/event-stream"
HEARTBEAT = b": keepalive\n\n"
LINE_EVENT = "line"
CLOSED_EVENT = "closed"
UNAVAILABLE_EVENT = "unavailable"


@dataclass(frozen=True, slots=True)
class Pacing:
    """The stream's cadence and bound: the module's constants by default, faster in a test."""

    tick_seconds: float = TICK_SECONDS
    heartbeat_seconds: float = HEARTBEAT_SECONDS
    bound: int = SUBSCRIPTION_BOUND


DEFAULT_PACING = Pacing()
"""The process's pacing: the module's constants."""


# --- Subscriptions ------------------------------------------------------------------------


class Slot:
    """One held subscription; ``release`` is idempotent, so the generator's ``finally`` and
    the response's background task may both call it."""

    __slots__ = ("_held", "_subscriptions")

    def __init__(self, subscriptions: Subscriptions) -> None:
        self._subscriptions = subscriptions
        self._held = True

    def release(self) -> None:
        if self._held:
            self._held = False
            self._subscriptions.release_one()


class Subscriptions:
    """The process's bound on concurrent streams, acquired under a lock.

    >>> subscriptions = Subscriptions(1)
    >>> first = subscriptions.try_acquire()
    >>> first is not None, subscriptions.try_acquire() is None, subscriptions.held
    (True, True, 1)
    >>> first.release(); first.release(); subscriptions.held
    0
    """

    def __init__(self, bound: int) -> None:
        if bound < 1:
            raise ValueError(f"a subscription bound is at least one, got {bound}")
        self._bound = bound
        self._held = 0
        self._lock = threading.Lock()

    @property
    def held(self) -> int:
        with self._lock:
            return self._held

    def try_acquire(self) -> Slot | None:
        """A slot, or ``None`` when the bound is reached."""
        with self._lock:
            if self._held >= self._bound:
                return None
            self._held += 1
        return Slot(self)

    def release_one(self) -> None:
        """One slot given back; a slot calls it once, whatever its callers do."""
        with self._lock:
            assert self._held > 0, "a slot is released once"
            self._held -= 1


# --- The cursor -------------------------------------------------------------------------

_CURSOR_DIGITS = 18
"""The most digits a cursor may have; every position of every log fits."""


@dataclass(frozen=True, slots=True)
class Cursor:
    """Where a subscription starts: the last position the client holds, zero for none."""

    position: int


@dataclass(frozen=True, slots=True)
class RejectedCursor:
    """A cursor the stream refuses: not a non-negative integer, or beyond the log."""

    reason: str


def cursor_of(
    after: str | None, last_event_id: str | None, last_position: int
) -> Cursor | RejectedCursor:
    """The cursor a request names, ``Last-Event-ID`` over ``after``, validated against the
    attempt's last committed position.

    >>> cursor_of(None, None, 5), cursor_of("3", None, 5), cursor_of("3", "4", 5)
    (Cursor(position=0), Cursor(position=3), Cursor(position=4))
    >>> cursor_of("5", None, 5), cursor_of("6", None, 5).reason
    (Cursor(position=5), 'the cursor is beyond the last committed position')
    >>> cursor_of("x", None, 5).reason, cursor_of("-1", None, 5).reason
    ('the cursor is not a position', 'the cursor is not a position')

    A position is ASCII decimal digits, bounded in length: ``str.isdigit`` admits other
    scripts' digits that ``int`` refuses, and the conversion itself is limited in digits
    (the external read of the step's commits, first finding).

    >>> cursor_of("\\u00b2", None, 5).reason, cursor_of("9" * 5000, None, 5).reason
    ('the cursor is not a position', 'the cursor is not a position')
    """
    raw = after if last_event_id is None else last_event_id
    if raw is None:
        return Cursor(0)
    text = raw.strip()
    if not (text.isascii() and text.isdigit() and len(text) <= _CURSOR_DIGITS):
        return RejectedCursor("the cursor is not a position")
    position = int(text)
    if position > last_position:
        return RejectedCursor("the cursor is beyond the last committed position")
    return Cursor(position)


# --- The frames -------------------------------------------------------------------------


def _fields(line: Line) -> dict[str, object]:
    return {
        "position": line.position,
        "recorded_at": line.recorded_at.isoformat(),
        "kind": line.kind.value,
        "text": line.text,
    }


def _frame(event: str, identifier: int | None, data: dict[str, object]) -> bytes:
    # JSON holds no raw newline, so one data line carries the whole payload.
    head = "" if identifier is None else f"id: {identifier}\n"
    return f"{head}event: {event}\ndata: {json.dumps(data)}\n\n".encode()


def line_frame(line: Line) -> bytes:
    """An ordinary frame: the position as the id, the line's fields as the data."""
    return _frame(LINE_EVENT, line.position, _fields(line))


def closing_frame(line: Line, status: TerminalStatus) -> bytes:
    """The terminal frame: the closing event's own line with the ending's status beside it."""
    return _frame(CLOSED_EVENT, line.position, {**_fields(line), "status": status.value})


def unavailable_frame(reason: str) -> bytes:
    """The stream's own ending when a tick cannot read the log."""
    return _frame(UNAVAILABLE_EVENT, None, {"reason": reason})


# --- The generator ----------------------------------------------------------------------


class TickSession(Protocol):
    """A log session one tick opens and closes: the whole load for a subscription's first
    tick, the events past a position for every later one."""

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState: ...

    def events_after(
        self, run_id: str, attempt: int, *, after: int
    ) -> tuple[LoggedEvent, ...]: ...

    def close(self) -> None: ...


Sessions = Callable[[], TickSession]
"""A fresh session per tick, as the composition root provides them."""

_UNAVAILABLE = (LogStoreUnavailable, LogStoreInvariantBroken, ValueError)
"""What a tick's read may raise: the store not answering or not bootstrapped, and an
attempt the log no longer holds, a defect of the deployment the stream reports as such."""


def _load(sessions: Sessions, run_id: str, attempt: int, rules: Rules) -> AttemptState:
    """A subscription's first tick: the whole fold, in a session of its own."""
    session = sessions()
    try:
        return session.load(run_id, attempt, rules=rules)
    finally:
        session.close()


def _events_after(
    sessions: Sessions, run_id: str, attempt: int, after: int
) -> tuple[LoggedEvent, ...]:
    """Every later tick: the events past ``after``, in a session of its own."""
    session = sessions()
    try:
        return session.events_after(run_id, attempt, after=after)
    finally:
        session.close()


async def frames(
    sessions: Sessions,
    run_id: str,
    attempt: int,
    rules: Rules,
    *,
    cursor: int,
    pacing: Pacing,
    slot: Slot,
) -> AsyncIterator[bytes]:
    """The frames after ``cursor`` for the attempt, under ``rules``: every committed line
    past the cursor as it is found, a heartbeat through silence, the closing frame at the
    terminal event, the unavailable frame if a read fails; the slot released on every exit.
    The first tick loads and narrates the whole log and the lines at or below the cursor are
    skipped; every later tick extends the held state by the events past its position, so
    the lines it yields are new by construction."""
    sent = cursor
    state: AttemptState | None = None
    last_frame_at = time.monotonic()
    try:
        while True:
            try:
                if state is None:
                    state = await anyio.to_thread.run_sync(_load, sessions, run_id, attempt, rules)
                    fresh = narration(state, rules)
                else:
                    new = await anyio.to_thread.run_sync(
                        _events_after, sessions, run_id, attempt, state.last_position
                    )
                    state, fresh = extend(state, new, rules)
            except _UNAVAILABLE as error:
                yield unavailable_frame(f"the log could not be read: {type(error).__name__}")
                return
            closed = state.closed
            for line in fresh:
                if line.position <= sent:
                    continue
                if closed is not None and line.position == closed.position:
                    yield closing_frame(line, ending_of(state).status)
                    return
                yield line_frame(line)
                sent = line.position
                last_frame_at = time.monotonic()
            if time.monotonic() - last_frame_at >= pacing.heartbeat_seconds:
                yield HEARTBEAT
                last_frame_at = time.monotonic()
            await anyio.sleep(pacing.tick_seconds)
    finally:
        slot.release()


__all__ = [
    "CLOSED_EVENT",
    "DEFAULT_PACING",
    "HEARTBEAT",
    "LINE_EVENT",
    "MEDIA_TYPE",
    "UNAVAILABLE_EVENT",
    "Cursor",
    "Pacing",
    "RejectedCursor",
    "Sessions",
    "Slot",
    "Subscriptions",
    "TickSession",
    "closing_frame",
    "cursor_of",
    "frames",
    "line_frame",
    "unavailable_frame",
]
