"""The narration stream over the surface rig, the entry ruling's acceptance: a stream over a
closed attempt yields exactly its lines in position order and ends with the closing frame; a
reconnection with the last id yields the remainder with no duplicate, the header winning over
the query parameter; a cursor at the terminal is a 204, one beyond the log or malformed a 400
after admission; lines appended while a stream is open arrive within a tick and a terminal
appended during polling is delivered as the closing frame before closure; a disconnection
during the wait releases the subscription, leaves every session closed and the attempt
unaffected; idle viewers do not prevent a replay page loading; the bound refuses the next
subscriber and admits one when a slot is released; an unpublishable attempt is the one
not-found page; a tick that cannot read the log ends the stream with the unavailable frame;
and a heartbeat crosses silence."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any, cast

from fastapi.testclient import TestClient

from leaveimpact.agent.log_events import LoggedEvent
from leaveimpact.agent.log_store import LogStoreUnavailable
from leaveimpact.agent.log_transition import AttemptState, Rules, fold
from leaveimpact.app.main import Services, create_app
from leaveimpact.app.narration import narration
from leaveimpact.app.stream import (
    CLOSED_EVENT,
    LINE_EVENT,
    UNAVAILABLE_EVENT,
    Pacing,
    Subscriptions,
)
from tests.unit import log_histories as histories
from tests.unit.publishable_fixture import CLOSED, CONFIGURATION, SERVED, history_in_world
from tests.unit.test_app_surface import CODE, FORGED, Rig, Sessions

FAST = Pacing(tick_seconds=0.01, heartbeat_seconds=0.08, bound=2)
LIVE = ("run-14", 1)
"""The rig's open attempt: admitted and nothing more, published as ``live``."""


class FailingSessions(Sessions):
    """The rig's sessions, every load refused once ``failing`` is set."""

    failing = False

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState:
        if self.failing:
            raise LogStoreUnavailable("connection refused: OperationalError")
        return super().load(run_id, attempt, rules=rules)


def client_of(rig: Rig, pacing: Pacing = FAST) -> TestClient:
    services = Services(
        CODE,
        CONFIGURATION,
        rig.store.ready_versions,
        rig.store.app_schema,
        rig.rows,
        rig.sessions,
        histories.RULES,
    )
    return TestClient(create_app(services, pacing))


def subscriptions_of(client: TestClient) -> Subscriptions:
    """The process's bound behind ``client``'s application."""
    return cast(Subscriptions, cast(Any, client.app).state.subscriptions)


