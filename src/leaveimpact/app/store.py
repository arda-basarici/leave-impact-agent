"""The demo surface's own PostgreSQL module: the app schema beside the run log, bootstrapped
by the deploy and checked by every read, over connections bounded on the connect and on
each statement.

The surface serves a replay only when an app-owned table of publishable attempts holds it
(the demo milestone's publishability ruling); that table, the live table beside it (one
row per attempt a visitor started: the capability's hash and the decision as recorded, the
live-path commands step) and the version row live here, in ``schema.sql`` beside this
module, and never in the log's schema, so the investigator's store learns nothing about
what the demo publishes. The public start's two rows are written together in one
transaction here (``start_section``); the start's rules serialize on the log store's own
connection, the one that commits the admission, and never here. The log store keeps one
connection for a worker's lifetime under a ten-second connect timeout and no statement
bound, the right
discipline for a process that owns one attempt and the wrong one for a web request: this
store opens a fresh connection per operation, three seconds to connect and three per
statement, and closes it before returning, so a request holds nothing while a browser
waits and a blocked statement ends the request instead of a thread. The bounds are per
statement, not per request: each operation of this module states how many statements it
makes (the version check first, then the reads one and the publication up to three), and a
page that performs several operations is bounded by their sum, which each route's docstring
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
from dataclasses import dataclass
from importlib import resources
from typing import Any, cast

import psycopg

from leaveimpact.app.live import Decision, LiveDraft, LiveRow
from leaveimpact.app.public import PublicationDraft, PublicId, PublishableRow
from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.jsonshape import JsonObject

Connection = psycopg.Connection[Any]
Connect = Callable[[str], Connection]
Boundary = Callable[[str], None]
"""The seam a test holds a side at, called with the point's name: the start's section at
``start-before-commit`` (the rows written, the transaction open), where a test lets the
process die with the log's admission committed and the rows lost; a no-op by default."""

SCHEMA_VERSION = 3
"""The layout this code writes and reads; a database at another version is refused. The
number names the layout and nothing else, advancing with every change to the DDL that
lands in a commit. Version 2 (the demo milestone's backup step) added the ``ledger_capture``
view and nothing else; version 3 (the live-path commands step) added the ``live_attempt``
table and nothing else."""

ADVANCED_FROM: frozenset[int] = frozenset({1, 2})
"""The earlier versions the bootstrap brings to ``SCHEMA_VERSION`` by applying the DDL as it
stands: every change between them was additive (a view created or replaced, a table created
where missing), so the one idempotent DDL file is the whole migration and no step alters a
row of data. A version outside this set and not the current one is refused as before, since
the DDL says nothing about how to reach the current layout from it; a change that is not
additive gets its own migration statement and this set is reset to the versions it reaches."""

CONNECT_TIMEOUT_S = 3
STATEMENT_TIMEOUT_MS = 3000
"""Each statement's bound and the connect's, chosen with the corpus adapter's readiness
read so a route making one statement of each answers inside the probes' eight-second
client timeout; the readiness route makes two reads on two connections, and its worst
case, twelve seconds, is stated at the route."""

_SELECT_VERSION = "SELECT version FROM app_schema"
_INSERT_VERSION = "INSERT INTO app_schema (version) VALUES (%s) ON CONFLICT DO NOTHING"
_ADVANCE_VERSION = "UPDATE app_schema SET version = %s WHERE version = ANY(%s)"
_SELECT_CAPTURE = (
    "SELECT coalesce(jsonb_agg(c ORDER BY c.ledger_id), '[]'::jsonb) FROM ledger_capture c"
)
"""The platform's backup script reads the view with this exact statement (the
exchange of 2026-10-23); the restore drill reads it the same way so the two compare equal."""
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
# The start's publishable row carries the admission's instant, not the clock's: the row
# and the live row beside it say the one moment the log recorded.
_INSERT_ROW_AT = (
    "INSERT INTO publishable_attempt "
    "(public_id, run_id, attempt, world_version, scenario_id, title, published_at, published_by) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
)
_LIVE ="public_id, run_id, attempt, key_digest, started_at, decision, decided_at"
_SELECT_LIVE = f"SELECT {_LIVE} FROM live_attempt WHERE public_id = %s"
_SELECT_LIVE_OF_ATTEMPT = f"SELECT {_LIVE} FROM live_attempt WHERE run_id = %s AND attempt = %s"
_INSERT_LIVE = (
    "INSERT INTO live_attempt (public_id, run_id, attempt, key_digest, started_at) "
    f"VALUES (%s, %s, %s, %s, %s) RETURNING {_LIVE}"
)


