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
statement, not per request: each operation of this module states how many statements it
makes (the reads one, the publication up to three), and a page that performs several
operations is bounded by their sum, which each route's docstring states.

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
from dataclasses import dataclass
from importlib import resources
from typing import Any

import psycopg

from leaveimpact.app.public import PublicationDraft, PublicId, PublishableRow
from leaveimpact.core.ids import ScenarioId, WorldVersion

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
_ROW = (
    "public_id, run_id, attempt, world_version, scenario_id, title, published_at, published_by"
)
_SELECT_ROWS_FOR = (
    f"SELECT {_ROW} FROM publishable_attempt WHERE world_version = %s "
    "ORDER BY published_at, public_id"
)
_SELECT_ROW = f"SELECT {_ROW} FROM publishable_attempt WHERE public_id = %s"
_SELECT_ROW_OF_ATTEMPT = (
    f"SELECT {_ROW} FROM publishable_attempt WHERE run_id = %s AND attempt = %s"
)
# The timestamp is the database's clock, as every stamp of the log is (the log store's
# rule: the store reads the database's clock and never the machine's).
_INSERT_ROW = (
    "INSERT INTO publishable_attempt "
    "(public_id, run_id, attempt, world_version, scenario_id, title, published_at, published_by) "
    f"VALUES (%s, %s, %s, %s, %s, %s, now(), %s) RETURNING {_ROW}"
)


class AppStoreUnavailable(Exception):
    """The store did not answer within the connect or the statement bound."""


class AppStoreInvariantBroken(Exception):
    """The database holds no app schema or one this code does not read."""


# --- the publication's outcomes ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Published:
    """The row this call wrote."""

    row: PublishableRow


@dataclass(frozen=True, slots=True)
class AlreadyPublished:
    """The same publication, written earlier: a repeat that changes nothing, the first
    timestamp kept."""

    row: PublishableRow


@dataclass(frozen=True, slots=True)
class SlugTaken:
    """The public id names another attempt."""

    existing: PublishableRow


@dataclass(frozen=True, slots=True)
class AttemptPublished:
    """The attempt is already published under another public id."""

    existing: PublishableRow


@dataclass(frozen=True, slots=True)
class PublicationConflict:
    """The same public id and attempt with another title or author: the repeat disagrees
    with the row and nothing is changed."""

    existing: PublishableRow


PublishOutcome = Published | AlreadyPublished | SlugTaken | AttemptPublished | PublicationConflict


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

    # --- the publishable table ---------------------------------------------------------

    def rows_for(self, world_version: WorldVersion) -> tuple[PublishableRow, ...]:
        """Every published row of ``world_version``, oldest first and by name within one
        instant: the listing's projection, which reads no log. One statement."""
        with self._connection() as conn:
            rows = conn.execute(_SELECT_ROWS_FOR, (world_version,)).fetchall()
        return tuple(_row_of(row) for row in rows)

    def row_of(self, public_id: PublicId) -> PublishableRow | None:
        """The row ``public_id`` names, ``None`` when none does. One statement."""
        with self._connection() as conn:
            row = conn.execute(_SELECT_ROW, (public_id,)).fetchone()
        return None if row is None else _row_of(row)

    def publish(self, draft: PublicationDraft) -> PublishOutcome:
        """Write ``draft``'s row, or say why it was not written. The insert is attempted
        first and the two uniqueness constraints decide the races: a public id taken or an
        attempt already published raises on the server, and the rows then read back say
        which, so two operators publishing at once get the same answers one after another
        would. A repeat identical to the row is ``AlreadyPublished`` with the first
        timestamp; the same id and attempt with another title or author is
        ``PublicationConflict``; nothing here updates or deletes. Up to three statements."""
        with self._connection() as conn:
            try:
                written = conn.execute(
                    _INSERT_ROW,
                    (
                        draft.public_id,
                        draft.run_id,
                        draft.attempt,
                        draft.world_version,
                        draft.scenario_id,
                        draft.title,
                        draft.published_by,
                    ),
                ).fetchone()
            except psycopg.errors.UniqueViolation:
                by_id = conn.execute(_SELECT_ROW, (draft.public_id,)).fetchone()
                by_attempt = conn.execute(
                    _SELECT_ROW_OF_ATTEMPT, (draft.run_id, draft.attempt)
                ).fetchone()
                return _refusal_of(
                    draft,
                    None if by_id is None else _row_of(by_id),
                    None if by_attempt is None else _row_of(by_attempt),
                )
        assert written is not None, "an insert with RETURNING yields its row"
        return Published(_row_of(written))

    @contextmanager
    def _connection(self) -> Generator[Connection]:
        try:
            with self._connect(self._dsn) as conn:
                yield conn
        except psycopg.OperationalError as exc:
            raise AppStoreUnavailable(
                f"the app store did not answer: {type(exc).__name__}"
            ) from exc


def _refusal_of(
    draft: PublicationDraft, by_id: PublishableRow | None, by_attempt: PublishableRow | None
) -> AlreadyPublished | SlugTaken | AttemptPublished | PublicationConflict:
    """Which uniqueness the insert hit, read off the rows that hold the draft's id and its
    attempt. The id's row is read first: when it names this attempt the question is whether
    the content agrees; when it names another, the id is taken whatever the attempt's
    standing; only an id nobody holds leaves the attempt's other row as the reason."""
    if by_id is not None:
        if (by_id.run_id, by_id.attempt) != (draft.run_id, draft.attempt):
            return SlugTaken(by_id)
        return AlreadyPublished(by_id) if by_id.agrees_with(draft) else PublicationConflict(by_id)
    assert by_attempt is not None, "a uniqueness violation names a row"
    return AttemptPublished(by_attempt)


def _row_of(row: tuple[Any, ...]) -> PublishableRow:
    public_id, run_id, attempt, world_version, scenario_id, title, published_at, published_by = row
    return PublishableRow(
        PublicId(str(public_id)),
        str(run_id),
        int(attempt),
        WorldVersion(str(world_version)),
        ScenarioId(str(scenario_id)),
        None if title is None else str(title),
        published_at,
        str(published_by),
    )


def _version_of(conn: Connection) -> int | None:
    """The version row, ``None`` for a database with no app schema or no version row."""
    try:
        row = conn.execute(_SELECT_VERSION).fetchone()
    except psycopg.errors.UndefinedTable:
        return None
    return None if row is None else int(row[0])
