"""The corpus adapter: the document reader and writer over PostgreSQL, and the schema bootstrap.

One class implements both document ports, because the read and the write side share
a connection and a world version; which side a caller holds is the type it is handed.
Construction does no I/O: the connection string and the configuration are two values,
and the connection opens on the first call.

**Scope.** Every statement filters by the configured world version and every insert
plants it, so one database holds a world per version, and the integration tests a
world per test, without one reading another. The identity map is the domain id
itself: the corpus is the project's own system, so its keys are the world's and
nothing translates.

**Search is full text and derives nothing.** The section table carries a generated
``tsvector`` over the body under the English configuration with a GIN index; a query
is parsed by ``websearch_to_tsquery`` (quoted phrases, ``-`` for exclusion, plain
words as AND), each matching section is ranked by the built-in ``ts_rank``, a
document takes its best section's rank, and the order is that rank descending with
the document id ascending as the stable tie-break, so the same corpus and query give
the same list on any machine. Effective dates are not applied: the port says the
caller keeps the documents effective at ``now``. Whether retrieval stays full text is
the investigator milestone's question, and this module is the one place that changes.

**Bootstrap, never migration.** ``ensure_schema`` applies the idempotent DDL beside
this module (``schema.sql``) and is called by the composition root, the way the Frappe
site schema and the Jira fields are; it never alters an existing table, because a
corpus is regenerated from the world bundle and a schema change is a new world
version.

**One document is one write.** The document row and its section rows land in one
transaction, so a document never exists without its sections; a duplicate id, of the
document or of a clause, is a constraint violation raised loud as ``ValueError`` with
the database error chained, the same rule the in-memory fake states — the writer adds
and never finds, and a second add of one id is the caller's bug.

**Faults.** A connection that cannot be opened, or one that fails under a statement,
is ``SourceUnreachable`` with the driver error chained and no retry on the wire: the
corpus runs beside the application on one host, so a connection fault is the host's
condition and a second attempt a moment later tells nothing new; the projector
restarts find-or-create. The failed connection is discarded so the next call opens a
fresh one. A row the translation cannot read is ``MalformedRecord`` (``records``).
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from importlib import resources
from typing import Any

import psycopg

from leaveimpact.adapters.corpus import records
from leaveimpact.core.entities import Document
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import DocumentId, WorldVersion
from leaveimpact.core.ports.errors import SourceUnreachable
from leaveimpact.core.ports.observed import Observed

Connection = psycopg.Connection[Any]
Connect = Callable[[str], Connection]
SEARCH_CONFIGURATION = "english"
_CONNECT_TIMEOUT_S = 10

_SELECT_DOCUMENT = """
    SELECT id, title, kind, effective_from FROM document
    WHERE world_version = %s AND id = %s
"""
_SELECT_SECTIONS = """
    SELECT id, position, body FROM section
    WHERE world_version = %s AND document_id = %s
    ORDER BY position
"""
_SEARCH = f"""
    SELECT document_id, max(ts_rank(search, query)) AS rank
    FROM section, websearch_to_tsquery('{SEARCH_CONFIGURATION}', %s) AS query
    WHERE world_version = %s AND search @@ query
    GROUP BY document_id
    ORDER BY rank DESC, document_id ASC
    LIMIT %s
"""
_INSERT_DOCUMENT = """
    INSERT INTO document (world_version, id, title, kind, effective_from)
    VALUES (%s, %s, %s, %s, %s)
"""
_INSERT_SECTION = """
    INSERT INTO section (world_version, id, document_id, position, body)
    VALUES (%s, %s, %s, %s, %s)
"""


@dataclass(frozen=True, slots=True)
class CorpusConfig:
    """The world version the adapter reads and writes under."""

    world_version: WorldVersion


def _connect(dsn: str) -> Connection:
    return psycopg.connect(dsn, connect_timeout=_CONNECT_TIMEOUT_S)


class CorpusAdapter:
    """Document reader and writer over one PostgreSQL database, scoped to one world version."""

    def __init__(self, *, dsn: str, config: CorpusConfig, connect: Connect = _connect) -> None:
        self._dsn = dsn
        self._config = config
        self._connect = connect
        self._connection: Connection | None = None

    @property
    def config(self) -> CorpusConfig:
        return self._config

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    # --- the read side --------------------------------------------------------------

    def document(self, id: DocumentId) -> Observed[Document] | None:
        world = self._config.world_version
        with self._guarded() as conn:
            row = conn.execute(_SELECT_DOCUMENT, (world, id)).fetchone()
            if row is None:
                return None
            sections = conn.execute(_SELECT_SECTIONS, (world, id)).fetchall()
        return Observed(records.document_from_rows(row, sections, world), Source.CORPUS)

    def search(self, query: str, *, limit: int) -> tuple[Observed[Document], ...]:
        if limit < 0:
            raise ValueError(f"limit must not be negative, got {limit}")
        if limit == 0:
            return ()
        world = self._config.world_version
        with self._guarded() as conn:
            hits = conn.execute(_SEARCH, (query, world, limit)).fetchall()
        found: list[Observed[Document]] = []
        for document_id, _ in hits:
            observed = self.document(DocumentId(str(document_id)))
            assert observed is not None, "a ranked section's document exists by foreign key"
            found.append(observed)
        return tuple(found)

    # --- the write side -------------------------------------------------------------

    def add_document(self, document: Document) -> str:
        """The document row and every section row in one transaction; returns the locator."""
        world = self._config.world_version
        where = records.locator(world, document.id)
        with self._guarded() as conn:
            try:
                with conn.transaction():
                    conn.execute(_INSERT_DOCUMENT, records.document_params(document, world))
                    for params in records.section_params(document, world):
                        conn.execute(_INSERT_SECTION, params)
            except psycopg.errors.IntegrityError as exc:
                raise ValueError(
                    f"{where} or one of its clause ids already exists in world {world}"
                ) from exc
        return where

    # --- preparation: the schema ------------------------------------------------------

    def ensure_schema(self) -> None:
        """The two tables and the search index, created where missing; never altered."""
        ddl = resources.files(__package__).joinpath("schema.sql").read_text(encoding="utf-8")
        with self._guarded() as conn, conn.transaction():
            # As bytes: the driver's query type admits a literal or bytes, and the file
            # beside this module is source, not input.
            conn.execute(ddl.encode())

    # --- the connection ---------------------------------------------------------------

    @contextmanager
    def _guarded(self) -> Generator[Connection]:
        """The connection for one call: opened if needed, a fault on the way out the port's."""
        if self._connection is None:
            try:
                self._connection = self._connect(self._dsn)
            except psycopg.OperationalError as exc:
                raise SourceUnreachable(
                    Source.CORPUS, f"connection refused: {type(exc).__name__}"
                ) from exc
        try:
            yield self._connection
        except psycopg.OperationalError as exc:
            self._drop()
            raise SourceUnreachable(
                Source.CORPUS, f"statement failed: {type(exc).__name__}"
            ) from exc

    def _drop(self) -> None:
        """Discard a connection that failed; the next call opens a fresh one."""
        if self._connection is not None:
            with suppress(psycopg.Error):
                self._connection.close()
            self._connection = None
