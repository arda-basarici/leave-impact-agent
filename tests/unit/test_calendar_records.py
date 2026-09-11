"""The calendar records module: the id encoding, the translation, and the one-event-of-copies rule.

The claims a cassette cannot make cheaply: the vendor id is in Google's alphabet and
stable; a payload reads back as the entity it was made from, whichever zone the copy
arrives in; and a set of copies is one event only when the copies agree and sit on
exactly the attendees' calendars — disagreement, a stranger's calendar, a missing
attendee's calendar and an attendee with no calendar are each malformed, never a
silent pick.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from leaveimpact.adapters.calendar import records
from leaveimpact.core.entities import CalendarEvent
from leaveimpact.core.ids import EmployeeId, EventId, employee_id, event_id
from leaveimpact.core.ports.errors import MalformedRecord

ISTANBUL = ZoneInfo("Europe/Istanbul")
SEDA, BARAN, DENIZ = employee_id(1), employee_id(2), employee_id(3)
CAL = {SEDA: "seda@cal", BARAN: "baran@cal", DENIZ: "deniz@cal"}
BY_CALENDAR = {calendar: person for person, calendar in CAL.items()}
REVIEW = CalendarEvent(
    event_id(7),
    "Customer review",
    datetime(2026, 9, 8, 13, 0, tzinfo=ISTANBUL),
    datetime(2026, 9, 8, 15, 0, tzinfo=ISTANBUL),
    (SEDA, BARAN),
)


def copy(event: CalendarEvent, **changes: Any) -> dict[str, Any]:
    """The payload as Google would return it, optionally altered."""
    return {**records.event_payload(event), **changes}


def in_utc(event: CalendarEvent) -> dict[str, Any]:
    """The same copy as a read with ``timeZone=UTC`` returns it."""
    return copy(
        event,
        start={"dateTime": event.start.astimezone(UTC).isoformat().replace("+00:00", "Z")},
        end={"dateTime": event.end.astimezone(UTC).isoformat().replace("+00:00", "Z")},
    )


def test_the_vendor_id_is_in_googles_alphabet_and_stable() -> None:
    vendor = records.vendor_event_id(event_id(42))
    assert re.fullmatch(r"[a-v0-9]{5,1024}", vendor)
    assert vendor == records.vendor_event_id(EventId("event_042"))
    assert vendor != records.vendor_event_id(event_id(43))


def test_a_payload_reads_back_as_the_event_in_any_zone() -> None:
    assert records.event_from_record(copy(REVIEW), CAL[SEDA]) == REVIEW
    assert records.event_from_record(in_utc(REVIEW), CAL[SEDA]) == REVIEW


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"extendedProperties": {}}, "no private extended properties"),
        ({"extendedProperties": {"private": {"attendees": "emp_001"}}}, "no event_id"),
        ({"extendedProperties": {"private": {"event_id": "event_007"}}}, "no attendees"),
        (
            {"extendedProperties": {"private": {"event_id": "event_007", "attendees": ";"}}},
            "no attendees",
        ),
        ({"start": {"date": "2026-09-08"}}, "start is not an instant"),
        (
            {"end": {"dateTime": "2026-09-08T15:00:00"}},
            "end '2026-09-08T15:00:00' carries no offset",
        ),
        ({"end": {"dateTime": "not a time"}}, "is not RFC 3339"),
        ({"end": {"dateTime": "2026-09-08T13:00:00+03:00"}}, "ends at or before it starts"),
        ({"summary": ""}, "no summary"),
    ],
)
def test_an_untranslatable_copy_is_malformed_with_its_locator(
    change: dict[str, Any], reason: str
) -> None:
    with pytest.raises(MalformedRecord, match=re.escape(reason)) as caught:
        records.event_from_record(copy(REVIEW, **change), CAL[SEDA])
    assert caught.value.locator == f"calendars/seda@cal/events/{records.vendor_event_id(REVIEW.id)}"


def test_copies_on_every_attendees_calendar_are_one_event() -> None:
    copies = [(CAL[SEDA], copy(REVIEW)), (CAL[BARAN], in_utc(REVIEW))]
    assert records.events_from_copies(copies, BY_CALENDAR) == (REVIEW,)


def test_events_keep_first_appearance_order_across_calendars() -> None:
    standup = CalendarEvent(event_id(8), "Standup", REVIEW.start, REVIEW.end, (SEDA, BARAN, DENIZ))
    copies = [
        (CAL[SEDA], copy(REVIEW)),
        (CAL[SEDA], copy(standup)),
        (CAL[BARAN], copy(standup)),
        (CAL[BARAN], copy(REVIEW)),
        (CAL[DENIZ], copy(standup)),
    ]
    assert records.events_from_copies(copies, BY_CALENDAR) == (REVIEW, standup)


def test_copies_that_disagree_are_malformed() -> None:
    copies = [(CAL[SEDA], copy(REVIEW)), (CAL[BARAN], copy(REVIEW, summary="Vendor call"))]
    with pytest.raises(MalformedRecord, match="the copy on baran@cal disagrees"):
        records.events_from_copies(copies, BY_CALENDAR)


def test_an_event_missing_from_an_attendees_calendar_is_half_written() -> None:
    with pytest.raises(
        MalformedRecord, match="on 1 of 2 attendees' calendars; missing for emp_002"
    ):
        records.events_from_copies([(CAL[SEDA], copy(REVIEW))], BY_CALENDAR)


def test_a_copy_on_a_non_attendees_calendar_is_malformed() -> None:
    copies = [(CAL[SEDA], copy(REVIEW)), (CAL[BARAN], copy(REVIEW)), (CAL[DENIZ], copy(REVIEW))]
    with pytest.raises(MalformedRecord, match="found on emp_003's calendar, who does not attend"):
        records.events_from_copies(copies, BY_CALENDAR)


def test_a_copy_on_an_unconfigured_calendar_is_malformed() -> None:
    copies = [(CAL[SEDA], copy(REVIEW)), ("stranger@cal", copy(REVIEW))]
    with pytest.raises(MalformedRecord, match="found on stranger@cal, which is nobody's calendar"):
        records.events_from_copies(copies, BY_CALENDAR)


def test_an_attendee_without_a_calendar_is_malformed() -> None:
    only_seda: dict[str, EmployeeId] = {CAL[SEDA]: SEDA}
    with pytest.raises(MalformedRecord, match="missing for emp_002"):
        records.events_from_copies([(CAL[SEDA], copy(REVIEW))], only_seda)


def test_no_copies_are_no_events() -> None:
    assert records.events_from_copies([], BY_CALENDAR) == ()
