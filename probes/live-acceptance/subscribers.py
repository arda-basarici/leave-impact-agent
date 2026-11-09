"""The live path's acceptance probe from a visitor's side (the demo milestone's step 16):
narration-stream subscribers held on one open attempt through the hostname with every
frame's arrival timed, the open page's latency sampled before and during the hold, the
subscription bound's refusal and one replacement after a release, and the open timeline
read for a content-security rule and the zone's beacon. Run from the workstation against
the public hostname while the attempt is open, the attempt's public id from the browser's
address bar::

    uv run python probes/live-acceptance/subscribers.py --attempt live-<id> \
        --clients 7 --label run2 --out <capture>/subscribers-run2.json

Each subscriber opens the events route from cursor 0, so its first tick loads the whole log
as the timeline page's own connection does, and records on a monotonic clock the instant it
connected, the instant of its first frame, every frame's event name, position, recorded
instant and arrival, every heartbeat's arrival, and how it ended (the closing frame, an
unavailable frame, an error, the probe's deadline). Buffering between the application and
a browser shows in two comparisons the reducer makes with no clock offset in them: the gaps
before heartbeats against the heartbeat's fifteen-second cadence, and the intervals between
consecutive line frames' recorded instants against the intervals between their arrivals.
The third comparison, a frame's arrival against its recorded instant, needs the offset of
the two clocks, which the Date header of a request to the readiness route bounds to its one
second of resolution plus the round trip; that request is made first and recorded.

The page latency is the open attempt's replay page fetched a few times before the
subscribers attach and again once every subscriber has its first frame, the same frozen
page when the run is awaiting its decision. After every subscriber has its first frame one
more connection is opened and its status recorded (the bound answers the unavailable page
at 503), the first subscriber is closed, and after a pause one more is opened and held, so
a released slot admitting a replacement is observed and not assumed. The timeline page is
fetched once with a browser's Accept and user agent, and its Content-Security-Policy
header, the inline script's presence and the beacon's host are recorded as the response
carried them. The subscribers then hold until every stream ends with the closing frame or
the deadline passes; a decision posted from the browser while they hold is the decision
measured under the bound. Nothing is asserted here: the reducer prints, the record judges.

A browser with the timeline page open holds a connection of its own, so the clients asked
for are one under the bound in that case; the count held and the bound are both recorded.
Instants are seconds from the probe's start on the monotonic clock, with the start's UTC
wall time recorded once, so the reducer can place them beside the sampler's epoch instants
and the log's own. Standard library only, so it runs from any checkout.

With ``--start`` the probe starts the attempt itself (the final smoke of the demo
milestone's step 17), since an attempt's active phase ends in about twenty seconds, inside
the time a probe needs to attach once a browser has shown the public id::

    uv run python probes/live-acceptance/subscribers.py --start --scenario scenario_028 \
        --decision decline --label runA --out <capture>/subscribers-runA.json

It reads the index as a browser does and posts the start form the page renders, with the
key the page minted and a scenario the form offers; it keeps the cookie the redirect sets,
opens every subscriber at once and holds them through the active phase with no other
request, so the host's samples in that phase are the streams' cost and nothing of the
probe's own. The bound's refusal, the release and the replacement move to the wait, once a
frame says the approval is requested, so no release gap falls in the active phase; after
``--awaiting-hold`` seconds it reads the holder's page with the cookie, takes the review's
digest from the decision form and posts the decision, timed at this client through the
edge, then holds to the closing frames. The open page's latency before the hold is not
taken in this mode, since nothing precedes the attach. Where the index shows no form (live
runs off) it posts one start with a key of its own and records the answer, the check that
a scripted post reaches the application through the edge and is refused by it. The reading
carries statuses, timings and the public id; the key, the cookie and every page body stay
in memory and are never written, the key being the capability to decide the attempt.
"""

from __future__ import annotations

import argparse
import contextlib
import email.utils
import html.parser
import http.client
import json
import secrets
import sys
import threading
import time
from datetime import UTC, datetime
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) leave-impact-acceptance-probe/1"
BROWSER_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
EVENTS_ACCEPT = "text/event-stream"
TERMINAL_EVENTS = ("closed", "unavailable")
HEADERS_KEPT = (
    "content-type",
    "content-encoding",
    "transfer-encoding",
    "content-security-policy",
    "content-security-policy-report-only",
    "cache-control",
    "server",
    "via",
    "cf-cache-status",
    "date",
)
INLINE_SCRIPT_MARK = "new EventSource("
BEACON_HOST = "static.cloudflareinsights.com"
FORM_TYPE = "application/x-www-form-urlencoded"
LIVE_RUNS_OFF_MARK = "Live runs are off"
"""The application's refusal of a start under the flag off, as its page words it."""
APPROVAL_KIND = "approval_requested"

