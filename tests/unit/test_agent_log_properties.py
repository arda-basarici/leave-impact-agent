"""Generated command sequences against properties stated apart from the implementation (the
event log step's ruling on placement and acceptance, part 6): positions are dense, a stale
generation never appends, there is one closure, a received event is one the log already
holds, replay repeats no recorded inference, and after a recorded stopping failure nothing
but segment bookkeeping, an approval and the closing event is appended. The generator draws
commands a worker or an operator might issue, legal or not, and never asks the transition
function what is legal: a generator that did would show only that the function agrees with
itself."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from leaveimpact.agent.log_events import (
    Abandoned,
    Approved,
    Completed,
    Event,
    Failed,
    LoggedEvent,
    Producer,
    Resumed,
    SegmentEnded,
    SegmentStarted,
    WorkerStamp,
    event_key,
)
from leaveimpact.agent.log_transition import Appended, Received, Refused, fold, next_state
from leaveimpact.core import AbandonmentReason, Approver, ReservationState
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as h

RULES = h.RULES
BASE = h.HISTORIES["a cut call"]()
SETTLED = h.LoggedSettlement(0, ReservationState.RECONCILED, None, 7)


def stopped_prefix() -> tuple[LoggedEvent, ...]:
    """An admitted, claimed attempt whose one count was refused: a recorded stopping failure
    with nothing closed yet."""
    log = h.History()
    log.admit(h.inputs(reservation=10 * cases.ALLOCATION))
    log.claim()
    log.worker(h.count_start("call-1"), offset=400)
    log.worker(
        h.count_outcome(
            "call-1",
            h.CountServiceError(403, "AccessDeniedException", "denied", None, 90),
            h.CountResult.REFUSED,
        ),
        offset=500,
    )
    return log.logged()


PREFIXES = (BASE[:2], BASE[:7], stopped_prefix())
"""Where a sequence starts: an attempt just claimed; one whose call is answered and awaits
its request; one stopped by a refused count. Random commands rarely build a stop from
nothing, so the stopped start is given, and the property over it is not vacuous."""
BOOKKEEPING = (SegmentStarted, SegmentEnded, Approved, Abandoned, Failed)
"""What may follow a recorded stopping failure: segment bookkeeping, an approval of a request
already made, and the closing event."""

type Command = tuple[str, int, int, int, Event]


def worker_events() -> st.SearchStrategy[Event]:
    """Events a worker might try, in or out of turn."""
    return st.sampled_from(
        [
            SegmentStarted(cases.REVISION, "nonce-x", "launch-x"),
            SegmentEnded(),
            h.count_start("call-1"),
            h.count_outcome("call-1"),
            h.count_outcome(
                "call-1",
                h.CountServiceError(403, "AccessDeniedException", "denied", None, 90),
                h.CountResult.REFUSED,
            ),
            h.intent(1),
            h.intent(1, 2),
            h.outcome(1, 1, h.complete(), response=h.body("end_turn", h.text("Done."))),
            h.ApprovalRequested((), cases.RULES, False),
            Resumed(),
            Completed(SETTLED),
        ]
    )


def outside_events() -> st.SearchStrategy[Event]:
    return st.sampled_from(
        [
            Approved(Approver.AUTOMATIC, cases.review_payload_digest((), cases.RULES)),
            Abandoned(1, AbandonmentReason.CANCELLED, SETTLED),
            Abandoned(0, AbandonmentReason.CANCELLED, SETTLED),
        ]
    )


@st.composite
def commands(draw: st.DrawFn) -> list[Command]:
    """A sequence of attempted appends: who (worker or outside), a generation, a segment, an
    offset, and the event; the generator knows nothing of what the log will accept."""
    count = draw(st.integers(min_value=1, max_value=14))
    held: list[Command] = []
    for _ in range(count):
        if draw(st.booleans()):
            held.append(
                (
                    "worker",
                    draw(st.integers(min_value=1, max_value=3)),
                    draw(st.integers(min_value=1, max_value=3)),
                    draw(st.integers(min_value=0, max_value=5_000)),
                    draw(worker_events()),
                )
            )
        else:
            held.append(("outside", 0, 0, 0, draw(outside_events())))
    return held


def attempted(prefix: tuple[LoggedEvent, ...], command: Command) -> LoggedEvent:
    who, generation, segment, offset, event = command
    position = len(prefix) + 1
    at = cases.ADMITTED + timedelta(seconds=position)
    envelope = WorkerStamp(generation, segment, offset) if who == "worker" else Producer("operator")
    try:
        return LoggedEvent(position, at, envelope, event)
    except ValueError:
        # A worker's event under a producer's envelope or the reverse: the kind decides.
        other = (
            Producer("operator")
            if who == "worker"
            else WorkerStamp(max(generation, 1), max(segment, 1), offset)
        )
        return LoggedEvent(position, at, other, event)


@given(st.sampled_from(range(len(PREFIXES))), commands())
@settings(max_examples=300, deadline=None)
def test_properties_hold_over_any_command_sequence(start: int, sequence: list[Command]) -> None:
    prefix = PREFIXES[start]
    state = fold(prefix, RULES)
    log: list[LoggedEvent] = list(prefix)
    closures = 0
    for command in sequence:
        logged = attempted(tuple(log), command)
        result = next_state(state, logged, RULES)
        match result:
            case Appended(after):
                # Positions are dense and the generation never goes backwards.
                assert after.last_position == state.last_position + 1
                assert after.generation >= state.generation
                stamp = logged.stamp
                if stamp is not None and not isinstance(logged.event, SegmentStarted):
                    # A stale generation never appends.
                    assert stamp.generation == state.generation
                if state.stopped is not None:
                    # After a recorded stopping failure, bookkeeping and the closing event only.
                    assert isinstance(logged.event, BOOKKEEPING)
                    assert after.stopped == state.stopped
                if after.closed is not None and state.closed is None:
                    closures += 1
                log.append(logged)
                state = after
            case Received(position):
                # A receipt names an event the log holds with the same key.
                held = next(e for e in log if e.position == position)
                assert event_key(held) == event_key(logged)
            case Refused():
                pass
    # One closure at most, and a closed log rejects everything after it.
    assert closures <= 1
    assert fold(tuple(log), RULES) == state
    if state.closed is not None:
        late = replace(log[-1], position=len(log) + 1)
        assert not isinstance(next_state(state, late, RULES), Appended)


@given(st.integers(min_value=1, max_value=len(BASE)))
def test_replay_repeats_no_recorded_inference(cut: int) -> None:
    """Folding a prefix twice gives one state, and re-appending any held event after the
    whole log is a receipt, never a new transition."""
    prefix = BASE[:cut]
    state = fold(prefix, RULES)
    assert fold(prefix, RULES) == state
    whole = fold(BASE, RULES)
    for held in BASE:
        assert next_state(whole, held, RULES) == Received(held.position)
