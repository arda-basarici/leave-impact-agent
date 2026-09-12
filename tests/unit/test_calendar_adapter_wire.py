"""The calendar adapter's wire behaviour over a scripted transport: what it sends, what it refuses.

The claims the cassette cannot make cheaply: an event is one insert per attendee's
calendar with the same body and the derived id, and a lost response is replayed
because the id makes a second arrival the same world; a 409 is answered by reading
the copy back, and only an identical, living copy lets the write go on; every read
passes the UTC zone and pages to completion; a 401 buys one refresh and one resend;
a person without a calendar is the caller's ordering bug before any request; a
successful response that is not an object is malformed with the request as locator;
preparation verifies a known calendar and creates an unknown one in its person's zone.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import httpx
import pytest

from leaveimpact.adapters.calendar import (
    CalendarAdapter,
    CalendarConfig,
    CalendarCredential,
    CalendarPrincipal,
)
from leaveimpact.adapters.calendar.records import event_payload, vendor_event_id
from leaveimpact.core.entities import CalendarEvent, Employee
from leaveimpact.core.enums import EmploymentType, Grade
from leaveimpact.core.ids import employee_id, event_id, team_id
from leaveimpact.core.ports.errors import IdentityConflict, MalformedRecord, SourceUnreachable
from leaveimpact.core.ports.read import CalendarReader
from leaveimpact.core.ports.write import CalendarWriter
from leaveimpact.core.worldtime import InstantSpan

Outcome = httpx.Response | Exception
ISTANBUL = ZoneInfo("Europe/Istanbul")
SEDA, BARAN, DENIZ = employee_id(1), employee_id(2), employee_id(3)
CAL = {SEDA: "seda@group.calendar.google.com", BARAN: "baran@cal", DENIZ: "deniz@cal"}
CONFIG = CalendarConfig(CAL)
CREDENTIAL = CalendarCredential("client", "secret", "refresh")
REVIEW = CalendarEvent(
    event_id(7),
    "Customer review",
    datetime(2026, 9, 8, 13, 0, tzinfo=ISTANBUL),
    datetime(2026, 9, 8, 15, 0, tzinfo=ISTANBUL),
    (SEDA, BARAN),
)
VENDOR = vendor_event_id(REVIEW.id)


class Scripted:
    """The outcomes in order; ``bearers`` is each request's token as sent, since a resend
    mutates the same request object."""

    def __init__(self, *outcomes: Outcome) -> None:
        self.seen: list[httpx.Request] = []
        self.bearers: list[str] = []
        self._outcomes: Iterator[Outcome] = iter(outcomes)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        self.bearers.append(request.headers.get("Authorization", ""))
        outcome = next(self._outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class Tokens:
    """A token source that counts refreshes; the bearer says which token it holds."""

    def __init__(self) -> None:
        self.refreshes = 0

    def bearer(self) -> str:
        return f"token-{self.refreshes}"

    def refresh(self) -> str:
        self.refreshes += 1
        return self.bearer()


def adapter(script: Scripted, tokens: Tokens | None = None) -> CalendarAdapter:
    return CalendarAdapter(
        credential=CREDENTIAL,
        config=CONFIG,
        base_url="https://calendar.invalid",
        sleep=lambda _: None,
        httpx_transport=httpx.MockTransport(script.handler),
        tokens=tokens or Tokens(),
    )


def principal(script: Scripted) -> CalendarPrincipal:
    return CalendarPrincipal(
        credential=CREDENTIAL,
        base_url="https://calendar.invalid",
        sleep=lambda _: None,
        httpx_transport=httpx.MockTransport(script.handler),
        tokens=Tokens(),
    )


def ok(payload: Any) -> httpx.Response:
    return httpx.Response(200, json=payload)


def status(code: int) -> httpx.Response:
    return httpx.Response(code, json={"error": {"code": code}})


def listing(*items: dict[str, Any], next_page: str | None = None) -> httpx.Response:
    body: dict[str, Any] = {"items": list(items)}
    if next_page:
        body["nextPageToken"] = next_page
    return ok(body)


def query(request: httpx.Request) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(str(request.url)).query).items()}


def test_the_adapter_conforms_to_both_calendar_ports() -> None:
    built = adapter(Scripted())
    reader: CalendarReader = built
    writer: CalendarWriter = built
    assert reader is writer


def test_an_event_is_one_insert_per_attendees_calendar_with_the_derived_id() -> None:
    script = Scripted(ok(event_payload(REVIEW)), ok(event_payload(REVIEW)))
    assert adapter(script).add_event(REVIEW) == VENDOR
    paths = [request.url.path for request in script.seen]
    assert paths == [
        "/calendars/seda@group.calendar.google.com/events",
        "/calendars/baran@cal/events",
    ]
    bodies = [json.loads(request.content) for request in script.seen]
    assert bodies[0] == bodies[1] == event_payload(REVIEW)
    assert bodies[0]["id"] == VENDOR
    assert bodies[0]["extendedProperties"]["private"] == {
        "event_id": "event_007",
        "attendees": "emp_001;emp_002",
    }
    assert script.bearers == ["Bearer token-0", "Bearer token-0"]


def test_an_insert_whose_response_was_lost_is_replayed_because_the_id_makes_it_one_world() -> None:
    script = Scripted(
        httpx.ReadTimeout("lost"), status(409), ok(event_payload(REVIEW)), ok(event_payload(REVIEW))
    )
    assert adapter(script).add_event(REVIEW) == VENDOR
    methods = [(request.method, request.url.path) for request in script.seen]
    assert methods == [
        ("POST", "/calendars/seda@group.calendar.google.com/events"),
        ("POST", "/calendars/seda@group.calendar.google.com/events"),
        ("GET", f"/calendars/seda@group.calendar.google.com/events/{VENDOR}"),
        ("POST", "/calendars/baran@cal/events"),
    ]


def test_a_409_is_verified_by_reading_the_copy_back_and_the_write_goes_on() -> None:
    script = Scripted(status(409), ok(event_payload(REVIEW)), ok(event_payload(REVIEW)))
    assert adapter(script).add_event(REVIEW) == VENDOR
    verify = script.seen[1]
    assert verify.method == "GET" and query(verify) == {"timeZone": "UTC"}
    assert script.seen[2].url.path == "/calendars/baran@cal/events"


def test_a_409_whose_copy_differs_from_the_intended_event_is_an_identity_conflict() -> None:
    script = Scripted(status(409), ok({**event_payload(REVIEW), "summary": "Vendor call"}))
    with pytest.raises(IdentityConflict, match="an existing event differs") as caught:
        adapter(script).add_event(REVIEW)
    assert caught.value.locator == f"calendars/{CAL[SEDA]}/events/{VENDOR}"
    assert len(script.seen) == 2, "no write to the next calendar"


@pytest.mark.parametrize(
    ("existing", "reason"),
    [
        (ok({**event_payload(REVIEW), "status": "cancelled"}), "held by a cancelled event"),
        (status(404), "answered 409 to the insert, then 404"),
    ],
)
def test_a_409_whose_copy_cannot_be_read_as_the_event_is_malformed_and_stops_the_write(
    existing: httpx.Response, reason: str
) -> None:
    script = Scripted(status(409), existing)
    with pytest.raises(MalformedRecord, match=reason) as caught:
        adapter(script).add_event(REVIEW)
    assert caught.value.locator == f"calendars/{CAL[SEDA]}/events/{VENDOR}"
    assert len(script.seen) == 2, "no write to the next calendar"


def test_an_attendee_without_a_calendar_is_the_callers_ordering_bug() -> None:
    stranger = CalendarEvent(
        event_id(9), "Onboarding", REVIEW.start, REVIEW.end, (employee_id(44),)
    )
    script = Scripted()
    with pytest.raises(LookupError, match="emp_044 has no calendar configured"):
        adapter(script).add_event(stranger)
    assert script.seen == []


def test_events_within_lists_every_calendar_in_utc_and_pages_to_completion() -> None:
    standup = CalendarEvent(event_id(8), "Standup", REVIEW.start, REVIEW.end, (SEDA, BARAN, DENIZ))
    script = Scripted(
        listing(event_payload(REVIEW), next_page="p2"),
        listing(event_payload(standup)),
        listing(event_payload(REVIEW), event_payload(standup)),
        listing(event_payload(standup)),
    )
    span = InstantSpan(
        datetime(2026, 9, 7, tzinfo=ISTANBUL), datetime(2026, 9, 14, tzinfo=ISTANBUL)
    )
    found = adapter(script).events_within(span)
    assert tuple(item.value for item in found) == (REVIEW, standup)
    first, second = query(script.seen[0]), query(script.seen[1])
    assert first["timeMin"] == "2026-09-06T21:00:00+00:00"
    assert first["timeMax"] == "2026-09-13T21:00:00+00:00"
    assert first["timeZone"] == "UTC" and first["singleEvents"] == "true"
    assert "pageToken" not in first and second["pageToken"] == "p2"
    assert [request.url.path for request in script.seen] == [
        "/calendars/seda@group.calendar.google.com/events",
        "/calendars/seda@group.calendar.google.com/events",
        "/calendars/baran@cal/events",
        "/calendars/deniz@cal/events",
    ]


def test_event_asks_every_calendar_by_derived_id_and_skips_the_absent() -> None:
    script = Scripted(ok(event_payload(REVIEW)), ok(event_payload(REVIEW)), status(404))
    found = adapter(script).event(REVIEW.id)
    assert found is not None and found.value == REVIEW
    assert [request.url.path for request in script.seen] == [
        f"/calendars/seda@group.calendar.google.com/events/{VENDOR}",
        f"/calendars/baran@cal/events/{VENDOR}",
        f"/calendars/deniz@cal/events/{VENDOR}",
    ]
    assert all(query(request) == {"timeZone": "UTC"} for request in script.seen)


def test_an_event_nobody_holds_is_none_and_a_cancelled_copy_counts_as_absent() -> None:
    script = Scripted(
        status(404), ok({**event_payload(REVIEW), "status": "cancelled"}), status(404)
    )
    assert adapter(script).event(REVIEW.id) is None


def test_a_copy_at_the_derived_id_carrying_another_id_is_malformed() -> None:
    other = {**event_payload(REVIEW)}
    other["extendedProperties"] = {
        "private": {"event_id": "event_008", "attendees": "emp_001;emp_002"}
    }
    script = Scripted(ok(other), ok(other), status(404))
    with pytest.raises(MalformedRecord, match="derived from event_007 carries event_008"):
        adapter(script).event(REVIEW.id)


def test_a_401_buys_one_refresh_and_one_resend() -> None:
    tokens = Tokens()
    script = Scripted(status(401), status(404), status(404), status(404))
    assert adapter(script, tokens).event(REVIEW.id) is None
    assert tokens.refreshes == 1
    assert script.bearers == ["Bearer token-0"] + ["Bearer token-1"] * 3


def test_a_second_401_is_the_sources_refusal() -> None:
    tokens = Tokens()
    script = Scripted(status(401), status(401))
    with pytest.raises(SourceUnreachable, match="401"):
        adapter(script, tokens).event(REVIEW.id)
    assert tokens.refreshes == 1


@pytest.mark.parametrize(
    "response", [httpx.Response(200, content=b"<html>"), httpx.Response(200, json=[1, 2])]
)
def test_a_successful_response_that_is_not_an_object_is_malformed(response: httpx.Response) -> None:
    with pytest.raises(MalformedRecord, match="response is not") as caught:
        adapter(Scripted(response)).event(REVIEW.id)
    assert caught.value.locator.startswith("GET /calendars/")


def test_a_listing_whose_items_are_not_objects_is_malformed() -> None:
    span = InstantSpan(datetime(2026, 9, 7, tzinfo=UTC), datetime(2026, 9, 14, tzinfo=UTC))
    with pytest.raises(MalformedRecord, match="an item is not an object"):
        adapter(Scripted(listing(), ok({"items": ["x"]}))).events_within(span)


def employee(id: Any, name: str, zone: str) -> Employee:
    return Employee(
        id, name, team_id(1), None, None, "Istanbul", "TR", zone, Grade.MID, EmploymentType.EMPLOYEE
    )


def test_preparation_verifies_a_known_calendar_and_creates_an_unknown_one_in_its_zone() -> None:
    script = Scripted(ok({"id": CAL[SEDA]}), ok({"id": "new@cal"}))
    made = principal(script).ensure_calendars(
        [
            employee(SEDA, "Seda Aksoy", "Europe/Istanbul"),
            employee(BARAN, "Baran Demir", "Europe/Berlin"),
        ],
        naming="CAS",
        known={SEDA: CAL[SEDA]},
    )
    assert made == {SEDA: CAL[SEDA], BARAN: "new@cal"}
    verify, create = script.seen
    assert (
        verify.method == "GET" and verify.url.path == "/calendars/seda@group.calendar.google.com"
    )
    assert create.method == "POST" and create.url.path == "/calendars"
    assert json.loads(create.content) == {
        "summary": f"CAS {BARAN} Baran Demir",
        "timeZone": "Europe/Berlin",
    }


def test_a_known_calendar_the_principal_does_not_hold_is_malformed() -> None:
    script = Scripted(status(404))
    with pytest.raises(MalformedRecord, match="configured for emp_001 but the principal holds no"):
        principal(script).ensure_calendars(
            [employee(SEDA, "Seda Aksoy", "Europe/Istanbul")],
            naming="CAS",
            known={SEDA: "gone@cal"},
        )


def test_a_created_calendar_without_an_id_is_malformed() -> None:
    script = Scripted(ok({"summary": "CAS Seda Aksoy"}))
    with pytest.raises(MalformedRecord, match="no id"):
        principal(script).ensure_calendars(
            [employee(SEDA, "Seda Aksoy", "Europe/Istanbul")], naming="CAS"
        )
