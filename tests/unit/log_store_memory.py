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

A test holds this log to the real store over the seventeen histories (same commands, same
positions, same events), so a worker test that passes here states something about the
store's behaviour and not only about this file's. The ``boundary`` seam fires at the store's
three points of a writing command so an ordering test reads the same names.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from leaveimpact.agent import ledger
from leaveimpact.agent.inventory import PublicationRecord
from leaveimpact.agent.ledger import LedgerEntry, LedgerHead
from leaveimpact.agent.log_events import (
    Abandoned,
    Admitted,
    CapExhausted,
    ClosingEvent,
    CommitOverride,
    Completed,
    Declined,
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
    log_format_of,
)
from leaveimpact.agent.log_store import (
    AdmissionReceipt,
    AdmissionRefusal,
    AdmissionRequest,
    AdmissionResult,
    AdmittedAttempt,
    AttemptRef,
    LogStoreConflict,
    RecordedAdmission,
    SlotHolder,
)
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
LEDGER = "ledger-memory"
"""The one ledger this store admits reserving attempts against, the name its status read
answers; the real store records the admission request's."""


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


@dataclass(frozen=True, slots=True)
class _RecordedRequest:
    """An admission request as recorded: what it asked (the run, the attempt, the
    admission's bytes, the ledger), the result it got, and when."""

    asked: tuple[str, int, bytes, str | None]
    result: AdmissionResult
    recorded_at: datetime


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
    requests: dict[str, _RecordedRequest] = field(default_factory=dict[str, _RecordedRequest])
    threshold: int = PLENTY
    """The room every reserving admission is judged against: this log keeps a head per
    attempt, so the room is the threshold whole, where the store judges against the
    ledger head's running total."""
    lock: threading.Lock = field(default_factory=threading.Lock)
    serial: threading.Lock = field(default_factory=threading.Lock)
    """The store's session-level lock: held across the commands inside ``serialized``,
    apart from ``lock``, which each command takes and releases on its own."""
    slot: SlotHolder | None = None
    """The host's execution slot as the store keeps it: taken by an admitted claim,
    refused to another attempt's claim while held, cleared by ownership when the holder's
    event ends its segment or closes the attempt (the live-path commands step, fork 5)."""
    publications: dict[tuple[str, int], PublicationRecord] = field(
        default_factory=dict[tuple[str, int], PublicationRecord]
    )
    """A publication record per attempt, set by a test; the store's publication commands
    are not mirrored, so a test of a publishing pass runs over the real store."""

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

    def events_after(
        self, run_id: str, attempt: int, *, after: int
    ) -> tuple[LoggedEvent, ...]:
        """The events past ``after``, as the store reads them up to the row's position."""
        with self.lock:
            return tuple(e for e in self._log(run_id, attempt) if e.position > after)

    def ledger_of(self, run_id: str, attempt: int) -> str | None:
        """The one ledger this store keeps, for a reserving attempt; ``None`` for one that
        reserved nothing, as the real store's row answers."""
        with self.lock:
            self._log(run_id, attempt)
            return LEDGER if (run_id, attempt) in self.heads else None

    def close(self) -> None:
        """The store's session close; this log keeps no connection."""

    def now(self) -> datetime:
        with self.lock:
            return self.clock()

    @contextmanager
    def serialized(self, name: str) -> Generator[None]:
        """The store's session-level lock: one holder of the block at a time, the commands
        inside it taking the command lock as they always do."""
        with self.serial:
            self.boundary("serialized")
            yield

    def admit(self, request: AdmissionRequest) -> AdmissionResult:
        """The store's admission over this log, under its lock: a recorded request answered
        as recorded and other content under its identity a conflict, the attempt number the
        next of its run (an existing attempt gives its receipt to identical inputs), the
        predecessor closed, the reservation judged against ``threshold`` as a fresh head's
        room, the admission at position 1 under the admitter, the request recorded. The
        predecessor's publication and ending rules are not mirrored: no unit test admits a
        successor."""
        inputs = request.inputs
        run_id, attempt = inputs.run_id, inputs.attempt
        admission = Admitted(inputs)
        asked = (
            run_id,
            attempt,
            event_bytes(admission, log_format=inputs.log_format_version),
            request.ledger_id,
        )
        with self.lock:
            self.boundary("locked")
            held = self.requests.get(request.request_id)
            if held is not None:
                if held.asked != asked:
                    raise LogStoreConflict(
                        f"request {request.request_id} was recorded for run {held.asked[0]} "
                        f"attempt {held.asked[1]} with other content, asked again for run "
                        f"{run_id} attempt {attempt}"
                    )
                return held.result
            at = self.clock()
            admitted_so_far = sum(1 for run, _ in self.logs if run == run_id)
            if attempt <= admitted_so_far:
                first = self.logs[(run_id, attempt)][0]
                if event_bytes(first.event, log_format=inputs.log_format_version) != asked[2]:
                    raise LogStoreConflict(
                        f"run {run_id} attempt {attempt} exists with other frozen inputs"
                    )
                result: AdmissionResult = AdmissionReceipt(
                    run_id, attempt, first.timestamp, self._reservation_revision(run_id, attempt)
                )
                self.requests[request.request_id] = _RecordedRequest(asked, result, at)
                return result
            if attempt != admitted_so_far + 1:
                raise LogStoreConflict(
                    f"run {run_id} has {admitted_so_far} attempts; attempt {attempt} is not "
                    "the next"
                )
            reason: str | None = None
            revision: int | None = None
            if attempt > 1 and not _is_closed(self.logs[(run_id, attempt - 1)]):
                reason = f"attempt {attempt - 1} is open"
            if reason is None and inputs.reservation_pico_usd is not None:
                head = LedgerHead(threshold_pico_usd=self.threshold)
                reason = ledger.reservation_refusal(head, inputs.reservation_pico_usd)
                if reason is None:
                    entry, after = ledger.admitted(
                        head, run_id, attempt, inputs.reservation_pico_usd
                    )
                    self.heads[(run_id, attempt)] = after
                else:
                    entry, _ = ledger.refused(
                        head, run_id, attempt, inputs.reservation_pico_usd, reason=reason
                    )
                self.entries.append(entry)
                revision = entry.revision
            if reason is not None:
                result = AdmissionRefusal(run_id, attempt, reason, revision)
            else:
                logged = LoggedEvent(1, at, request.admitter, admission)
                transition = next_state(AttemptState(), logged, request.rules)
                assert isinstance(transition, Appended), transition
                self.logs[(run_id, attempt)] = [logged]
                result = AdmissionReceipt(run_id, attempt, at, revision)
            self.requests[request.request_id] = _RecordedRequest(asked, result, at)
            self.boundary("before-commit")
            return result

    def recorded_admission(self, request_id: str) -> RecordedAdmission | None:
        with self.lock:
            held = self.requests.get(request_id)
        if held is None:
            return None
        result = held.result
        admitted = isinstance(result, AdmissionReceipt)
        return RecordedAdmission(
            request_id,
            result.run_id,
            result.attempt,
            admitted,
            held.recorded_at,
            None if isinstance(result, AdmissionReceipt) else result.reason,
        )

    def admitted_by(
        self, admitter: Producer, ledger_id: str, *, since: datetime
    ) -> tuple[AdmittedAttempt, ...]:
        """The store's read: the attempts admitted against ``ledger_id`` (this log's one
        ledger, for every reserving attempt) by ``admitter`` at or after ``since``, and
        every open one, in admission order."""
        with self.lock:
            listed = [
                AdmittedAttempt(run_id, attempt, log[0].timestamp, _is_closed(log))
                for (run_id, attempt), log in self.logs.items()
                if ledger_id == LEDGER
                and (run_id, attempt) in self.heads
                and log[0].envelope == admitter
                and (log[0].timestamp >= since or not _is_closed(log))
            ]
        return tuple(sorted(listed, key=lambda each: (each.admitted_at, each.run_id, each.attempt)))

    def open_attempts(self) -> tuple[AttemptRef, ...]:
        with self.lock:
            return tuple(
                AttemptRef(run_id, attempt)
                for (run_id, attempt), log in sorted(self.logs.items())
                if not _is_closed(log)
            )

    def execution_slot(self) -> SlotHolder | None:
        with self.lock:
            return self.slot

    def publication_of(self, run_id: str, attempt: int) -> PublicationRecord | None:
        with self.lock:
            return self.publications.get((run_id, attempt))

    def _release(self, run_id: str, attempt: int, after: AttemptState) -> None:
        """The store's release by ownership: the slot cleared when the state after the
        event ends its last segment or closes the attempt and this attempt at this
        generation holds it; under ``lock``."""
        segment_ended = bool(after.segments) and after.segments[-1].ended
        if after.closed is None and not segment_ended:
            return
        holder = self.slot
        if holder is not None and (holder.run_id, holder.attempt, holder.generation) == (
            run_id,
            attempt,
            after.generation,
        ):
            self.slot = None

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
                if event_bytes(held.event, log_format=log_format_of(log)) != event_bytes(
                    event, log_format=log_format_of(log)
                ):
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
                holder = self.slot
                if holder is not None and (holder.run_id, holder.attempt) != (run_id, attempt):
                    return Refused(
                        f"the host's execution slot is held by run {holder.run_id} attempt "
                        f"{holder.attempt} at generation {holder.generation}"
                    )
                log.append(logged)
                self.nonces[(run_id, attempt, nonce)] = logged
                self.slot = SlotHolder(
                    run_id, attempt, transition.state.generation, launch, logged.timestamp
                )
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
            event,
            Admitted | SegmentStarted | Completed | CapExhausted | Failed | Abandoned | Declined,
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
                self._release(run_id, attempt, transition.state)
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
        precondition: Callable[[AttemptState], str | None] | None = None,
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
                return _closed_again(current.closed, closing, _format_of(current))
            if precondition is not None:
                unmet = precondition(current)
                if unmet is not None:
                    return Refused(unmet)
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
                self._release(run_id, attempt, transition.state)
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

    def _reservation_revision(self, run_id: str, attempt: int) -> int | None:
        return next(
            (
                entry.revision
                for entry in self.entries
                if entry.kind is ledger.EntryKind.ADMITTED
                and (entry.run_id, entry.attempt) == (run_id, attempt)
            ),
            None,
        )


