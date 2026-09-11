"""The Google Calendar adapter: both calendar ports over REST v3, and the principal's preparation.

Two classes over one wire. ``CalendarAdapter`` implements both calendar ports over a
configured identity map — which secondary calendar is whose — and ``CalendarPrincipal``
is the preparation the composition root runs first: one secondary calendar per person
under the single consumer principal, whose ids are what the manifest records and the
adapter is then handed. The map is configuration and not discovery because the
``calendar.app.created`` scope refuses to list calendars (probed 2026-08-23): the
principal remembers the ids it made or it has lost them, so a known id is verified with
a read and an unknown person gets a new calendar; a manifest lost after creation leaves
orphans only a human can see.

**The wire is ours.** Step 9's tooling ruling named Google's discovery client; this
adapter rides the shared ``Transport`` instead, with google-auth keeping only the
credential and its refresh (the deviation ruled 2026-09-12 with the reviewer's
concurrence). The six calls are plain paths under one base URL, the client ships no
types, and its own retry loop sleeps on the wall clock outside the injected ``sleep``
— one retry rule and one wire-test style beat a second HTTP stack. The refresh grant
rides google-auth's ``requests`` transport, which the cassette machinery records and
whose form fields the scrub filters. The bearer is an httpx auth flow: refreshed
before a request when the library says the token is stale, and once more on a 401.

**Every insert is replayable, and 409 is "verify", not "written".** Google accepts a
caller-supplied event id, and the id is derived from the domain id (``records``), so an
insert that arrives twice answers 409 for the copy the first arrival made. That makes
``add_event`` restartable on its own: a copy that exists is read back and compared to
the intended event, and the write continues to the next attendee's calendar; a copy
that differs, or one Google holds as cancelled (it keeps deleted ids and answers 409
for them), is ``MalformedRecord`` — existence is success only when the existing object
is the intended one. This is the calendar's form of "identity lands last": no marker
is needed because the wire itself makes the write idempotent, and a half-written event
is completed by the same call rather than duplicated.

**Reads collect and the records module judges.** ``events_within`` lists every
configured calendar over the span (Google's ``timeMin``/``timeMax`` are the half-open
overlap the port defines) and ``event`` asks every calendar for the derived id, since
the system cannot say which calendars hold an id; the copies then become events under
the consistency rule in ``records``. Every read passes ``timeZone=UTC`` so identical
copies on calendars in different zones arrive in one representation; correctness never
rested on it, since aware instants compare by instant, but one form keeps the cassette
bodies and the comparison plain.

**Faults.** The transport turns exhausted retries and undeclared statuses into
``SourceUnreachable``; a failed token refresh is the same, raised inside the auth
flow. A copy the translation cannot read raises ``MalformedRecord`` (``records``), and
so does a successful response that is not a JSON object, with the request as locator.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol, cast
from urllib.parse import quote

import httpx
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials

from leaveimpact.adapters.calendar import records
from leaveimpact.adapters.transport import DEFAULT_POLICY, Transport, TransportPolicy
from leaveimpact.core.entities import CalendarEvent, Employee
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import EmployeeId, EventId
from leaveimpact.core.ports.errors import MalformedRecord, SourceUnreachable
from leaveimpact.core.ports.observed import Observed
from leaveimpact.core.worldtime import InstantSpan, as_utc

GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
_PAGE = 250  # Google's maximum for events.list
_READ_ZONE = "UTC"
Record = dict[str, Any]


@dataclass(frozen=True, slots=True)
class CalendarCredential:
    """An OAuth client and the refresh token a consent flow minted for it; the repr shows none.

    The consent flow itself stays in the probes: production never runs one, it holds
    the refresh token the flow produced (the file google-auth writes, whose keys
    ``from_authorized_user_info`` reads).
    """

    client_id: str
    client_secret: str
    refresh_token: str
    token_uri: str = GOOGLE_TOKEN_URI

    def __repr__(self) -> str:
        return "CalendarCredential(client_id=…, client_secret=…, refresh_token=…)"

    @classmethod
    def from_authorized_user_info(cls, info: Mapping[str, Any]) -> CalendarCredential:
        """The credential from the JSON google-auth's ``Credentials.to_json`` writes."""
        return cls(
            client_id=str(info["client_id"]),
            client_secret=str(info["client_secret"]),
            refresh_token=str(info["refresh_token"]),
            token_uri=str(info.get("token_uri") or GOOGLE_TOKEN_URI),
        )


