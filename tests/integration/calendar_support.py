"""Recording-time support for the calendar cassette: the cassette calendars removed.

The ``calendar.app.created`` scope cannot list calendars, so a recording cannot start
by finding what a previous run left; it starts clean by creating its own calendars and
ends by deleting them, inside the cassette, so a replay replays the deletes too and
never touches the principal. A recording that dies between the two leaves orphan
calendars under the principal that only its human owner can see and remove. It runs
through the same transport under the same bearer. Test support, not adapter
capability: the adapter never deletes.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote

from leaveimpact.adapters.transport import Transport


def delete_calendars(transport: Transport, calendar_ids: Iterable[str]) -> None:
    """Delete each calendar; one already gone is not an error."""
    for calendar_id in calendar_ids:
        transport.request(
            "DELETE", f"/calendars/{quote(calendar_id, safe='')}", replayable=True, ok=(204, 404)
        )
