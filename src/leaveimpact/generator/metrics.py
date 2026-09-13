"""The checkpoint's cost measured at the shell: a timing wrapper around the world store.

The step 12 ruling on the checkpoint kept the per-record cadence — one manifest overwrite
after every projected record, the one-write crash window of the projector step — and
made the first live run the measurement gate: count, total seconds, the p50 and p95 of
one checkpoint, bytes written, and the checkpoint's share of the whole projection, so a
later cadence change rests on a number and not on intuition. The numbers come from here,
a wrapper the entry point puts around the world store, so the composition root stays
unaware of timing and the store stays a store; they go to the run's log and to the
findings, never into the manifest, whose bytes are the projection's commit record.

Only ``overwrite`` is timed, because only the checkpoint uses it; the final artifacts'
conditional puts are counted apart, since a rerun's equal cases cost a read each and
would otherwise blur the checkpoint's own number. Timing is monotonic and local to the
process, never the wall clock the law reserves for composition roots.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from leaveimpact.adapters.object_store.read import StoredObject
from leaveimpact.adapters.object_store.write import ObjectWriter, PutReceipt


@dataclass(frozen=True, slots=True)
class CheckpointSummary:
    """One run's checkpoint numbers, as the log and the findings report them."""

    count: int
    total_seconds: float
    p50_seconds: float
    p95_seconds: float
    bytes_written: int
    conditional_puts: int
    share_of_run: float
    """The checkpoint's seconds over the run's, in [0, 1]; zero when the run took no time."""

    def lines(self) -> tuple[str, ...]:
        """The summary as the run prints it, one number per line."""
        return (
            f"checkpoint_count={self.count}",
            f"checkpoint_total_seconds={self.total_seconds:.3f}",
            f"checkpoint_p50_seconds={self.p50_seconds:.3f}",
            f"checkpoint_p95_seconds={self.p95_seconds:.3f}",
            f"checkpoint_bytes_written={self.bytes_written}",
            f"conditional_puts={self.conditional_puts}",
            f"checkpoint_share_of_run={self.share_of_run:.3f}",
        )


class TimedObjectWriter:
    """``ObjectWriter`` over ``inner``, timing every overwrite and counting the conditional puts."""

    def __init__(self, inner: ObjectWriter, clock: Callable[[], float] = time.perf_counter) -> None:
        self._inner = inner
        self._clock = clock
        self._durations: list[float] = []
        self._bytes = 0
        self._conditional_puts = 0

    def get(self, key: str) -> StoredObject | None:
        return self._inner.get(key)

    def list_keys(self, prefix: str) -> tuple[str, ...]:
        return self._inner.list_keys(prefix)

    def put_if_absent(self, key: str, content: bytes) -> PutReceipt:
        self._conditional_puts += 1
        return self._inner.put_if_absent(key, content)

    def overwrite(self, key: str, content: bytes) -> PutReceipt:
        started = self._clock()
        try:
            return self._inner.overwrite(key, content)
        finally:
            self._durations.append(self._clock() - started)
            self._bytes += len(content)

    def summary(self, run_seconds: float) -> CheckpointSummary:
        """The numbers so far, the share computed against ``run_seconds``."""
        total = sum(self._durations)
        return CheckpointSummary(
            count=len(self._durations),
            total_seconds=total,
            p50_seconds=percentile(self._durations, 50),
            p95_seconds=percentile(self._durations, 95),
            bytes_written=self._bytes,
            conditional_puts=self._conditional_puts,
            share_of_run=total / run_seconds if run_seconds > 0 else 0.0,
        )


def percentile(values: list[float], rank: int) -> float:
    """The nearest-rank percentile of ``values``; zero for no values.

    >>> percentile([0.3, 0.1, 0.2, 0.4], 50), percentile([0.3, 0.1, 0.2, 0.4], 95)
    (0.2, 0.4)
    >>> percentile([], 50)
    0.0
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    position = max(0, min(len(ordered) - 1, -(-rank * len(ordered) // 100) - 1))
    return ordered[position]