class TokenSource(Protocol):
    """Where the bearer comes from: the live refresh, or a test's constant."""

    def bearer(self) -> str:
        """A token believed valid now — refreshed first if the source knows it is stale."""
        ...

    def refresh(self) -> str:
        """A new token, whatever the source believed; called after the server refused one."""
        ...


class GoogleTokens:
    """The live token source: google-auth's credential, refreshed over its requests transport."""

    def __init__(self, credential: CalendarCredential) -> None:
        self._credentials = Credentials(
            None,
            refresh_token=credential.refresh_token,
            token_uri=credential.token_uri,
            client_id=credential.client_id,
            client_secret=credential.client_secret,
        )
        self._request = GoogleRequest()

    def bearer(self) -> str:
        if not self._credentials.valid:
            return self.refresh()
        return self._token()

    def refresh(self) -> str:
        try:
            # google-auth types the transport parameter loosely; the request is its own.
            self._credentials.refresh(self._request)  # pyright: ignore[reportUnknownMemberType]
        except GoogleAuthError as exc:
            raise SourceUnreachable(
                Source.CALENDAR, f"token refresh failed: {type(exc).__name__}"
            ) from exc
        return self._token()

    def _token(self) -> str:
        token = cast(str | None, self._credentials.token)  # pyright: ignore[reportUnknownMemberType]
        if not token:
            raise SourceUnreachable(Source.CALENDAR, "token refresh returned no access token")
        return token


class BearerAuth(httpx.Auth):
    """The bearer header from a token source; a 401 buys one refresh and one resend."""

    requires_response_body = False

    def __init__(self, tokens: TokenSource) -> None:
        self._tokens = tokens

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response]:
        request.headers["Authorization"] = f"Bearer {self._tokens.bearer()}"
        response = yield request
        if response.status_code != 401:
            return
        request.headers["Authorization"] = f"Bearer {self._tokens.refresh()}"
        yield request


@dataclass(frozen=True, slots=True)
class CalendarConfig:
    """Whose calendar is whose: the identity map the principal's preparation produced.

    A calendar belongs to one person, so two people on one calendar is a configuration
    defect and fails here.

    >>> CalendarConfig({EmployeeId("emp_001"): "a@x", EmployeeId("emp_002"): "a@x"})
    Traceback (most recent call last):
    ...
    ValueError: calendar 'a@x' is configured for more than one person
    """

    calendar_by_employee: Mapping[EmployeeId, str]

    def __post_init__(self) -> None:
        frozen = MappingProxyType(dict(self.calendar_by_employee))
        object.__setattr__(self, "calendar_by_employee", frozen)
        seen: set[str] = set()
        for calendar_id in frozen.values():
            if calendar_id in seen:
                raise ValueError(f"calendar {calendar_id!r} is configured for more than one person")
            seen.add(calendar_id)

    @property
    def employee_by_calendar(self) -> Mapping[str, EmployeeId]:
        return MappingProxyType(
            {calendar_id: person for person, calendar_id in self.calendar_by_employee.items()}
        )


