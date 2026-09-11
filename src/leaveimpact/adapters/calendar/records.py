"""Google Calendar record shapes, both directions, and the rule that makes one event of its copies.

Pure: every function takes the JSON Google returns and gives back entities or payloads,
so where each fact lives on a Google event and what a set of copies must agree on is
testable without a principal. The adapter (``adapter``) owns the wire.

**Where the facts live.** A domain event is one Google event *per attendee's calendar*:
each person's secondary calendar shows their own busy time, which is what a free/busy
query reads and what the timezone-gap distractor turns on, and the organizer is not a
world fact (every write comes from one principal). The copies are identical: the title
is the summary, the span is ``start``/``end`` as aware instants, and the domain id and
the attendee ids ride ``extendedProperties.private`` — the adapter's custom fields,
which Google stores verbatim and returns with the event. Google's own event id is the
SHA-1 hex digest of the domain id — forty lower-case hex characters, inside the
base32hex alphabet Google accepts — so the vendor identity is derivable and never a
second identity to persist; it is the same on every calendar because Google requires
uniqueness per calendar only, which is what lets a read ask any calendar for an event
by id.

**One event from its copies.** A read collects copies from every configured calendar
and this module groups them by planted id. A group is one event when every copy
translates to the same entity and the calendars it was found on are exactly its
attendees' calendars, one copy each. Copies that disagree, a copy on a calendar whose
person is not an attendee, two copies on one calendar (a second Google event carrying
the same planted id — the derived id keeps the projector from making one, so it is
corruption, and a domain id has exactly one vendor representation per place or the
record is malformed, the rule the Frappe adapter applies to a select), an attendee
with no configured calendar, or an event present on fewer calendars than it names
attendees — a write that stopped halfway — are each ``MalformedRecord``, never a
silent choice of one copy, because the reader's contract is one record per event with
every attendee, and a half-written event would otherwise read as a smaller meeting.

**Malformed means untranslatable.** An event without its planted id or attendees, a
start or end that is a date rather than an instant, an instant without an offset, an
attendee list that does not parse — each raises ``MalformedRecord`` with
``calendars/<calendar>/events/<event>`` as locator.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any, cast

from leaveimpact.core.entities import CalendarEvent, Employee
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import EmployeeId, EventId
from leaveimpact.core.ports.errors import MalformedRecord

Record = dict[str, Any]

# The private extended properties the world facts live in.
EVENT_ID_PROPERTY = "event_id"
ATTENDEES_PROPERTY = "attendees"
ATTENDEE_SEPARATOR = ";"
# Google's event id alphabet: base32hex (0-9, a-v), lower case, 5 to 1024 characters;
# a hex digest uses the first sixteen of those characters.
_BASE32HEX = "0123456789abcdefghijklmnopqrstuv"
CANCELLED = "cancelled"


def vendor_event_id(id: EventId) -> str:
    """Google's id for the event: the SHA-1 hex digest of the domain id, forty characters.

    Deterministic, so a replayed insert meets its own earlier copy (409) instead of
    minting a second one, and derivable, so nothing persists it. Hex is a subset of
    Google's alphabet, so no further encoding is needed.

    >>> vendor_event_id(EventId("event_007"))
    'ec21fc62735787c36a3371aa5fb83bd0a819994e'
    >>> len(vendor_event_id(EventId("event_007"))), set(_BASE32HEX) >= set(
    ...     vendor_event_id(EventId("event_007")))
    (40, True)
    """
    return hashlib.sha1(id.encode()).hexdigest()


def locator(calendar_id: str, vendor_id: str) -> str:
    return f"calendars/{calendar_id}/events/{vendor_id}"


# --- calendars -------------------------------------------------------------------------


def calendar_payload(employee: Employee, naming: str) -> Record:
    """The secondary calendar for ``employee``: named under the world's prefix, in their zone.

    The zone is display only — every instant written carries its offset — but a
    calendar in its person's zone shows their day the way they would see it.

    >>> from leaveimpact.core.enums import EmploymentType, Grade
    >>> from leaveimpact.core.ids import employee_id, team_id
    >>> deniz = Employee(employee_id(4), "Deniz Yılmaz", team_id(1), None, None, "Istanbul",
    ...                  "TR", "Europe/Istanbul", Grade.SENIOR, EmploymentType.EMPLOYEE)
    >>> calendar_payload(deniz, "W1")
    {'summary': 'W1 Deniz Yılmaz', 'timeZone': 'Europe/Istanbul'}
    """
    return {"summary": f"{naming} {employee.name}", "timeZone": employee.timezone}


# --- events ----------------------------------------------------------------------------


def event_payload(event: CalendarEvent) -> Record:
    """The Google event for ``event``, the same body on every attendee's calendar."""
    return {
        "id": vendor_event_id(event.id),
        "summary": event.title,
        "start": {"dateTime": event.start.isoformat()},
        "end": {"dateTime": event.end.isoformat()},
        "extendedProperties": {
            "private": {
                EVENT_ID_PROPERTY: event.id,
                ATTENDEES_PROPERTY: ATTENDEE_SEPARATOR.join(event.attendee_ids),
            }
        },
    }


