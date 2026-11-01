"""The live path's acceptance reduction (the demo milestone's step 16): the subscriber
readings and the host's samples under a capture directory reduced to `reading.json` with
every cited figure printed, so the step's record and the worker's Compose limit are numbers
with a script behind them. Run from the repository root::

    uv run python probes/live-acceptance/reduce.py probes/captures/live-acceptance/<date>

Over each `subscribers-*.json` (the workstation probe's reading): the subscribers held and
how each ended; the delay from connection to first frame; the gap before every heartbeat
against the heartbeat's fifteen-second cadence; the intervals between consecutive line frames'
recorded instants against the intervals between their arrivals, both after the first tick's
dump, so a lag or a bunching is delivery and not the backlog; the delivery of each frame
against its recorded instant under the clock offset the probe bounded; the status past the
bound, the release and the replacement; the open page's latency before and during the
hold; the timeline's content-security header, inline script and beacon; and the attempt's
phase boundaries read off the frames' kinds (admitted, approval requested, the decision,
the closing frame), which place the host's samples; an attempt no probe followed gets its
boundaries from a `phases-<label>.json` the operator enters from the attempt's timeline,
read through the hostname after the close, the file naming its source. Over each `*-samples.jsonl` (the
sampler's lines, one every few seconds across a whole run): per container and per phase the
largest `memory.current`, the CPU rate as the delta of the cgroup's `usage_usec` over the
phase's wall time, the kill and restart counters' movement, and at idle the host's memory in
use outside the three bounded services, the baseline the worker's budget line reads. The
worker's limit is the memory baseline's rule applied to its largest sampled current
(`limit_of`, imported from that reducer so one rule has one body); the app's and the
database's limits in the host fit are the same rule over the larger of the committed peak
and the peak here, since a new level that passes a peak moves that limit, and the fit
reads the moved one. The eight-subscriber figure is the app's rate over the sample pairs
that fall inside the subscriber hold (every client at its first frame to the release, the
replacement's first frame to the hold's end, the release gap excluded), phase by phase,
less the idle phase's rate, and it is quoted only over a floor of held coverage; a rate
over the whole active span would dilute the hold with the seconds before the clients
were ready (the group's external read, first finding). A container absent from a sample
is counted in every phase it is absent from, never averaged away, and a capture with any
absence does not qualify to set a limit (its second finding).

The capture's digests are over decoded lines, as the memory baseline's are, so a Windows
checkout and a Linux one agree. Nothing here reads the log or the instance: the reducer is
a pure function of the files, rerun by the unit test that holds the committed reading.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROBES = Path(__file__).resolve().parent.parent
BOUNDED = ("leaveimpact-app-1", "leaveimpact-postgres-1", "leaveimpact-worker-1")
APP, POSTGRES, WORKER = BOUNDED
CADENCE_SECONDS = 15.0
DUMP_SECONDS = 1.0
"""Frames arriving within this of a subscriber's first frame are the first tick's dump of
the log so far; the interval comparisons start after it."""
BUNCH_ARRIVAL_SECONDS = 0.05
BUNCH_RECORDED_SECONDS = 2.0
PHASE_KINDS = ("admitted", "approval_requested", "approved", "declined", "abandoned")
HOLD_COVERAGE_SECONDS = 20.0
"""The least wall time of held sample pairs inside a phase for its held CPU rate to be
quoted; under it the rate is reported as insufficient coverage."""
CPU_BUDGET = 0.2
CPU_FORECAST = 0.14
"""The stream module's forecast for eight subscriptions on one open attempt and the
step's budget, in seconds of the interpreter's second above idle."""


def _memory_baseline_rule() -> Any:
    spec = importlib.util.spec_from_file_location(
        "memory_baseline_reduce", PROBES / "memory-baseline" / "reduce.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_text(source: Path) -> str:
    """The file's lines joined by newline, whatever mark and line ending the checkout gave it."""
    return "\n".join(source.read_text(encoding="utf-8-sig").splitlines()) + "\n"


def digest(source: Path) -> str:
    return hashlib.sha256(canonical_text(source).encode("utf-8")).hexdigest()


def _quantiles(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(values)
    p95 = ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]
    return {
        "count": len(values),
        "min": round(ordered[0], 4),
        "median": round(statistics.median(ordered), 4),
        "p95": round(p95, 4),
        "max": round(ordered[-1], 4),
    }