class _Wire:
    """One principal's session: the transport under the bearer, and the JSON-object rule."""

    def __init__(
        self,
        base_url: str,
        tokens: TokenSource,
        policy: TransportPolicy,
        sleep: Callable[[float], None] | None,
        httpx_transport: httpx.BaseTransport | None,
    ) -> None:
        extra: dict[str, Any] = {}
        if sleep is not None:
            extra["sleep"] = sleep
        self.transport = Transport(
            base_url=base_url.rstrip("/"),
            source=Source.CALENDAR,
            headers={"Accept": "application/json"},
            auth=BearerAuth(tokens),
            policy=policy,
            httpx_transport=httpx_transport,
            **extra,
        )

    def get(self, path: str, *, ok: tuple[int, ...] = (200,), **kwargs: Any) -> Record | None:
        """The object at ``path``; ``None`` for an acceptable 404."""
        response = self.transport.request("GET", path, replayable=True, ok=ok, **kwargs)
        if response.status_code == 404:
            return None
        return self._object(response, f"GET {path}")

    def post(
        self, path: str, *, replayable: bool, ok: tuple[int, ...] = (200,), **kwargs: Any
    ) -> httpx.Response:
        return self.transport.request("POST", path, replayable=replayable, ok=ok, **kwargs)

    def delete(self, path: str) -> None:
        self.transport.request("DELETE", path, replayable=True, ok=(204, 404))

    def object(self, response: httpx.Response, locator: str) -> Record:
        return self._object(response, locator)

    @staticmethod
    def _object(response: httpx.Response, locator: str) -> Record:
        try:
            body: Any = response.json()
        except ValueError as exc:
            raise MalformedRecord(Source.CALENDAR, locator, "response is not JSON") from exc
        if not isinstance(body, dict):
            raise MalformedRecord(Source.CALENDAR, locator, "response is not an object")
        return cast(Record, body)


def _calendar_path(calendar_id: str) -> str:
    return f"/calendars/{quote(calendar_id, safe='')}"


def _event_path(calendar_id: str, vendor_id: str) -> str:
    return f"{_calendar_path(calendar_id)}/events/{vendor_id}"