def frames_of(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """The frames of a stream as it arrives: a mapping per frame, the data decoded, a
    comment line as ``{"comment": ...}``."""
    frame: dict[str, Any] = {}
    for line in lines:
        if line == "":
            if frame:
                yield frame
                frame = {}
        elif line.startswith(":"):
            yield {"comment": line}
        else:
            key, _, value = line.partition(": ")
            frame[key] = json.loads(value) if key == "data" else value


def feed(rig: Rig, logged: LoggedEvent) -> None:
    """``logged``, an event of a recorded history, appended to the rig's open attempt as the
    worker would have appended it."""
    memory = rig.sessions.memory
    with memory.lock:
        memory.logs[LIVE].append(logged)


def expected_lines(events: tuple[LoggedEvent, ...]) -> list[dict[str, Any]]:
    return [
        {
            "position": line.position,
            "recorded_at": line.recorded_at.isoformat(),
            "kind": line.kind.value,
            "text": line.text,
        }
        for line in narration(fold(events, histories.RULES), histories.RULES)
    ]


# --- A closed attempt ------------------------------------------------------------------------


def test_a_stream_over_a_closed_attempt_yields_its_lines_in_order_and_ends() -> None:
    rig = Rig()
    with client_of(rig).stream("GET", "/replays/served/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-store"
        frames = list(frames_of(response.iter_lines()))
    lines = expected_lines(history_in_world(CLOSED, SERVED))
    assert [f["data"] for f in frames] == [
        *lines[:-1],
        {**lines[-1], "status": "completed"},
    ]
    assert [f["event"] for f in frames] == [LINE_EVENT] * (len(lines) - 1) + [CLOSED_EVENT]
    assert [f["id"] for f in frames] == [str(line["position"]) for line in lines]
    assert rig.sessions.opened == rig.sessions.closed


def test_a_reconnection_with_the_last_id_yields_the_remainder_with_no_duplicate() -> None:
    rig = Rig()
    client = client_of(rig)
    lines = expected_lines(history_in_world(CLOSED, SERVED))
    with client.stream("GET", "/replays/served/events", headers={"Last-Event-ID": "3"}) as response:
        frames = list(frames_of(response.iter_lines()))
    assert [f["data"]["position"] for f in frames] == [line["position"] for line in lines[3:]]
    with client.stream("GET", "/replays/served/events?after=3") as response:
        assert [f["data"]["position"] for f in frames_of(response.iter_lines())] == [
            line["position"] for line in lines[3:]
        ]
    # The header wins over the parameter: a reconnecting browser knows better than the page.
    with client.stream(
        "GET", "/replays/served/events?after=1", headers={"Last-Event-ID": "5"}
    ) as response:
        assert [f["data"]["position"] for f in frames_of(response.iter_lines())] == [
            line["position"] for line in lines[5:]
        ]


def test_a_cursor_at_the_terminal_is_a_204_and_one_beyond_or_malformed_a_400() -> None:
    rig = Rig()
    client = client_of(rig)
    last = len(history_in_world(CLOSED, SERVED))
    assert client.get(f"/replays/served/events?after={last}").status_code == 204
    beyond = client.get(f"/replays/served/events?after={last + 1}")
    assert beyond.status_code == 400 and "beyond" in beyond.text
    for malformed in ("x", "-1", "1.5", ""):
        assert client.get(f"/replays/served/events?after={malformed}").status_code == 400
    # A forged name with any cursor is the not-found page, so the cursor reveals nothing.
    page = client.get(f"/replays/{FORGED}")
    forged = client.get(f"/replays/{FORGED}/events?after={last + 1}")
    assert forged.status_code == 404 and forged.content == page.content
    assert subscriptions_of(client).held == 0


# --- A live attempt ----------------------------------------------------------------------


def test_lines_appended_while_a_stream_is_open_arrive_and_the_terminal_closes_it() -> None:
    rig = Rig()
    events = history_in_world(CLOSED, SERVED, run_id=LIVE[0])
    lines = expected_lines(events)
    with client_of(rig).stream("GET", "/replays/live/events") as response:
        frames = frames_of(response.iter_lines())
        assert next(frames)["data"] == lines[0]
        for logged in events[1:-1]:
            feed(rig, logged)
            assert next(frames)["data"] == lines[logged.position - 1]
        feed(rig, events[-1])
        closing = next(frames)
        assert closing["event"] == CLOSED_EVENT
        assert closing["data"] == {**lines[-1], "status": "completed"}
        assert next(frames, None) is None
    assert rig.sessions.opened == rig.sessions.closed


def test_a_disconnection_during_the_wait_releases_the_subscription_and_the_attempt() -> None:
    rig = Rig()
    client = client_of(rig)
    subscriptions = subscriptions_of(client)
    with client.stream("GET", "/replays/live/events") as response:
        # The iterator is held: a discarded one is collected, which closes the response and
        # is itself a disconnection.
        frames = frames_of(response.iter_lines())
        assert next(frames)["data"]["position"] == 1
        assert subscriptions.held == 1
    assert subscriptions.held == 0
    assert rig.sessions.opened == rig.sessions.closed
    # The investigation is unaffected: the worker's next event appends as before.
    events = history_in_world(CLOSED, SERVED, run_id=LIVE[0])
    feed(rig, events[1])
    assert rig.sessions.load(*LIVE, rules=histories.RULES).last_position == 2


def test_idle_viewers_do_not_prevent_a_replay_page_loading() -> None:
    rig = Rig()
    client = client_of(rig)
    with (
        client.stream("GET", "/replays/live/events") as first,
        client.stream("GET", "/replays/live/events") as second,
    ):
        assert first.status_code == 200 and second.status_code == 200
        page = client.get("/replays/served")
        assert page.status_code == 200 and "The handover nobody wrote down" in page.text


def test_the_bound_refuses_the_next_subscriber_and_admits_one_when_a_slot_frees() -> None:
    rig = Rig()
    client = client_of(rig)
    with (
        client.stream("GET", "/replays/live/events") as first,
        client.stream("GET", "/replays/live/events") as second,
    ):
        assert first.status_code == 200 and second.status_code == 200
        refused = client.get("/replays/live/events")
        assert refused.status_code == 503
        assert refused.content == client.get("/replays/unfoldable").content
    with client.stream("GET", "/replays/live/events") as third:
        assert third.status_code == 200


def test_a_tick_that_cannot_read_the_log_ends_the_stream_with_the_unavailable_frame() -> None:
    rig = Rig()
    rig.sessions = FailingSessions(rig.sessions.memory)
    client = client_of(rig)
    with client.stream("GET", "/replays/live/events") as response:
        frames = frames_of(response.iter_lines())
        assert next(frames)["data"]["position"] == 1
        rig.sessions.failing = True
        ending = next(frames)
        assert ending["event"] == UNAVAILABLE_EVENT
        assert ending["data"] == {"reason": "the log could not be read: LogStoreUnavailable"}
        assert next(frames, None) is None
    assert subscriptions_of(client).held == 0
    assert rig.sessions.opened == rig.sessions.closed


def test_a_heartbeat_crosses_silence() -> None:
    rig = Rig()
    with client_of(rig).stream("GET", "/replays/live/events") as response:
        frames = frames_of(response.iter_lines())
        assert next(frames)["data"]["position"] == 1
        assert next(frames) == {"comment": ": keepalive"}


def test_a_stream_over_an_unpublishable_attempt_is_the_not_found_page() -> None:
    rig = Rig()
    client = client_of(rig)
    page = client.get("/replays/nobody-here")
    for name in ("embargoed", FORGED, "nobody-here"):
        refused = client.get(f"/replays/{name}/events")
        assert refused.status_code == 404 and refused.content == page.content
    assert rig.sessions.opened == rig.sessions.closed
