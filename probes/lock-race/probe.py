"""A worker's append against a takeover, on two PostgreSQL connections: what a generation
guard keeps out when it is read without a lock, and what it keeps out under a row lock.

An attempt is a row holding a generation. A worker appends events stamped with the
generation it claimed; a takeover increments the generation and appends the new segment's
start. The rule the event log needs is that once a takeover has committed, the displaced
worker appends nothing. Four sequences are driven to a known interleaving and the log is
read afterwards:

- *plain, read then insert*: the worker reads the generation in its transaction, the
  takeover commits, the worker inserts and commits.
- *plain, one guarded statement*: the worker's single ``INSERT ... SELECT ... WHERE
  generation = mine`` is held in mid-execution, the takeover commits, the statement is let
  go. Under read committed a statement sees the snapshot taken when it started, so the guard
  is expected to pass on a generation that is no longer current.
- *locked, worker first*: the worker reads the row ``FOR UPDATE``, the takeover's locking
  read waits on it, the worker appends and commits, the takeover goes on.
- *locked, takeover first*: the takeover holds the row with its increment uncommitted, the
  worker's locking read waits, the takeover commits, and the worker reads whatever the wait
  hands it.

A sequence shows the race when the log, in insertion order, holds an event of the old
generation after the new segment's start.

No step waits on a clock. A step that must happen while another connection is blocked waits
until the server itself reports that connection waiting on a lock (``pg_stat_activity``),
polled under a deadline; the one-statement form is held by an advisory lock a third
connection owns, taken inside the statement after its snapshot exists.

    DATABASE_URL=postgresql://... python probes/lock-race/probe.py

Everything happens in a schema created for the run and dropped at its end.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import psycopg

Connection = psycopg.Connection[tuple[Any, ...]]

RUN = "run"
ATTEMPT = 1
BARRIER_KEY = 7_081_005
DEADLINE_SECONDS = 10.0

_SETUP = """
CREATE TABLE attempts (
    run_id text NOT NULL,
    attempt integer NOT NULL,
    generation integer NOT NULL,
    PRIMARY KEY (run_id, attempt)
);
CREATE TABLE events (
    seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id text NOT NULL,
    attempt integer NOT NULL,
    generation integer NOT NULL,
    kind text NOT NULL
);
"""

_READ = "SELECT generation FROM attempts WHERE run_id = %s AND attempt = %s"
_INSERT = "INSERT INTO events (run_id, attempt, generation, kind) VALUES (%s, %s, %s, %s)"
_GUARDED_INSERT = """
INSERT INTO events (run_id, attempt, generation, kind)
SELECT run_id, attempt, generation, 'tool_result'
FROM attempts
WHERE run_id = %s AND attempt = %s AND generation = %s
  AND (SELECT count(*) FROM (SELECT pg_advisory_xact_lock(%s)) AS barrier) = 1
"""


@dataclass(frozen=True, slots=True)
class Observed:
    """One sequence as it ended: what the worker read and did, and the log it left."""

    form: str
    worker_read: str
    worker_appended: bool
    log: tuple[tuple[int, str], ...]
    forecast_stale: bool

    @property
    def stale_after_takeover(self) -> bool:
        """An event of an older generation inserted after a newer generation's event."""
        highest = 0
        for generation, _ in self.log:
            if generation < highest:
                return True
            highest = max(highest, generation)
        return False


def wait_until_blocked(observer: Connection, pid: int) -> None:
    """Return once the server reports backend ``pid`` waiting on a lock."""
    deadline = time.monotonic() + DEADLINE_SECONDS
    while time.monotonic() < deadline:
        row = observer.execute(
            "SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", (pid,)
        ).fetchone()
        if row is not None and row[0] == "Lock":
            return
    raise RuntimeError(f"backend {pid} was expected to wait on a lock and never did")


def takeover_statements(connection: Connection, *, locking: bool) -> None:
    """The takeover up to its commit: read the row, increment, append the segment's start."""
    read = _READ + (" FOR UPDATE" if locking else "")
    row = connection.execute(read, (RUN, ATTEMPT)).fetchone()
    assert row is not None
    connection.execute(
        "UPDATE attempts SET generation = %s WHERE run_id = %s AND attempt = %s",
        (row[0] + 1, RUN, ATTEMPT),
    )
    connection.execute(_INSERT, (RUN, ATTEMPT, row[0] + 1, "segment_started"))


def plain_read_then_insert(worker: Connection, taker: Connection, **_: Any) -> tuple[str, bool]:
    row = worker.execute(_READ, (RUN, ATTEMPT)).fetchone()
    assert row is not None
    takeover_statements(taker, locking=False)
    taker.commit()
    appended = row[0] == 1
    if appended:
        worker.execute(_INSERT, (RUN, ATTEMPT, 1, "tool_result"))
    worker.commit()
    return f"generation {row[0]}, no lock, before the takeover", appended


