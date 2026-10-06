"""The events: each kind round-trips through its bytes, an event is identified by its kind
and key and compared by its versioned canonical content, the identifiers an export carries
are keys rendered, and an unknown kind refuses by name."""

from __future__ import annotations

import pytest

from leaveimpact.agent.log_events import (
    LOG_FORMAT_VERSION,
    CountKey,
    EventKind,
    LoggedEvent,
    ModelReadKey,
    PrefetchKey,
    Producer,
    WorkerStamp,
    call_id,
    count_id,
    decode_event,
    decode_logged_event,
    encode_event,
    encode_logged_event,
    event_bytes,
    event_key,
    kind_of,
    operation_id,
)
from leaveimpact.core import Approver, RegisteredInputBound
from leaveimpact.core.jsonshape import canonical_bytes
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories

EVERY_HISTORY = [logged for build in histories.HISTORIES.values() for logged in build()]


def test_the_histories_hold_every_kind() -> None:
    held = {kind_of(logged.event) for logged in EVERY_HISTORY}
    assert held == set(EventKind) - {EventKind.CAP_EXHAUSTED, EventKind.FINALIZATION_ENTERED}
    assert len(EventKind) == 16


@pytest.mark.parametrize(
    "logged", EVERY_HISTORY, ids=lambda e: f"{e.position}-{kind_of(e.event).value}"
)
def test_every_logged_event_round_trips_through_its_json(logged: LoggedEvent) -> None:
    data = encode_logged_event(logged)
    assert decode_logged_event(data) == logged
    assert canonical_bytes(encode_logged_event(decode_logged_event(data))) == canonical_bytes(data)


def test_bytes_carry_the_log_format_version_and_the_kind_and_not_the_envelope() -> None:
    first = EVERY_HISTORY[0]
    held = event_bytes(first.event)
    assert f'"log_format":{LOG_FORMAT_VERSION}'.encode() in held
    assert b'"kind":"admitted"' in held
    assert b'"position"' not in held and b'"timestamp"' not in held
    moved = LoggedEvent(first.position + 5, first.timestamp, first.envelope, first.event)
    assert event_bytes(moved.event) == held


def test_an_unknown_kind_refuses_by_name() -> None:
    with pytest.raises(ValueError, match="not an event kind this log format holds: 'paused'"):
        decode_event("paused", {})


def test_a_segment_event_is_keyed_by_its_stamps_segment() -> None:
    starts = [
        logged for logged in EVERY_HISTORY if kind_of(logged.event) is EventKind.SEGMENT_STARTED
    ]
    assert all(
        event_key(logged) == (EventKind.SEGMENT_STARTED, (logged.stamp.segment,))  # type: ignore[union-attr]
        for logged in starts
    )


def test_an_outside_producers_event_takes_no_stamp_and_a_workers_takes_one() -> None:
    admitted = EVERY_HISTORY[0]
    with pytest.raises(ValueError, match="admitted is not an event a worker appends"):
        LoggedEvent(1, admitted.timestamp, WorkerStamp(1, 1, 0), admitted.event)
    started = next(e for e in EVERY_HISTORY if kind_of(e.event) is EventKind.SEGMENT_STARTED)
    with pytest.raises(ValueError, match="segment_started is not an event an outside producer"):
        LoggedEvent(2, started.timestamp, Producer("operator"), started.event)


def test_identifiers_are_keys_rendered() -> None:
    assert operation_id(PrefetchKey(1)) == "prefetch/1"
    assert operation_id(ModelReadKey(1, "tu_1")) == "call-1/tu_1"
    assert call_id(2) == "call-2"
    key = CountKey(RegisteredInputBound("provider_count", 1), cases.COUNTING_MODEL, cases.DIGEST, 3)
    assert count_id(key) == cases.exhausted_count_id(3)
    assert count_id(key).startswith("count/provider_count-1/model-a-base/")


def test_content_tells_two_approvals_apart() -> None:
    from leaveimpact.agent.log_events import Approved

    one = Approved(Approver.AUTOMATIC, cases.DIGEST)
    other = Approved(Approver.HUMAN, cases.DIGEST)
    assert encode_event(one) != encode_event(other)
    assert event_bytes(one) != event_bytes(other)
