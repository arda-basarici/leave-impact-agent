"""Support for the corpus integration tests: the database to use, a world version per test,
and a cache world loaded through the real loader.

The corpus is the project's own system, so there is no cassette: the tests run
against the real PostgreSQL the suite is configured with (``DATABASE_URL``; the Compose
service in CI, ``just db-up`` on a laptop) and skip without it, failing under ``CI``
where a missing service is broken wiring. Each test loads under a world version of
its own, so tests never read one another and a re-run never meets a previous run's
rows; the version's rows are deleted at the end, sections before documents before levels
before the world row, for the foreign keys. Test support, not adapter capability: neither
the adapter nor the loader ever deletes.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from uuid import uuid4

import psycopg
import pytest

from leaveimpact.adapters.corpus import CorpusAdapter, CorpusConfig
from leaveimpact.adapters.corpus.loader import CacheWorld, ensure_schema, load_world
from leaveimpact.core.entities import Document
from leaveimpact.core.ids import DocumentId, WorldVersion
from leaveimpact.core.run_record import BASE_CORPUS_LEVEL, WorldProjection
from leaveimpact.world.levels import BASE_CORPUS_LEVELS, CorpusLevels, SealedLevel


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    if os.environ.get("CI"):
        pytest.fail("DATABASE_URL unset in CI — the PostgreSQL service wiring is broken")
    pytest.skip("DATABASE_URL unset — the PostgreSQL service is not running here")


def fresh_world() -> WorldVersion:
    return WorldVersion(f"test-{uuid4().hex[:12]}")


def drop_world(url: str, world_version: WorldVersion) -> None:
    """Every row the world version holds, children first."""
    with psycopg.connect(url, connect_timeout=5) as conn:
        conn.execute("DELETE FROM section WHERE world_version = %s", (world_version,))
        conn.execute("DELETE FROM document WHERE world_version = %s", (world_version,))
        conn.execute("DELETE FROM level WHERE world_version = %s", (world_version,))
        conn.execute("DELETE FROM world WHERE world_version = %s", (world_version,))


def cache_world(
    world_version: WorldVersion,
    documents: Sequence[Document],
    *,
    pool: Sequence[DocumentId] = (),
    padded: int | None = None,
) -> CacheWorld:
    """A development cache world over ``documents``; ``pool`` names the filler documents in
    rank order and ``padded`` seals a second level holding that many of them."""
    levels = (
        BASE_CORPUS_LEVELS
        if padded is None
        else CorpusLevels(
            (SealedLevel(BASE_CORPUS_LEVEL, 0), SealedLevel("padded", padded)), tuple(pool)
        )
    )
    return CacheWorld(world_version, WorldProjection.UNPROJECTED, None, levels, tuple(documents))


def loaded_adapter(
    url: str, world: CacheWorld, level: str = BASE_CORPUS_LEVEL
) -> Iterator[CorpusAdapter]:
    """An adapter at ``level`` over ``world`` loaded through the loader, its schema ensured;
    the world dropped afterwards."""
    ensure_schema(url)
    load_world(url, world)
    adapter = CorpusAdapter(dsn=url, config=CorpusConfig(world.version), level=level)
    try:
        yield adapter
    finally:
        adapter.close()
        drop_world(url, world.version)