_START = time.monotonic()
_STARTED_EPOCH = time.time()


def now() -> float:
    """Seconds since the probe started, on the monotonic clock."""
    return round(time.monotonic() - _START, 4)


def log(message: str) -> None:
    print(f"{now():8.2f}s  {message}", file=sys.stderr, flush=True)


def _connection(base: str, timeout: float) -> http.client.HTTPConnection:
    parts = urlsplit(base)
    host = parts.hostname or ""
    if parts.scheme == "https":
        return http.client.HTTPSConnection(host, parts.port or 443, timeout=timeout)
    return http.client.HTTPConnection(host, parts.port or 80, timeout=timeout)


def _kept(headers: http.client.HTTPMessage) -> dict[str, str]:
    return {name: value for name, value in ((n, headers.get(n)) for n in HEADERS_KEPT) if value}


def timed_request(
    base: str,
    method: str,
    path: str,
    accept: str,
    *,
    fields: dict[str, str] | None = None,
    cookie: str | None = None,
    timeout: float = 30.0,
) -> tuple[dict[str, Any], http.client.HTTPMessage | None]:
    """One request timed on the monotonic clock: status, seconds to the whole body, the
    body's length and the headers kept, beside the response's own headers for the caller
    that reads a redirect or a cookie off them. ``fields`` is posted as a form with the
    Origin a browser's post carries; ``cookie`` is the Cookie header. A redirect is never
    followed. An error is recorded as the record, never raised. The record carries the
    body, which every caller pops before a reading is written."""
    started = now()
    connection = _connection(base, timeout)
    headers = {"Accept": accept, "User-Agent": USER_AGENT, "Host": urlsplit(base).netloc}
    payload: bytes | None = None
    if fields is not None:
        payload = urlencode(fields).encode("ascii")
        headers["Content-Type"] = FORM_TYPE
        headers["Origin"] = base
    if cookie:
        headers["Cookie"] = cookie
    try:
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        body = response.read()
        record = {
            "path": path,
            "status": response.status,
            "seconds": round(now() - started, 4),
            "bytes": len(body),
            "headers": _kept(response.headers),
            "body": body.decode("utf-8", errors="replace"),
        }
        return record, response.headers
    except OSError as error:
        return {
            "path": path,
            "status": None,
            "seconds": round(now() - started, 4),
            "error": repr(error),
        }, None
    finally:
        connection.close()


def timed_get(
    base: str, path: str, accept: str, timeout: float = 30.0, cookie: str | None = None
) -> dict[str, Any]:
    """One GET timed on the monotonic clock, the record alone: status, seconds to the
    whole body, the body's length and the headers kept; an error recorded as the record,
    never raised."""
    return timed_request(base, "GET", path, accept, cookie=cookie, timeout=timeout)[0]


def clock_offset(base: str) -> dict[str, Any]:
    """The server's Date header against this clock: the offset in seconds (server minus
    local at the request's midpoint), the round trip, and the header's one-second
    resolution, which together bound every recorded-to-arrival comparison."""
    before_epoch, before = time.time(), time.monotonic()
    read = timed_get(base, "/ready", "application/json")
    after = time.monotonic()
    date = read.get("headers", {}).get("date")
    server_epoch = email.utils.parsedate_to_datetime(date).timestamp() if date else None
    midpoint = before_epoch + (after - before) / 2
    return {
        "status": read["status"],
        "date": date,
        "round_trip_seconds": round(after - before, 4),
        "resolution_seconds": 1.0,
        "offset_seconds": None if server_epoch is None else round(server_epoch - midpoint, 3),
    }


