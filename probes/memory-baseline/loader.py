"""The memory baseline's load generator (the demo milestone's step 10): web readers and
stream loopers against the deployed app for a fixed hold, run from a one-off container of
the app's own image on the stack's network, reporting what it did as one JSON object on
stdout. The host script starts it in the background and samples memory while it holds.

Readers cycle the public pages over every replay the listing names (the report, its trail,
its timeline, the results page, the listing), each from its own offset so sixteen readers
do not walk the same replay in step. Stream loopers fetch a closed attempt's whole
narration stream from cursor 0 and start again: a looper never pauses, so K loopers place
at least the tick load of K idle subscriptions on the app and PostgreSQL, which is what
the instance can show while no attempt is open (the step's fourth fork). A refusal by the
subscription bound, 503, is counted and the looper pauses before its next fetch.

Every read's latency is recorded, so whether the thread pool binds before memory does
(the step's third fork) reads off the same run. The script imports nothing from the
package: it needs the image's Python and ``httpx``, no world, no store, no credential.
The pass criterion is in ``probes/README.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

LISTING = "/replays"
LINK = re.compile(r'href="/replays/([a-z0-9-]+)"')
REFUSED_PAUSE_SECONDS = 0.5
"""A looper's pause after the bound refuses it, so refusals are counted, not spun."""


@dataclass
class Tally:
    """What one kind of client did: statuses, latencies and transport errors."""

    by_status: dict[str, int] = field(default_factory=dict)
    latencies_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    bytes_read: int = 0

    def record(self, status: int, elapsed_seconds: float, size: int) -> None:
        key = str(status)
        self.by_status[key] = self.by_status.get(key, 0) + 1
        self.latencies_ms.append(elapsed_seconds * 1000.0)
        self.bytes_read += size

    def fail(self, error: Exception) -> None:
        self.errors.append(f"{type(error).__name__}: {error}"[:160])

    def summary(self) -> dict[str, object]:
        return {
            "by_status": dict(sorted(self.by_status.items())),
            "latency_ms": quantiles(self.latencies_ms),
            "bytes": self.bytes_read,
            "error_count": len(self.errors),
            "errors": self.errors[:3],
        }


def quantiles(values: list[float]) -> dict[str, float]:
    """Count, median, 95th percentile (nearest rank), maximum and mean, one decimal."""
    if not values:
        return {}
    ordered = sorted(values)
    last = len(ordered) - 1

    def at(fraction: float) -> float:
        return ordered[min(last, int(fraction * last))]

    return {
        "count": len(ordered),
        "p50": round(at(0.5), 1),
        "p95": round(at(0.95), 1),
        "max": round(ordered[-1], 1),
        "mean": round(sum(ordered) / len(ordered), 1),
    }


def pages_of(public_id: str) -> list[str]:
    return [
        f"/replays/{public_id}",
        f"/replays/{public_id}/trail",
        f"/replays/{public_id}/timeline",
        "/results",
        LISTING,
    ]


async def reader(
    client: httpx.AsyncClient, ids: list[str], offset: int, stop_at: float, tally: Tally
) -> None:
    index = offset
    while time.monotonic() < stop_at:
        public_id = ids[index % len(ids)]
        index += 1
        for path in pages_of(public_id):
            if time.monotonic() >= stop_at:
                return
            started = time.monotonic()
            try:
                response = await client.get(path)
            except httpx.HTTPError as error:
                tally.fail(error)
                continue
            tally.record(response.status_code, time.monotonic() - started, len(response.content))


async def looper(
    client: httpx.AsyncClient, ids: list[str], offset: int, stop_at: float, tally: Tally
) -> None:
    index = offset
    while time.monotonic() < stop_at:
        public_id = ids[index % len(ids)]
        index += 1
        started = time.monotonic()
        size = 0
        try:
            async with client.stream(
                "GET", f"/replays/{public_id}/events", params={"after": "0"}
            ) as response:
                status = response.status_code
                if status == 200:
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                else:
                    await response.aread()
        except httpx.HTTPError as error:
            tally.fail(error)
            continue
        tally.record(status, time.monotonic() - started, size)
        if status == 503:
            await asyncio.sleep(REFUSED_PAUSE_SECONDS)


async def run(
    args: argparse.Namespace, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, object]:
    """The levels' summary; ``transport`` lets a test run the clients against an in-process
    app, the instance run leaving it at the default."""
    connections = args.readers + args.streams + 2
    limits = httpx.Limits(max_connections=connections, max_keepalive_connections=connections)
    async with httpx.AsyncClient(
        base_url=args.base_url, timeout=httpx.Timeout(60.0), limits=limits, transport=transport
    ) as client:
        listing = await client.get(LISTING)
        listing.raise_for_status()
        ids = sorted(set(LINK.findall(listing.text)))
        if not ids:
            raise SystemExit("the listing names no replay; nothing to load")
        reads, streams = Tally(), Tally()
        started_at = datetime.now(UTC)
        stop_at = time.monotonic() + args.hold
        tasks = [reader(client, ids, i * 7, stop_at, reads) for i in range(args.readers)]
        tasks += [looper(client, ids, i * 11, stop_at, streams) for i in range(args.streams)]
        await asyncio.gather(*tasks)
        ended_at = datetime.now(UTC)
    return {
        "label": args.label,
        "readers": args.readers,
        "streams": args.streams,
        "hold_seconds": args.hold,
        "replays": len(ids),
        "reads": reads.summary(),
        "streams_fetched": streams.summary(),
        "started_at": started_at.isoformat(timespec="seconds"),
        "ended_at": ended_at.isoformat(timespec="seconds"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default="http://app:8000")
    parser.add_argument("--readers", type=int, default=0)
    parser.add_argument("--streams", type=int, default=0)
    parser.add_argument("--hold", type=float, default=45.0, help="seconds to hold the load")
    parser.add_argument("--label", default="level")
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run(parse_args())), separators=(",", ":")))