def _epoch(recorded_at: str) -> float:
    return datetime.fromisoformat(recorded_at).timestamp()


# --- The subscribers ----------------------------------------------------------------------


def _held(reading: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        s for s in reading["subscribers"] if s["status"] == 200 and s["first_frame_at"] is not None
    ]


def _heartbeat_gaps(subscriber: dict[str, Any]) -> list[float]:
    arrivals = sorted(
        [(f["arrival"], "frame") for f in subscriber["frames"]]
        + [(h, "heartbeat") for h in subscriber["heartbeats"]]
    )
    gaps = []
    for previous, current in zip(arrivals, arrivals[1:], strict=False):
        if current[1] == "heartbeat":
            gaps.append(current[0] - previous[0])
    return gaps


def _after_dump(subscriber: dict[str, Any]) -> list[dict[str, Any]]:
    first = subscriber["first_frame_at"]
    return [
        f
        for f in subscriber["frames"]
        if f.get("recorded_at") and f["arrival"] - first >= DUMP_SECONDS
    ]


def _interval_lags(subscriber: dict[str, Any]) -> tuple[list[float], int]:
    frames = _after_dump(subscriber)
    lags, bunched = [], 0
    for previous, current in zip(frames, frames[1:], strict=False):
        recorded = _epoch(current["recorded_at"]) - _epoch(previous["recorded_at"])
        arrived = current["arrival"] - previous["arrival"]
        lags.append(arrived - recorded)
        if arrived < BUNCH_ARRIVAL_SECONDS and recorded > BUNCH_RECORDED_SECONDS:
            bunched += 1
    return lags, bunched


def _deliveries(reading: dict[str, Any], subscriber: dict[str, Any]) -> list[float]:
    offset = reading["clock"]["offset_seconds"]
    if offset is None:
        return []
    started = reading["started_epoch"]
    return [
        (started + f["arrival"]) - _epoch(f["recorded_at"]) - offset
        for f in _after_dump(subscriber)
    ]


def _phases(reading: dict[str, Any]) -> dict[str, Any]:
    """The attempt's boundaries as the most complete subscriber saw them: the recorded
    instant of each phase kind and of the closing frame, as ISO text and epoch."""
    held = _held(reading)
    if not held:
        return {}
    fullest = max(held, key=lambda s: len(s["frames"]))
    boundaries: dict[str, Any] = {}
    for frame in fullest["frames"]:
        kind, recorded = frame.get("kind"), frame.get("recorded_at")
        if kind in PHASE_KINDS and recorded and kind not in boundaries:
            boundaries[kind] = {
                "recorded_at": recorded,
                "epoch": round(_epoch(recorded), 3),
                "position": frame["position"],
            }
        if frame.get("event") == "closed" and recorded:
            boundaries["closed"] = {
                "recorded_at": recorded,
                "epoch": round(_epoch(recorded), 3),
                "position": frame["position"],
                "status": frame.get("status"),
            }
    return boundaries


def _held_intervals(reading: dict[str, Any]) -> list[dict[str, Any]]:
    """When the full set of subscribers was held, on the host's clock: from every
    subscriber's first frame to the release, and from the replacement's first frame to the
    hold's end; the release gap between them is not held. Instants are moved from the
    probe's clock by the bounded offset, zero when the Date header gave none."""
    started = reading["started_epoch"]
    offset = reading["clock"]["offset_seconds"] or 0.0
    ready = reading.get("all_first_frames_at")
    released = (reading.get("released") or {}).get("ended_at")
    replaced = (reading.get("replacement") or {}).get("first_frame_at")
    ended = reading.get("hold_ended_at")
    intervals = []
    for name, start, end in (("held", ready, released), ("held again", replaced, ended)):
        if start is not None and end is not None and end > start:
            intervals.append(
                {
                    "name": name,
                    "from": round(started + start + offset, 3),
                    "to": round(started + end + offset, 3),
                    "seconds": round(end - start, 3),
                }
            )
    return intervals


def _page(samples: list[dict[str, Any]]) -> dict[str, Any]:
    seconds = [s["seconds"] for s in samples if s.get("status") == 200]
    return {
        "statuses": sorted({str(s.get("status")) for s in samples}),
        "seconds": _quantiles(seconds),
    }


