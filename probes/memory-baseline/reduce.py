"""The memory baseline's reduction (the demo milestone's step 10): the host script's saved
output reduced to `reading.json` and the rule of `probes/README.md` applied to it with
every input printed, so the limits in `compose.yaml` and the stream's subscription bound
are numbers with a script behind them. Run from the repository root::

    uv run python probes/memory-baseline/reduce.py probes/captures/memory-baseline/2026-10-24

The reduction takes, per level, the maximum over the three samples of each container's
`memory.current` and anonymous pages and the app's thread count, the minimum of the
host's available memory, and the loader's own counts and latency quantiles. The rule: a
service's limit is 1.5 times the largest `memory.current` sampled for it over every
level, rounded up to the next 64 MiB; the two limits plus the worker's 512 MiB reservation
stay under the host's total minus the idle host baseline (memory in use outside the two
containers the limits bound, the largest idle sample: the proxy's Caddy and hello
containers are the platform's residents and stay inside the baseline, since nothing here
allocates for them); the subscription bound stays at the deployed value when the combined
level fits the app's limit and its reader latency stays within twice the readers-only
level. `memory.peak`, the kernel's own high-water mark over the container's life, is
reported beside each limit with whether the limit clears 1.5 times it too; it is not the
rule's input, since it predates the run. The app's current at one, four and eight loopers
is reported as the three numbers it is, since they show no slope a per-looper cost could
be read from. The unit test `tests/unit/test_memory_baseline.py` holds the committed
reading, `compose.yaml` and the stream module to this arithmetic.

The capture's digest is over its decoded lines joined by newline, not its bytes: the send
script saved it through PowerShell with a byte-order mark and CRLF, git stores it LF, and
a digest of the bytes would differ between a Windows checkout and a Linux one (the first
external read of the step's commits found exactly that).
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

MIB = 1024 * 1024
HEADROOM = 1.5
ROUNDING = 64 * MIB
WORKER_RESERVATION = 512 * MIB
APP = "leaveimpact-app-1"
POSTGRES = "leaveimpact-postgres-1"
DEPLOYED_BOUND = 8
COMBINED_LEVEL = "r16s8"
READERS_LEVEL = "r16"
LEVELS = ("idle", "r1", "r4", "r16", "s1", "s4", "s8", "r16s8")


def limit_of(peak_current: int) -> int:
    """The rule's limit in bytes: headroom on the peak, rounded up to the next 64 MiB."""
    return math.ceil(peak_current * HEADROOM / ROUNDING) * ROUNDING


def mem_limit_of(limit_bytes: int) -> str:
    """The limit as Compose spells it (`384m`)."""
    assert limit_bytes % MIB == 0
    return f"{limit_bytes // MIB}m"


def canonical_text(source: Path) -> str:
    """The capture's lines joined by newline, whatever mark and line ending the file on
    disk carries; what the digest and the parse read."""
    return "\n".join(source.read_text(encoding="utf-8-sig").splitlines()) + "\n"


def capture_digest(source: Path) -> str:
    """SHA-256 of the canonical text, the same on every checkout."""
    return hashlib.sha256(canonical_text(source).encode("utf-8")).hexdigest()


def parse(text: str) -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]]]:
    """The host's header lines, the loader summaries and the samples from the saved stdout."""
    header: dict[str, str] = {}
    loaders: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            record = json.loads(line)
            (loaders if "hold_seconds" in record else samples).append(record)
        elif line.startswith("work "):
            header["work"] = line[5:]
        elif line.startswith("deployed "):
            header["deployed"] = line[9:]
        elif line.startswith("cgroup "):
            header["cgroup"] = line
        elif line.startswith("cpus "):
            header["cpus"] = line[5:]
        elif line.endswith(".aarch64") or line.endswith(".x86_64"):
            header["kernel"] = line
        elif line == "no swap":
            header["swap"] = "none"
    return header, loaders, samples


