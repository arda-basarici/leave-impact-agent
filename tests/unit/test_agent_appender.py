"""The stamped writer over the in-memory log, and the in-memory log held to the store.

The appender's claims: its stamps name the claim's generation and segment with offsets from
the segment's monotonic clock, drawn when the log calls the factory under its lock; an
``Appended`` threads the state; a ``Received`` keeps it, and a receipt for an event the
threaded state lacks is a harness fault; a ``Refused`` is raised as ``AppendRefused`` with
the refusal and the event, nothing appended; a close carries the settlement the log filled.

The in-memory log's claim: the sixteen histories replayed through its commands, each event
through the command its kind takes, come back as the fixtures hold them, the ledger revision
of a settlement masked (the store's integration suite makes the same substitution).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime

import pytest

from leaveimpact.agent.appender import Appender, AppendRefused
from leaveimpact.agent.log_events import (
    Abandoned,
    CapExhausted,
    Completed,
    Failed,
    LoggedEvent,
    SegmentStarted,
    WorkerStamp,
    kind_of,
)
from leaveimpact.agent.log_transition import Appended, AttemptState
from leaveimpact.core import FailureCategory, HarnessSite, HarnessSiteName
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit.log_store_memory import MemoryLog

RULES = histories.RULES
RUN, ATTEMPT = "run-12", 1


class ScriptedClock:
    """The given instants in order, one per reading."""

    def __init__(self, instants: list[datetime]) -> None:
        self.instants: Iterator[datetime] = iter(instants)

    def __call__(self) -> datetime:
        return next(self.instants)


def step(log: MemoryLog, logged: LoggedEvent, state: AttemptState) -> Appended:
    """One event through the command its kind takes, which must append it."""
    event = logged.event
    match event:
        case SegmentStarted():
            result = log.claim(
                RUN,
                ATTEMPT,
                harness=event.harness,
                nonce=event.nonce,
                launch=event.launch,
                override=event.override,
                rules=RULES,
                state=state,
            )
        case Completed() | CapExhausted() | Failed() | Abandoned():
            result = log.close_attempt(
                RUN,
                ATTEMPT,
                logged.envelope,
                replace(event, settlement=None),
                rules=RULES,
                state=state,
            )
        case _:
            result = log.append(RUN, ATTEMPT, logged.envelope, event, rules=RULES, state=state)
    assert isinstance(result, Appended), (logged.position, kind_of(event).value, result)
    return result


def revision_masked(logged: LoggedEvent) -> LoggedEvent:
    event = logged.event
    if isinstance(event, Completed | CapExhausted | Failed | Abandoned) and event.settlement:
        return replace(
            logged, event=replace(event, settlement=replace(event.settlement, ledger_revision=0))
        )
    return logged


@pytest.mark.parametrize("name", list(histories.HISTORIES))
def test_the_memory_log_replays_every_history_as_the_store_does(name: str) -> None:
    events = histories.HISTORIES[name]()
    log = MemoryLog(clock=ScriptedClock([logged.timestamp for logged in events[1:]]))
    log.seed(events[:1])
    state = log.load(RUN, ATTEMPT, rules=RULES)
    for logged in events[1:]:
        state = step(log, logged, state).state
    stored = log.events(RUN, ATTEMPT)
    assert [revision_masked(e) for e in stored] == [revision_masked(e) for e in events]
    assert log.load(RUN, ATTEMPT, rules=RULES) == state


# --- The appender ----------------------------------------------------------------------------


def claimed(**log_options: object) -> tuple[MemoryLog, AttemptState, tuple[LoggedEvent, ...]]:
    """A log holding the admission and the first claim of the cut-call history."""
    events = histories.HISTORIES["a cut call"]()
    log = MemoryLog(**log_options)  # type: ignore[arg-type]
    log.seed(events[:2])
    return log, log.load(RUN, ATTEMPT, rules=RULES), events


def test_stamps_name_the_claims_generation_and_segment_with_offsets_from_its_clock() -> None:
    order: list[str] = []
    readings = iter([10.0, 10.25, 10.3])

    def monotonic() -> float:
        order.append("stamp")
        return next(readings)

    log, state, events = claimed(boundary=order.append)
    appender = Appender.after_claim(log, state, rules=RULES, monotonic=monotonic)
    assert order == ["stamp"], "the origin is read at the claim"
    del order[:]
    appender.append(events[2].event)
    assert order == ["locked", "stamp", "decided", "before-commit"]
    appender.append(events[3].event)
    assert [e.envelope for e in log.events(RUN, ATTEMPT)[2:]] == [
        WorkerStamp(1, 1, 250),
        WorkerStamp(1, 1, 300),
    ]


def test_an_append_threads_the_state_the_log_folds_to() -> None:
    log, state, events = claimed()
    appender = Appender.after_claim(log, state, rules=RULES)
    for logged in events[2:5]:
        after = appender.append(logged.event)
        assert after is appender.state
    assert appender.state == log.load(RUN, ATTEMPT, rules=RULES)
    assert appender.state.last_position == 5


def test_a_receipt_keeps_the_state_and_one_for_an_event_the_state_lacks_raises() -> None:
    log, state, events = claimed()
    appender = Appender.after_claim(log, state, rules=RULES)
    stale = Appender.after_claim(log, state, rules=RULES)
    before = appender.append(events[2].event)
    again = appender.append(events[2].event)
    assert again is before and log.load(RUN, ATTEMPT, rules=RULES).last_position == 3
    with pytest.raises(
        RuntimeError, match="position 3, which the state the worker threads does not"
    ):
        stale.append(events[2].event)


def test_a_refused_append_raises_with_the_refusal_and_the_event_and_appends_nothing() -> None:
    log, state, events = claimed()
    fenced = Appender.after_claim(log, state, rules=RULES)
    takeover = log.claim(
        RUN, ATTEMPT, harness=cases.REVISION, nonce="nonce-2", launch="launch-2", rules=RULES
    )
    assert isinstance(takeover, Appended) and takeover.state.generation == 2
    with pytest.raises(AppendRefused) as raised:
        fenced.append(events[2].event)
    assert raised.value.refused.reason == "generation 1 is not the current 2"
    assert raised.value.event == events[2].event
    assert log.load(RUN, ATTEMPT, rules=RULES).last_position == 3, "the takeover alone"
    assert fenced.state is state, "a refusal changes no state"


def test_a_close_carries_the_settlement_the_log_filled() -> None:
    log, state, _ = claimed()
    appender = Appender.after_claim(log, state, rules=RULES)
    closing = Failed(
        FailureCategory.DEFECT, HarnessSite(HarnessSiteName.UNHANDLED), "a fault", None
    )
    after = appender.close(closing)
    held = after.closing
    assert held is not None and held.settlement is not None
    assert held.settlement.ledger_revision == 2 and len(log.entries) == 2
    assert after.closed is not None and isinstance(after.closed.envelope, WorkerStamp)
    assert (after.closed.envelope.generation, after.closed.envelope.segment) == (1, 1)


def test_an_appender_follows_a_claim() -> None:
    events = histories.HISTORIES["a cut call"]()
    log = MemoryLog()
    log.seed(events[:1])
    with pytest.raises(ValueError, match="follows a claim"):
        Appender.after_claim(log, log.load(RUN, ATTEMPT, rules=RULES), rules=RULES)
