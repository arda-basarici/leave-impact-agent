"""The corpus adapter: the document reader over the PostgreSQL cache, scoped to a world
version and a corpus level.

Construction does no I/O: the connection string, the configuration and the level are
values, and the connection opens on the first call. The adapter reads and never writes:
the cache is filled by the loader (``loader``) from a world's sealed documents, which is
cache materialization and not authorship, and a reader that could also write was the
shape the M1 build settled when the generator still projected documents into this
database; since the step 12 corpus ruling the canonical documents are objects in the
world bucket, and the one class holding both ports lost its reason (the M2 step 9 design).

**Scope.** Every statement filters by the configured world version and joins the world's
row on ``ready``, so a version is served whole or not at all; and every statement filters
by the level before anything is ranked. A level is a name the world sealed with a count
into its pool: a document whose ``pool_rank`` is null is scenario-owned and in every
level, and a pool document is in the level exactly when its rank is below the level's
count. The count is resolved once, at the first call, from the ``level`` row the loader
wrote, and a level the world never sealed, or a version the cache does not serve, is
``UnservedCorpus`` naming both: a composition root that configured a version or a level
the cache does not hold is a configuration fault, loud at the first read, never an empty
corpus that grades as absence. The identity map is the domain id itself: the corpus is
the project's own system, so its keys are the world's and nothing translates.

**Search is full text and derives nothing.** The section table carries a generated
``tsvector`` over the body under the English configuration with a GIN index; a query
is parsed by ``websearch_to_tsquery`` (quoted phrases, ``-`` for exclusion, plain
words as AND), each matching section of a document the level holds is ranked by the
built-in ``ts_rank``, a document takes its best section's rank, and the order is that
rank descending with the document id ascending as the stable tie-break, so the same
corpus and query give the same list on any machine. ``ts_rank`` reads the section and the
query alone and no statistic of the table (PostgreSQL's ranking functions use no global
information, and the loader's acceptance test holds a document's order equal at two
levels), so filtering by level before ranking is exactly a corpus of that level's
documents, and the padded level and the base level differ only in what is there to find.
Effective dates are not applied: the port says the caller keeps the documents effective
at ``now``. Whether retrieval stays full text is the investigator milestone's question,
and this module is the one place that changes.

**A read leaves nothing open.** The connection runs in autocommit, because psycopg's
default opens a transaction at the first statement and holds it until a commit, and a
reader that never commits would then see one snapshot for its whole life: a document the
loader committed after the reader's first call would stay invisible until the connection
closed. Autocommit makes each select its own transaction, so the next call sees the
present cache.

**Faults.** A connection that cannot be opened, or one that fails under a statement,
is ``SourceUnreachable`` for the corpus after one attempt, the connection discarded so
the next call opens a fresh one; a row the translation cannot read is ``MalformedRecord``
with the document as locator (``records``). Retries are the caller's, as for every port.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from typing import Any

import psycopg

from leaveimpact.adapters.corpus import records
from leaveimpact.core.entities import Document
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import DocumentId, WorldVersion
from leaveimpact.core.ports.errors import SourceUnreachable
from leaveimpact.core.ports.observed import Observed
from leaveimpact.core.run_record import BASE_CORPUS_LEVEL

Connection = psycopg.Connection[Any]
Connect = Callable[[str], Connection]
SEARCH_CONFIGURATION = "english"
_CONNECT_TIMEOUT_S = 10

# Every read joins the world's row on `ready` and filters the document by the level's
# count: null rank is scenario-owned, a pool document is held when its rank is below it.
_SELECT_LEVEL = """
    SELECT level.filler_count
    FROM level JOIN world USING (world_version)
    WHERE level.world_version = %s AND level.name = %s AND world.ready
"""
_SELECT_DOCUMENT = """
    SELECT document.id, document.title, document.kind, document.effective_from
    FROM document JOIN world USING (world_version)
    WHERE document.world_version = %s AND document.id = %s AND world.ready
      AND (document.pool_rank IS NULL OR document.pool_rank < %s)
"""
_SELECT_SECTIONS = """
    SELECT id, position, body FROM section
    WHERE world_version = %s AND document_id = %s
    ORDER BY position
