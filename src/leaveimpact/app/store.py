"""The demo surface's own PostgreSQL module: the app schema beside the run log, bootstrapped
by the deploy and checked by every read, over connections bounded on the connect and on
each statement.

The surface serves a replay only when an app-owned table of publishable attempts holds it
(the demo milestone's publishability ruling); that table and its version row live here, in
``schema.sql`` beside this module, and never in the log's schema, so the investigator's
store learns nothing about what the demo publishes. The log store keeps one connection for
a worker's lifetime under a ten-second connect timeout and no statement bound, the right
discipline for a process that owns one attempt and the wrong one for a web request: this
store opens a fresh connection per operation, three seconds to connect and three per
statement, and closes it before returning, so a request holds nothing while a browser
waits and a blocked statement ends the request instead of a thread. The bounds are per
statement, not per request: an operation of this module makes one statement, and a page
that performs several operations is bounded by their sum, which each route's docstring
states.

Two refusals, by name and never by driver message: ``AppStoreUnavailable`` when the store
did not answer within either bound (a cancelled statement is an operational error to the
driver, so the next read starts clean), and ``AppStoreInvariantBroken`` when the database
holds no app schema or another version, which the bootstrap and the content reads raise
and the readiness read reports as a state. Nothing here repairs: ``ensure_schema`` is the
one writer of the layout, run by the deploy's bootstrap line, and a read that finds the
schema missing says so rather than creating it, since a read that mended state would hide
a deploy that skipped the step (the readiness ruling).
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from importlib import resources
from typing import Any

import psycopg

Connection = psycopg.Connection[Any]
Connect = Callable[[str], Connection]

SCHEMA_VERSION = 1
"""The layout this code writes and reads; a database at another version is refused. The
number names the layout and nothing else, advancing with every change to the DDL that
lands in a commit."""

CONNECT_TIMEOUT_S = 3
STATEMENT_TIMEOUT_MS = 3000
"""Each statement's bound and the connect's, chosen with the corpus adapter's readiness
read so a route making one statement of each answers inside the probes' eight-second
client timeout; the readiness route makes two reads on two connections, and its worst
case, twelve seconds, is stated at the route."""

_SELECT_VERSION = "SELECT version FROM app_schema"
_INSERT_VERSION = "INSERT INTO app_schema (version) VALUES (%s) ON CONFLICT DO NOTHING"


class AppStoreUnavailable(Exception):
    """The store did not answer within the connect or the statement bound."""


class AppStoreInvariantBroken(Exception):
    """The database holds no app schema or one this code does not read."""


def connect_bounded(dsn: str) -> Connection:
    """A fresh autocommit connection bounded on the connect and on every statement."""
    return psycopg.connect(
        dsn,
        connect_timeout=CONNECT_TIMEOUT_S,
        options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS}",
        autocommit=True,
    )


class AppStore:
    """The app schema over one database; construction does no I/O, every operation opens
    and closes its own bounded connection."""

    def __init__(self, *, dsn: str, connect: Connect = connect_bounded) -> None:
        self._dsn = dsn
        self._connect = connect

    def ensure_schema(self) -> None:
        """The tables created where missing and the version row written where absent, then
        the version checked; never alters an existing table. ``AppStoreInvariantBroken``
        when the database holds another version, ``AppStoreUnavailable`` when it does not
        answer."""
        ddl = resources.files(__package__).joinpath("schema.sql").read_text(encoding="utf-8")
        with self._connection() as conn:
            try:
                with conn.transaction():
                    conn.execute(ddl.encode())
                    conn.execute(_INSERT_VERSION, (SCHEMA_VERSION,))
            except psycopg.errors.UndefinedTable as exc:
                # The publishable table references the log's attempt row, so the DDL needs
                # the log's schema first; the deploy runs the two bootstraps in that order.
                raise AppStoreInvariantBroken(
                    "the run log is not bootstrapped: the publishable table references its "
                    "attempt table; run `python -m leaveimpact.agent bootstrap-log` first"
                ) from exc
            version = _version_of(conn)
        if version != SCHEMA_VERSION:
            raise AppStoreInvariantBroken(
                f"this code reads and writes app schema version {SCHEMA_VERSION}, the database "
                f"holds version {version}"
            )

    def schema_supported(self) -> bool:
        """Whether the database holds the app schema at this code's version: the readiness
        route's third bit. False for a missing table or another version, never an
        exception, since a deploy that skipped the bootstrap is a state the route reports;
        ``AppStoreUnavailable`` when the store does not answer."""
        with self._connection() as conn:
            return _version_of(conn) == SCHEMA_VERSION

    @contextmanager
    def _connection(self) -> Generator[Connection]:
        try:
            with self._connect(self._dsn) as conn:
                yield conn
        except psycopg.OperationalError as exc:
            raise AppStoreUnavailable(
                f"the app store did not answer: {type(exc).__name__}"
            ) from exc


def _version_of(conn: Connection) -> int | None:
    """The version row, ``None`` for a database with no app schema or no version row."""
    try:
        row = conn.execute(_SELECT_VERSION).fetchone()
    except psycopg.errors.UndefinedTable:
        return None
    return None if row is None else int(row[0])
