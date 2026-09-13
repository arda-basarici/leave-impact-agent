"""The checkpoint timer: every overwrite timed and its bytes counted, the conditional puts
counted apart and never timed, the reads passed through, the summary's percentiles by
nearest rank on the durations seen, the share against the run's seconds and zero for a run
of no time, and the printed lines one number each."""

from __future__ import annotations

from collections.abc import Callable
from itertools import count

import pytest

from leaveimpact.generator.metrics import TimedObjectWriter
from tests.unit.in_memory_object_store import InMemoryObjectStore


def ticking(step: float) -> Callable[[], float]:
    ticks = count()
    return lambda: next(ticks) * step


def test_overwrites_are_timed_and_conditional_puts_only_counted() -> None:
    inner = InMemoryObjectStore()
    timed = TimedObjectWriter(inner, clock=ticking(0.1))
    for n in range(4):
        timed.overwrite("preparing/v/world-manifest.json", b"x" * (n + 1))
    timed.put_if_absent("worlds/v/scenario-specs.json", b"specs")
    timed.put_if_absent("worlds/v/scenario-specs.json", b"specs")
    assert timed.get("worlds/v/scenario-specs.json") is not None
    assert timed.list_keys("worlds/") == ("worlds/v/scenario-specs.json",)

    summary = timed.summary(run_seconds=2.0)
    assert summary.count == 4
    assert summary.bytes_written == 1 + 2 + 3 + 4
    assert summary.conditional_puts == 2
    assert summary.total_seconds == pytest.approx(0.4)
    assert summary.p50_seconds == pytest.approx(0.1)
    assert summary.p95_seconds == pytest.approx(0.1)
    assert summary.share_of_run == pytest.approx(0.2)
    assert summary.lines()[0] == "checkpoint_count=4"
    assert summary.lines()[-1] == "checkpoint_share_of_run=0.200"


def test_an_empty_run_summarizes_to_zeros_without_dividing() -> None:
    summary = TimedObjectWriter(InMemoryObjectStore()).summary(run_seconds=0.0)
    assert (summary.count, summary.total_seconds, summary.p50_seconds, summary.share_of_run) == (
        0,
        0.0,
        0.0,
        0.0,
    )
