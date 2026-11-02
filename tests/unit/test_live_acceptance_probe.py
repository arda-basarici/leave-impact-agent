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
    assert rule["qualifies"] is True and rule["absences"] == []
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
    assert rule["qualifies"] is False
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