def _required(record: Record, key: str, locator: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise MalformedRecord(Source.CALENDAR, locator, f"no {key}")
    return value


class CalendarPrincipal:
    """Preparation of the principal for a world: a secondary calendar per person.

    Called by the composition root before the adapter is built, never by the adapter;
    ``ensure_calendars`` returns the map the adapter's configuration needs.
    """

    def __init__(
        self,
        *,
        credential: CalendarCredential,
        base_url: str = GOOGLE_CALENDAR_API,
        policy: TransportPolicy = DEFAULT_POLICY,
        sleep: Callable[[float], None] | None = None,
        httpx_transport: httpx.BaseTransport | None = None,
        tokens: TokenSource | None = None,
    ) -> None:
        self._wire = _Wire(
            base_url, tokens or GoogleTokens(credential), policy, sleep, httpx_transport
        )

    def close(self) -> None:
        self._wire.transport.close()

    def ensure_calendars(
        self,
        employees: Iterable[Employee],
        *,
        naming: str,
        known: Mapping[EmployeeId, str] = MappingProxyType({}),
    ) -> dict[EmployeeId, str]:
        """A calendar per employee: the known id verified by a read, the unknown created.

        ``naming`` prefixes every summary (``W1 Deniz Yılmaz``) so a human can tell a
        world's calendars from a cassette's. A known id the principal does not hold is
        ``MalformedRecord``: the manifest and the principal disagree, which nothing
        here can repair.
        """
        calendars: dict[EmployeeId, str] = {}
        for employee in employees:
            remembered = known.get(employee.id)
            if remembered is not None:
                if self._wire.get(_calendar_path(remembered), ok=(200, 404)) is None:
                    raise MalformedRecord(
                        Source.CALENDAR,
                        f"calendars/{remembered}",
                        f"configured for {employee.id} but the principal holds no such calendar",
                    )
                calendars[employee.id] = remembered
                continue
            response = self._wire.post(
                "/calendars", replayable=False, json=records.calendar_payload(employee, naming)
            )
            made = self._wire.object(response, "POST /calendars")
            calendars[employee.id] = _required(made, "id", "POST /calendars")
        return calendars


class CalendarAdapter:
    """Calendar reader and writer over one principal, across the configured calendars."""

    def __init__(
        self,
        *,
        credential: CalendarCredential,
        config: CalendarConfig,
        base_url: str = GOOGLE_CALENDAR_API,
        policy: TransportPolicy = DEFAULT_POLICY,
        sleep: Callable[[float], None] | None = None,
        httpx_transport: httpx.BaseTransport | None = None,
        tokens: TokenSource | None = None,
    ) -> None:
        self._config = config
        self._wire = _Wire(
            base_url, tokens or GoogleTokens(credential), policy, sleep, httpx_transport
        )

    @property
    def config(self) -> CalendarConfig:
        return self._config

    def close(self) -> None:
        self._wire.transport.close()

    # --- the read side --------------------------------------------------------------

    def event(self, id: EventId) -> Observed[CalendarEvent] | None:
        vendor_id = records.vendor_event_id(id)
        copies: list[tuple[str, Record]] = []
        for calendar_id in self._config.calendar_by_employee.values():
            copy = self._wire.get(
                _event_path(calendar_id, vendor_id), ok=(200, 404), params={"timeZone": _READ_ZONE}
            )
            if copy is not None and not records.is_cancelled(copy):
                copies.append((calendar_id, copy))
        events = records.events_from_copies(copies, self._config.employee_by_calendar)
        if not events:
            return None
        (event,) = events
        if event.id != id:
            raise MalformedRecord(
                Source.CALENDAR,
                records.locator(copies[0][0], vendor_id),
                f"the copy at the id derived from {id} carries {event.id}",
            )
        return Observed(event, Source.CALENDAR)

    def events_within(self, span: InstantSpan) -> tuple[Observed[CalendarEvent], ...]:
        window = {
            "timeMin": as_utc(span.start).isoformat(),
            "timeMax": as_utc(span.end).isoformat(),
        }
        copies: list[tuple[str, Record]] = []
        for calendar_id in self._config.calendar_by_employee.values():
            copies.extend((calendar_id, copy) for copy in self._list_events(calendar_id, window))
        return tuple(
            Observed(event, Source.CALENDAR)
            for event in records.events_from_copies(copies, self._config.employee_by_calendar)
        )

    # --- the write side -------------------------------------------------------------

    def add_event(self, event: CalendarEvent) -> str:
        """One copy on each attendee's calendar; a copy that exists is verified, not rewritten."""
        calendars = [self._calendar_of(person) for person in event.attendee_ids]
        payload = records.event_payload(event)
        vendor_id = records.vendor_event_id(event.id)
        for calendar_id in calendars:
            path = f"{_calendar_path(calendar_id)}/events"
            response = self._wire.post(path, replayable=True, ok=(200, 409), json=payload)
            if response.status_code == 409:
                self._verify_existing(calendar_id, vendor_id, event)
        return vendor_id

    def _verify_existing(self, calendar_id: str, vendor_id: str, intended: CalendarEvent) -> None:
        where = records.locator(calendar_id, vendor_id)
        existing = self._wire.get(
            _event_path(calendar_id, vendor_id), ok=(200, 404), params={"timeZone": _READ_ZONE}
        )
        if existing is None:
            raise MalformedRecord(Source.CALENDAR, where, "answered 409 to the insert, then 404")
        if records.is_cancelled(existing):
            raise MalformedRecord(
                Source.CALENDAR, where, "the id is held by a cancelled event; Google keeps it"
            )
        found = records.event_from_record(existing, calendar_id)
        if found != intended:
            raise MalformedRecord(
                Source.CALENDAR, where, f"an existing event differs: {found} is not {intended}"
            )

    # --- the wire ---------------------------------------------------------------------

    def _list_events(self, calendar_id: str, window: Mapping[str, str]) -> list[Record]:
        """Every event on ``calendar_id`` overlapping the window, paged to completion."""
        path = f"{_calendar_path(calendar_id)}/events"
        params: dict[str, Any] = {
            **window,
            "singleEvents": "true",
            "timeZone": _READ_ZONE,
            "maxResults": _PAGE,
        }
        found: list[Record] = []
        while True:
            page = self._wire.get(path, params=params)
            assert page is not None  # a 404 is not acceptable on a list
            items = page.get("items", [])
            if not isinstance(items, list):
                raise MalformedRecord(Source.CALENDAR, f"GET {path}", "items is not a list")
            for item in cast(list[Any], items):
                if not isinstance(item, dict):
                    raise MalformedRecord(
                        Source.CALENDAR, f"GET {path}", "an item is not an object"
                    )
                found.append(cast(Record, item))
            token = page.get("nextPageToken")
            if not isinstance(token, str) or not token:
                return found
            params["pageToken"] = token

    def _calendar_of(self, person: EmployeeId) -> str:
        calendar_id = self._config.calendar_by_employee.get(person)
        if calendar_id is None:
            raise LookupError(
                f"{person} has no calendar configured; prepare the principal's calendars first"
            )
        return calendar_id
