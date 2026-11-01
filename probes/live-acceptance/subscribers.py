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
"""

from __future__ import annotations

import argparse
import contextlib
import email.utils
import http.client
import json
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

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


def timed_get(base: str, path: str, accept: str, timeout: float = 30.0) -> dict[str, Any]:
    """One GET timed on the monotonic clock: status, seconds to the whole body, the body's
    length and the headers kept; an error recorded as the record, never raised."""
    started = now()
    connection = _connection(base, timeout)
    try:
        connection.request(
            "GET",
            path,
            headers={"Accept": accept, "User-Agent": USER_AGENT, "Host": urlsplit(base).netloc},
        )
        response = connection.getresponse()
        body = response.read()
        return {
            "path": path,
            "status": response.status,
            "seconds": round(now() - started, 4),
            "bytes": len(body),
            "headers": _kept(response.headers),
            "body": body.decode("utf-8", errors="replace"),
        }
    except OSError as error:
        return {
            "path": path,
            "status": None,
            "seconds": round(now() - started, 4),
            "error": repr(error),
        }
    finally:
        connection.close()


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
    parser.add_argument(
        "--attempt", required=True, help="the open attempt's public id, live-<32 hex digits>"
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
        default=7,
        help="subscribers held before the one past the bound is tried: the bound itself, "
        "or one under it when a browser holds the timeline page",
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
    reading = run(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(reading, indent=1) + "\n", encoding="utf-8", newline="\n")
    log(f"written {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
