"""The live path's acceptance instruments (`probes/live-acceptance`) against a local server
that speaks the stream module's own frames: the subscribers probe holds its clients, sees
the bound's refusal and the replacement, times the page, reads the timeline's headers and
ends on the closing frame; the reducer regenerates the figures from the probe's reading
and places the host's samples by the phases the frames carry. The frames are built by the
stream module's builders, so the probe's parser is tested on the producer's bytes and not
on a hand-written copy of them; the samples are the sampler's shape with the fields the
acceptance added, written here by hand and marked so, until the committed capture
replaces them.

The start mode (the final smoke) runs against a second local server whose index, start
answer, holder's page and decision answer are the real application's, taken from the live
routes' rig over the in-memory stores, so the probe's form reading and its cookie are
tested on what the application renders and sets; only the stream is the server's own,
paced so an active phase exists."""

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
from urllib.parse import parse_qs

import pytest

from leaveimpact.adapters.frappe.adapter import AccessServiceToken
from leaveimpact.agent.log_events import EventKind
from leaveimpact.app.main import COOKIE
from leaveimpact.app.narration import Line
from leaveimpact.app.stream import HEARTBEAT, closing_frame, line_frame
from leaveimpact.core.run_record import TerminalStatus
from tests.unit import test_app_decide as deciding
from tests.unit import test_app_live_routes as routes
from tests.unit.publishable_fixture import SCENARIO

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
    assert rule["qualifies"] is True and rule["absences"] == []
    assert rule["counters_moved"] == [] and rule["accepted"] is True
    assert [i["name"] for i in subscribers["held_intervals"]] == ["held", "held again"]
    assert all(i["seconds"] > 0 for i in subscribers["held_intervals"])
    # The fixture's frames are stamped at T0 and the probe ran now, so the held intervals
    # fall in no phase here; the held rate is then insufficient coverage, never a number.
    load = reading["subscriber_load"]["phases"]["run2:active"]
    assert load["sufficient"] is False and load["above_idle"] is None
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
                assert level["containers"][container]["absent_samples"] == 0, (label, phase)
                assert "current_max" in level["containers"][container], (label, phase)
        for container, counters in samples["counters"].items():
            assert counters["oom_kill_last"] == counters["oom_kill_first"] == 0, container
            assert counters["restarts_last"] == counters["restarts_first"], container
    assert reading["worker_rule"]["qualifies"] is True
    assert reading["worker_rule"]["accepted"] is True
    # No probe started a run at the acceptance, so nothing is pooled and no idle window
    # was entered: the active phases stay unmeasured there, as its record says.
    assert reading["idle_window"] is None
    assert reading["pooled_active"]["runs"] == {}
    assert reading["pooled_active"]["sufficient"] is False
    assert reading["pooled_active"]["above_idle"] is None


