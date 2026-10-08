"""The corpus cache loader: one served world's documents and levels into PostgreSQL, in one
transaction, the version marked ready as its last statement.

Gated by the import law like a writer (only ``adapters`` and the ``cache`` shell may name
it), and still not a writer in the domain's sense: it implements no write port, since
filling the cache from a sealed world is materialization and not authorship, and the
narrow loader the build plan asks for is this one function over one record (the M2
step 9 design, forks 5 and 6). What it is handed is ``CacheWorld``, the application-side
statement of a served world: the version, how it came to be, the manifest digest the
verdict approved where there is one, the levels and the pool's order, and every document.
The record refuses what cannot be one world (a pool id with no document, a document
sealed twice, a digest on an unprojected world or none on a projected one), so the
transaction below writes rows and checks counts and judges nothing else.

**One transaction, ready last.** The world row goes in unready, then the levels, then the
documents with their pool rank, then the sections; the row counts are read back inside
the same transaction and compared with the record; ``ready`` is flipped by the last
statement; the commit is the one atomic step the build plan names. A crash anywhere before
it leaves no row, and a reader joining on ``ready`` never sees a version half filled. A
version already ready is left as it is and reported so, provided it was cached as the same
kind of world under the same manifest digest: the cache is filled once per version, and a
sealed object under a final prefix cannot change, so there is nothing a second load could
correct, and a ready row of another provenance (a development root's unprojected load
beside a later projected one) is refused rather than silently kept. Two loaders racing on
one version serialize on a transaction-scoped advisory lock keyed by the version, taken
before the row is read, since a row lock cannot cover a row that is not there yet; the
second finds the first's commit.

**Bootstrap, never migration.** ``ensure_schema`` applies the idempotent DDL beside the
adapter (``schema.sql``) and then reads the ``document`` table's columns back and refuses
a table of an older shape by name, since ``CREATE TABLE IF NOT EXISTS`` alters nothing
and a cache is a rebuilt database when its schema changes (fork 9). The composition root
calls it once before loading, the way the Frappe site schema and the Jira fields are
ensured.

**Faults.** A connection that cannot be opened or fails under a statement is
``SourceUnreachable`` for the corpus; a count that does not read back, a schema of
another shape or a race the lock did not cover is ``CacheRefused`` naming what was
expected, and the transaction is rolled back by the exception leaving the block.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from importlib import resources
from typing import Any, LiteralString

import psycopg

from leaveimpact.adapters.corpus import records
from leaveimpact.core.entities import Document
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import DocumentId, WorldVersion
from leaveimpact.core.ports.errors import SourceUnreachable
from leaveimpact.core.run_record import WorldProjection
from leaveimpact.world.levels import CorpusLevels

Connection = psycopg.Connection[Any]
Connect = Callable[[str], Connection]
_CONNECT_TIMEOUT_S = 10

DOCUMENT_COLUMNS = frozenset(
    {"world_version", "id", "title", "kind", "effective_from", "pool_rank"}
)
"""What the ``document`` table holds at this schema; a table missing a name is an older shape."""

_SELECT_DOCUMENT_COLUMNS = """
    SELECT column_name FROM information_schema.columns
    WHERE table_schema = current_schema() AND table_name = 'document'
"""
# The transaction-scoped advisory lock on the version's hash is taken before anything is
# read: `SELECT ... FOR UPDATE` locks nothing when the row does not exist yet, so two
# loaders racing on a fresh version would both see no row and the second's insert would be
# refused by the primary key (the review's second finding, reproduced on the service).
_LOCK_VERSION = "SELECT pg_advisory_xact_lock(hashtext(%s))"
_SELECT_WORLD = "SELECT projection, manifest_digest, ready FROM world WHERE world_version = %s"
_INSERT_WORLD = """
    INSERT INTO world (world_version, projection, manifest_digest, ready)
    VALUES (%s, %s, %s, %s)
"""
_INSERT_LEVEL = "INSERT INTO level (world_version, name, filler_count) VALUES (%s, %s, %s)"
_INSERT_DOCUMENT = """
    INSERT INTO document (world_version, id, title, kind, effective_from, pool_rank)
    VALUES (%s, %s, %s, %s, %s, %s)
"""
_INSERT_SECTION = """
    INSERT INTO section (world_version, id, document_id, position, body)
    VALUES (%s, %s, %s, %s, %s)
"""
_COUNT_DOCUMENTS = "SELECT count(*) FROM document WHERE world_version = %s"
_COUNT_SECTIONS = "SELECT count(*) FROM section WHERE world_version = %s"
_MARK_READY = "UPDATE world SET ready = true WHERE world_version = %s"


class CacheRefused(Exception):
    """The cache is not in the state the loader expects; the message says what was expected."""


class LoadOutcome(StrEnum):
    """What one load did: filled the version, or found it ready and left it."""

    LOADED = "loaded"
    ALREADY_READY = "already_ready"


@dataclass(frozen=True, slots=True)
class CacheWorld:
    """A served world as the cache records it: the version, how it came to be, the manifest
    digest its verdict approved (projected worlds only), its levels and pool, every document.

    >>> from datetime import date
    >>> from leaveimpact.core.enums import DocumentKind
    >>> from leaveimpact.world.levels import BASE_CORPUS_LEVELS
    >>> doc = Document(DocumentId("doc_001"), "Policy", DocumentKind.POLICY, date(2026, 1, 1), ())
    >>> CacheWorld(WorldVersion("a" * 64), WorldProjection.PROJECTED, None, BASE_CORPUS_LEVELS,
    ...            (doc,))
    Traceback (most recent call last):
    ...
    ValueError: a projected world is cached under the manifest digest its verdict approved
    """

    version: WorldVersion
    projection: WorldProjection
    manifest_digest: str | None
    levels: CorpusLevels
    documents: tuple[Document, ...]

    def __post_init__(self) -> None:
        if (self.manifest_digest is None) != (self.projection is WorldProjection.UNPROJECTED):
            raise ValueError(
                "a projected world is cached under the manifest digest its verdict approved"
                if self.manifest_digest is None
                else "an unprojected world has no manifest and no digest to cache under"
            )
        ids = [document.id for document in self.documents]
        if len(set(ids)) != len(ids):
            raise ValueError(f"a document is cached once, got {ids}")
        missing = [id for id in self.levels.pool if id not in set(ids)]
        if missing:
            raise ValueError(f"the pool names documents the world does not hold: {missing}")

    def pool_rank(self, id: DocumentId) -> int | None:
        """The document's position in the pool, or ``None`` for a scenario-owned one."""
        try:
            return self.levels.pool.index(id)
        except ValueError:
            return None