def reduce_level(label: str, samples: list[dict[str, Any]], loader: dict[str, Any] | None) -> dict[str, Any]:
    """One level: the samples' extremes and the loader's own account."""
    containers: dict[str, dict[str, int]] = {}
    for name in sorted({name for sample in samples for name in sample["containers"]}):
        readings = [sample["containers"][name] for sample in samples]
        if any("absent" in reading for reading in readings):
            containers[name] = {"absent": 1}
            continue
        containers[name] = {
            "current_max": max(reading["cur"] for reading in readings),
            "anon_max": max(reading["anon"] for reading in readings),
            "threads_max": max(reading["thr"] for reading in readings),
            "peak": max(reading["peak"] for reading in readings),
        }
    level: dict[str, Any] = {
        "samples": len(samples),
        "host_available_min": min(sample["host"]["avail"] for sample in samples),
        # Outside the two containers the limits bound; the proxy's containers stay inside.
        "host_used_outside_stack_max": max(
            sample["host"]["total"]
            - sample["host"]["avail"]
            - sum(sample["containers"][name]["cur"] for name in (APP, POSTGRES))
            for sample in samples
        ),
        "containers": containers,
    }
    if loader is not None:
        hold = loader["hold_seconds"]
        reads, streams = loader["reads"], loader["streams_fetched"]
        level["loader"] = {
            "readers": loader["readers"],
            "streams": loader["streams"],
            "reads": reads["by_status"],
            "reads_per_second": round(sum(reads["by_status"].values()) / hold, 2),
            "read_latency_ms": reads["latency_ms"],
            "stream_fetches": streams["by_status"],
            "stream_fetches_per_second": round(sum(streams["by_status"].values()) / hold, 2),
            "stream_fetch_ms": streams["latency_ms"],
            "errors": reads["error_count"] + streams["error_count"],
        }
    return level


def apply_rule(levels: dict[str, dict[str, Any]], host_total: int) -> dict[str, Any]:
    """The rule over the reduced levels, every input kept beside its output."""

    def peak_current(name: str) -> int:
        return max(level["containers"][name]["current_max"] for level in levels.values())

    def kernel_peak(name: str) -> int:
        return max(level["containers"][name]["peak"] for level in levels.values())

    app_peak, postgres_peak = peak_current(APP), peak_current(POSTGRES)
    app_limit, postgres_limit = limit_of(app_peak), limit_of(postgres_peak)
    baseline = levels["idle"]["host_used_outside_stack_max"]
    budget = host_total - baseline
    total = app_limit + postgres_limit + WORKER_RESERVATION
    combined, readers = levels[COMBINED_LEVEL], levels[READERS_LEVEL]
    combined_fits = combined["containers"][APP]["current_max"] <= app_limit
    latency_ratio = (
        combined["loader"]["read_latency_ms"]["p50"] / readers["loader"]["read_latency_ms"]["p50"]
    )
    return {
        "headroom": HEADROOM,
        "rounding_bytes": ROUNDING,
        "worker_reservation_bytes": WORKER_RESERVATION,
        "app": {
            "peak_current_bytes": app_peak,
            "limit_bytes": app_limit,
            "mem_limit": mem_limit_of(app_limit),
            "kernel_peak_bytes": kernel_peak(APP),
            "limit_clears_headroom_on_kernel_peak": app_limit >= kernel_peak(APP) * HEADROOM,
        },
        "postgres": {
            "peak_current_bytes": postgres_peak,
            "limit_bytes": postgres_limit,
            "mem_limit": mem_limit_of(postgres_limit),
            "kernel_peak_bytes": kernel_peak(POSTGRES),
            "limit_clears_headroom_on_kernel_peak": postgres_limit >= kernel_peak(POSTGRES) * HEADROOM,
        },
        "host": {
            "total_bytes": host_total,
            "idle_baseline_bytes": baseline,
            "budget_bytes": budget,
            "limits_plus_reservation_bytes": total,
            "fits": total <= budget,
            "spare_bytes": budget - total,
        },
        "bound": {
            "deployed": DEPLOYED_BOUND,
            "combined_level": COMBINED_LEVEL,
            "combined_app_current_max": combined["containers"][APP]["current_max"],
            "combined_fits_app_limit": combined_fits,
            "latency_ratio_combined_over_readers": round(latency_ratio, 2),
            "latency_within_twice": latency_ratio <= 2.0,
            "subscription_bound": DEPLOYED_BOUND if combined_fits and latency_ratio <= 2.0 else None,
            "app_current_max_at_loopers": {
                label: levels[label]["containers"][APP]["current_max"] for label in ("s1", "s4", "s8")
            },
        },
    }


