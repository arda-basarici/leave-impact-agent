"""The event log in memory with the store's semantics, so the worker runs at the unit level.

The worker is written against ``LogCommands`` and not the PostgreSQL module, and this is
the second implementation of those commands: the same receipts (equal content under a held
identifier, a repeated claim under a held nonce), the same conflicts (other content under a
held identifier, raised as ``LogStoreConflict`` before the transition), the same settlement
filled under the closing event from the attempt's account and a ledger head, the same
refusals by type on ``append``, and the same cutoff rule for a caller's state (used when its
counters agree with the log, folded otherwise). What it has none of is a lock, a wire or a
schema: a single ``threading.Lock`` serializes the commands so two appenders in one test
behave as two connections would in their legal orders, and nothing here can be unavailable.

A test holds this log to the real store over the sixteen histories (same commands, same
positions, same events), so a worker test that passes here states something about the
store's behaviour and not only about this file's. The ``boundary`` seam fires at the store's
three points of a writing command so an ordering test reads the same names.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from leaveimpact.agent import ledger
from leaveimpact.agent.ledger import LedgerEntry, LedgerHead
from leaveimpact.agent.log_events import (
    Abandoned,
    Admitted,
    CapExhausted,
    ClosingEvent,
    CommitOverride,
    Completed,
    Envelope,
    Event,
    Failed,
    LoggedEvent,
    LoggedSettlement,
    Producer,
    SegmentStarted,
    Stamping,
    WorkerStamp,
    event_bytes,
    event_key,
    kind_of,
)
from leaveimpact.agent.log_store import LogStoreConflict
from leaveimpact.agent.log_transition import (
    Appended,
    AttemptState,
    Received,
    Refused,
    Rules,
    Transition,
    fold,
    next_state,
)
from leaveimpact.core.run_account import settle
from leaveimpact.core.run_timing import HarnessRevision
from tests.unit import format_fixtures as cases

PLENTY = 10**15


@dataclass
class Ticking:
    """A clock advancing one second per reading from ``start``; the default."""

    start: datetime = cases.ADMITTED
    readings: int = 0

    def __call__(self) -> datetime:
        self.readings += 1
        return self.start + timedelta(seconds=self.readings)


def _no_boundary(name: str) -> None:
    return None


@dataclass
class MemoryLog:
    """Every attempt's log, the segment-start events by claim nonce, and one ledger head per
    reserving attempt, behind one lock. ``clock`` gives each appended event its timestamp."""

    clock: Callable[[], datetime] = field(default_factory=Ticking)
    boundary: Callable[[str], None] = _no_boundary
    logs: dict[tuple[str, int], list[LoggedEvent]] = field(
        default_factory=dict[tuple[str, int], list[LoggedEvent]]
    )
    nonces: dict[tuple[str, int, str], LoggedEvent] = field(
        default_factory=dict[tuple[str, int, str], LoggedEvent]
    )
    heads: dict[tuple[str, int], LedgerHead] = field(
        default_factory=dict[tuple[str, int], LedgerHead]
    )
    entries: list[LedgerEntry] = field(default_factory=list[LedgerEntry])
    lock: threading.Lock = field(default_factory=threading.Lock)

    # --- seeding -----------------------------------------------------------------------

    def seed(self, events: tuple[LoggedEvent, ...]) -> None:
        """``events`` as an attempt's stored log, the head reserved when its admission does.
        The first event is the admission; the rest are stored as given, nonces included."""
        first = events[0]
        assert isinstance(first.event, Admitted), "a log starts with its admission"
        inputs = first.event.inputs
        key = (inputs.run_id, inputs.attempt)
        assert key not in self.logs, f"{key} is seeded once"
        self.logs[key] = list(events)
        for logged in events:
            if isinstance(logged.event, SegmentStarted):
                self.nonces[(*key, logged.event.nonce)] = logged
        if inputs.reservation_pico_usd is not None:
            head = LedgerHead(threshold_pico_usd=PLENTY)
            entry, head = ledger.admitted(
                head, inputs.run_id, inputs.attempt, inputs.reservation_pico_usd
            )
            self.entries.append(entry)
            self.heads[key] = head

    def events(self, run_id: str, attempt: int) -> tuple[LoggedEvent, ...]:
        with self.lock:
            return tuple(self._log(run_id, attempt))

    # --- the commands ------------------------------------------------------------------

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState:
        with self.lock:
            return fold(self._log(run_id, attempt), rules)

    def now(self) -> datetime:
        with self.lock:
            return self.clock()

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
    ) -> Transition:
        event = SegmentStarted(harness, nonce, launch, override)
        with self.lock:
            log = self._log(run_id, attempt)
            self.boundary("locked")
            held = self.nonces.get((run_id, attempt, nonce))
            current = self._current(log, state, rules)
            if held is not None:
                stamp = held.stamp
                assert stamp is not None
                if event_bytes(held.event) != event_bytes(event):
                    raise LogStoreConflict(
                        f"run {run_id} attempt {attempt} holds another content under the "
                        f"claim nonce of the segment start at position {held.position}"
                    )
                if stamp.generation == current.generation:
                    return Received(held.position)
                return Refused(
                    f"the claim under this nonce opened generation {stamp.generation}, fenced "
                    f"by generation {current.generation}"
                )
            number = len(current.segments) + 1
            logged = LoggedEvent(len(log) + 1, self.clock(), WorkerStamp(number, number, 0), event)
            transition = next_state(current, logged, rules)
            self.boundary("decided")
            if isinstance(transition, Appended):
                log.append(logged)
                self.nonces[(run_id, attempt, nonce)] = logged
            self.boundary("before-commit")
            return transition

    def append(
        self,
        run_id: str,
        attempt: int,
        envelope: Envelope | Stamping,
        event: Event,
        *,
        rules: Rules,
        state: AttemptState | None = None,
    ) -> Transition:
        if isinstance(
            event, Admitted | SegmentStarted | Completed | CapExhausted | Failed | Abandoned
        ):
            raise ValueError(
                f"{kind_of(event).value} is appended through its own command, not append"
            )
        with self.lock:
            log = self._log(run_id, attempt)
            self.boundary("locked")
            stamped = _envelope_of(envelope)
            logged = LoggedEvent(len(log) + 1, self.clock(), stamped, event)
            received = _receipt(log, logged)
            if received is not None:
                return received
            transition = next_state(self._current(log, state, rules), logged, rules)
            self.boundary("decided")
            if isinstance(transition, Appended):
                log.append(logged)
            self.boundary("before-commit")
            return transition

    def close_attempt(
        self,
        run_id: str,
        attempt: int,
        envelope: Envelope | Stamping,
        closing: ClosingEvent,
        *,
        rules: Rules,
        state: AttemptState | None = None,
    ) -> Transition:
        if closing.settlement is not None:
            raise ValueError(
                "the store computes the settlement; pass the closing event without one"
            )
        with self.lock:
            log = self._log(run_id, attempt)
            self.boundary("locked")
            current = self._current(log, state, rules)
            if current.closed is not None:
                return _closed_again(current.closed, closing)
            stamped = _envelope_of(envelope)
            inputs = current.inputs
            assert inputs is not None
            settlement: LoggedSettlement | None = None
            written: tuple[LedgerEntry, LedgerHead] | None = None
            if inputs.reservation_pico_usd is not None:
                head = self.heads[(run_id, attempt)]
                computed = settle(current.account)
                entry, after = ledger.settled(
                    head,
                    run_id,
                    attempt,
                    reservation_pico_usd=inputs.reservation_pico_usd,
                    charged_pico_usd=computed.charged_pico_usd,
                )
                settlement = LoggedSettlement(
                    computed.charged_pico_usd, computed.state, computed.kept_reason, entry.revision
                )
                written = (entry, after)
            filled: ClosingEvent = replace(closing, settlement=settlement)
            logged = LoggedEvent(len(log) + 1, self.clock(), stamped, filled)
            transition = next_state(current, logged, rules)
            self.boundary("decided")
            if isinstance(transition, Appended):
                if written is not None:
                    self.entries.append(written[0])
                    self.heads[(run_id, attempt)] = written[1]
                log.append(logged)
            self.boundary("before-commit")
            return transition

    # --- internals ---------------------------------------------------------------------

    def _log(self, run_id: str, attempt: int) -> list[LoggedEvent]:
        try:
            return self.logs[(run_id, attempt)]
        except KeyError:
            raise ValueError(f"run {run_id} has no attempt {attempt}") from None

    def _current(
        self, log: list[LoggedEvent], state: AttemptState | None, rules: Rules
    ) -> AttemptState:
        if state is not None and state.last_position == len(log):
            return state
        return fold(log, rules)


def _envelope_of(envelope: Envelope | Stamping) -> Envelope:
    if isinstance(envelope, WorkerStamp | Producer):
        return envelope
    return envelope()


def _receipt(log: list[LoggedEvent], logged: LoggedEvent) -> Received | None:
    key = event_key(logged)
    for held in log:
        if event_key(held) != key:
            continue
        if event_bytes(held.event) == event_bytes(logged.event):
            return Received(held.position)
        raise LogStoreConflict(
            f"the log holds another content under the identifier of the "
            f"{kind_of(logged.event).value} at position {held.position}"
        )
    return None


def _closed_again(held: LoggedEvent, closing: ClosingEvent) -> Transition:
    held_event = held.event
    if kind_of(held_event) is not kind_of(closing):
        return Refused(f"the attempt is closed at position {held.position}")
    assert isinstance(held_event, Completed | CapExhausted | Failed | Abandoned)
    masked: ClosingEvent = replace(held_event, settlement=None)
    if event_bytes(masked) == event_bytes(closing):
        return Received(held.position)
    raise LogStoreConflict(
        f"the attempt is closed at position {held.position} by a {kind_of(closing).value} "
        f"with other content"
    )


__all__ = ["MemoryLog", "Ticking"]