"""
_SELECT_DOCUMENT_IDS = """
    SELECT document.id
    FROM document JOIN world USING (world_version)
    WHERE document.world_version = %s AND world.ready
      AND (document.pool_rank IS NULL OR document.pool_rank < %s)
"""
_SEARCH = f"""
    SELECT section.document_id, max(ts_rank(section.search, query)) AS rank
    FROM section
      JOIN document ON document.world_version = section.world_version
                   AND document.id = section.document_id
      JOIN world ON world.world_version = section.world_version,
      websearch_to_tsquery('{SEARCH_CONFIGURATION}', %s) AS query
    WHERE section.world_version = %s AND world.ready
      AND (document.pool_rank IS NULL OR document.pool_rank < %s)
      AND section.search @@ query
    GROUP BY section.document_id
    ORDER BY rank DESC, section.document_id ASC
    LIMIT %s
"""


@dataclass(frozen=True, slots=True)
class CorpusConfig:
    """The world version the adapter reads under; what preparation resolved and the manifest
    records. The level is the run's choice and travels beside it, never in it."""

    world_version: WorldVersion


class UnservedCorpus(Exception):
    """The configured version is not ready in the cache, or the world sealed no such level:
    a configuration fault at the composition root, raised at the first read."""

    def __init__(self, world_version: WorldVersion, level: str) -> None:
        super().__init__(
            f"the corpus cache serves no level {level!r} of world {world_version}: the version "
            "is not loaded and ready, or the world sealed no level by that name"
        )
        self.world_version = world_version
        self.level = level


def _connect(dsn: str) -> Connection:
    # Autocommit: the module docstring says why a read must leave no transaction open.
    return psycopg.connect(dsn, connect_timeout=_CONNECT_TIMEOUT_S, autocommit=True)


class CorpusAdapter:
    """Document reader over one PostgreSQL cache, scoped to one world version at one level."""

    def __init__(
        self,
        *,
        dsn: str,
        config: CorpusConfig,
        level: str = BASE_CORPUS_LEVEL,
        connect: Connect = _connect,
    ) -> None:
        self._dsn = dsn
        self._config = config
        self._level = level
        self._connect = connect
        self._connection: Connection | None = None
        self._filler_count: int | None = None

    @property
    def config(self) -> CorpusConfig:
        return self._config

    @property
    def level(self) -> str:
        return self._level

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    # --- the read side --------------------------------------------------------------

    def document(self, id: DocumentId) -> Observed[Document] | None:
        world = self._config.world_version
        with self._guarded() as conn:
            held = self._held(conn)
            row = conn.execute(_SELECT_DOCUMENT, (world, id, held)).fetchone()
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
            held = self._held(conn)
            hits = conn.execute(_SEARCH, (query, world, held, limit)).fetchall()
        found: list[Observed[Document]] = []
        for document_id, _ in hits:
            observed = self.document(DocumentId(str(document_id)))
            assert observed is not None, "a ranked section's document exists by foreign key"
            found.append(observed)
        return tuple(found)

    # --- inspection: what the version holds at this level ---------------------------------

    def held_document_ids(self) -> frozenset[DocumentId]:
        """Every document id the level holds under this world version.

        Outside the read port on purpose: the investigator finds documents by id or by
        search and never enumerates the corpus, so the port offers no enumeration, and
        the validator's exactness claim for documents — nothing missing, nothing foreign
        under the version — needs one. The same shape as Frappe's held employee numbers
        and Jira's held markers, an inspection the composition roots call and the
        application never sees.
        """
        world = self._config.world_version
        with self._guarded() as conn:
            held = self._held(conn)
            rows = conn.execute(_SELECT_DOCUMENT_IDS, (world, held)).fetchall()
        return frozenset(DocumentId(str(row[0])) for row in rows)

    # --- the level ------------------------------------------------------------------

    def _held(self, conn: Connection) -> int:
        """How much of the pool the configured level holds, resolved once from the cache."""
        if self._filler_count is None:
            row = conn.execute(_SELECT_LEVEL, (self._config.world_version, self._level)).fetchone()
            if row is None:
                raise UnservedCorpus(self._config.world_version, self._level)
            self._filler_count = int(row[0])
        return self._filler_count

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