def check_document_columns(found: Sequence[str]) -> None:
    """Refuse a ``document`` table whose columns are not this schema's, naming the shortfall."""
    missing = sorted(DOCUMENT_COLUMNS - set(found))
    if missing:
        raise CacheRefused(
            f"the document table lacks {missing}: an older schema; the cache is a rebuilt "
            "database, never an altered one"
        )


def ensure_schema(dsn: str, *, connect: Connect | None = None) -> None:
    """The four tables and the search index, created where missing, never altered; the
    document table's columns then read back and an older shape refused."""
    ddl = resources.files(__package__).joinpath("schema.sql").read_text(encoding="utf-8")
    with _connection(dsn, connect) as conn:
        with conn.transaction():
            # As bytes: the driver's query type admits a literal or bytes, and the file
            # beside this module is source, not input.
            conn.execute(ddl.encode())
        with conn.transaction():
            found = [str(row[0]) for row in conn.execute(_SELECT_DOCUMENT_COLUMNS).fetchall()]
    check_document_columns(found)


def load_world(dsn: str, world: CacheWorld, *, connect: Connect | None = None) -> LoadOutcome:
    """``world`` into the cache under its version, in one transaction, ready last; a version
    already ready is left as it is."""
    version = world.version
    with _connection(dsn, connect) as conn, conn.transaction():
        conn.execute(_LOCK_VERSION, (version,))
        row = conn.execute(_SELECT_WORLD, (version,)).fetchone()
        if row is not None:
            projection, digest, ready = str(row[0]), row[1], bool(row[2])
            if not ready:
                raise CacheRefused(
                    f"world {version} has a row and is not ready: a load that neither "
                    "committed nor rolled back, which this loader never leaves"
                )
            if (projection, digest) != (world.projection.value, world.manifest_digest):
                raise CacheRefused(
                    f"world {version} is ready as {projection} under manifest {digest}, and "
                    f"the served world is {world.projection.value} under "
                    f"{world.manifest_digest}: a version is cached once, and not as another"
                )
            return LoadOutcome.ALREADY_READY
        conn.execute(
            _INSERT_WORLD, records.world_params(version, world.projection, world.manifest_digest)
        )
        for params in records.level_params(version, world.levels.levels):
            conn.execute(_INSERT_LEVEL, params)
        for document in world.documents:
            conn.execute(
                _INSERT_DOCUMENT,
                records.document_params(document, version, world.pool_rank(document.id)),
            )
            for params in records.section_params(document, version):
                conn.execute(_INSERT_SECTION, params)
        _check_count(conn, _COUNT_DOCUMENTS, version, len(world.documents), "documents")
        sections = sum(len(document.sections) for document in world.documents)
        _check_count(conn, _COUNT_SECTIONS, version, sections, "sections")
        conn.execute(_MARK_READY, (version,))
    return LoadOutcome.LOADED


def _check_count(
    conn: Connection, statement: LiteralString, version: WorldVersion, expected: int, what: str
) -> None:
    row = conn.execute(statement, (version,)).fetchone()
    found = int(row[0]) if row is not None else 0
    if found != expected:
        raise CacheRefused(f"{found} {what} read back under {version}, {expected} were written")


class _connection:
    """A connection for one loader call, its faults translated into the port's vocabulary."""

    def __init__(self, dsn: str, connect: Connect | None) -> None:
        self._dsn = dsn
        self._connect = connect or _default_connect
        self._conn: Connection | None = None

    def __enter__(self) -> Connection:
        try:
            self._conn = self._connect(self._dsn)
        except psycopg.OperationalError as exc:
            raise SourceUnreachable(
                Source.CORPUS, f"connection refused: {type(exc).__name__}"
            ) from exc
        return self._conn

    def __exit__(self, kind: object, value: object, traceback: object) -> None:
        assert self._conn is not None
        try:
            self._conn.close()
        finally:
            self._conn = None
        if isinstance(value, psycopg.OperationalError):
            raise SourceUnreachable(
                Source.CORPUS, f"statement failed: {type(value).__name__}"
            ) from value
        if isinstance(value, psycopg.errors.IntegrityError):
            raise CacheRefused(
                f"a row the loader wrote was refused: {type(value).__name__}"
            ) from value


def _default_connect(dsn: str) -> Connection:
    return psycopg.connect(dsn, connect_timeout=_CONNECT_TIMEOUT_S)
