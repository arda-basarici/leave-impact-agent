"""The stamped writer a worker's nodes append through: one generation's segment, its offsets
from a monotonic clock drawn under the lock, and the attempt's state threaded forward.

A worker owns one generation of one attempt for the life of one process (the event log
step's ruling on recovery and endings, part 5), and every durable step it takes is an event
under a ``WorkerStamp`` of that generation, the segment the claim opened and an offset on
the segment's clock. This module is the one place a worker's envelope is made: the nodes
hand it events and get the state after them, and the store, which receives the stamp as a
factory, draws the offset once the attempt row is locked (the ruling on the event, part 9).
The clock is ``time.monotonic`` from the instant of the claim, so offsets are nondecreasing
in position order within the segment and say nothing about wall time.

The state is threaded, not folded: each command passes the state it holds and keeps the
state the store returns (the store group's design: equal counters on an append-only log are
equal prefixes, and the store folds only when they disagree). An ``Appended`` replaces it.
A ``Received`` is the receipt for an event the log already holds, which a recovering worker
meets when it replays a step whose event survived its predecessor's death; the state it
holds already includes that event, so nothing changes, and a receipt for an event it does
not hold is a fault of this harness and raises. A ``Refused`` becomes ``AppendRefused``: the
fence, the stop, a closure, or the worker's own illegal event, which the driver tells
apart by reloading the log and never by the reason's text (the worker group's first fork).
The store's own exceptions propagate unchanged.

``LogCommands`` names the five commands a worker uses, so the driver and the nodes are
written against the commands and not the PostgreSQL module: the store satisfies it
structurally, and a test's in-memory implementation runs the same worker at the unit level.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from leaveimpact.agent.log_events import (
    ClosingEvent,
    CommitOverride,
    Envelope,
    Event,
    LoggedEvent,
    Stamping,
    WorkerStamp,
    event_key,
)
from leaveimpact.agent.log_transition import (
    Appended,
    AttemptState,
    Received,
    Refused,
    Rules,
    Transition,
)
from leaveimpact.core.run_timing import HarnessRevision


class LogCommands(Protocol):
    """The event log's commands a worker uses; ``LogStore`` satisfies it, and so does a
    test's in-memory log. Each command's contract is the store's."""

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState: ...

    def claim(
        self,
        run_id: str,
        attempt: int,
        *,
        harness: HarnessRevision,
        nonce: str,
        launch: str,
        rules: Rules,
        override: CommitOverride | None = None,
        state: AttemptState | None = None,
    ) -> Transition: ...

    def append(
        self,
        run_id: str,
        attempt: int,
        envelope: Envelope | Stamping,
        event: Event,
        *,
        rules: Rules,
        state: AttemptState | None = None,
    ) -> Transition: ...

    def close_attempt(
        self,
        run_id: str,
        attempt: int,
        envelope: Envelope | Stamping,
        closing: ClosingEvent,
        *,
        rules: Rules,
        state: AttemptState | None = None,
    ) -> Transition: ...

    def now(self) -> datetime: ...


class AppendRefused(Exception):
    """The transition refused a worker's event. What it means, the fence, the stop, a closure
    or the worker's own illegal event, is the driver's to read from the log; the reason is
    kept for the record and is never the classification's input."""

    def __init__(self, refused: Refused, event: Event) -> None:
        super().__init__(refused.reason)
        self.refused = refused
        self.event = event


@dataclass
class Appender:
    """One generation's writer over ``store``: the stamp factory the store calls under the
    lock, and the two writing commands with the state threaded through them.

    ``origin`` is the monotonic instant the segment's clock starts at, the claim's; a
    recovering worker's appender starts a new one with its own claim. ``monotonic`` is the
    clock, a seam for tests that script offsets.
    """

    store: LogCommands
    run_id: str
    attempt: int
    rules: Rules
    generation: int
    segment: int
    state: AttemptState
    origin: float
    monotonic: Callable[[], float] = time.monotonic

    @classmethod
    def after_claim(
        cls,
        store: LogCommands,
        state: AttemptState,
        *,
        rules: Rules,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> Appender:
        """The appender of the segment ``state``'s claim just opened, its clock starting now."""
        inputs, current = state.inputs, state.current_segment
        if inputs is None or current is None:
            raise ValueError("an appender follows a claim; the state holds no segment")
        return cls(
            store,
            inputs.run_id,
            inputs.attempt,
            rules,
            state.generation,
            current.number,
            state,
            monotonic(),
            monotonic,
        )

    def stamp(self) -> WorkerStamp:
        """The worker's envelope now: the generation, the segment, and whole milliseconds on
        the segment's clock. Called by the store under the lock, never before."""
        offset_ms = int((self.monotonic() - self.origin) * 1000)
        return WorkerStamp(self.generation, self.segment, offset_ms)

    def append(self, event: Event) -> AttemptState:
        """``event`` under this worker's stamp; the state after it."""
        transition = self.store.append(
            self.run_id, self.attempt, self.stamp, event, rules=self.rules, state=self.state
        )
        return self._threaded(transition, event)

    def close(self, closing: ClosingEvent) -> AttemptState:
        """The closing event under this worker's stamp, the store filling its settlement; the
        state after it."""
        transition = self.store.close_attempt(
            self.run_id, self.attempt, self.stamp, closing, rules=self.rules, state=self.state
        )
        return self._threaded(transition, closing)

    def _threaded(self, transition: Transition, event: Event) -> AttemptState:
        match transition:
            case Appended(state):
                self.state = state
                return state
            case Received(position):
                held = {event_key(logged) for logged in self.state.events}
                # The key is a function of the kind and the content; the provenance given
                # here is a stand-in and reaches no comparison.
                at = self.state.events[0].timestamp
                key = event_key(LoggedEvent(position, at, self.stamp(), event))
                if key not in held:
                    raise RuntimeError(
                        f"the log holds the worker's event at position {position}, which the "
                        f"state the worker threads does not"
                    )
                return self.state
            case Refused():
                raise AppendRefused(transition, event)


__all__ = ["AppendRefused", "Appender", "LogCommands"]
