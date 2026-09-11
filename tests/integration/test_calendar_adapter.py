"""The calendar adapter against the principal, recorded once and replayed on every push.

One scenario end to end: three cassette calendars made under the principal, one in a
zone six hours and more from Istanbul; three events written — a standup all three
attend, a review two attend, a call one attends — then the review written a second
time, which is the restart the adapter promises: every insert answers 409, every copy
is read back and matches, the locator is the same. Then everything read back through
the reader's two questions — the week, a narrower window, an empty one, the event by
id, an id nobody holds — and the calendars deleted. The claims are the port's: what
the writer added, the reader returns as the same entity once, attendees complete,
whichever calendars it lives on and whatever zone they display in; a span selects by
overlap; an absent identity is ``None``. Two are the principal's, proven live: a
supplied id makes the insert idempotent, and the app-created scope may delete the
calendars it made.

Recording (``just test-record``) needs the token file's directory in the environment;
replay needs nothing and the token refresh replays with its secrets filtered. The
``CAS`` naming is the cassette scope; a world's calendars are never these.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from leaveimpact.adapters.calendar import (
    BearerAuth,
    CalendarAdapter,
    CalendarConfig,
    CalendarCredential,
    CalendarPrincipal,
    GoogleTokens,
)
from leaveimpact.adapters.calendar.adapter import GOOGLE_CALENDAR_API
from leaveimpact.adapters.transport import Transport
from leaveimpact.core.entities import CalendarEvent, Employee
from leaveimpact.core.enums import EmploymentType, Grade, Source
from leaveimpact.core.ids import employee_id, event_id, team_id
from leaveimpact.core.worldtime import InstantSpan
from tests.integration.calendar_support import delete_calendars
from tests.recording import google_authorized_user_info

pytestmark = [pytest.mark.integration, pytest.mark.vcr]

ISTANBUL = ZoneInfo("Europe/Istanbul")
NAMING = "CAS"


def person(number: int, name: str, city: str, country: str, zone: str) -> Employee:
    return Employee(
        employee_id(number),
        name,
        team_id(901),
        None,
        None,
        city,
        country,
        zone,
        Grade.MID,
        EmploymentType.EMPLOYEE,
    )


SEDA = person(901, "Seda Aksoy", "Istanbul", "TR", "Europe/Istanbul")
BARAN = person(902, "Baran Demir", "Berlin", "DE", "Europe/Berlin")
DENIZ = person(903, "Deniz Yılmaz", "San Francisco", "US", "America/Los_Angeles")
PEOPLE = (SEDA, BARAN, DENIZ)


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=ISTANBUL)


STANDUP = CalendarEvent(
    event_id(901), "Standup", at(8, 9), at(8, 9, 15), (SEDA.id, BARAN.id, DENIZ.id)
)
REVIEW = CalendarEvent(event_id(902), "Customer review", at(8, 13), at(8, 15), (SEDA.id, BARAN.id))
CALL = CalendarEvent(event_id(903), "Vendor call", at(9, 18), at(9, 19), (DENIZ.id,))


def credential() -> CalendarCredential:
    info = google_authorized_user_info()
    if info is not None:
        return CalendarCredential.from_authorized_user_info(info)
    return CalendarCredential("replay", "replay", "replay")


def test_events_written_are_read_back_once_with_every_attendee() -> None:
    cred = credential()
    principal = CalendarPrincipal(credential=cred, sleep=lambda _: None)
    made = principal.ensure_calendars(PEOPLE, naming=NAMING)
    principal.close()
    assert set(made) == {SEDA.id, BARAN.id, DENIZ.id} and len(set(made.values())) == 3
    try:
        adapter = CalendarAdapter(
            credential=cred, config=CalendarConfig(made), sleep=lambda _: None
        )
        locators = [adapter.add_event(STANDUP), adapter.add_event(REVIEW), adapter.add_event(CALL)]
        assert all(locators) and len(set(locators)) == 3
        assert adapter.add_event(REVIEW) == locators[1], "a restart meets its own copies"

        week = InstantSpan(at(7, 0), at(14, 0))
        found = adapter.events_within(week)
        assert all(item.source is Source.CALENDAR for item in found)
        assert {item.value for item in found} == {STANDUP, REVIEW, CALL}
        assert len(found) == 3, "one record per event, not one per calendar"

        tuesday_afternoon = InstantSpan(at(8, 14), at(8, 18))
        assert {item.value for item in adapter.events_within(tuesday_afternoon)} == {REVIEW}
        assert adapter.events_within(InstantSpan(at(8, 15), at(9, 18))) == ()

        review = adapter.event(REVIEW.id)
        assert review is not None and review.value == REVIEW
        assert adapter.event(event_id(999)) is None
        adapter.close()
    finally:
        with Transport(
            base_url=GOOGLE_CALENDAR_API,
            source=Source.CALENDAR,
            auth=BearerAuth(GoogleTokens(cred)),
            sleep=lambda _: None,
        ) as raw:
            delete_calendars(raw, made.values())