def _rows(
    offsets: range, cpu_per_sample: dict[range, int], worker: int | None = 240 * 2**20
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cpu = 10_000_000
    for offset in offsets:
        step = next((v for r, v in cpu_per_sample.items() if offset in r), 50_000)
        cpu += step
        rows.append(_sample(T0.timestamp() + offset, 200 * 2**20, worker, cpu))
    return rows


def test_the_held_rate_is_over_the_hold_and_not_diluted_by_the_seconds_before_it() -> None:
    """The external read's first finding: clients ready 80 s into a 100 s investigation
    whose extra load is 0.8 s a second read as 0.16 over the whole span. The held rate
    reads the 0.8, the whole-span rate the dilution, and a hold under the floor is
    insufficient rather than a number."""
    reduce = cast(Any, _module("reduce"))
    base = T0.timestamp()
    # One sample every 5 s, a sample's CPU step being the work since the sample before:
    # idle at 0.01 s/s, the span 0 to 100 at idle until 80, then 0.81 s/s (4.05 s of CPU
    # a sample) for the four steps of the last 20 s while eight clients are held.
    rows = _rows(range(-20, 125, 5), {range(85, 101): 4_050_000, range(0, 85): 50_000})
    windows = [("run:active", base, base + 100.0)]
    held = [(base + 80.0, base + 100.0)]
    reading = reduce.reduce_samples(rows, windows, held)
    active = reading["phases"]["run:active"]["containers"]["leaveimpact-app-1"]
    assert active["cpu_rate"]["mean"] == pytest.approx(0.17, abs=0.01), "the diluted figure"
    assert active["cpu_rate_held"]["mean"] == pytest.approx(0.81, abs=0.01)
    assert reading["phases"]["run:active"]["held_seconds"] == 20.0
    load = reduce.subscriber_load({"runs": reading}, ["run"])["phases"]["run:active"]
    assert load["sufficient"] is True
    assert load["above_idle"] == pytest.approx(0.80, abs=0.01)
    assert load["within_budget"] is False and load["within_forecast"] is False
    short = reduce.reduce_samples(rows, windows, [(base + 90.0, base + 100.0)])
    assert short["phases"]["run:active"]["held_seconds"] == 10.0
    assert reduce.subscriber_load({"runs": short}, ["run"])["phases"]["run:active"] == {
        "samples": "runs",
        "held_seconds": 10.0,
        "sufficient": False,
        "app_rate_held": pytest.approx(0.81, abs=0.01),
        "app_rate_all_pairs": pytest.approx(0.17, abs=0.01),
        "idle_rate": pytest.approx(0.01, abs=0.001),
        "above_idle": None,
        "within_budget": None,
        "within_forecast": None,
    }


def test_a_container_absent_from_one_sample_is_counted_and_disqualifies_the_capture() -> None:
    """The second finding: one missing worker reading among three gave ordinary maxima
    and no mark. The count is kept in the phase, the rule names the absence, and the
    capture does not qualify to set a limit."""
    reduce = cast(Any, _module("reduce"))
    rows = _rows(range(0, 15, 5), {})
    rows[1]["containers"]["leaveimpact-worker-1"] = {"absent": "no such container"}
    reading = reduce.reduce_samples(rows, [], [])
    worker = reading["phases"]["idle"]["containers"]["leaveimpact-worker-1"]
    assert worker["absent_samples"] == 1 and worker["current_max"] == 240 * 2**20
    assert reading["phases"]["idle"]["containers"]["leaveimpact-app-1"]["absent_samples"] == 0
    baseline = json.loads(
        (ROOT / "probes" / "memory-baseline" / "reading.json").read_text(encoding="utf-8")
    )
    rule = reduce.worker_rule({"runs": reading}, baseline, reduce._memory_baseline_rule())
    assert rule["qualifies"] is False and rule["accepted"] is False
    assert rule["absences"] == [
        {
            "samples": "runs",
            "phase": "idle",
            "container": "leaveimpact-worker-1",
            "absent_samples": 1,
        }
    ]
    assert rule["worker_mem_limit"] == "384m", "the figure is still derived, and not qualified"


def test_the_host_fit_sums_the_rule_over_the_combined_peaks_not_the_committed_limits() -> None:
    """The third finding: peaks of 375 MiB app, 188 MiB database and 400 MiB worker summed
    the committed limits to 1,216 MiB and fit; the rule over the combined peaks is
    1,536 MiB and does not, on this fixture's budget."""
    reduce = cast(Any, _module("reduce"))
    rows = _rows(range(0, 15, 5), {}, worker=400 * 2**20)
    for row in rows:
        row["containers"]["leaveimpact-app-1"]["cur"] = 375 * 2**20
        row["containers"]["leaveimpact-postgres-1"]["cur"] = 188 * 2**20
        # The host as the idle capture read it: 558 MiB in use outside the three bounded
        # services, so the budget is 1,282.6 MiB of the 1,840.8.
        row["host"]["avail"] = 1_930_240_000 - 558_200_000 - (375 + 188 + 400) * 2**20
    reading = reduce.reduce_samples(rows, [], [])
    baseline = json.loads(
        (ROOT / "probes" / "memory-baseline" / "reading.json").read_text(encoding="utf-8")
    )
    rule = reduce.worker_rule({"runs": reading}, baseline, reduce._memory_baseline_rule())
    assert rule["app_passes_committed_peak"] and rule["postgres_passes_committed_peak"]
    assert rule["app_mem_limit"] == "576m" and rule["postgres_mem_limit"] == "320m"
    assert rule["worker_mem_limit"] == "640m"
    assert rule["limits_sum_bytes"] == (576 + 320 + 640) * 2**20
    committed = rule["app_committed_limit_bytes"] + rule["postgres_committed_limit_bytes"]
    assert committed + 640 * 2**20 == 1216 * 2**20, "what the first form summed"
    assert rule["budget_bytes"] < rule["limits_sum_bytes"] and rule["fits"] is False
    assert rule["qualifies"] is True and rule["accepted"] is False, "derived, and not fitting"


# --- the final smoke's reductions (M3 step 17) --------------------------------------------


def test_a_pair_spanning_the_release_gap_is_not_a_held_pair() -> None:
    """The design pass's external read, first finding: held 0 to 10 and 15 to 20 with a
    sample every 5 s and 0.25 s a second while held. Each sample's membership tested apart
    counted the pair across the gap, 20 s at 0.1875; a held pair lies in one interval,
    15 s at 0.25."""
    reduce = cast(Any, _module("reduce"))
    base = T0.timestamp()
    rows = _rows(
        range(0, 25, 5), {range(5, 11): 1_250_000, range(11, 16): 0, range(16, 21): 1_250_000}
    )
    reading = reduce.reduce_samples(
        rows,
        [("run:awaiting", base, base + 20.0)],
        [(base, base + 10.0), (base + 15.0, base + 20.0)],
    )
    phase = reading["phases"]["run:awaiting"]
    assert phase["held_seconds"] == 15.0
    held = phase["containers"]["leaveimpact-app-1"]["cpu_rate_held"]
    assert held["mean"] == 0.25 and held["usage_usec"] == 3_750_000
    assert held["wall_seconds"] == 15.0
    assert phase["held_samples"] == 5, "every sample lies in some interval; the pair does not"


def _two_started_runs(second_hold_from: float = 102.0) -> tuple[Any, dict[str, Any]]:
    """Two active phases of 20 s a hundred seconds apart, a sample every 2 s, the app at
    0.2 s a second inside them and 0.01 outside; each held from 2 s in, 18 s of pairs."""
    reduce = cast(Any, _module("reduce"))
    base = T0.timestamp()
    rows = _rows(
        range(-60, 180, 2),
        {range(1, 21): 400_000, range(101, 121): 400_000, range(-60, 180): 20_000},
    )
    windows = [("runA:active", base, base + 20.0), ("runB:active", base + 100.0, base + 120.0)]
    held = [(base + 2.0, base + 20.0), (base + second_hold_from, base + 120.0)]
    return reduce, reduce.reduce_samples(rows, windows, held)


def test_the_pooled_active_rate_is_the_duration_weighted_rate_of_the_started_runs() -> None:
    """Fork 13 as amended: neither run reaches the 20 s floor alone (18 s of pairs each),
    the pool of both does (36 s), and its rate is the summed usage over the summed wall
    time less the idle rate; the verdict is over the pool, each run's own figure beside it."""
    reduce, reading = _two_started_runs()
    alone = reduce.subscriber_load({"runs": reading}, ["runA", "runB"])["phases"]
    assert alone["runA:active"]["held_seconds"] == 18.0
    assert alone["runA:active"]["sufficient"] is False, "one run stays under the floor"
    pool = reduce.pooled_active({"runs": reading}, ["runA", "runB"])
    assert pool["runs"] == {
        "runA": {"held_seconds": 18.0, "app_rate_held": 0.2, "reaches_run_floor": True},
        "runB": {"held_seconds": 18.0, "app_rate_held": 0.2, "reaches_run_floor": True},
    }
    assert pool["held_seconds"] == 36.0 and pool["app_rate_held"] == 0.2
    assert pool["idle_rate"] == 0.01 and pool["sufficient"] is True
    assert pool["above_idle"] == 0.19
    assert pool["within_budget"] is True and pool["within_forecast"] is False


def test_a_pool_of_one_run_or_with_a_run_under_its_floor_is_unmeasured() -> None:
    """The pooling contract: one run cannot carry the verdict, and an insufficient pool is
    unmeasured, never a number. A lone run is refused whatever its coverage; a second run
    held for 8 s leaves the pool at 26 s, over the pool's floor, and still unmeasured."""
    reduce, reading = _two_started_runs()
    lone = reduce.pooled_active({"runs": reading}, ["runA"])
    assert lone["held_seconds"] == 18.0 and lone["sufficient"] is False
    assert lone["above_idle"] is None and lone["within_budget"] is None
    reduce, short = _two_started_runs(second_hold_from=112.0)
    pool = reduce.pooled_active({"runs": short}, ["runA", "runB"])
    assert pool["runs"]["runB"] == {
        "held_seconds": 8.0,
        "app_rate_held": 0.2,
        "reaches_run_floor": False,
    }
    assert pool["held_seconds"] == 26.0 and pool["sufficient"] is False
    assert pool["above_idle"] is None and pool["within_budget"] is None
    nobody = reduce.pooled_active({"runs": short}, [])
    assert nobody["runs"] == {} and nobody["app_rate_held"] is None


def test_an_entered_idle_window_is_the_baseline_and_the_rest_is_between() -> None:
    """The external read's second point: unmatched time was all idle, so a run without
    boundaries, or the minutes after a close, sat in the baseline. With an entered window
    the baseline is that window alone; the samples outside it and outside every run are
    `between`, kept for the memory floor and out of the CPU baseline."""
    reduce = cast(Any, _module("reduce"))
    base = T0.timestamp()
    # Idle at 0.01 until the run; after its close the app works at 0.1 for a minute (a
    # second run nobody entered boundaries for), which the unmatched reading takes as idle.
    rows = _rows(
        range(-60, 100, 2), {range(1, 21): 400_000, range(31, 91): 200_000, range(-60, 100): 20_000}
    )
    windows = [("runA:active", base, base + 20.0)]
    unmatched = reduce.reduce_samples(rows, windows, [])
    diluted = unmatched["phases"]["idle"]["containers"]["leaveimpact-app-1"]["cpu_rate"]["mean"]
    # 58 s before the run at 0.01, then 76 s after it holding thirty steps at 0.1 and eight
    # at 0.01: 0.58 + 6.0 + 0.16 = 6.74 s of CPU over 134 s.
    assert diluted == 0.0503 and "between" not in unmatched["phases"]
    entered = reduce.reduce_samples(rows, windows, [], (base - 60.0, base - 10.0))
    assert set(entered["phases"]) == {"idle", "runA:active", "between"}
    idle = entered["phases"]["idle"]["containers"]["leaveimpact-app-1"]["cpu_rate"]
    assert idle["mean"] == 0.01 and idle["wall_seconds"] == 50.0
    between = entered["phases"]["between"]["containers"]["leaveimpact-app-1"]["cpu_rate"]
    assert between["mean"] > 0.05, "the unentered run is outside the baseline"


def test_an_idle_window_that_overlaps_a_run_is_refused_by_name(tmp_path: Path) -> None:
    reduce = cast(Any, _module("reduce"))
    base = T0.timestamp()
    window = {
        "from": T0.isoformat(),
        "to": (T0 + timedelta(seconds=300)).isoformat(),
        "source": "a test",
    }
    (tmp_path / "idle-window.json").write_text(json.dumps(window), encoding="utf-8")
    sources: dict[str, str] = {}
    clear = reduce._idle_window(tmp_path, [("runA:active", base + 400.0, base + 420.0)], sources)
    assert clear == {"from": base, "to": base + 300.0, "seconds": 300.0, "source": "a test"}
    assert list(sources) == ["idle-window.json"], "the window is a source, digested"
    with pytest.raises(ValueError, match="the idle window overlaps the phase runA:active"):
        reduce._idle_window(tmp_path, [("runA:active", base + 290.0, base + 310.0)], {})
    assert reduce._idle_window(tmp_path / "absent", [], {}) is None


def test_a_moved_kill_or_restart_counter_refuses_the_capture() -> None:
    """Criterion (f) as the external read made it explicit: a limit derived from a capture
    in which a container was restarted is not accepted, though every sample is present and
    the limits fit."""
    reduce = cast(Any, _module("reduce"))
    rows = _rows(range(0, 15, 5), {})
    rows[-1]["containers"]["leaveimpact-worker-1"]["restarts"] = 1
    reading = reduce.reduce_samples(rows, [], [])
    baseline = json.loads(
        (ROOT / "probes" / "memory-baseline" / "reading.json").read_text(encoding="utf-8")
    )
    rule = reduce.worker_rule({"runs": reading}, baseline, reduce._memory_baseline_rule())
    assert rule["qualifies"] is True and rule["fits"] is True
    assert rule["counters_moved"] == [
        {
            "samples": "runs",
            "container": "leaveimpact-worker-1",
            "counter": "restarts",
            "first": 0,
            "last": 1,
        }
    ]
    assert rule["accepted"] is False


# --- the start mode against the application's own pages -----------------------------------


LIVE_ATTEMPT = deciding.PUBLIC_ID
ACTIVE_SECONDS = 0.6
"""How long the local stream takes from the start to its approval request, so the probe
has an active phase to hold through."""


class _Live:
    """The started flow's local server state: the real application's pages and answers,
    captured once from the live routes' rig over the in-memory stores (the index's form
    with the key it minted, the start's redirect and cookie, the holder's page with its
    decision form, the decision's redirect, and the flag-off index and refusal), beside
    what the probe posted and the streams open against the bound."""

    def __init__(self, *, flag_on: bool = True) -> None:
        self.flag_on = flag_on
        self.lock = threading.Lock()
        self.open = 0
        self.refused = 0
        self.started_at: float | None = None
        self.decided = threading.Event()
        self.decision: str | None = None
        self.posted_key: str | None = None
        self.holder_reads = 0
        fresh = routes.Rig()
        with fresh.client() as web:
            self.index = web.get("/").text
            self.key = str(fresh.minter.minted[0])
            start = web.post(
                "/start", data={"key": self.key, "scenario_id": SCENARIO}, follow_redirects=False
            )
        assert start.status_code == 303 and start.headers["location"] == f"/replays/{LIVE_ATTEMPT}"
        self.start_headers = (start.headers["location"], start.headers["set-cookie"])
        waiting, path = routes.awaiting_rig()
        with waiting.client({COOKIE: deciding.KEY}) as web:
            self.holder = web.get(path).text
            decided = web.post(
                f"{path}/decision",
                data={"decision": "decline", "payload_digest": deciding.DIGEST},
                follow_redirects=False,
            )
        assert decided.status_code == 303
        self.decision_location = decided.headers["location"]
        off = routes.Rig(configuration=routes.OFF)
        with off.client() as web:
            self.off_index = web.get("/").text
            refusal = web.post("/start", data=routes.form(1), follow_redirects=False)
        assert refusal.status_code == 403
        self.off_refusal = refusal.text


def _live_handler(live: _Live) -> type[http.server.BaseHTTPRequestHandler]:
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 (the base's name)
            pass

        def _answer(
            self, status: int, body: bytes, headers: tuple[tuple[str, str], ...] = ()
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def _form(self) -> dict[str, str]:
            length = int(self.headers.get("Content-Length", "0"))
            fields = parse_qs(self.rfile.read(length).decode("ascii"))
            return {name: values[0] for name, values in fields.items()}

        def _holds_the_key(self) -> bool:
            return self.headers.get("Cookie") == f"{COOKIE}={live.key}"

        def do_GET(self) -> None:  # noqa: N802 (the handler's contract)
            if self.path == "/ready":
                self._answer(200, b'{"ready": true}')
            elif self.path == "/":
                self._answer(200, (live.index if live.flag_on else live.off_index).encode())
            elif self.path == f"/replays/{LIVE_ATTEMPT}":
                if self._holds_the_key():
                    live.holder_reads += 1
                    self._answer(200, live.holder.encode())
                else:
                    self._answer(200, b"<html><body>the open page</body></html>")
            elif self.path == f"/replays/{LIVE_ATTEMPT}/timeline":
                self._answer(200, b"<html><script>var s = new EventSource('/x');</script></html>")
            elif self.path.startswith(f"/replays/{LIVE_ATTEMPT}/events"):
                self._stream()
            else:
                self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802 (the handler's contract)
            form = self._form()
            if self.path == "/start":
                live.posted_key = form.get("key")
                if not live.flag_on:
                    self._answer(403, live.off_refusal.encode())
                elif form != {"key": live.key, "scenario_id": SCENARIO}:
                    self._answer(400, b"the form is not the index's")
                else:
                    live.started_at = time.monotonic()
                    location, cookie = live.start_headers
                    self._answer(303, b"", (("Location", location), ("Set-Cookie", cookie)))
            elif self.path == f"/replays/{LIVE_ATTEMPT}/decision":
                expected = {"approve", "decline"}
                if not self._holds_the_key():
                    self._answer(403, b"the capability")
                elif (
                    form.get("payload_digest") != deciding.DIGEST
                    or form.get("decision") not in expected
                ):
                    self._answer(400, b"the form")
                else:
                    live.decision = form["decision"]
                    live.decided.set()
                    self._answer(303, b"", (("Location", live.decision_location),))
            else:
                self.send_error(404)

        def _stream(self) -> None:
            with live.lock:
                if live.open >= BOUND:
                    live.refused += 1
                    self._answer(503, b"unavailable")
                    return
                live.open += 1
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                self._chunk(line_frame(_line(1, EventKind.ADMITTED, 0.0)))
                self._chunk(line_frame(_line(2, EventKind.SEGMENT_STARTED, 1.0)))
                assert live.started_at is not None
                requested = live.started_at + ACTIVE_SECONDS
                if not self._wait(lambda: time.monotonic() >= requested):
                    return
                self._chunk(line_frame(_line(3, EventKind.APPROVAL_REQUESTED, 21.0)))
                self._chunk(HEARTBEAT)
                if not self._wait(live.decided.is_set):
                    return
                if live.decision == "approve":
                    self._chunk(line_frame(_line(4, EventKind.APPROVED, 70.0)))
                    closing = closing_frame(
                        _line(5, EventKind.COMPLETED, 75.0), TerminalStatus.COMPLETED
                    )
                else:
                    closing = closing_frame(
                        _line(4, EventKind.DECLINED, 70.0), TerminalStatus.DECLINED
                    )
                self._chunk(closing)
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except OSError:
                pass
            finally:
                with live.lock:
                    live.open -= 1

        def _wait(self, done: Any) -> bool:
            """Wait for ``done``, watching the socket for the peer's close as the
            application's disconnect listener does; false when the client went away."""
            deadline = time.monotonic() + 20
            while not done() and time.monotonic() < deadline:
                readable, _, _ = select.select([self.connection], [], [], 0.05)
                if readable and self.connection.recv(1, socket.MSG_PEEK) == b"":
                    return False
            return True

        def _chunk(self, body: bytes) -> None:
            self.wfile.write(f"{len(body):x}\r\n".encode() + body + b"\r\n")
            self.wfile.flush()

    return Handler


def _serve_live(live: _Live) -> tuple[_QuietServer, str]:
    httpd = _QuietServer(("127.0.0.1", 0), _live_handler(live))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def _run_started(base: str, out: Path, *extra: str) -> tuple[dict[str, Any], str]:
    probe = _module("subscribers")
    argv = [
        "subscribers.py",
        "--base",
        base,
        "--start",
        "--scenario",
        SCENARIO,
        "--out",
        str(out),
        "--label",
        "runA",
        "--bound",
        str(BOUND),
        "--page-samples",
        "2",
        "--hold",
        "0.3",
        "--awaiting-hold",
        "0.5",
        "--read-timeout",
        "10",
        "--first-frame-wait",
        "10",
        "--replacement-pause",
        "0.3",
        *extra,
    ]
    assert cast(Any, probe).main(argv) == 0
    text = out.read_text(encoding="utf-8")
    return cast(dict[str, Any], json.loads(text)), text


@pytest.mark.parametrize(
    ("decision", "kinds", "status"),
    [
        ("decline", ["admitted", "segment_started", "approval_requested", "declined"], "declined"),
        (
            "approve",
            ["admitted", "segment_started", "approval_requested", "approved", "completed"],
            "completed",
        ),
    ],
)
def test_the_start_mode_starts_holds_through_the_active_phase_and_decides(
    tmp_path: Path, decision: str, kinds: list[str], status: str
) -> None:
    """Forks 13 and 15 of the final smoke: the probe posts the form the application's index
    renders, holds every stream from the start through the active phase with the bound's
    checks moved to the wait, reads the review's digest off the holder's page with the
    cookie the start set, posts the decision and ends on the closing frames. The written
    reading carries no key, no cookie and no page."""
    live = _Live()
    httpd, base = _serve_live(live)
    try:
        reading, text = _run_started(
            base, tmp_path / "subscribers-runA.json", "--decision", decision, "--max-seconds", "30"
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert reading["mode"] == "started" and reading["attempt"] == LIVE_ATTEMPT
    assert reading["index"]["form_present"] is True and reading["index"]["scenarios_offered"] >= 1
    start = reading["start"]
    assert start["status"] == 303 and start["location_path"] == f"/replays/{LIVE_ATTEMPT}"
    assert start["cookies_set"] == 1 and start["live_runs_off_text"] is False
    assert live.posted_key == live.key, "the key the page minted, not one of the probe's"
    assert reading["clients"] == BOUND, "no browser holds a stream, so the bound itself"
    assert 0 < reading["reach_seconds"] < ACTIVE_SECONDS, "held inside the active phase"
    assert reading["all_first_frames_at"] < reading["approval_seen_at"]
    assert reading["approval_seen_at"] < reading["released"]["ended_at"], (
        "the release falls in the wait, never in the active phase"
    )
    assert reading["beyond_bound"]["status"] == 503 and reading["replacement"]["status"] == 200
    assert reading["page_before"] == [] and len(reading["page_during"]) == 2
    assert reading["decision"] == {
        "asked": decision,
        "page_status": 200,
        "page_seconds": reading["decision"]["page_seconds"],
        "form_present": True,
        "posted": True,
        "sent_at": reading["decision"]["sent_at"],
        "status": 303,
        "seconds": reading["decision"]["seconds"],
        "location_host": None,
        "location_path": f"/replays/{LIVE_ATTEMPT}",
        "review_digest": deciding.DIGEST,
        "error": None,
    }
    assert live.decision == decision and live.holder_reads == 1
    assert reading["hold_ended_by"] == "closing frames"
    for subscriber in reading["subscribers"]:
        if subscriber["status"] != 200 or subscriber["index"] == reading["released"]["index"]:
            continue
        assert [f["kind"] for f in subscriber["frames"]] == kinds, subscriber["index"]
        assert subscriber["frames"][-1]["status"] == status
    assert live.key not in text and COOKIE not in text, "the capability is never written"
    assert "payload_digest" not in text and "<form" not in text, "nor a page's markup"

    reduced = cast(Any, _module("reduce")).reduce_subscribers(reading)
    assert reduced["mode"] == "started"
    assert reduced["started"] == {
        "scenario": SCENARIO,
        "start_status": 303,
        "start_seconds": start["seconds"],
        "reach_seconds": reading["reach_seconds"],
        "decision": decision,
        "decision_posted": True,
        "decision_status": 303,
        "decision_seconds": reading["decision"]["seconds"],
    }
    assert [i["name"] for i in reduced["held_intervals"]] == ["held", "held again"]
    assert reduced["phases"]["closed"]["status"] == status
    assert reduced["page_during_over_before"] is None, "nothing precedes the attach"


def test_the_start_mode_under_the_flag_off_records_the_applications_refusal(
    tmp_path: Path,
) -> None:
    """Fork 16's second check: the index renders no form, so the probe posts one start
    with a key of its own and the reading is the application's answer, 403 with its
    wording, and no stream; the key it posted is not in the file."""
    live = _Live(flag_on=False)
    httpd, base = _serve_live(live)
    try:
        reading, text = _run_started(base, tmp_path / "start-refusal.json", "--max-seconds", "10")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert reading["attempt"] is None and "subscribers" not in reading
    assert reading["index"]["form_present"] is False and reading["index"]["status"] == 200
    start = reading["start"]
    assert start["posted"] is True and start["status"] == 403
    assert start["live_runs_off_text"] is True and start["cookies_set"] == 0
    assert start["location_path"] is None
    assert live.posted_key is not None and len(live.posted_key) == 32
    assert live.posted_key != live.key and live.posted_key not in text
    assert live.open == 0 and live.started_at is None


def test_a_started_run_that_never_requests_approval_is_held_to_its_end_undecided(
    tmp_path: Path,
) -> None:
    """A run that fails before its approval request (the smoke's stop condition): no
    bound check, no release and no decision; the streams are held to the probe's deadline
    and the reducer reads one held interval from the first frames to the hold's end."""
    live = _Live()
    httpd, base = _serve_live(live)
    try:
        reading, _ = _run_started(
            base, tmp_path / "subscribers-runA.json", "--active-wait", "0.2", "--max-seconds", "2"
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert reading["attempt"] == LIVE_ATTEMPT and reading["approval_seen_at"] is None
    assert reading["decision"] is None and reading["released"] is None
    assert reading["timeline"] is None and reading["hold_ended_by"] == "deadline"
    assert live.decision is None and live.holder_reads == 0
    reduced = cast(Any, _module("reduce")).reduce_subscribers(reading)
    assert [i["name"] for i in reduced["held_intervals"]] == ["held"]
    assert reduced["held_intervals"][0]["seconds"] > 1.0
    assert reduced["timeline"]["status"] is None and reduced["started"]["decision"] is None


# --- the worker's Access check and the sender's splices -----------------------------------


CLIENT_ID = "0123456789abcdef.access"
CLIENT_SECRET = "a-secret-the-check-must-never-print"
REDIRECT = "https://team.example.invalid/cdn-cgi/access/login/hr?kid=abc&meta=SIGNED-BLOB"


def _edge_handler() -> type[http.server.BaseHTTPRequestHandler]:
    """A login page behind an edge that reads the service token: the page with the pair,
    a redirect to the organization's login without it, its query carrying a blob."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 (the base's name)
            pass

        def do_GET(self) -> None:  # noqa: N802 (the handler's contract)
            token = AccessServiceToken(CLIENT_ID, CLIENT_SECRET)
            given = {name: self.headers.get(name) for name in token.headers}
            if self.path == "/login" and given == token.headers:
                body = b"<html>the login page</html>"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(302)
                self.send_header("Location", REDIRECT)
                self.send_header("Content-Length", "0")
                self.end_headers()

    return Handler


def test_the_access_check_prints_statuses_and_hosts_and_never_a_value_or_a_query() -> None:
    """Fork 16's first check as the external read re-cut it: nonempty is said for each
    name, and the edge is asked with the pair and without it; the lines carry the status
    and the redirect's host, and neither half of the pair nor the redirect's query. The
    headers are the adapter's own, so the check sends what the worker's transport sends."""
    check = cast(Any, _module("access_check"))
    assert tuple(AccessServiceToken("a", "b").headers) == check.HEADERS
    httpd = _QuietServer(("127.0.0.1", 0), _edge_handler())
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    host = f"127.0.0.1:{httpd.server_address[1]}"
    id_name, secret_name = check.NAMES
    try:
        held = check.lines(
            {id_name: CLIENT_ID, secret_name: CLIENT_SECRET, check.BASE: f"http://{host}/"}
        )
        # Compose's empty defaults: the names are there and hold nothing, and the edge
        # answers two empty headers as it answers none.
        empty = check.lines({id_name: "", secret_name: "", check.BASE: f"http://{host}"})
        stale = check.lines(
            {id_name: CLIENT_ID, secret_name: "rolled", check.BASE: f"http://{host}"}
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
    refused = "status 302, location host team.example.invalid"
    assert held == [
        f"access {id_name} nonempty",
        f"access {secret_name} nonempty",
        f"frappe base host {host}",
        "access login with the pair: status 200, location host -",
        f"access login without it: {refused}",
    ]
    assert empty == [
        f"access {id_name} empty",
        f"access {secret_name} empty",
        f"frappe base host {host}",
        f"access login with the pair: {refused}",
        f"access login without it: {refused}",
    ]
    assert stale[:2] == held[:2], "nonempty says nothing of a stale value"
    assert stale[3] == f"access login with the pair: {refused}", "the edge says it"
    printed = "\n".join(held + empty + stale)
    assert CLIENT_ID not in printed and CLIENT_SECRET not in printed and "rolled" not in printed
    assert "SIGNED-BLOB" not in printed and "kid=" not in printed
    assert check.lines({}) == [
        f"access {id_name} empty",
        f"access {secret_name} empty",
        "frappe base host unset",
    ]


def test_the_check_reads_the_names_compose_hands_the_worker_and_the_sender_splices_all() -> None:
    """Two mirrors held structurally: the three names the check reads are ones
    `compose.yaml` passes into the worker, and every placeholder the host script carries
    is one the sender replaces, so no action reaches the host with a token unspliced."""
    check = cast(Any, _module("access_check"))
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    for name in (*check.NAMES, check.BASE):
        assert f"      {name}: ${{{name}:-}}" in compose, name
    host = (PROBE / "host.sh").read_text(encoding="utf-8")
    sender = (PROBE / "send.ps1").read_text(encoding="utf-8")
    placeholders = sorted({part.split('"')[0] for part in host.split('"<')[1:]})
    assert placeholders == [
        "action>",
        "base64 of access_check.py>",
        "base64 of sampler.py>",
        "cadence>",
        "offset>",
        "work>",
    ]
    for placeholder in placeholders:
        assert f'.Replace("<{placeholder}"' in sender, placeholder


# --- the fold memo's capture (M3 step 17) -------------------------------------------------


FOLD_MEMO_CAPTURE = ROOT / "probes" / "captures" / "live-acceptance" / "2026-11-02"
WORKER = BOUNDED[2]
FOLD_MEMO_CRITERION = 0.05
"""The worker's idle CPU rate, in seconds a second, under the three acceptance attempts
inside the lookback, fixed before the capture at the step's entry: the fold memo is
accepted at or under it."""


def test_the_fold_memo_reading_regenerates_from_its_committed_capture() -> None:
    """The second capture of the sampler, idle under the three acceptance attempts after
    the fold memo's deploy, reduced to its own reading beside the acceptance's."""
    reduce = _module("reduce")
    reading = json.loads((PROBE / "reading-fold-memo.json").read_text(encoding="utf-8"))
    assert reading["capture"] == FOLD_MEMO_CAPTURE.name
    for name, value in reading["sources"].items():
        assert cast(Any, reduce).digest(FOLD_MEMO_CAPTURE / name) == value, name
    assert cast(Any, reduce).reduce_capture(FOLD_MEMO_CAPTURE) == reading


def worker_rate_by_minute(rows: list[dict[str, Any]]) -> list[float]:
    """The worker's CPU rate over each minute of the capture from its first sample, the
    cgroup's microseconds over the samples' wall time."""
    start = rows[0]["ts"]
    buckets: dict[int, list[float]] = {}
    for before, after in zip(rows, rows[1:], strict=False):
        minute = int((before["ts"] - start) // 60)
        cpu = (after["containers"][WORKER]["cpu"] - before["containers"][WORKER]["cpu"]) / 1e6
        bucket = buckets.setdefault(minute, [0.0, 0.0])
        bucket[0] += cpu
        bucket[1] += after["ts"] - before["ts"]
    return [round(cpu / wall, 4) for _, (cpu, wall) in sorted(buckets.items())]


def test_the_fold_memo_meets_the_criterion_whole_and_minute_by_minute() -> None:
    """The finding the memo answers: 0.172 s a second at three attempts before it, the
    plateau read by the minute. After it, the whole capture reads 0.019 and no minute above
    0.021, under the 0.05 criterion with the fill pass before the capture's start (the
    worker restarted on the deploy a minute before the sampler); the residue above the
    empty-table tick of 0.010 is the two fresh reads per attempt per pass."""
    reading = json.loads((PROBE / "reading-fold-memo.json").read_text(encoding="utf-8"))
    idle = reading["samples"]["idle"]["phases"]["idle"]
    worker = idle["containers"][WORKER]
    assert worker["cpu_rate"]["seconds"] >= 600
    assert worker["cpu_rate"]["mean"] == 0.0193
    assert worker["cpu_rate"]["mean"] <= FOLD_MEMO_CRITERION
    samples = (FOLD_MEMO_CAPTURE / "idle-samples.jsonl").read_text(encoding="utf-8")
    rows = [json.loads(line) for line in samples.splitlines() if line.strip()]
    minutes = worker_rate_by_minute(rows)
    assert len(minutes) == 16
    assert min(minutes) == 0.0187 and max(minutes) == 0.0207
    assert all(rate <= FOLD_MEMO_CRITERION for rate in minutes)


# --- the final smoke's capture (M3 step 17) -----------------------------------------------


SMOKE_CAPTURE = ROOT / "probes" / "captures" / "live-acceptance" / "2026-11-09"


def _smoke_reading() -> dict[str, Any]:
    text = (PROBE / "reading-final-smoke.json").read_text(encoding="utf-8")
    return cast(dict[str, Any], json.loads(text))


def test_the_final_smoke_reading_regenerates_from_its_committed_capture() -> None:
    """The third capture of the sampler: two runs the probe started and decided, one from
    a phone with its boundaries entered, the idle window entered, reduced to its own
    reading beside the acceptance's."""
    reduce = _module("reduce")
    reading = _smoke_reading()
    assert reading["capture"] == SMOKE_CAPTURE.name
    assert sorted(reading["sources"]) == [
        "idle-window.json",
        "phases-runC.json",
        "runs-samples.jsonl",
        "subscribers-runA.json",
        "subscribers-runB.json",
    ]
    for name, value in reading["sources"].items():
        assert cast(Any, reduce).digest(SMOKE_CAPTURE / name) == value, name
    assert cast(Any, reduce).reduce_capture(SMOKE_CAPTURE) == reading


def test_the_final_smoke_pools_the_active_phases_inside_the_budget_and_the_forecast() -> None:
    """The measurement the acceptance could not take: eight streams held from the first
    second of two started runs. The criterion was fixed before the capture (the pooled
    rate above idle at most 0.2, each run bringing 10 s and the pool 20 s); the pool reads
    0.1312 over 47.4 s against the entered idle window, under the 0.14 forecast too."""
    reading = _smoke_reading()
    assert reading["idle_window"]["seconds"] == 375.0
    assert reading["pooled_active"] == {
        "runs": {
            "runA": {"held_seconds": 23.7, "app_rate_held": 0.1823, "reaches_run_floor": True},
            "runB": {"held_seconds": 23.7, "app_rate_held": 0.1621, "reaches_run_floor": True},
        },
        "run_floor_seconds": 10.0,
        "coverage_floor_seconds": 20.0,
        "held_seconds": 47.4,
        "app_rate_held": 0.1722,
        "idle_rate": 0.041,
        "idle_seconds": 372.4,
        "sufficient": True,
        "above_idle": 0.1312,
        "within_budget": True,
        "within_forecast": True,
    }
    phases = reading["samples"]["runs"]["phases"]
    assert set(phases) == {
        "idle",
        "between",
        "runA:active",
        "runA:awaiting",
        "runB:active",
        "runB:awaiting",
        "runB:resumed",
        "runC:active",
        "runC:awaiting",
        "runC:resumed",
    }, "run C sits in its own phases, never in the baseline"
    spans = {w["name"]: round(w["to"] - w["from"], 2) for w in reading["windows"]}
    assert spans["runA:active"] == 26.8 and spans["runB:active"] == 26.29
    assert spans["runC:active"] == 32.53


def test_the_final_smoke_streams_and_decisions_as_the_probe_recorded_them() -> None:
    """What each started run recorded at the client, and what its streams showed. The
    intervals between frames kept the recorded ones (no clock offset in that measure) and
    nothing bunched. The delivery against the recorded instant in the active phase reads
    a p95 of 2.0001 and 2.094 s under a clock bound of 1.5 and 1.3 s: the criterion the
    design pass wrote on that measure (p95 under 2 s) is not met as written, which the
    record says and this test holds, so the figure cannot be restated later."""
    subscribers = _smoke_reading()["subscribers"]
    run_a, run_b = subscribers["runA"], subscribers["runB"]
    assert run_a["started"] == {
        "scenario": "scenario_028",
        "start_status": 303,
        "start_seconds": 0.4122,
        "reach_seconds": 1.1151,
        "decision": "decline",
        "decision_posted": True,
        "decision_status": 303,
        "decision_seconds": 0.8601,
    }
    assert run_b["started"]["reach_seconds"] == 1.1152
    assert run_b["started"]["decision"] == "approve"
    assert run_b["started"]["decision_seconds"] == 0.73
    for run in (run_a, run_b):
        assert run["ended"] == {"closed": 8, "closed by the probe": 1, "refused": 1}
        assert run["beyond_bound"]["status"] == 503 and run["replacement"]["status"] == 200
        assert run["bunched_pairs"] == 0 and run["errors"] == []
        assert run["heartbeat_gap_seconds"]["min"] > 15.0
        assert run["heartbeat_gap_seconds"]["max"] < 16.0
        assert run["timeline"]["content_security_policy"] is None
    assert run_a["interval_lag_seconds"]["p95"] == 0.5541
    assert run_b["interval_lag_seconds"]["p95"] == 0.6039
    assert run_a["active_delivery_seconds"]["p95"] == 2.0001
    assert run_b["active_delivery_seconds"]["p95"] == 2.094
    assert run_a["delivery_bound_seconds"] == 1.521 and run_b["delivery_bound_seconds"] == 1.288
    assert run_a["phases"]["closed"]["status"] == "declined"
    assert run_b["phases"]["closed"]["status"] == "completed"


def test_the_final_smoke_keeps_the_worker_limit_and_the_verdict_accepts_the_capture() -> None:
    """Criterion (f): no absence, no kill or restart counted, the three derived limits
    fitting the budget this capture's own baseline leaves. The worker's largest current,
    292.4 MiB in run C's active phase, keeps 448m by 6.3 MiB of the rule's step."""
    rule = _smoke_reading()["worker_rule"]
    assert rule["worker_peak_current_bytes"] == 306_569_216
    assert rule["worker_mem_limit"] == "448m"
    assert rule["app_mem_limit"] == "384m" and rule["postgres_mem_limit"] == "192m"
    assert rule["absences"] == [] and rule["counters_moved"] == []
    assert rule["limits_sum_bytes"] == 1024 * 2**20
    assert rule["budget_bytes"] == 1_318_666_240 and rule["spare_bytes"] == 244_924_416
    assert rule["fits"] is True and rule["accepted"] is True
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "    mem_limit: 448m" in compose, "the limit the capture derives is the one deployed"
