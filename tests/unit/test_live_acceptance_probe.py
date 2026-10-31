"""The live path's acceptance instruments (`probes/live-acceptance`) against a local server
that speaks the stream module's own frames: the subscribers probe holds its clients, sees
the bound's refusal and the replacement, times the page, reads the timeline's headers and
ends on the closing frame; the reducer regenerates the figures from the probe's reading
and places the host's samples by the phases the frames carry. The frames are built by the
stream module's builders, so the probe's parser is tested on the producer's bytes and not
on a hand-written copy of them; the samples are the sampler's shape with the fields the
acceptance added, written here by hand and marked so, until the committed capture
replaces them."""

from __future__ import annotations

import http.server
import importlib.util
import json
import select
import socket
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from leaveimpact.agent.log_events import EventKind
from leaveimpact.app.narration import Line
from leaveimpact.app.stream import HEARTBEAT, closing_frame, line_frame
from leaveimpact.core.run_record import TerminalStatus

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "probes" / "live-acceptance"
ATTEMPT = "live-" + "ab" * 16
BOUND = 3
T0 = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)


def _module(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"live_acceptance_{name}", PROBE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _line(position: int, kind: EventKind, seconds: float) -> Line:
    return Line(position, T0 + timedelta(seconds=seconds), kind, f"line {position}")


class _Stack:
    """What the local server holds between requests: the streams open against the bound,
    the decision the test posts, and the body every stream writes."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.open = 0
        self.decided = threading.Event()
        self.refused = 0


def _handler(stack: _Stack) -> type[http.server.BaseHTTPRequestHandler]:
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 (the base's name)
            pass

        def _page(self, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 (the handler's contract)
            if self.path == "/ready":
                self._page(b'{"ready": true}', "application/json")
            elif self.path == f"/replays/{ATTEMPT}":
                time.sleep(0.01)
                self._page(b"<html><body>the open page</body></html>")
            elif self.path == f"/replays/{ATTEMPT}/timeline":
                self._page(
                    b"<html><body><ol id=timeline></ol>"
                    b"<script>var s = new EventSource('/x');</script>"
                    b'<script type="module" '
                    b'src="https://static.cloudflareinsights.com/beacon.min.js/x"></script>'
                    b"</body></html>"
                )
            elif self.path.startswith(f"/replays/{ATTEMPT}/events"):
                self._stream()
            else:
                self.send_error(404)

        def _stream(self) -> None:
            with stack.lock:
                if stack.open >= BOUND:
                    stack.refused += 1
                    body = b"unavailable"
                    self.send_response(503)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                stack.open += 1
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                # The dump: the log so far in one tick, then live frames at their own pace.
                for position, kind, seconds in (
                    (1, EventKind.ADMITTED, 0.0),
                    (2, EventKind.SEGMENT_STARTED, 1.0),
                    (3, EventKind.APPROVAL_REQUESTED, 30.0),
                ):
                    self._chunk(line_frame(_line(position, kind, seconds)))
                self._chunk(HEARTBEAT)
                time.sleep(0.3)
                self._chunk(HEARTBEAT)
                # The application releases a slot when the client disconnects, through the
                # response's disconnect listener; this server models that by watching the
                # socket for the peer's close while it waits for the decision.
                deadline = time.monotonic() + 20
                while not stack.decided.is_set() and time.monotonic() < deadline:
                    readable, _, _ = select.select([self.connection], [], [], 0.05)
                    if readable and self.connection.recv(1, socket.MSG_PEEK) == b"":
                        return
                self._chunk(
                    closing_frame(_line(4, EventKind.DECLINED, 45.0), TerminalStatus.DECLINED)
                )
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except OSError:
                pass
            finally:
                with stack.lock:
                    stack.open -= 1

        def _chunk(self, body: bytes) -> None:
            self.wfile.write(f"{len(body):x}\r\n".encode() + body + b"\r\n")
            self.wfile.flush()

    return Handler


class _QuietServer(http.server.ThreadingHTTPServer):
    """A handler whose client went away raises on its next write; that is the probe
    closing a stream on purpose, not a finding, so it is not printed."""

    def handle_error(self, request: Any, client_address: Any) -> None:
        pass


@pytest.fixture
def server() -> Any:
    stack = _Stack()
    httpd = _QuietServer(("127.0.0.1", 0), _handler(stack))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield stack, f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _run_probe(base: str, out: Path, stack: _Stack) -> dict[str, Any]:
    probe = _module("subscribers")
    argv = [
        "subscribers.py",
        "--base",
        base,
        "--attempt",
        ATTEMPT,
        "--out",
        str(out),
        "--label",
        "run2",
        "--clients",
        str(BOUND),
        "--bound",
        str(BOUND),
        "--page-samples",
        "3",
        "--hold",
        "0.5",
        "--max-seconds",
        "20",
        "--read-timeout",
        "10",
        "--first-frame-wait",
        "10",
        "--replacement-pause",
        "0.3",
        "--stagger",
        "0.05",
    ]

    def decide_once_held() -> None:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if stack.refused >= 1 and stack.open == BOUND:
                break
            time.sleep(0.05)
        time.sleep(0.8)  # past the hold's floor, so the hold ends on the closing frames
        stack.decided.set()

    threading.Thread(target=decide_once_held, daemon=True).start()
    assert cast(Any, probe).main(argv) == 0
    return cast(dict[str, Any], json.loads(out.read_text(encoding="utf-8")))


def test_the_probe_holds_the_clients_sees_the_bound_and_ends_on_the_closing_frame(
    server: tuple[_Stack, str], tmp_path: Path
) -> None:
    stack, base = server
    reading = _run_probe(base, tmp_path / "subscribers-run2.json", stack)
    held = [s for s in reading["subscribers"] if s["status"] == 200]
    assert reading["beyond_bound"]["status"] == 503, "the bound answers the unavailable page"
    assert (
        reading["replacement"]["status"] == 200
        and reading["replacement"]["first_frame_at"] is not None
    )
    assert reading["released"]["ended"] == "closed by the probe"
    assert reading["hold_ended_by"] == "closing frames"
    # BOUND held, one released, one replacement: BOUND + 1 streams were admitted in all.
    assert len(held) == BOUND + 1
    for subscriber in held:
        if subscriber["index"] == reading["released"]["index"]:
            continue
        assert subscriber["ended"] == "closed", subscriber
        kinds = [f["kind"] for f in subscriber["frames"]]
        assert kinds == ["admitted", "segment_started", "approval_requested", "declined"]
        assert subscriber["frames"][-1]["event"] == "closed"
        assert subscriber["frames"][-1]["status"] == "declined"
        assert len(subscriber["heartbeats"]) == 2
        assert subscriber["headers"]["content-type"].startswith("text/event-stream")
    assert reading["timeline"]["inline_script_present"] is True
    assert reading["timeline"]["beacon_present"] is True
    assert "content-security-policy" not in reading["timeline"]["headers"]
    assert reading["clock"]["offset_seconds"] is not None
    assert len(reading["page_before"]) == 3 and len(reading["page_during"]) == 3


def _sample(ts: float, app: int, worker: int | None, cpu_app: int) -> dict[str, Any]:
    """One sampler line as the sampler writes it with the acceptance's fields; a worker of
    None is the container absent. Hand-written: the committed capture replaces this."""

    def container(cur: int, cpu: int) -> dict[str, Any]:
        return {
            "cur": cur,
            "peak": cur,
            "thr": 12,
            "cpu": cpu,
            "oom": 0,
            "restarts": 0,
            "anon": cur - 1000,
            "file": 1000,
            "shm": 0,
            "kern": 0,
            "slab": 0,
        }

    containers: dict[str, Any] = {
        "leaveimpact-app-1": container(app, cpu_app),
        "leaveimpact-postgres-1": container(90 * 2**20, 1_000_000),
        "proxy-caddy-1": container(30 * 2**20, 500_000),
        "leaveimpact-worker-1": {"absent": "no such container"}
        if worker is None
        else container(worker, 2_000_000),
    }
    return {
        "label": "acceptance",
        "t": datetime.fromtimestamp(ts, UTC).strftime("%H:%M:%S"),
        "ts": ts,
        "host": {
            "total": 1_930_240_000,
            "avail": 1_200_000_000,
            "free": 0,
            "buffers": 0,
            "cached": 0,
            "shm": 0,
            "swap": 0,
        },
        "containers": containers,
    }


def test_the_reducer_places_the_samples_by_the_frames_phases_and_applies_the_rule(
    server: tuple[_Stack, str], tmp_path: Path
) -> None:
    stack, base = server
    capture = tmp_path / "2026-11-01"
    capture.mkdir()
    _run_probe(base, capture / "subscribers-run2.json", stack)
    reduce = _module("reduce")
    # Samples at 5 s across the frames' recorded instants: before the admission (idle),
    # during the active span (admitted at 0 to approval requested at 30), the wait (30 to
    # 45), and after the close; the app's CPU counter advances 1.2 s a sample under the hold.
    base_ts = T0.timestamp()
    rows: list[dict[str, Any]] = []
    cpu = 10_000_000
    for offset in range(-10, 60, 5):
        active = 0 <= offset <= 30
        cpu += 1_200_000 if active else 50_000
        worker = 240 * 2**20 if 0 <= offset <= 45 else 113 * 2**20
        rows.append(_sample(base_ts + offset, (200 + (20 if active else 0)) * 2**20, worker, cpu))
    (capture / "runs-samples.jsonl").write_text(
        "\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n", encoding="utf-8"
    )
    reading = cast(Any, reduce).reduce_capture(capture)
    cast(Any, reduce).print_derivation(reading)

    subscribers = reading["subscribers"]["run2"]
    assert subscribers["held"] == BOUND + 1, "the bound, the released one and its replacement"
    assert subscribers["beyond_bound"]["status"] == 503
    # Two heartbeats a stream for the BOUND that lived to the closing frame; the released
    # one saw one or two, depending on when the probe shut it.
    assert 2 * BOUND + 1 <= subscribers["heartbeat_gap_seconds"]["count"] <= 2 * BOUND + 2
    assert subscribers["phases"]["admitted"]["recorded_at"] == T0.isoformat()
    assert subscribers["phases"]["closed"]["status"] == "declined"
    assert subscribers["timeline"]["content_security_policy"] is None
    assert subscribers["page_during_over_before"] is not None
    assert [w["name"] for w in reading["windows"]] == ["run2:active", "run2:awaiting"]

    samples = reading["samples"]["runs"]
    assert set(samples["phases"]) == {"idle", "run2:active", "run2:awaiting"}
    active = samples["phases"]["run2:active"]
    assert active["containers"]["leaveimpact-app-1"]["current_max"] == 220 * 2**20
    assert active["containers"]["leaveimpact-app-1"]["cpu_rate"]["mean"] == pytest.approx(
        0.24, abs=0.01
    )
    assert samples["phases"]["idle"]["containers"]["leaveimpact-app-1"]["cpu_rate"]["mean"] < 0.02
    assert samples["phases"]["idle"]["host_used_outside_bounded_max"] == (
        1_930_240_000 - 1_200_000_000 - 200 * 2**20 - 90 * 2**20 - 113 * 2**20
    )
    rule = reading["worker_rule"]
    assert rule["worker_peak_current_bytes"] == 240 * 2**20
    assert rule["worker_mem_limit"] == "384m", "1.5 × 240 MiB = 360, rounded up to 64 MiB"
    assert rule["app_passes_committed_peak"] is False
    assert rule["fits"] is True
    assert samples["counters"]["leaveimpact-worker-1"]["oom_kill_last"] == 0


CAPTURE = ROOT / "probes" / "captures" / "live-acceptance" / "2026-11-01"
BOUNDED = ("leaveimpact-app-1", "leaveimpact-postgres-1", "leaveimpact-worker-1")


def test_the_committed_reading_regenerates_from_the_committed_capture() -> None:
    """The reducer's first real input: the sampler's lines fetched from the instance,
    reduced to the committed reading exactly, each source held by its digest over decoded
    lines, every container present in every sample and no kill or restart counted."""
    reduce = _module("reduce")
    reading = json.loads((PROBE / "reading.json").read_text(encoding="utf-8"))
    assert reading["capture"] == CAPTURE.name
    for name, value in reading["sources"].items():
        assert cast(Any, reduce).digest(CAPTURE / name) == value, name
    assert cast(Any, reduce).reduce_capture(CAPTURE) == reading
    for label, samples in reading["samples"].items():
        for phase, level in samples["phases"].items():
            for container in BOUNDED:
                assert "absent" not in level["containers"][container], (label, phase, container)
        for container, counters in samples["counters"].items():
            assert counters["oom_kill_last"] == counters["oom_kill_first"] == 0, container
            assert counters["restarts_last"] == counters["restarts_first"], container