def reduce_subscribers(reading: dict[str, Any]) -> dict[str, Any]:
    held = _held(reading)
    first_frame = [s["first_frame_at"] - s["connected_at"] for s in held]
    gaps = [g for s in held for g in _heartbeat_gaps(s)]
    lags, bunched = [], 0
    for s in held:
        subscriber_lags, subscriber_bunched = _interval_lags(s)
        lags.extend(subscriber_lags)
        bunched += subscriber_bunched
    deliveries = [d for s in held for d in _deliveries(reading, s)]
    clock = reading["clock"]
    page_before, page_during = _page(reading["page_before"]), _page(reading["page_during"])
    ratio = None
    if page_before["seconds"] and page_during["seconds"]:
        ratio = round(page_during["seconds"]["median"] / page_before["seconds"]["median"], 2)
    events_headers = held[0]["headers"] if held else {}
    timeline = reading["timeline"]
    return {
        "label": reading["label"],
        "attempt": reading["attempt"],
        "started_utc": reading["started_utc"],
        "bound": reading["bound"],
        "clients_asked": reading["clients"],
        "held": len(held),
        "subscribers": len(reading["subscribers"]),
        "ended": {
            reason: sum(1 for s in reading["subscribers"] if s["ended"] == reason)
            for reason in sorted({str(s["ended"]) for s in reading["subscribers"]})
        },
        "errors": [s["error"] for s in reading["subscribers"] if s["error"]],
        "first_frame_seconds": _quantiles(first_frame),
        "line_frames_after_dump": sum(len(_after_dump(s)) for s in held),
        "heartbeat_gap_seconds": _quantiles(gaps),
        "heartbeat_cadence_seconds": CADENCE_SECONDS,
        "interval_lag_seconds": _quantiles(lags),
        "bunched_pairs": bunched,
        "delivery_seconds": _quantiles(deliveries),
        "delivery_bound_seconds": round(
            clock["resolution_seconds"] + clock["round_trip_seconds"], 3
        ),
        "clock_offset_seconds": clock["offset_seconds"],
        "beyond_bound": reading["beyond_bound"],
        "released": reading["released"],
        "replacement": reading["replacement"],
        "page_before": page_before,
        "page_during": page_during,
        "page_during_over_before": ratio,
        "events_headers": events_headers,
        "timeline": {
            "status": timeline["status"],
            "content_security_policy": timeline.get("headers", {}).get("content-security-policy"),
            "report_only": timeline.get("headers", {}).get("content-security-policy-report-only"),
            "inline_script_present": timeline["inline_script_present"],
            "beacon_present": timeline["beacon_present"],
        },
        "hold_ended_by": reading.get("hold_ended_by"),
        "phases": _phases(reading),
        "held_intervals": _held_intervals(reading),
    }


# --- The samples --------------------------------------------------------------------------


def _windows(phases_by_label: dict[str, dict[str, Any]]) -> list[tuple[str, float, float]]:
    """(name, from, to) in epoch seconds: each run's active span (admitted to approval
    requested), its wait (to the decision), and its resumption (an approval to the close)."""
    windows = []
    for label, phases in phases_by_label.items():
        admitted = phases.get("admitted", {}).get("epoch")
        requested = phases.get("approval_requested", {}).get("epoch")
        decided = next(
            (phases[k]["epoch"] for k in ("approved", "declined", "abandoned") if k in phases), None
        )
        closed = phases.get("closed", {}).get("epoch")
        if admitted is not None and requested is not None:
            windows.append((f"{label}:active", admitted, requested))
        if requested is not None and decided is not None:
            windows.append((f"{label}:awaiting", requested, decided))
        if "approved" in phases and closed is not None:
            windows.append((f"{label}:resumed", phases["approved"]["epoch"], closed))
    return windows


def _label_of(ts: float, windows: list[tuple[str, float, float]]) -> str:
    for name, start, end in windows:
        if start <= ts <= end:
            return name
    return "idle"