class Subscriber(threading.Thread):
    """One stream held in a thread; what it saw is read off it after it ends."""

    def __init__(self, index: int, base: str, path: str, read_timeout: float) -> None:
        super().__init__(name=f"subscriber-{index}", daemon=True)
        self.index = index
        self.base = base
        self.path = path
        self.read_timeout = read_timeout
        self.opened_at: float | None = None
        self.connected_at: float | None = None
        self.status: int | None = None
        self.headers: dict[str, str] = {}
        self.first_frame_at: float | None = None
        self.frames: list[dict[str, Any]] = []
        self.heartbeats: list[float] = []
        self.ended: str | None = None
        self.ended_at: float | None = None
        self.error: str | None = None
        self._stop = threading.Event()
        self._connection: http.client.HTTPConnection | None = None

    def run(self) -> None:
        self.opened_at = now()
        connection = _connection(self.base, self.read_timeout)
        self._connection = connection
        try:
            connection.request(
                "GET",
                self.path,
                headers={
                    "Accept": EVENTS_ACCEPT,
                    "User-Agent": USER_AGENT,
                    "Cache-Control": "no-store",
                    "Host": urlsplit(self.base).netloc,
                },
            )
            response = connection.getresponse()
        except OSError as error:
            self._end("error", repr(error))
            return
        self.connected_at = now()
        self.status = response.status
        self.headers = _kept(response.headers)
        if response.status != 200:
            response.read()
            self._end("refused")
            return
        buffer: list[str] = []
        try:
            while not self._stop.is_set():
                raw = response.readline()
                if not raw:
                    # A socket this probe shut ends the read with an empty line on Linux
                    # and with an error on Windows; both are the probe's own close.
                    self._end("closed by the probe" if self._stop.is_set() else "eof")
                    return
                arrival = now()
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                if line == "":
                    if buffer:
                        self._frame(buffer, arrival)
                        buffer = []
                    continue
                if line.startswith(":"):
                    self.heartbeats.append(arrival)
                    continue
                buffer.append(line)
        except OSError as error:
            if self.ended is None and self._stop.is_set():
                self._end("closed by the probe")  # the shutdown's own error is not a finding
            elif self.ended is None:
                self._end("error", repr(error))
        finally:
            connection.close()
            if self.ended is None:
                self._end("closed by the probe")

    def _frame(self, lines: list[str], arrival: float) -> None:
        event: str | None = None
        position: int | None = None
        data: Any = None
        for line in lines:
            name, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if name == "event":
                event = value
            elif name == "id":
                position = int(value)
            elif name == "data":
                data = json.loads(value)
        if self.first_frame_at is None:
            self.first_frame_at = arrival
        frame: dict[str, Any] = {"event": event, "position": position, "arrival": arrival}
        if isinstance(data, dict):
            for key in ("recorded_at", "kind", "status", "reason"):
                if key in data:
                    frame[key] = data[key]
        self.frames.append(frame)
        if event in TERMINAL_EVENTS:
            self._end(event)
            self._stop.set()

    def _end(self, reason: str, error: str | None = None) -> None:
        if self.ended is None:
            self.ended = reason
            self.ended_at = now()
        if error is not None and self.error is None:
            self.error = error

    def close(self) -> None:
        """Shut the socket under the blocked read, so the slot is released now and not at
        the read timeout."""
        self._stop.set()
        connection = self._connection
        sock = getattr(connection, "sock", None)
        if sock is not None:
            with contextlib.suppress(OSError):
                sock.shutdown(2)

    def record(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "opened_at": self.opened_at,
            "connected_at": self.connected_at,
            "status": self.status,
            "headers": self.headers,
            "first_frame_at": self.first_frame_at,
            "frames": self.frames,
            "heartbeats": self.heartbeats,
            "ended": self.ended,
            "ended_at": self.ended_at,
            "error": self.error,
        }


