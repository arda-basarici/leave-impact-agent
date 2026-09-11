"""Support for the corpus integration tests: the database to use, and a world version per test.

The corpus is the project's own system, so there is no cassette: the tests run
against the real PostgreSQL the suite is configured with (``DATABASE_URL``; the Compose
service in CI, ``just db-up`` on a laptop) and skip without it, failing under ``CI``
where a missing service is broken wiring. Each test writes under a world version of
its own, so tests never read one another and a re-run never meets a previous run's
rows; the version's rows are deleted at the end, sections before documents for the
foreign key. Test support, not adapter capability: the adapter never deletes.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest

from leaveimpact.adapters.corpus import CorpusAdapter, CorpusConfig
from leaveimpact.core.ids import WorldVersion


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
    """Every row the world version holds, sections first."""
    with psycopg.connect(url, connect_timeout=5) as conn:
        conn.execute("DELETE FROM section WHERE world_version = %s", (world_version,))
        conn.execute("DELETE FROM document WHERE world_version = %s", (world_version,))


def adapter_for(url: str, world_version: WorldVersion) -> Iterator[CorpusAdapter]:
    """An adapter over a fresh world, its schema ensured; the world dropped afterwards."""
    adapter = CorpusAdapter(dsn=url, config=CorpusConfig(world_version))
    adapter.ensure_schema()
    try:
        yield adapter
    finally:
        adapter.close()
        drop_world(url, world_version)