def _rate(pairs: list[tuple[dict[str, Any], dict[str, Any]]], name: str) -> dict[str, Any] | None:
    """The container's CPU rate over the phase: the cgroup's `usage_usec` summed over the
    consecutive sample pairs that both lie in the phase, over their wall time; a phase a
    run interrupts (idle before and after it) is two stretches and never the span between
    them. The largest single step is kept beside the mean."""
    steps = []
    for previous, current in pairs:
        before = previous["containers"].get(name, {"absent": 1})
        after = current["containers"].get(name, {"absent": 1})
        if "absent" in before or "absent" in after:
            continue
        if before.get("cpu") is None or after.get("cpu") is None:
            continue
        seconds = current["ts"] - previous["ts"]
        if seconds > 0:
            steps.append(((after["cpu"] - before["cpu"]) / 1e6, seconds))
    if not steps:
        return None
    used, wall = sum(u for u, _ in steps), sum(w for _, w in steps)
    return {
        "mean": round(used / wall, 4),
        "step_max": round(max(u / w for u, w in steps), 4),
        "seconds": round(wall, 1),
    }


def _present(samples: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [
        s["containers"][name]
        for s in samples
        if "absent" not in s["containers"].get(name, {"absent": 1})
    ]


def _inside(ts: float, intervals: list[tuple[float, float]]) -> bool:
    return any(start <= ts <= end for start, end in intervals)


def reduce_samples(
    samples: list[dict[str, Any]],
    windows: list[tuple[str, float, float]],
    held: list[tuple[float, float]] = (),
) -> dict[str, Any]:
    """The samples by phase: per container the extremes over the phase's samples, the
    count of samples the container was absent from (zero on a complete capture, never
    dropped), the CPU rate over the phase's consecutive pairs, and the same rate over the
    pairs whose both samples fall inside a held interval, with that coverage in seconds;
    the idle baseline outside the bounded services; the counters' first and last values."""
    samples = sorted(samples, key=lambda s: s["ts"])
    held = list(held)
    names = sorted({name for s in samples for name in s["containers"]})
    labels = [_label_of(s["ts"], windows) for s in samples]
    flags = [_inside(s["ts"], held) for s in samples]
    by_phase: dict[str, list[dict[str, Any]]] = {}
    pairs: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    held_pairs: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for index, (sample, label) in enumerate(zip(samples, labels, strict=True)):
        by_phase.setdefault(label, []).append(sample)
        if index > 0 and labels[index - 1] == label:
            pair = (samples[index - 1], sample)
            pairs.setdefault(label, []).append(pair)
            if flags[index - 1] and flags[index]:
                held_pairs.setdefault(label, []).append(pair)
    phases: dict[str, Any] = {}
    for phase, rows in by_phase.items():
        containers: dict[str, Any] = {}
        for name in names:
            present = _present(rows, name)
            reading: dict[str, Any] = {"absent_samples": len(rows) - len(present)}
            if present:
                reading.update(
                    {
                        "current_max": max(c["cur"] for c in present),
                        "anon_max": max(c["anon"] for c in present),
                        "threads_max": max(c["thr"] for c in present),
                        "cpu_rate": _rate(pairs.get(phase, []), name),
                        "cpu_rate_held": _rate(held_pairs.get(phase, []), name),
                    }
                )
            containers[name] = reading
        held_seconds = sum(c["ts"] - p["ts"] for p, c in held_pairs.get(phase, []))
        phases[phase] = {
            "samples": len(rows),
            "from": rows[0]["t"],
            "to": rows[-1]["t"],
            "held_samples": sum(1 for s, f in zip(samples, flags, strict=True) if f and s in rows),
            "held_seconds": round(held_seconds, 1),
            "host_available_min": min(s["host"]["avail"] for s in rows),
            "host_used_outside_bounded_max": max(
                s["host"]["total"]
                - s["host"]["avail"]
                - sum(
                    s["containers"][n]["cur"]
                    for n in BOUNDED
                    if "absent" not in s["containers"].get(n, {"absent": 1})
                )
                for s in rows
            ),
            "containers": containers,
        }
    counters = {}
    for name in names:
        present = _present(samples, name)
        if present:
            counters[name] = {
                "oom_kill_first": present[0].get("oom"),
                "oom_kill_last": present[-1].get("oom"),
                "restarts_first": present[0].get("restarts"),
                "restarts_last": present[-1].get("restarts"),
            }
    return {
        "samples": len(samples),
        "from": samples[0]["t"],
        "to": samples[-1]["t"],
        "span_seconds": round(samples[-1]["ts"] - samples[0]["ts"], 1),
        "host_total": samples[0]["host"]["total"],
        "phases": phases,
        "counters": counters,
    }


def subscriber_load(sample_readings: dict[str, Any], labels: list[str]) -> dict[str, Any]:
    """The eight-subscriber check: for each run's active and awaiting phase, the app's CPU
    rate over the held pairs less the idle phase's rate over all its pairs, quoted only
    when the held coverage reaches the floor, against the forecast and the budget."""
    out: dict[str, Any] = {
        "forecast_above_idle": CPU_FORECAST,
        "budget_above_idle": CPU_BUDGET,
        "coverage_floor_seconds": HOLD_COVERAGE_SECONDS,
        "phases": {},
    }
    for source, reading in sample_readings.items():
        idle = reading["phases"].get("idle", {}).get("containers", {}).get(APP, {})
        idle_rate = (idle.get("cpu_rate") or {}).get("mean")
        for label in labels:
            for phase in ("active", "awaiting"):
                name = f"{label}:{phase}"
                level = reading["phases"].get(name)
                if level is None:
                    continue
                app = level["containers"].get(APP, {})
                held = app.get("cpu_rate_held")
                entry: dict[str, Any] = {
                    "samples": source,
                    "held_seconds": level["held_seconds"],
                    "sufficient": level["held_seconds"] >= HOLD_COVERAGE_SECONDS,
                    "app_rate_held": None if held is None else held["mean"],
                    "app_rate_all_pairs": (app.get("cpu_rate") or {}).get("mean"),
                    "idle_rate": idle_rate,
                }
                if entry["sufficient"] and held is not None and idle_rate is not None:
                    above = round(held["mean"] - idle_rate, 4)
                    entry["above_idle"] = above
                    entry["within_budget"] = above <= CPU_BUDGET
                    entry["within_forecast"] = above <= CPU_FORECAST
                else:
                    entry["above_idle"] = None
                    entry["within_budget"] = None
                    entry["within_forecast"] = None
                out["phases"][name] = entry
    return out


def _absences(sample_readings: dict[str, Any]) -> list[dict[str, Any]]:
    """Every sample a bounded container was absent from, by reading and phase."""
    return [
        {
            "samples": source,
            "phase": phase,
            "container": name,
            "absent_samples": c["absent_samples"],
        }
        for source, reading in sample_readings.items()
        for phase, level in reading["phases"].items()
        for name in BOUNDED
        for c in [level["containers"].get(name, {"absent_samples": level["samples"]})]
        if c["absent_samples"] > 0
    ]


def worker_rule(
    sample_readings: dict[str, Any], baseline_reading: dict[str, Any], rule: Any
) -> dict[str, Any]:
    """The worker's limit by the memory baseline's rule over every sampled phase; the
    app's and the database's limits by the same rule over the larger of the committed peak
    and the peak here, so a peak that moves a limit moves the fit; the host fit over those
    three; and whether the capture qualifies to set a limit, which it does only when no
    bounded container was absent from any sample."""

    def largest(name: str) -> int | None:
        values = [
            phase["containers"][name]["current_max"]
            for reading in sample_readings.values()
            for phase in reading["phases"].values()
            if "current_max" in phase["containers"].get(name, {})
        ]
        return max(values) if values else None

    worker_peak = largest(WORKER)
    committed = baseline_reading["rule"]
    idle_baselines = [
        reading["phases"]["idle"]["host_used_outside_bounded_max"]
        for reading in sample_readings.values()
        if "idle" in reading["phases"]
    ]
    host_total = next((r["host_total"] for r in sample_readings.values()), None)
    absences = _absences(sample_readings)
    result: dict[str, Any] = {
        "worker_peak_current_bytes": worker_peak,
        "worker_limit_bytes": None if worker_peak is None else rule.limit_of(worker_peak),
        "worker_mem_limit": None
        if worker_peak is None
        else rule.mem_limit_of(rule.limit_of(worker_peak)),
        "idle_baseline_outside_bounded_bytes": max(idle_baselines) if idle_baselines else None,
        "host_total_bytes": host_total,
        "absences": absences,
        "qualifies": worker_peak is not None and not absences,
    }
    for key, name in (("app", APP), ("postgres", POSTGRES)):
        here = largest(name)
        committed_peak = committed[key]["peak_current_bytes"]
        combined = max(committed_peak, here or 0)
        result[f"{key}_peak_here_bytes"] = here
        result[f"{key}_committed_peak_bytes"] = committed_peak
        result[f"{key}_passes_committed_peak"] = (here or 0) > committed_peak
        result[f"{key}_committed_limit_bytes"] = committed[key]["limit_bytes"]
        result[f"{key}_limit_bytes"] = rule.limit_of(combined)
        result[f"{key}_mem_limit"] = rule.mem_limit_of(rule.limit_of(combined))
    if worker_peak is not None and idle_baselines and host_total is not None:
        limits = (
            result["app_limit_bytes"] + result["postgres_limit_bytes"] + rule.limit_of(worker_peak)
        )
        budget = host_total - max(idle_baselines)
        result["limits_sum_bytes"] = limits
        result["budget_bytes"] = budget
        result["fits"] = limits <= budget
        result["spare_bytes"] = budget - limits
    return result


# --- The capture --------------------------------------------------------------------------


def reduce_capture(capture: Path) -> dict[str, Any]:
    rule = _memory_baseline_rule()
    baseline = json.loads((PROBES / "memory-baseline" / "reading.json").read_text(encoding="utf-8"))
    sources: dict[str, str] = {}
    subscribers: dict[str, Any] = {}
    for path in sorted(capture.glob("subscribers-*.json")):
        sources[path.name] = digest(path)
        reading = json.loads(canonical_text(path))
        subscribers[reading["label"]] = reduce_subscribers(reading)
    phases_by_label = {label: r["phases"] for label, r in subscribers.items()}
    entered: dict[str, Any] = {}
    for path in sorted(capture.glob("phases-*.json")):
        sources[path.name] = digest(path)
        record = json.loads(canonical_text(path))
        entered[record["label"]] = {
            kind: {"recorded_at": record[kind], "epoch": round(_epoch(record[kind]), 3)}
            for kind in (*PHASE_KINDS, "closed")
            if kind in record
        }
        phases_by_label.setdefault(record["label"], entered[record["label"]])
    windows = _windows(phases_by_label)
    held = [
        (interval["from"], interval["to"])
        for r in subscribers.values()
        for interval in r["held_intervals"]
    ]
    samples: dict[str, Any] = {}
    for path in sorted(capture.glob("*-samples.jsonl")):
        sources[path.name] = digest(path)
        rows = [json.loads(line) for line in canonical_text(path).splitlines() if line.strip()]
        samples[path.name[: -len("-samples.jsonl")]] = reduce_samples(rows, windows, held)
    return {
        "capture": capture.name,
        "sources": sources,
        "subscribers": subscribers,
        "entered_phases": entered,
        "windows": [{"name": n, "from": f, "to": t} for n, f, t in windows],
        "held": [{"from": f, "to": t} for f, t in held],
        "samples": samples,
        "subscriber_load": subscriber_load(samples, list(subscribers)) if samples else None,
        "worker_rule": worker_rule(samples, baseline, rule) if samples else None,
    }


def mib(value: float | None) -> str:
    return "absent" if value is None else f"{value / (1024 * 1024):.1f} MiB"


def _q(q: dict[str, Any] | None) -> str:
    if not q:
        return "none"
    return f"n={q['count']} min {q['min']} med {q['median']} p95 {q['p95']} max {q['max']}"


def _cur(containers: dict[str, Any], name: str) -> str:
    reading = containers.get(name, {})
    if "current_max" not in reading:
        return "absent"
    absent = reading["absent_samples"]
    return mib(reading["current_max"]) + (f" (-{absent})" if absent else "")


def _cpu(containers: dict[str, Any], name: str, key: str = "cpu_rate") -> str:
    rate = containers.get(name, {}).get(key)
    return "-" if not rate else f"{rate['mean']:.3f}"


def print_derivation(reading: dict[str, Any]) -> None:
    print(f"capture {reading['capture']}")
    for name, value in reading["sources"].items():
        print(f"  {name}  sha256 {value[:16]}…")
    for label, s in reading["subscribers"].items():
        print(f"\n== subscribers {label} on {s['attempt']} at {s['started_utc']}")
        print(
            f"bound {s['bound']}, asked {s['clients_asked']}, held {s['held']} of "
            f"{s['subscribers']} opened; ended {s['ended']}; errors {s['errors']}"
        )
        print(f"first frame after connect (s): {_q(s['first_frame_seconds'])}")
        print(
            f"heartbeat gaps (s), cadence {s['heartbeat_cadence_seconds']}: "
            f"{_q(s['heartbeat_gap_seconds'])}"
        )
        print(
            f"line frames after the dump {s['line_frames_after_dump']}; interval lag "
            f"arrival−recorded (s): {_q(s['interval_lag_seconds'])}; bunched pairs "
            f"{s['bunched_pairs']}"
        )
        print(
            f"delivery arrival−recorded−offset (s): {_q(s['delivery_seconds'])}, offset "
            f"{s['clock_offset_seconds']}, bound ±{s['delivery_bound_seconds']}"
        )
        print(f"past the bound: {s['beyond_bound']}; released: {s['released']}")
        print(f"replacement: {s['replacement']}")
        print(f"page before: {s['page_before']}")
        print(f"page during: {s['page_during']}; during/before {s['page_during_over_before']}")
        print(f"events headers: {s['events_headers']}")
        print(f"timeline: {s['timeline']}")
        phases = ", ".join(f"{k} {v['recorded_at']}" for k, v in s["phases"].items())
        print(f"hold ended by {s['hold_ended_by']}; phases: {phases}")
        print(f"held intervals on the host clock: {s['held_intervals']}")
    for label, r in reading["samples"].items():
        print(
            f"\n== samples {label}: {r['samples']} over {r['span_seconds']} s "
            f"({r['from']} to {r['to']}), host {mib(r['host_total'])}"
        )
        print(
            f"{'phase':<22}{'n':>4}{'held s':>8}{'app cur':>14}{'app cpu/s':>11}{'held':>8}"
            f"{'worker cur':>14}{'worker cpu/s':>13}{'pg cur':>11}{'outside':>12}"
        )
        for phase, p in r["phases"].items():
            c = p["containers"]
            print(
                f"{phase:<22}{p['samples']:>4}{p['held_seconds']:>8}{_cur(c, APP):>14}"
                f"{_cpu(c, APP):>11}{_cpu(c, APP, 'cpu_rate_held'):>8}{_cur(c, WORKER):>14}"
                f"{_cpu(c, WORKER):>13}{_cur(c, POSTGRES):>11}"
                f"{mib(p['host_used_outside_bounded_max']):>12}"
            )
        print(f"counters: {r['counters']}")
    load = reading.get("subscriber_load")
    if load:
        print(
            f"\nsubscriber load (app CPU over held pairs less idle; forecast "
            f"{load['forecast_above_idle']}, budget {load['budget_above_idle']}, "
            f"coverage floor {load['coverage_floor_seconds']} s):"
        )
        for name, entry in load["phases"].items():
            print(f"  {name}: {entry}")
    w = reading["worker_rule"]
    if w:
        print(
            f"\nworker: peak memory.current {mib(w['worker_peak_current_bytes'])} × 1.5, "
            f"rounded up to 64 MiB → {w['worker_mem_limit']}; qualifies {w['qualifies']}; "
            f"absences {w['absences']}"
        )
        for name in ("app", "postgres"):
            print(
                f"{name} peak here {mib(w[f'{name}_peak_here_bytes'])} vs committed "
                f"{mib(w[f'{name}_committed_peak_bytes'])} "
                f"(passes: {w[f'{name}_passes_committed_peak']}); limit by the rule over the "
                f"larger {w[f'{name}_mem_limit']} "
                f"(committed {mib(w[f'{name}_committed_limit_bytes'])})"
            )
        if "fits" in w:
            budget = mib(w["budget_bytes"])
            baseline = mib(w["idle_baseline_outside_bounded_bytes"])
            print(
                f"host: total {mib(w['host_total_bytes'])} − idle outside the three bounded "
                f"{baseline} = budget {budget}; limits {mib(w['limits_sum_bytes'])}; "
                f"fits {w['fits']}, spare {mib(w['spare_bytes'])}"
            )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.split("::")[0].strip(), file=sys.stderr)
        return 2
    # The derivation prints ×, → and −; a Windows console in its legacy code page would
    # refuse them after the reading is written, so the stream is reconfigured first.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    reading = reduce_capture(Path(argv[1]))
    out = Path(__file__).with_name("reading.json")
    out.write_text(json.dumps(reading, indent=1) + "\n", encoding="utf-8", newline="\n")
    print_derivation(reading)
    print(f"\nwritten {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