def _is_closed(log: list[LoggedEvent]) -> bool:
    """Whether the log holds a closing event: the attempt row's flag, as the store keeps it."""
    return any(
        isinstance(logged.event, Completed | CapExhausted | Failed | Abandoned | Declined)
        for logged in log
    )


def _envelope_of(envelope: Envelope | Stamping) -> Envelope:
    if isinstance(envelope, WorkerStamp | Producer):
        return envelope
    return envelope()


def _receipt(log: list[LoggedEvent], logged: LoggedEvent) -> Received | None:
    key = event_key(logged)
    for held in log:
        if event_key(held) != key:
            continue
        if event_bytes(held.event, log_format=log_format_of(log)) == event_bytes(
            logged.event, log_format=log_format_of(log)
        ):
            return Received(held.position)
        raise LogStoreConflict(
            f"the log holds another content under the identifier of the "
            f"{kind_of(logged.event).value} at position {held.position}"
        )
    return None


def _format_of(state: AttemptState) -> int:
    inputs = state.inputs
    assert inputs is not None
    return inputs.log_format_version


def _closed_again(held: LoggedEvent, closing: ClosingEvent, log_format: int) -> Transition:
    held_event = held.event
    if kind_of(held_event) is not kind_of(closing):
        return Refused(f"the attempt is closed at position {held.position}")
    assert isinstance(held_event, Completed | CapExhausted | Failed | Abandoned | Declined)
    masked: ClosingEvent = replace(held_event, settlement=None)
    if event_bytes(masked, log_format=log_format) == event_bytes(closing, log_format=log_format):
        return Received(held.position)
    raise LogStoreConflict(
        f"the attempt is closed at position {held.position} by a {kind_of(closing).value} "
        f"with other content"
    )


__all__ = ["MemoryLog", "Ticking"]
