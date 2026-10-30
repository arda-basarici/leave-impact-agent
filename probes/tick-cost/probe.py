"""The narration tick's cost on the instance (the demo milestone's step 15, the live pages):
for every closed attempt of one ledger, the tick the stream makes once a second per
subscription, a fresh bounded log session loading the attempt and the narration folded over
it, timed in CPU and wall over paired repetitions; and each attempt's durations off its
log, for the wait the pages explain. Run from a one-off container of the deployed image on
the stack's network by ``host.sh``, printing one JSON object on stdout.

The tick is reproduced from the narration stream's own parts, not re-implemented: ``LogStore`` with
the app's bounded connect for the load, ``narration`` for the fold, the registration's
rules through the read model's ``rules_under``, so a change to either moves this reading.
CPU is ``time.process_time`` (this process's user and system time, the database server's
excluded) and wall ``time.perf_counter``; a whole tick is the two parts summed within one
repetition before any percentile is taken, so the whole-tick percentile is over paired
samples and never a sum of two percentiles (the step's external read). The rule the
reading feeds was fixed at the step's entry, before the run: ``c`` is the 95th percentile
of the whole tick's CPU on the attempt whose tick measured highest, and eight
subscriptions on one open
attempt cost ``8c`` of the one interpreter's second; the budget constant below is the
rule's fifth of the interpreter, a design value and not a measurement. Beside the whole tick,
the fixed cost of a tick that finds nothing new is timed on each attempt (a fresh session,
the version check, the row read, the close), which is what an incremental tick pays when the
log has not moved; the first run's reading held no such figure and the shape's choice
turned on it.

Nothing a visitor may not see is printed: attempts are numbered in run-id order and no run
id, scenario or text leaves the process; counts, seconds and the deployed world's event
counts only.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from leaveimpact.agent.log_store import LogStore
from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.app.config import committed_configuration
from leaveimpact.app.narration import narration
from leaveimpact.app.read_model import instants_of, rules_under
from leaveimpact.app.store import connect_bounded

RULE_BUDGET_SECONDS = 0.2
"""The step's budget, fixed before the run: eight ticks a second may take a fifth of the
interpreter."""
SUBSCRIBERS = 8
"""The stream's subscription bound, the viewers the rule prices."""


@dataclass(frozen=True, slots=True)
class Sample:
    """One repetition's paired timings, in seconds."""

    load_cpu: float
    load_wall: float
    fold_cpu: float
    fold_wall: float

    @property
    def whole_cpu(self) -> float:
        return self.load_cpu + self.fold_cpu

    @property
    def whole_wall(self) -> float:
        return self.load_wall + self.fold_wall