def _wait_for_first_frames(subscribers: list[Subscriber], seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if all(s.first_frame_at is not None or s.ended is not None for s in subscribers):
            return True
        time.sleep(0.1)
    return False


def _timeline_read(base: str, attempt: str) -> dict[str, Any]:
    read = timed_get(base, f"/replays/{attempt}/timeline", BROWSER_ACCEPT)
    body = read.pop("body", "")
    read["inline_script_present"] = INLINE_SCRIPT_MARK in body
    read["beacon_present"] = BEACON_HOST in body
    return read


def _page_samples(base: str, attempt: str, count: int) -> list[dict[str, Any]]:
    samples = []
    for _ in range(count):
        read = timed_get(base, f"/replays/{attempt}", BROWSER_ACCEPT)
        read.pop("body", None)
        samples.append(read)
    return samples


class _Forms(html.parser.HTMLParser):
    """A page's forms by id, as a browser reads them: each form's action, the values of
    its named inputs and the option values of its named selects."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: dict[str, dict[str, Any]] = {}
        self._form: dict[str, Any] | None = None
        self._select: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        given = dict(attrs)
        if tag == "form":
            self._form = {"action": given.get("action"), "fields": {}, "options": {}}
            self.forms[given.get("id") or ""] = self._form
            return
        name = given.get("name")
        if self._form is None:
            return
        if tag == "input" and name:
            self._form["fields"][name] = given.get("value") or ""
        elif tag == "select" and name:
            self._select = name
            self._form["options"][name] = []
        elif tag == "option" and self._select is not None:
            self._form["options"][self._select].append(given.get("value") or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._form, self._select = None, None
        elif tag == "select":
            self._select = None


def forms_of(body: str) -> dict[str, dict[str, Any]]:
    """The forms of ``body`` by their id attribute."""
    parser = _Forms()
    parser.feed(body)
    return parser.forms


class _Jar:
    """The cookies a response set, sent back on the paths they are scoped to, as a browser
    does. Held in memory for the probe's life and never written: the start's cookie is
    the key that decides the attempt."""

    def __init__(self) -> None:
        self._cookies: list[tuple[str, str, str]] = []

    def take(self, headers: http.client.HTTPMessage | None) -> int:
        """Keep every cookie ``headers`` sets; the count kept."""
        kept = 0
        for line in (headers.get_all("set-cookie") or []) if headers is not None else []:
            jar: SimpleCookie = SimpleCookie()
            try:
                jar.load(line)
            except CookieError:
                continue  # a cookie this parser refuses is one the probe never needed
            for name, morsel in jar.items():
                self._cookies.append((name, morsel.coded_value, morsel["path"] or "/"))
                kept += 1
        return kept

    def header_for(self, path: str) -> str | None:
        """The Cookie header for a request to ``path``; ``None`` when no cookie is scoped
        to it."""
        pairs = [
            f"{name}={value}" for name, value, scope in self._cookies if path.startswith(scope)
        ]
        return "; ".join(pairs) or None


def _attempt_of(path: str) -> str | None:
    """The public id a start's redirect names (``/replays/live-<id>``), or ``None``."""
    prefix = "/replays/"
    name = path[len(prefix) :] if path.startswith(prefix) else ""
    return name if name.startswith("live-") and "/" not in name else None


def _location(headers: http.client.HTTPMessage | None) -> tuple[str | None, str | None]:
    """A response's Location as its host and its path; the query is never kept, since a
    redirect an edge writes can carry signed metadata about the visitor."""
    value = headers.get("location") if headers is not None else None
    if not value:
        return None, None
    parts = urlsplit(value)
    return parts.netloc or None, parts.path or None


def _wait_for_kind(subscribers: list[Subscriber], kind: str, seconds: float) -> float | None:
    """The probe's instant at which a held stream has shown a frame of ``kind``; ``None``
    when every stream ended first or the wait passed."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if any(f.get("kind") == kind for s in subscribers for f in list(s.frames)):
            return now()
        if all(s.ended is not None for s in subscribers):
            return None
        time.sleep(0.1)
    return None


def _hold_while_open(subscribers: list[Subscriber], seconds: float) -> None:
    """Wait ``seconds``, or until every stream has ended."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and any(s.ended is None for s in subscribers):
        time.sleep(0.2)


def _start(base: str, scenario: str) -> tuple[dict[str, Any], dict[str, Any], _Jar]:
    """The index read and the start posted as the page offers it: the index's record, the
    start's record with the instant it was sent, and the cookies the answer set. Where the
    index renders no form the start is posted with a key of the probe's own, so the
    application's refusal is the answer recorded."""
    jar = _Jar()
    page = timed_get(base, "/", BROWSER_ACCEPT)
    form = forms_of(page.pop("body", "")).get("start")
    index: dict[str, Any] = {**page, "form_present": form is not None}
    if form is None:
        key = secrets.token_hex(16)
    else:
        key = form["fields"].get("key", "")
        offered = form["options"].get("scenario_id", [])
        index["scenarios_offered"] = len(offered)
        if scenario not in offered:
            return index, {"posted": False, "reason": f"the form does not offer {scenario}"}, jar
    sent = now()
    answer, headers = timed_request(
        base, "POST", "/start", BROWSER_ACCEPT, fields={"key": key, "scenario_id": scenario}
    )
    body = answer.pop("body", "")
    host, path = _location(headers)
    start = {
        "posted": True,
        "sent_at": sent,
        "status": answer["status"],
        "seconds": answer["seconds"],
        "headers": answer.get("headers", {}),
        "location_host": host,
        "location_path": path,
        "live_runs_off_text": LIVE_RUNS_OFF_MARK in body,
        "cookies_set": jar.take(headers),
        "error": answer.get("error"),
    }
    return index, start, jar


def _decide(base: str, attempt: str, jar: _Jar, decision: str) -> dict[str, Any]:
    """The holder's page read with the start's cookie and the decision posted through its
    form: the review's digest from the hidden field, the post timed at this client."""
    path = f"/replays/{attempt}"
    page = timed_get(base, path, BROWSER_ACCEPT, cookie=jar.header_for(path))
    form = forms_of(page.pop("body", "")).get("decision")
    record: dict[str, Any] = {
        "asked": decision,
        "page_status": page["status"],
        "page_seconds": page["seconds"],
        "form_present": form is not None,
    }
    if form is None:
        return {**record, "posted": False}
    action = form["action"] or f"{path}/decision"
    digest = form["fields"].get("payload_digest", "")
    sent = now()
    answer, headers = timed_request(
        base,
        "POST",
        action,
        BROWSER_ACCEPT,
        fields={"decision": decision, "payload_digest": digest},
        cookie=jar.header_for(action),
    )
    answer.pop("body", None)
    host, location = _location(headers)
    return {
        **record,
        "posted": True,
        "sent_at": sent,
        "status": answer["status"],
        "seconds": answer["seconds"],
        "location_host": host,
        "location_path": location,
        "review_digest": digest,
        "error": answer.get("error"),
    }


def run_started(args: argparse.Namespace) -> dict[str, Any]:
    """The start mode: the attempt started from the index's form, every subscriber held
    from its first second through the active phase, the bound's checks and the decision in
    the wait, the hold to the closing frames. A start the application does not admit is
    the reading: its status, and no stream opened."""
    base = args.base.rstrip("/")
    reading: dict[str, Any] = {
        "probe": "subscribers",
        "mode": "started",
        "label": args.label,
        "started_utc": datetime.fromtimestamp(_STARTED_EPOCH, UTC).isoformat(),
        "started_epoch": round(_STARTED_EPOCH, 3),
        "base": base,
        "attempt": None,
        "scenario": args.scenario,
        "bound": args.bound,
        "clients": args.clients,
        "hold_seconds": args.hold,
        "awaiting_hold_seconds": args.awaiting_hold,
        "deadline_seconds": args.max_seconds,
        "timeline": None,
        "page_before": [],
        "page_during": [],
        "beyond_bound": None,
        "released": None,
        "replacement": None,
        "decision": None,
    }
    log("clock offset against the readiness route's Date header")
    reading["clock"] = clock_offset(base)
    log(f"the index, then the start of {args.scenario} as its form offers it")
    reading["index"], reading["start"], jar = _start(base, args.scenario)
    start = reading["start"]
    attempt = _attempt_of(start.get("location_path") or "")
    if not start["posted"] or start["status"] != 303 or attempt is None:
        log(f"no attempt started: index form {reading['index']['form_present']}, start {start}")
        return reading
    reading["attempt"] = attempt
    log(f"started {attempt} in {start['seconds']} s; {args.clients} subscribers at once")
    events_path = f"/replays/{attempt}/events?after=0"
    held: list[Subscriber] = []
    everyone: list[Subscriber] = []
    try:
        for index in range(args.clients):
            subscriber = Subscriber(index, base, events_path, args.read_timeout)
            subscriber.start()
            held.append(subscriber)
            everyone.append(subscriber)
        reading["attached_at"] = now()
        complete = _wait_for_first_frames(held, args.first_frame_wait)
        reading["all_first_frames_at"] = now() if complete else None
        reading["reach_seconds"] = (
            round(reading["all_first_frames_at"] - start["sent_at"], 4) if complete else None
        )
        log(f"every first frame {reading['reach_seconds']} s after the start was sent")
        log("holding through the active phase with no other request")
        reading["approval_seen_at"] = _wait_for_kind(held, APPROVAL_KIND, args.active_wait)
        if reading["approval_seen_at"] is None:
            log("no approval request seen; holding to the close with no decision")
        else:
            log("the approval is requested; the timeline, the open page, the bound")
            reading["timeline"] = _timeline_read(base, attempt)
            reading["page_during"] = _page_samples(base, attempt, args.page_samples)
            _bound_release_replacement(args, base, events_path, held, everyone, reading)
            log(f"held in the wait {args.awaiting_hold} s before the decision")
            _hold_while_open(held, args.awaiting_hold)
            reading["decision"] = _decide(base, attempt, jar, args.decision)
            log(f"the decision: {reading['decision']}")
        _hold_to_close(args, held, reading)
    except KeyboardInterrupt:
        reading["hold_ended_at"] = now()
        reading["hold_ended_by"] = "interrupt"
        log("interrupted; closing and writing what was seen")
    finally:
        for subscriber in everyone:
            subscriber.close()
        for subscriber in everyone:
            subscriber.join(5)
    reading["subscribers"] = [s.record() for s in everyone]
    reading["finished_at"] = now()
    return reading


def _bound_release_replacement(
    args: argparse.Namespace,
    base: str,
    events_path: str,
    held: list[Subscriber],
    everyone: list[Subscriber],
    reading: dict[str, Any],
) -> None:
    """One connection past the bound with its status recorded, the first subscriber
    released, and one replacement opened after a pause and held; ``held`` and
    ``everyone`` are moved with it."""
    log("one connection past the bound")
    beyond = Subscriber(len(everyone), base, events_path, args.read_timeout)
    beyond.start()
    everyone.append(beyond)
    _wait_for_first_frames([beyond], args.first_frame_wait)
    if beyond.ended is None and beyond.first_frame_at is not None:
        # The bound was not reached (fewer clients than the bound less the browser's own):
        # the connection was admitted and is held like the others.
        held.append(beyond)
    reading["beyond_bound"] = {
        "index": beyond.index,
        "status": beyond.status,
        "ended": beyond.ended,
    }
    log(f"past the bound: status {beyond.status}, ended {beyond.ended}")

    log("the first subscriber released, a replacement after a pause")
    released = held.pop(0)
    released.close()
    released.join(5)
    reading["released"] = {
        "index": released.index,
        "ended": released.ended,
        "ended_at": released.ended_at,
    }
    time.sleep(args.replacement_pause)
    replacement = Subscriber(len(everyone), base, events_path, args.read_timeout)
    replacement.start()
    everyone.append(replacement)
    _wait_for_first_frames([replacement], args.first_frame_wait)
    held.append(replacement)
    reading["replacement"] = {
        "index": replacement.index,
        "status": replacement.status,
        "first_frame_at": replacement.first_frame_at,
        "ended": replacement.ended,
    }
    log(f"replacement: status {replacement.status}, first frame {replacement.first_frame_at}")


def _hold_to_close(
    args: argparse.Namespace, held: list[Subscriber], reading: dict[str, Any]
) -> None:
    """Hold until every held stream has ended and the hold's floor has passed, or the
    probe's deadline; how the hold ended is recorded."""
    log(
        f"holding {len(held)} subscribers until their closing frames, at least {args.hold} s, "
        f"at most {args.max_seconds} s; a decision posted now is measured under them"
    )
    hold_until = time.monotonic() + args.hold
    deadline = _START + args.max_seconds
    last_report = time.monotonic()
    while time.monotonic() < deadline:
        all_ended = all(s.ended is not None for s in held)
        if all_ended and time.monotonic() >= hold_until:
            break
        if time.monotonic() - last_report >= 30:
            frames = sum(len(s.frames) for s in held)
            beats = sum(len(s.heartbeats) for s in held)
            ended = sum(s.ended is not None for s in held)
            log(f"holding: {frames} frames, {beats} heartbeats, {ended} ended")
            last_report = time.monotonic()
        time.sleep(0.2)
    reading["hold_ended_at"] = now()
    reading["hold_ended_by"] = (
        "closing frames" if all(s.ended is not None for s in held) else "deadline"
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    base = args.base.rstrip("/")
    events_path = f"/replays/{args.attempt}/events?after=0"
    reading: dict[str, Any] = {
        "probe": "subscribers",
        "label": args.label,
        "started_utc": datetime.fromtimestamp(_STARTED_EPOCH, UTC).isoformat(),
        "started_epoch": round(_STARTED_EPOCH, 3),
        "base": base,
        "attempt": args.attempt,
        "bound": args.bound,
        "clients": args.clients,
        "hold_seconds": args.hold,
        "deadline_seconds": args.max_seconds,
    }
    log("clock offset against the readiness route's Date header")
    reading["clock"] = clock_offset(base)
    clock = reading["clock"]
    log(f"offset {clock['offset_seconds']} s, round trip {clock['round_trip_seconds']} s")
    log("the timeline page with a browser's headers")
    reading["timeline"] = _timeline_read(base, args.attempt)
    timeline = reading["timeline"]
    log(
        f"timeline {timeline['status']}, csp "
        f"{timeline.get('headers', {}).get('content-security-policy')!r}, inline script "
        f"{timeline['inline_script_present']}, beacon {timeline['beacon_present']}"
    )
    log(f"the open page {args.page_samples} times before the subscribers")
    reading["page_before"] = _page_samples(base, args.attempt, args.page_samples)

    held: list[Subscriber] = []
    everyone: list[Subscriber] = []
    try:
        for index in range(args.clients):
            subscriber = Subscriber(index, base, events_path, args.read_timeout)
            subscriber.start()
            held.append(subscriber)
            everyone.append(subscriber)
            time.sleep(args.stagger)
        reading["attached_at"] = now()
        log(f"{args.clients} subscribers opened; waiting for their first frames")
        complete = _wait_for_first_frames(held, args.first_frame_wait)
        reading["all_first_frames_at"] = now() if complete else None
        log("first frames: " + ", ".join(f"#{s.index} {s.status} {s.first_frame_at}" for s in held))
        log(f"the open page {args.page_samples} times under the hold")
        reading["page_during"] = _page_samples(base, args.attempt, args.page_samples)

        _bound_release_replacement(args, base, events_path, held, everyone, reading)
        _hold_to_close(args, held, reading)
    except KeyboardInterrupt:
        reading["hold_ended_at"] = now()
        reading["hold_ended_by"] = "interrupt"
        log("interrupted; closing and writing what was seen")
    finally:
        for subscriber in everyone:
            subscriber.close()
        for subscriber in everyone:
            subscriber.join(5)
    reading["subscribers"] = [s.record() for s in everyone]
    reading["finished_at"] = now()
    return reading


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="https://leave-agent.ardabasarici.dev")
    parser.add_argument("--attempt", help="the open attempt's public id, live-<32 hex digits>")
    parser.add_argument(
        "--start",
        action="store_true",
        help="start the attempt from the index's form and decide it, in place of --attempt",
    )
    parser.add_argument("--scenario", default="scenario_028", help="with --start: the scenario")
    parser.add_argument(
        "--decision",
        choices=("approve", "decline"),
        default="decline",
        help="with --start: the decision posted after the awaiting hold",
    )
    parser.add_argument(
        "--awaiting-hold",
        type=float,
        default=40.0,
        help="with --start: seconds held in the wait after the replacement, before the decision",
    )
    parser.add_argument(
        "--active-wait",
        type=float,
        default=240.0,
        help="with --start: the longest wait for the frame that requests the approval",
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="the JSON reading's path under the capture directory",
    )
    parser.add_argument("--label", default="run", help="which run of the acceptance this is")
    parser.add_argument(
        "--clients",
        type=int,
        default=None,
        help="subscribers held before the one past the bound is tried: the bound itself "
        "(the default with --start), or one under it when a browser holds the timeline "
        "page (the default with --attempt)",
    )
    parser.add_argument(
        "--bound",
        type=int,
        default=8,
        help="the deployed subscription bound, recorded beside the count",
    )
    parser.add_argument("--page-samples", type=int, default=5)
    parser.add_argument(
        "--hold",
        type=float,
        default=60.0,
        help="seconds held at least after the replacement, for the heartbeats",
    )
    parser.add_argument(
        "--max-seconds", type=float, default=1500.0, help="the probe's own deadline"
    )
    parser.add_argument(
        "--read-timeout",
        type=float,
        default=60.0,
        help="a stream read's timeout; the heartbeat cadence is 15 s",
    )
    parser.add_argument("--first-frame-wait", type=float, default=90.0)
    parser.add_argument("--replacement-pause", type=float, default=3.0)
    parser.add_argument("--stagger", type=float, default=0.2)
    args = parser.parse_args(argv[1:])
    if args.start == (args.attempt is not None):
        parser.error("exactly one of --attempt and --start")
    if args.clients is None:
        args.clients = args.bound if args.start else args.bound - 1
    reading = run_started(args) if args.start else run(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(reading, indent=1) + "\n", encoding="utf-8", newline="\n")
    log(f"written {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