def plain_one_statement(
    worker: Connection,
    taker: Connection,
    *,
    observer: Connection,
    holder: Connection,
    background: Callable[[Callable[[], Any]], Future[Any]],
) -> tuple[str, bool]:
    holder.execute("SELECT pg_advisory_lock(%s)", (BARRIER_KEY,))

    def guarded() -> int:
        inserted = worker.execute(_GUARDED_INSERT, (RUN, ATTEMPT, 1, BARRIER_KEY)).rowcount
        worker.commit()
        return inserted

    statement = background(guarded)
    wait_until_blocked(observer, worker.info.backend_pid)
    takeover_statements(taker, locking=False)
    taker.commit()
    holder.execute("SELECT pg_advisory_unlock(%s)", (BARRIER_KEY,))
    inserted = statement.result(timeout=DEADLINE_SECONDS)
    return "the guard, inside a statement that began before the takeover", inserted == 1


def locked_worker_first(
    worker: Connection,
    taker: Connection,
    *,
    observer: Connection,
    background: Callable[[Callable[[], Any]], Future[Any]],
    **_: Any,
) -> tuple[str, bool]:
    row = worker.execute(_READ + " FOR UPDATE", (RUN, ATTEMPT)).fetchone()
    assert row is not None

    def takeover() -> None:
        takeover_statements(taker, locking=True)
        taker.commit()

    taking = background(takeover)
    wait_until_blocked(observer, taker.info.backend_pid)
    appended = row[0] == 1
    if appended:
        worker.execute(_INSERT, (RUN, ATTEMPT, 1, "tool_result"))
    worker.commit()
    taking.result(timeout=DEADLINE_SECONDS)
    return f"generation {row[0]}, row locked, the takeover waiting", appended


def locked_takeover_first(
    worker: Connection,
    taker: Connection,
    *,
    observer: Connection,
    background: Callable[[Callable[[], Any]], Future[Any]],
    **_: Any,
) -> tuple[str, bool]:
    takeover_statements(taker, locking=True)

    def locking_read() -> int:
        row = worker.execute(_READ + " FOR UPDATE", (RUN, ATTEMPT)).fetchone()
        assert row is not None
        return row[0]

    reading = background(locking_read)
    wait_until_blocked(observer, worker.info.backend_pid)
    taker.commit()
    generation = reading.result(timeout=DEADLINE_SECONDS)
    appended = generation == 1
    if appended:
        worker.execute(_INSERT, (RUN, ATTEMPT, 1, "tool_result"))
    worker.commit()
    return f"generation {generation}, after waiting on the takeover's lock", appended


FORMS: tuple[tuple[str, Callable[..., tuple[str, bool]], bool], ...] = (
    ("plain, read then insert", plain_read_then_insert, True),
    ("plain, one guarded statement", plain_one_statement, True),
    ("locked, worker first", locked_worker_first, False),
    ("locked, takeover first", locked_takeover_first, False),
)


def main() -> None:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL names the local PostgreSQL; it is unset")
    schema = f"lock_race_{uuid.uuid4().hex[:8]}"
    options = f"-c search_path={schema}"

    def connect(*, autocommit: bool) -> Connection:
        return psycopg.connect(url, autocommit=autocommit, options=options)

    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(f"CREATE SCHEMA {schema}")
        try:
            with (
                connect(autocommit=True) as observer,
                connect(autocommit=True) as holder,
                ThreadPoolExecutor(max_workers=1) as pool,
            ):
                observer.execute(_SETUP)
                version = observer.execute("SHOW server_version").fetchone()
                isolation = observer.execute("SHOW default_transaction_isolation").fetchone()
                assert version is not None and isolation is not None
                print(f"PostgreSQL {version[0]}, default isolation {isolation[0]}\n")
                results: list[Observed] = []
                for form, sequence, forecast_stale in FORMS:
                    observer.execute("TRUNCATE events RESTART IDENTITY; DELETE FROM attempts")
                    observer.execute("INSERT INTO attempts VALUES (%s, %s, 1)", (RUN, ATTEMPT))
                    observer.execute(_INSERT, (RUN, ATTEMPT, 1, "segment_started"))
                    with connect(autocommit=False) as worker, connect(autocommit=False) as taker:
                        read, appended = sequence(
                            worker, taker, observer=observer, holder=holder, background=pool.submit
                        )
                    log = observer.execute("SELECT generation, kind FROM events ORDER BY seq")
                    results.append(Observed(form, read, appended, tuple(log), forecast_stale))
        finally:
            admin.execute(f"DROP SCHEMA {schema} CASCADE")

    for result in results:
        print(result.form)
        print(f"  the worker read      {result.worker_read}")
        print(f"  the worker appended  {'yes' if result.worker_appended else 'no'}")
        print("  the log, in order    " + ", ".join(f"g{g} {kind}" for g, kind in result.log))
        stale = result.stale_after_takeover
        met = "met" if stale == result.forecast_stale else "NOT MET"
        print(
            f"  old generation after the takeover: {'yes' if stale else 'no'} "
            f"(forecast {'yes' if result.forecast_stale else 'no'}, {met})\n"
        )


if __name__ == "__main__":
    main()