def percentile(values: list[float], rank: float) -> float:
    """The nearest-rank percentile of ``values`` (``rank`` in 0..100), on the sorted list.

    >>> percentile([3.0, 1.0, 2.0, 4.0], 50), percentile([3.0, 1.0, 2.0, 4.0], 95)
    (2.0, 4.0)
    """
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, -(-rank * len(ordered) // 100) - 1))
    return ordered[int(index)]


def summary(values: list[float]) -> dict[str, float]:
    return {
        "median": round(statistics.median(values), 6),
        "p95": round(percentile(values, 95), 6),
        "max": round(max(values), 6),
    }


def one_tick(dsn: str, run_id: str, attempt: int, rules: Rules) -> tuple[Sample, AttemptState]:
    """The stream's tick as the route makes it: a fresh bounded session, the load, the
    session closed, then the fold; both timed."""
    cpu0, wall0 = time.process_time(), time.perf_counter()
    session = LogStore(dsn=dsn, connect=connect_bounded)
    try:
        state = session.load(run_id, attempt, rules=rules)
    finally:
        session.close()
    cpu1, wall1 = time.process_time(), time.perf_counter()
    lines = narration(state, rules)
    cpu2, wall2 = time.process_time(), time.perf_counter()
    assert lines, "a closed attempt narrates at least its admission"
    return Sample(cpu1 - cpu0, wall1 - wall0, cpu2 - cpu1, wall2 - wall1), state


def one_idle_tick(dsn: str, run_id: str, attempt: int) -> tuple[float, float]:
    """The fixed cost of a tick that finds nothing new, as an incremental tick would pay
    it: a fresh bounded session (the connect and the version check), the attempt's row
    read, the session closed; CPU and wall. ``ledger_of`` is the store's one public read
    that is exactly the guarded row read and nothing more, so it stands in for the events
    read with a lower bound the live pages step adds, which returns no row here."""
    cpu0, wall0 = time.process_time(), time.perf_counter()
    session = LogStore(dsn=dsn, connect=connect_bounded)
    try:
        session.ledger_of(run_id, attempt)
    finally:
        session.close()
    return time.process_time() - cpu0, time.perf_counter() - wall0


def durations_of(state: AttemptState) -> dict[str, float | None]:
    """Seconds between the log's instants: the admission to the approval request, the
    request to the approval, the approval to the close, and the admission to the close;
    ``None`` where the attempt never reached the later event."""
    instants = instants_of(state)

    def at(event: object) -> datetime | None:
        position = getattr(event, "position", None)
        return None if position is None else instants.get(position)

    admitted = instants.get(1)
    requested = at(state.approval_requested)
    approved = at(state.approved)
    closed = at(state.closed)

    def gap(start: datetime | None, end: datetime | None) -> float | None:
        if start is None or end is None:
            return None
        return round((end - start).total_seconds(), 3)

    return {
        "admission_to_request": gap(admitted, requested),
        "request_to_approval": gap(requested, approved),
        "approval_to_close": gap(approved, closed),
        "admission_to_close": gap(admitted, closed),
    }


def measure(dsn: str, ledger: str, repetitions: int, warmup: int, rules: Rules) -> dict[str, Any]:
    """The reading over every closed attempt of ``ledger``: per attempt the paired timings'
    summaries and its durations, then the rule's inputs and branch over the highest."""
    listing = LogStore(dsn=dsn, connect=connect_bounded)
    try:
        snapshot = listing.snapshot(ledger)
    finally:
        listing.close()
    attempts = sorted(
        (row for row in snapshot.attempts if row.ledger_id == ledger and row.closed),
        key=lambda row: (row.run_id, row.attempt),
    )
    readings: list[dict[str, Any]] = []
    for number, row in enumerate(attempts, start=1):
        samples: list[Sample] = []
        state: AttemptState | None = None
        for repetition in range(warmup + repetitions):
            sample, state = one_tick(dsn, row.run_id, row.attempt, rules)
            if repetition >= warmup:
                samples.append(sample)
        assert state is not None
        idle = [one_idle_tick(dsn, row.run_id, row.attempt) for _ in range(warmup + repetitions)]
        idle = idle[warmup:]
        readings.append(
            {
                "attempt": number,
                "events": len(state.events),
                "lines": len(narration(state, rules)),
                "idle_cpu": summary([cpu for cpu, _ in idle]),
                "idle_wall": summary([wall for _, wall in idle]),
                "load_cpu": summary([s.load_cpu for s in samples]),
                "load_wall": summary([s.load_wall for s in samples]),
                "fold_cpu": summary([s.fold_cpu for s in samples]),
                "fold_wall": summary([s.fold_wall for s in samples]),
                "whole_cpu": summary([s.whole_cpu for s in samples]),
                "whole_wall": summary([s.whole_wall for s in samples]),
                "durations_s": durations_of(state),
            }
        )
    highest = max(readings, key=lambda r: r["whole_cpu"]["p95"], default=None)
    rule: dict[str, Any] = {"budget_seconds": RULE_BUDGET_SECONDS, "subscribers": SUBSCRIBERS}
    if highest is not None:
        c: float = highest["whole_cpu"]["p95"]
        eight = SUBSCRIBERS * c
        rule.update(
            {
                "c_seconds": round(c, 6),
                "eight_c_seconds": round(eight, 6),
                "highest_attempt": highest["attempt"],
                "branch": (
                    "keep the per-subscription tick"
                    if eight <= RULE_BUDGET_SECONDS
                    else "share the fold per attempt"
                    if c <= RULE_BUDGET_SECONDS
                    else "undecided: the fold alone exceeds the budget"
                ),
            }
        )
    closes = [r["durations_s"]["admission_to_close"] for r in readings]
    requests = [r["durations_s"]["admission_to_request"] for r in readings]
    return {
        "ledger": ledger,
        "schema_version": snapshot.schema_version,
        "taken_at": snapshot.taken_at.isoformat(),
        "attempts_measured": len(readings),
        "repetitions": repetitions,
        "warmup": warmup,
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(),
        "attempts": readings,
        "durations_s": {
            "admission_to_close": summary_or_none(closes),
            "admission_to_request": summary_or_none(requests),
        },
        "rule": rule,
    }


def summary_or_none(values: list[float | None]) -> dict[str, float] | None:
    """The summary over the known values, ``None`` when no attempt reached the event."""
    known = [float(v) for v in values if v is not None]
    return summary(known) if known else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="The narration tick's cost over one ledger's closed attempts."
    )
    parser.add_argument(
        "--ledger", required=True, help="the ledger whose closed attempts are timed"
    )
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=1)
    args = parser.parse_args()
    dsn = os.environ["DATABASE_URL"]
    registration = Path(os.environ["LEAVEIMPACT_REGISTRATION_FILE"]).read_bytes()
    rules = rules_under(committed_configuration(), registration)
    reading = measure(dsn, args.ledger, args.repetitions, args.warmup, rules)
    json.dump(reading, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
