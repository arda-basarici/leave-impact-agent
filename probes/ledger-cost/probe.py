"""The ledger page's two readings on the instance (the demo milestone's step 15, the ledger
page): over every settled attempt of one ledger, the cost of recomputing its retained
liability from the log, which is what the page's memo pays once per process, and the
settlement's charged amount with its split into known consumption and retained liability,
which is what the page sums and the figure it quotes as a charge forecast until a visitor
run settles. Run from a one-off container of the deployed image on the stack's network by
``host.sh``, printing one JSON object on stdout.

The memo's work is reproduced from its parts, not re-implemented: ``LogStore`` with the
app's bounded connect for the load, the account rule's ``settle`` and ``figures_of`` over
the folded account, the registration's rules through the read model's ``rules_under``, so
a change to any of them moves this reading. The cold pass is the memo's own history: one
fresh session and one load per settled attempt in run-id order, each timed in CPU
(``process_time``, this process's own) and wall (``perf_counter``), the pass's sum being
what the first view after a process start pays; the repetitions after it characterize the
spread per attempt and never enter the cold figure. The rule the reading feeds was fixed
before the run: the pass's mean CPU per attempt times the attempts a month of the daily cap
admits is the forecast first view a month into the demo, and at or under the budget below
the lazy memo stays, above it the memo is warmed at the process's start or the figures
column (the retained liability's fork, option (b)) lands before the flag flips.

Each attempt is also checked, since the page will compare the same three numbers on every
view: the account rule's charge equals the charge the closing event logged and the amount
the ledger's settled entry holds, the rule's state equals the logged state, and a reconciled
settlement retains nothing (the memo's shortcut, held here on real data). A failed check is
in the reading and the exit is 1.

Nothing a visitor may not see is printed: attempts are numbered in run-id order and no run
id, scenario or text leaves the process; counts, seconds, pico-dollars and the deployed
world's event counts only.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from leaveimpact.agent.ledger import EntryKind, LedgerEntry
from leaveimpact.agent.log_store import LogStore
from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.app.config import committed_configuration
from leaveimpact.app.read_model import rules_under
from leaveimpact.app.store import connect_bounded
from leaveimpact.core.run_account import figures_of, settle
from leaveimpact.core.run_ending import ReservationState

COLD_BUDGET_SECONDS = 5.0
"""The step's budget, fixed before the run: the first view after a process start, a month
into the demo at the daily cap, may cost five seconds of the interpreter; a design value."""
FORECAST_DAYS = 30
"""The month the forecast prices, at the configured daily cap."""


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


def one_load(
    dsn: str, run_id: str, attempt: int, rules: Rules
) -> tuple[float, float, AttemptState]:
    """The memo's load as the page makes it: a fresh bounded session, the fold, the session
    closed; CPU and wall seconds and the state."""
    cpu0, wall0 = time.process_time(), time.perf_counter()
    session = LogStore(dsn=dsn, connect=connect_bounded)
    try:
        state = session.load(run_id, attempt, rules=rules)
    finally:
        session.close()
    return time.process_time() - cpu0, time.perf_counter() - wall0, state


def checked(
    number: int, state: AttemptState, entry: LedgerEntry | None
) -> tuple[dict[str, Any], list[str]]:
    """The attempt's figures from the account rule beside what the log and the ledger
    recorded, and every disagreement as a sentence naming the attempt by its number."""
    failures: list[str] = []
    computed = settle(state.account)
    figures = figures_of(state.account)
    closing = state.closed
    logged = getattr(closing.event, "settlement", None) if closing is not None else None
    if logged is None:
        failures.append(f"attempt {number} is closed with no settlement logged")
    elif (logged.charged_pico_usd, logged.state) != (computed.charged_pico_usd, computed.state):
        failures.append(
            f"attempt {number}: the rule charges {computed.charged_pico_usd} "
            f"{computed.state.value}, the log says {logged.charged_pico_usd} {logged.state.value}"
        )
    if entry is None:
        failures.append(f"attempt {number} has no settled entry on the ledger")
    elif entry.amount_pico_usd != computed.charged_pico_usd:
        failures.append(
            f"attempt {number}: the rule charges {computed.charged_pico_usd}, the ledger's "
            f"settled entry holds {entry.amount_pico_usd}"
        )
    if figures.total_pico_usd != computed.charged_pico_usd:
        failures.append(f"attempt {number}: the figures' total is not the charge")
    if computed.state is ReservationState.RECONCILED and figures.retained_pico_usd != 0:
        failures.append(f"attempt {number}: reconciled and retaining {figures.retained_pico_usd}")
    record = {
        "attempt": number,
        "events": len(state.events),
        "settlement_state": computed.state.value,
        "kept_reason": None if computed.kept_reason is None else computed.kept_reason.value,
        "charged_pico_usd": computed.charged_pico_usd,
        "known_pico_usd": figures.known_pico_usd,
        "retained_pico_usd": figures.retained_pico_usd,
        "ledger_revision": None if entry is None else entry.revision,
    }
    return record, failures


def one_settlements_read(dsn: str, ledger: str) -> tuple[float, float, int]:
    """The page's memo fill as the page makes it: a fresh bounded session, every closed
    attempt's logged settlement on the ledger in one statement, the session closed; CPU and
    wall seconds and the rows returned."""
    cpu0, wall0 = time.process_time(), time.perf_counter()
    session = LogStore(dsn=dsn, connect=connect_bounded)
    try:
        rows = len(session.settlements_of(ledger))
    finally:
        session.close()
    return time.process_time() - cpu0, time.perf_counter() - wall0, rows


def measure(dsn: str, ledger: str, repetitions: int, warmup: int, rules: Rules) -> dict[str, Any]:
    """The reading over every settled attempt of ``ledger``: the cold pass, each attempt's
    figures and checks, the repetitions' summaries, the charges' sums and the rule."""
    listing = LogStore(dsn=dsn, connect=connect_bounded)
    try:
        snapshot = listing.snapshot(ledger)
        view = listing.ledger_view(ledger)
    finally:
        listing.close()
    settled = {
        (entry.run_id, entry.attempt): entry
        for entry in view.entries
        if entry.kind is EntryKind.SETTLED
    }
    attempts = sorted(
        (row for row in snapshot.attempts if row.ledger_id == ledger and row.closed),
        key=lambda row: (row.run_id, row.attempt),
    )
    by_kind = {kind.value: 0 for kind in EntryKind}
    for entry in view.entries:
        by_kind[entry.kind.value] += 1

    # The cold pass first, in order, one load each: the memo's first fill.
    cold: list[tuple[float, float]] = []
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for number, row in enumerate(attempts, start=1):
        cpu, wall, state = one_load(dsn, row.run_id, row.attempt, rules)
        cpu1 = time.process_time()
        record, found = checked(number, state, settled.get((row.run_id, row.attempt)))
        figure_cpu = time.process_time() - cpu1
        cold.append((cpu, wall))
        record["cold"] = {
            "load_cpu": round(cpu, 6),
            "load_wall": round(wall, 6),
            "figure_cpu": round(figure_cpu, 6),
        }
        records.append(record)
        failures.extend(found)
    if len(records) != len(settled):
        failures.append(
            f"{len(records)} closed attempts on the ledger and {len(settled)} settled entries"
        )

    # Then the repetitions, for the spread per attempt; none of these is the cold figure.
    for record, row in zip(records, attempts, strict=True):
        samples = [
            one_load(dsn, row.run_id, row.attempt, rules)[:2] for _ in range(warmup + repetitions)
        ][warmup:]
        record["load_cpu"] = summary([cpu for cpu, _ in samples])
        record["load_wall"] = summary([wall for _, wall in samples])

    # The settlements read (the ledger page's memo fill, after fork G4-4): one statement for
    # every closed attempt's closing event, timed cold then over the repetitions; absent on
    # an image older than the page, in which case the reading says so.
    settlements_read: dict[str, Any] | None = None
    if hasattr(LogStore, "settlements_of"):
        timings = [one_settlements_read(dsn, ledger) for _ in range(1 + warmup + repetitions)]
        cold_read = timings[0]
        warm = timings[1 + warmup :]
        settlements_read = {
            "rows": cold_read[2],
            "cold_cpu_s": round(cold_read[0], 6),
            "cold_wall_s": round(cold_read[1], 6),
            "cpu": summary([cpu for cpu, _, _ in warm]),
            "wall": summary([wall for _, wall, _ in warm]),
        }

    charges = [r["charged_pico_usd"] for r in records]
    count = len(charges)
    total = sum(charges)
    pass_cpu = sum(cpu for cpu, _ in cold)
    pass_wall = sum(wall for _, wall in cold)
    daily = committed_configuration().daily_admissions
    forecast_attempts = FORECAST_DAYS * daily
    rate = pass_cpu / count if count else 0.0
    forecast = rate * forecast_attempts
    return {
        "ledger": ledger,
        "schema_version": snapshot.schema_version,
        "taken_at": snapshot.taken_at.isoformat(),
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(),
        "repetitions": repetitions,
        "warmup": warmup,
        "head": {
            "total_pico_usd": view.head.total_pico_usd,
            "revision": view.head.revision,
            "threshold_pico_usd": view.head.threshold_pico_usd,
        },
        "entries_by_kind": by_kind,
        "attempts_measured": count,
        "attempts": records,
        "charges": {
            "count": count,
            "sum_pico_usd": total,
            "mean_pico_usd": round(total / count) if count else None,
            "known_sum_pico_usd": sum(r["known_pico_usd"] for r in records),
            "retained_sum_pico_usd": sum(r["retained_pico_usd"] for r in records),
            "reconciled": sum(1 for r in records if r["settlement_state"] == "reconciled"),
            "kept": sum(1 for r in records if r["settlement_state"] == "kept"),
        },
        "cold": {
            "pass_cpu_s": round(pass_cpu, 6),
            "pass_wall_s": round(pass_wall, 6),
            "per_attempt_cpu_ms": (summary([cpu * 1000 for cpu, _ in cold]) if cold else None),
            "mean_per_attempt_cpu_s": round(rate, 6),
            "daily_admissions": daily,
            "forecast_days": FORECAST_DAYS,
            "forecast_attempts": forecast_attempts,
            "forecast_cpu_s": round(forecast, 6),
            "forecast_settlements_read_cpu_s": (
                None
                if settlements_read is None or count == 0
                else round(settlements_read["cold_cpu_s"] / count * forecast_attempts, 6)
            ),
            "budget_seconds": COLD_BUDGET_SECONDS,
            "branch": (
                "the lazy memo stays"
                if forecast <= COLD_BUDGET_SECONDS
                else "warm the memo at the process start, or the figures column before the flip"
            ),
        },
        "settlements_read": settlements_read,
        "checks": {"passed": not failures, "failures": failures},
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="The ledger page's cold cost and charges over one ledger's settled attempts."
    )
    parser.add_argument("--ledger", required=True, help="the ledger read")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    args = parser.parse_args()
    dsn = os.environ["DATABASE_URL"]
    registration = Path(os.environ["LEAVEIMPACT_REGISTRATION_FILE"]).read_bytes()
    rules = rules_under(committed_configuration(), registration)
    reading = measure(dsn, args.ledger, args.repetitions, args.warmup, rules)
    json.dump(reading, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0 if reading["checks"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