def event_from_record(record: Record, calendar_id: str) -> CalendarEvent:
    """One copy of an event, as Google returned it from ``calendar_id``.

    >>> event_from_record({"id": "abc12", "summary": "Standup",
    ...                    "start": {"dateTime": "2026-09-08T06:00:00Z"},
    ...                    "end": {"dateTime": "2026-09-08T06:15:00Z"},
    ...                    "extendedProperties": {"private": {
    ...                        "event_id": "event_001", "attendees": "emp_001;emp_002"}}},
    ...                   "cal@group.calendar.google.com")
    ... # doctest: +NORMALIZE_WHITESPACE
    CalendarEvent(id='event_001', title='Standup',
                  start=datetime.datetime(2026, 9, 8, 6, 0, tzinfo=datetime.timezone.utc),
                  end=datetime.datetime(2026, 9, 8, 6, 15, tzinfo=datetime.timezone.utc),
                  attendee_ids=('emp_001', 'emp_002'))
    """
    where = locator(calendar_id, str(record.get("id", "?")))
    private = _private(record, where)
    attendees = _text(private, ATTENDEES_PROPERTY, where)
    attendee_ids = tuple(EmployeeId(item) for item in attendees.split(ATTENDEE_SEPARATOR) if item)
    if not attendee_ids:
        raise MalformedRecord(Source.CALENDAR, where, "no attendees")
    start = _instant(record, "start", where)
    end = _instant(record, "end", where)
    if end <= start:
        raise MalformedRecord(
            Source.CALENDAR, where, f"ends at or before it starts: {start}..{end}"
        )
    return CalendarEvent(
        id=EventId(_text(private, EVENT_ID_PROPERTY, where)),
        title=_text(record, "summary", where),
        start=start,
        end=end,
        attendee_ids=attendee_ids,
    )


def is_cancelled(record: Record) -> bool:
    """Whether Google holds this copy as deleted — an id it keeps and answers 409 for."""
    return record.get("status") == CANCELLED


def events_from_copies(
    copies: Iterable[tuple[str, Record]], employee_by_calendar: Mapping[str, EmployeeId]
) -> tuple[CalendarEvent, ...]:
    """The events a set of (calendar id, Google event) copies make, one per planted id.

    ``employee_by_calendar`` is the configured identity map inverted: whose calendar
    each copy came from. The order is the copies' first appearance.
    """
    grouped: dict[EventId, list[tuple[str, CalendarEvent]]] = {}
    for calendar_id, record in copies:
        event = event_from_record(record, calendar_id)
        grouped.setdefault(event.id, []).append((calendar_id, event))
    return tuple(
        _one_event(id, found, employee_by_calendar) for id, found in grouped.items()
    )


def _one_event(
    id: EventId,
    found: list[tuple[str, CalendarEvent]],
    employee_by_calendar: Mapping[str, EmployeeId],
) -> CalendarEvent:
    first_calendar, event = found[0]
    where = locator(first_calendar, vendor_event_id(id))
    for calendar_id, copy in found[1:]:
        if copy != event:
            raise MalformedRecord(
                Source.CALENDAR,
                where,
                f"the copy on {calendar_id} disagrees: {copy} is not {event}",
            )
    seen: dict[EmployeeId, str] = {}
    for calendar_id, _ in found:
        person = employee_by_calendar.get(calendar_id)
        if person is None:
            raise MalformedRecord(
                Source.CALENDAR, where, f"found on {calendar_id}, which is nobody's calendar"
            )
        if person not in event.attendee_ids:
            raise MalformedRecord(
                Source.CALENDAR, where, f"found on {person}'s calendar, who does not attend"
            )
        if person in seen:
            raise MalformedRecord(
                Source.CALENDAR, where, f"twice on {person}'s calendar; one copy per place"
            )
        seen[person] = calendar_id
    missing = [person for person in event.attendee_ids if person not in seen]
    if missing:
        raise MalformedRecord(
            Source.CALENDAR,
            where,
            f"on {len(seen)} of {len(event.attendee_ids)} attendees' calendars; "
            f"missing for {', '.join(missing)}",
        )
    return event


# --- the pieces ------------------------------------------------------------------------


def _object(record: Record, key: str) -> Record | None:
    value = record.get(key)
    return cast(Record, value) if isinstance(value, dict) else None


def _private(record: Record, where: str) -> Record:
    extended = _object(record, "extendedProperties")
    private = _object(extended, "private") if extended is not None else None
    if private is None:
        raise MalformedRecord(Source.CALENDAR, where, "no private extended properties")
    return private


def _text(record: Record, key: str, where: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise MalformedRecord(Source.CALENDAR, where, f"no {key}")
    return value


def _instant(record: Record, key: str, where: str) -> datetime:
    """``record[key].dateTime`` as an aware instant; a date-only end or a naive one is malformed."""
    moment = _object(record, key)
    raw = moment.get("dateTime") if moment is not None else None
    if not isinstance(raw, str):
        raise MalformedRecord(Source.CALENDAR, where, f"{key} is not an instant")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise MalformedRecord(Source.CALENDAR, where, f"{key} {raw!r} is not RFC 3339") from exc
    if parsed.tzinfo is None:
        raise MalformedRecord(Source.CALENDAR, where, f"{key} {raw!r} carries no offset")
    return parsed
