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
    event_key_bytes,
    kind_of,
    log_digest,
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


def test_key_bytes_are_equal_exactly_when_the_keys_are() -> None:
    """The store's unique index rests on the text form agreeing with ``event_key`` over
    every pair of logged events the histories hold, equal keys across histories included."""
    keyed = [(event_key(logged), event_key_bytes(logged)) for logged in EVERY_HISTORY]
    for key, text in keyed:
        for other_key, other_text in keyed:
            assert (key == other_key) == (text == other_text), (key, other_key)
    for build in histories.HISTORIES.values():
        events = build()
        assert len({event_key_bytes(logged) for logged in events}) == len(events)


def test_key_bytes_name_the_kind_and_the_structured_key_and_nothing_of_the_envelope() -> None:
    intent = next(
        logged for logged in EVERY_HISTORY if kind_of(logged.event) is EventKind.DISPATCH_INTENT
    )
    assert event_key_bytes(intent) == b'{"kind":"dispatch_intent","key":{"call":1,"number":1}}'
    moved = LoggedEvent(intent.position + 3, intent.timestamp, intent.envelope, intent.event)
    assert event_key_bytes(moved) == event_key_bytes(intent)
    admitted = EVERY_HISTORY[0]
    assert event_key_bytes(admitted) == b'{"kind":"admitted","key":{}}'


def test_the_log_digest_covers_provenance_and_order() -> None:
    events = histories.HISTORIES["a cut call"]()
    digest = log_digest(events)
    assert len(digest) == 64 and digest == log_digest(list(events))
    assert log_digest(events[:-1]) != digest
    first = events[0]
    moved = first.timestamp.replace(microsecond=1)
    later = LoggedEvent(first.position, moved, first.envelope, first.event)
    assert log_digest((later, *events[1:])) != digest
    assert log_digest((events[1], events[0], *events[2:])) != digest