def reduce_capture(capture: Path) -> dict[str, Any]:
    source = capture / "host.out.txt"
    header, loaders, samples = parse(canonical_text(source))
    by_label = {loader["label"]: loader for loader in loaders}
    levels = {
        label: reduce_level(label, [s for s in samples if s["label"] == label], by_label.get(label))
        for label in LEVELS
    }
    host_total = samples[0]["host"]["total"]
    idle = [s for s in samples if s["label"] == "idle" and "processes" in s]
    return {
        "capture": capture.name,
        "source_sha256": capture_digest(source),
        "host": {**header, "total_bytes": host_total},
        "largest_processes_at_idle": idle[0]["processes"] if idle else [],
        "levels": levels,
        "rule": apply_rule(levels, host_total),
    }


def mib(value: float) -> str:
    return f"{value / MIB:.1f} MiB"


def print_derivation(reading: dict[str, Any]) -> None:
    rule = reading["rule"]
    print(f"capture {reading['capture']}, host.out.txt sha256 {reading['source_sha256'][:16]}…")
    print(f"host {reading['host']}")
    print()
    print(f"{'level':<7}{'app cur':>12}{'app anon':>12}{'app thr':>8}{'pg cur':>12}{'pg anon':>12}"
          f"{'caddy':>10}{'avail':>12}  loader")
    for label, level in reading["levels"].items():
        c = level["containers"]
        loader = level.get("loader")
        account = ""
        if loader:
            reads = loader["read_latency_ms"]
            fetches = loader["stream_fetch_ms"]
            account = (
                f"reads {sum(loader['reads'].values())} ({loader['reads_per_second']}/s"
                f"{', p50 ' + str(reads['p50']) + ' ms' if reads else ''}); "
                f"fetches {sum(loader['stream_fetches'].values())} ({loader['stream_fetches_per_second']}/s"
                f"{', p50 ' + str(fetches['p50']) + ' ms' if fetches else ''}); errors {loader['errors']}"
            )
        print(
            f"{label:<7}{mib(c[APP]['current_max']):>12}{mib(c[APP]['anon_max']):>12}"
            f"{c[APP]['threads_max']:>8}{mib(c[POSTGRES]['current_max']):>12}"
            f"{mib(c[POSTGRES]['anon_max']):>12}{mib(c['proxy-caddy-1']['current_max']):>10}"
            f"{mib(level['host_available_min']):>12}  {account}"
        )
    print()
    for name in ("app", "postgres"):
        r = rule[name]
        print(
            f"{name}: peak memory.current {mib(r['peak_current_bytes'])} × {HEADROOM} = "
            f"{mib(r['peak_current_bytes'] * HEADROOM)}, rounded up to 64 MiB → {r['mem_limit']} "
            f"({mib(r['limit_bytes'])}); kernel memory.peak {mib(r['kernel_peak_bytes'])}, "
            f"the limit clears {HEADROOM} × it: {r['limit_clears_headroom_on_kernel_peak']}"
        )
    h = rule["host"]
    print(
        f"host: total {mib(h['total_bytes'])} − idle baseline outside the containers "
        f"{mib(h['idle_baseline_bytes'])} = budget {mib(h['budget_bytes'])}; limits "
        f"{rule['app']['mem_limit']} + {rule['postgres']['mem_limit']} + worker {mib(WORKER_RESERVATION)} = "
        f"{mib(h['limits_plus_reservation_bytes'])}; fits: {h['fits']}, spare {mib(h['spare_bytes'])}"
    )
    b = rule["bound"]
    print(
        f"bound: combined level {b['combined_level']} app current {mib(b['combined_app_current_max'])} "
        f"≤ app limit: {b['combined_fits_app_limit']}; reader p50 ratio combined/readers "
        f"{b['latency_ratio_combined_over_readers']} ≤ 2: {b['latency_within_twice']} → "
        f"subscription bound {b['subscription_bound']}; app current at 1, 4, 8 loopers: "
        + ", ".join(mib(value) for value in b["app_current_max_at_loopers"].values())
        + " (no slope to read a per-looper cost from)"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.split("::")[0].strip(), file=sys.stderr)
        return 2
    capture = Path(argv[1])
    reading = reduce_capture(capture)
    out = Path(__file__).with_name("reading.json")
    out.write_text(json.dumps(reading, indent=1) + "\n", encoding="utf-8", newline="\n")
    print_derivation(reading)
    print(f"\nwritten {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