def _no_boundary(name: str) -> None:
    return None


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

    def __init__(
        self, *, dsn: str, connect: Connect = connect_bounded, boundary: Boundary = _no_boundary
    ) -> None:
        self._dsn = dsn
        self._connect = connect
        self._boundary = boundary

    def ensure_schema(self) -> None:
        """The version read first and a database at a version this code neither writes nor
        advances from refused before anything is applied; then, in one transaction, the
        tables created where missing and the view replaced, the version row written where
        absent or advanced from a version in ``ADVANCED_FROM``, and the version checked
        again; never alters an existing table. The read comes first because the DDL
        replaces the view: a rollback to older code bootstrapping a newer database would
        otherwise put the older view under the newer version row and then refuse, a state
        the version row cannot see. The transaction means a database is at its old version
        with its old layout or at the new one with the new, never between.
        ``AppStoreInvariantBroken`` when the database holds another version,
        ``AppStoreUnavailable`` when it does not answer."""
        ddl = resources.files(__package__).joinpath("schema.sql").read_text(encoding="utf-8")
        with self._connection(check_version=False) as conn:
            held = _version_of(conn)
            if held is not None and held != SCHEMA_VERSION and held not in ADVANCED_FROM:
                raise AppStoreInvariantBroken(
                    f"this code reads and writes app schema version {SCHEMA_VERSION}, the "
                    f"database holds version {held}, which it does not advance from; nothing "
                    "was applied"
                )
            try:
                with conn.transaction():
                    conn.execute(ddl.encode())
                    conn.execute(_INSERT_VERSION, (SCHEMA_VERSION,))
                    conn.execute(_ADVANCE_VERSION, (SCHEMA_VERSION, sorted(ADVANCED_FROM)))
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
        with self._connection(check_version=False) as conn:
            return _version_of(conn) == SCHEMA_VERSION

    def ledger_capture(self) -> list[JsonObject]:
        """The ``ledger_capture`` view's rows as the backup script records them: one JSON
        object per ledger, ordered by ledger id, the keys in the server's canonical order,
        so a restored database's read compares with the recorded capture by equality. The
        version check and one statement."""
        with self._connection() as conn:
            row = conn.execute(_SELECT_CAPTURE).fetchone()
        assert row is not None, "an aggregate answers one row"
        rows = row[0]
        if not isinstance(rows, list):
            raise AppStoreInvariantBroken(
                f"the ledger capture decoded as {type(rows).__name__}, not a list of rows"
            )
        return cast(list[JsonObject], rows)

    # --- the publishable table ---------------------------------------------------------

    def rows_for(self, world_version: WorldVersion) -> tuple[PublishableRow, ...]:
        """Every published row of ``world_version``, oldest first and by name within one
        instant: the listing's projection, which reads no log. The version check and one
        statement."""
        with self._connection() as conn:
            rows = conn.execute(_SELECT_ROWS_FOR, (world_version,)).fetchall()
        return tuple(_row_of(row) for row in rows)

    def row_of(self, public_id: PublicId) -> PublishableRow | None:
        """The row ``public_id`` names, ``None`` when none does. The version check and one
        statement."""
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
        ``PublicationConflict``; nothing here updates or deletes. The version check and up to
        three statements."""
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

    # --- the live table ----------------------------------------------------------------

    def live_row_of(self, public_id: PublicId) -> LiveRow | None:
        """The live row ``public_id`` names, ``None`` when the attempt was not started by a
        visitor (a replay the operator published has none). The version check and one
        statement."""
        with self._connection() as conn:
            row = conn.execute(_SELECT_LIVE, (public_id,)).fetchone()
        return None if row is None else _live_of(row)

    @contextmanager
    def start_section(self) -> Generator[StartSection]:
        """The rows of one started attempt, written in one transaction on one connection:
        the yielded writer reads a live row by attempt and writes the publishable row and
        the live row together; the transaction commits when the block ends and rolls back
        on an exception leaving it, so the two rows exist together or not at all. This
        section serializes nothing: the public start's rules and the log's admission run
        under the log store's own session-level lock, on the connection that commits the
        admission, and this block is entered after that admission committed (the live-path
        commands step, fork 1 as amended at group 2's external read: a lock on this
        store's connection died with that connection while the admission went on to
        commit). A crash before the block ends leaves the admission with no rows, the
        orphan the next start counts from the log and the sweeper closes at the wait's
        deadline. The version check and the writer's statements, each under the statement
        bound."""
        with self._connection() as conn, conn.transaction():
            yield StartSection(conn)
            self._boundary("start-before-commit")

    @contextmanager
    def _connection(self, *, check_version: bool = True) -> Generator[Connection]:
        """One operation's connection, the schema version checked on it first unless the
        operation is the check itself or the bootstrap: a database at another layout
        refuses every read and write of the publishable table, as the log store refuses on
        every connection, so an unready schema never serves a page or takes a row while the
        readiness route says 503 (the step's external read)."""
        try:
            with self._connect(self._dsn) as conn:
                if check_version:
                    version = _version_of(conn)
                    if version != SCHEMA_VERSION:
                        raise AppStoreInvariantBroken(
                            f"this code reads and writes app schema version {SCHEMA_VERSION}, "
                            f"the database holds {'none' if version is None else version}; run "
                            "`python -m leaveimpact.app bootstrap`"
                        )
                yield conn
        except psycopg.OperationalError as exc:
            raise AppStoreUnavailable(
                f"the app store did not answer: {type(exc).__name__}"
            ) from exc
        except psycopg.errors.UndefinedTable as exc:
            # A read of the publishable table on a database the bootstrap never reached:
            # the readiness route reports it as a state, and a page answers 503, never a
            # driver's traceback.
            raise AppStoreInvariantBroken(
                "the app schema is not bootstrapped: run `python -m leaveimpact.app bootstrap`"
            ) from exc


class StartSection:
    """The writer a start holds inside its critical section: the live rows read and
    written on the section's connection, inside its transaction, so a crash before the
    block ends leaves none of them."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def live_row_of_attempt(self, run_id: str, attempt: int) -> LiveRow | None:
        """The live row of ``attempt`` of ``run_id``, ``None`` when the start that admitted
        it never wrote one (a crash between the log's commit and this section's)."""
        row = self._conn.execute(_SELECT_LIVE_OF_ATTEMPT, (run_id, attempt)).fetchone()
        return None if row is None else _live_of(row)

    def write(self, publishable: PublicationDraft, live: LiveDraft) -> LiveRow:
        """The publishable row and the live row of one started attempt, the publishable
        one dated at the live one's ``started_at``; the two name one attempt and one public
        id, or ``ValueError``. The constraints decide what the section's lock did not: a
        public id or an attempt already in either table raises on the server, an
        invariant of this module and never a visitor's outcome, since the section's rules
        read the log before any write."""
        if (publishable.public_id, publishable.run_id, publishable.attempt) != (
            live.public_id,
            live.run_id,
            live.attempt,
        ):
            raise ValueError("the publishable row and the live row name one attempt")
        self._conn.execute(
            _INSERT_ROW_AT,
            (
                publishable.public_id,
                publishable.run_id,
                publishable.attempt,
                publishable.world_version,
                publishable.scenario_id,
                publishable.title,
                live.started_at,
                publishable.published_by,
            ),
        )
        written = self._conn.execute(
            _INSERT_LIVE,
            (live.public_id, live.run_id, live.attempt, live.key_digest, live.started_at),
        ).fetchone()
        assert written is not None, "an insert with RETURNING yields its row"
        return _live_of(written)


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


def _live_of(row: tuple[Any, ...]) -> LiveRow:
    public_id, run_id, attempt, key_digest, started_at, decision, decided_at = row
    return LiveRow(
        PublicId(str(public_id)),
        str(run_id),
        int(attempt),
        str(key_digest),
        started_at,
        None if decision is None else Decision(str(decision)),
        decided_at,
    )


def _version_of(conn: Connection) -> int | None:
    """The version row, ``None`` for a database with no app schema or no version row."""
    try:
        row = conn.execute(_SELECT_VERSION).fetchone()
    except psycopg.errors.UndefinedTable:
        return None
    return None if row is None else int(row[0])
