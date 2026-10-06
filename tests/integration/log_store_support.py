"""Support for the event log store's integration tests: a throwaway schema per test, stores
over it with the seams the tests drive, and the barrier a two-connection test holds a side at.

The store is the project's own system, so there is no cassette: the tests run against the
real PostgreSQL the suite is configured with (``DATABASE_URL``; the Compose service in CI,
``just db-up`` on a laptop) and skip without it, failing under ``CI``. Each test gets a
PostgreSQL schema of its own, named into every connection's ``search_path``, so the store's
unqualified table names land there and tests never read one another; the schema is dropped
whole at the end, the way the lock-race probe isolated its run.

*The clock.* A scripted clock hands the store the timestamps a fixture's history recorded,
one per command in order, so the sixteen histories replay through the store and rebuild
their exports exactly; the default clock is the database's.

*The barrier.* The store calls its ``boundary`` seam at ``locked``, ``decided`` and
``before-commit``. ``Hold`` blocks a store's thread at one named point until the test
releases it, and ``wait_until_blocked`` returns once the server's own activity view shows
the other connection waiting on a lock, so an interleaving is driven to one order with no
sleep anywhere.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from leaveimpact.agent.log_store import LogStore
from tests.integration.corpus_support import database_url

Connection = psycopg.Connection[Any]

DEADLINE_SECONDS = 10.0


@dataclass
class Scripted:
    """A clock that returns the given instants in order, one per call, and fails loudly when
    asked for more than it was given."""

    instants: list[datetime]
    given: int = 0

    def __call__(self, conn: Connection) -> datetime:
        if self.given >= len(self.instants):
            raise AssertionError(f"the scripted clock was asked for instant {self.given + 1}")
        at = self.instants[self.given]
        self.given += 1
        return at


@dataclass
class Hold:
    """A boundary that blocks at ``at`` until released; ``reached`` is set when it arrives."""

    at: str
    reached: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)

    def __call__(self, name: str) -> None:
        if name != self.at:
            return
        self.reached.set()
        if not self.release.wait(DEADLINE_SECONDS):
            raise AssertionError(f"held at {self.at!r} and never released")

    def wait_reached(self) -> None:
        if not self.reached.wait(DEADLINE_SECONDS):
            raise AssertionError(f"the boundary {self.at!r} was never reached")


@dataclass
class Rig:
    """One test's schema and the connections it opened, by the store that opened them."""

    url: str
    schema: str
    connections: dict[int, Connection] = field(default_factory=dict[int, Connection])
    opened: int = 0

    def connect_for(self, key: int) -> Callable[[str], Connection]:
        def connect(dsn: str) -> Connection:
            conn = psycopg.connect(
                dsn, connect_timeout=5, autocommit=True, options=f"-c search_path={self.schema}"
            )
            self.connections[key] = conn
            return conn

        return connect

    def store(
        self,
        *,
        clock: Callable[[Connection], datetime] | None = None,
        boundary: Callable[[str], None] | None = None,
    ) -> LogStore:
        self.opened += 1
        key = self.opened
        extra: dict[str, Any] = {}
        if clock is not None:
            extra["clock"] = clock
        if boundary is not None:
            extra["boundary"] = boundary
        return LogStore(dsn=self.url, connect=self.connect_for(key), **extra)

    def backend_pid(self, store: LogStore) -> int:
        """The server pid of ``store``'s connection, once it has opened one."""
        deadline = time.monotonic() + DEADLINE_SECONDS
        while time.monotonic() < deadline:
            conn = _connection_of(store)
            if conn is not None:
                return int(conn.info.backend_pid)
        raise AssertionError("the store never opened a connection")

    def observer(self) -> Connection:
        return psycopg.connect(self.url, connect_timeout=5, autocommit=True)


def _connection_of(store: LogStore) -> Connection | None:
    # The store keeps its connection private; a test rig reads it to find the backend pid
    # the activity view reports, which is no part of the store's contract.
    return getattr(store, "_connection")  # noqa: B009 - a private attribute, read on purpose


def wait_until_blocked(observer: Connection, pid: int) -> None:
    """Return once the server reports backend ``pid`` waiting on a lock (the probe's wait)."""
    deadline = time.monotonic() + DEADLINE_SECONDS
    while time.monotonic() < deadline:
        row = observer.execute(
            "SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", (pid,)
        ).fetchone()
        if row is not None and row[0] == "Lock":
            return
    raise AssertionError(f"backend {pid} was expected to wait on a lock and never did")


def rig_for(url: str) -> Iterator[Rig]:
    """A schema of its own, its tables ensured; dropped whole afterwards."""
    schema = f"log_store_{uuid4().hex[:12]}"
    with psycopg.connect(url, connect_timeout=5, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    rig = Rig(url, schema)
    try:
        setup = rig.store()
        setup.ensure_schema()
        setup.close()
        yield rig
    finally:
        for conn in rig.connections.values():
            with suppress(psycopg.Error):
                conn.close()
        with psycopg.connect(url, connect_timeout=5, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def rig() -> Iterator[Rig]:
    yield from rig_for(database_url())


__all__ = ["Hold", "Rig", "Scripted", "rig", "rig_for", "wait_until_blocked"]
