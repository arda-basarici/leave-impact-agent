"""Google Calendar: one secondary calendar per synthetic person under a single consumer
principal, a domain event as one identical copy on each attendee's calendar, the
domain id and the attendees carried in private extended properties as world facts.

Google's own event ids, calendar ids and timestamps are vendor identity and vendor
time, kept inside the adapter. ``records`` holds the pure translation between Google
events and domain entities and the rule that makes one event of its copies;
``adapter`` holds the wire, the bearer, the identity map and the principal's
preparation whose result — the calendar per person — the adapter is configured with.
"""

from leaveimpact.adapters.calendar.adapter import (
    BearerAuth,
    CalendarAdapter,
    CalendarConfig,
    CalendarCredential,
    CalendarPrincipal,
    GoogleTokens,
    TokenSource,
)

__all__ = [
    "BearerAuth",
    "CalendarAdapter",
    "CalendarConfig",
    "CalendarCredential",
    "CalendarPrincipal",
    "GoogleTokens",
    "TokenSource",
]
