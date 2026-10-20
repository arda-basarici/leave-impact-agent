"""The demo surface's store over the real PostgreSQL: the app schema applied beside the log's
in one schema, idempotent and versioned, read as unsupported before the bootstrap and after
a version the code does not know, the publishable table's reference to the log's attempt
row refusing a row for an attempt the log does not hold, and the statement bound cancelling
a read a lock holds past three seconds, the next read clean."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest
from psycopg import sql

from leaveimpact.app.store import (
    SCHEMA_VERSION,
    STATEMENT_TIMEOUT_MS,
    AppStore,
    AppStoreInvariantBroken,
    AppStoreUnavailable,
)
from tests.integration.log_store_support import Rig, rig

pytestmark = pytest.mark.integration

_ = rig  # the fixture, imported for pytest to find


def app_store(rig: Rig) -> AppStore:
    """The store over the rig's schema with the production bounds, since the rig's own
    connector carries no statement timeout."""

    def connect(dsn: str) -> psycopg.Connection[Any]:
        return psycopg.connect(
            dsn,
            connect_timeout=3,
            autocommit=True,
            options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS} -c search_path={rig.schema}",
        )

    return AppStore(dsn=rig.url, connect=connect)


def in_schema(rig: Rig, statement: str) -> sql.Composed:
    """``statement`` with its one ``{}`` filled by the rig's schema name, quoted."""
    return sql.SQL(statement).format(sql.Identifier(rig.schema))  # type: ignore[arg-type]


def test_the_schema_is_unsupported_before_the_bootstrap_and_idempotent_after(rig: Rig) -> None:
    store = app_store(rig)
    assert store.schema_supported() is False
    store.ensure_schema()
    assert store.schema_supported() is True
    store.ensure_schema()
    with rig.observer() as observer:
        rows = observer.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
            (rig.schema,),
        ).fetchall()
        tables = {str(row[0]) for row in rows}
        assert {"app_schema", "publishable_attempt", "attempt", "event"} <= tables
        versions = observer.execute(in_schema(rig, "SELECT version FROM {}.app_schema")).fetchall()
    assert versions == [(SCHEMA_VERSION,)]


def test_another_version_is_unsupported_and_the_bootstrap_refuses_it(rig: Rig) -> None:
    store = app_store(rig)
    store.ensure_schema()
    with rig.observer() as observer:
        observer.execute(
            in_schema(rig, "UPDATE {}.app_schema SET version = %s"), (SCHEMA_VERSION + 1,)
        )
    assert store.schema_supported() is False
    with pytest.raises(AppStoreInvariantBroken, match=f"holds version {SCHEMA_VERSION + 1}"):
        store.ensure_schema()


def test_a_publishable_row_for_an_attempt_the_log_does_not_hold_cannot_exist(rig: Rig) -> None:
    app_store(rig).ensure_schema()
    insert = in_schema(
        rig,
        "INSERT INTO {}.publishable_attempt "
        "(public_id, run_id, attempt, world_version, scenario_id, published_at, published_by) "
        "VALUES ('ghost', 'run-none', 1, 'w', 's', now(), 'test')",
    )
    with rig.observer() as observer, pytest.raises(psycopg.errors.ForeignKeyViolation):
        observer.execute(insert)


def test_a_read_a_lock_holds_is_cancelled_at_the_statement_bound_and_the_next_is_clean(
    rig: Rig,
) -> None:
    """The bound is the server's, so a transaction holding the version table lets the
    connect succeed and the select wait; three seconds later the read is the store's named
    unavailability and nothing is left open."""
    store = app_store(rig)
    store.ensure_schema()
    with rig.observer() as holder, holder.transaction():
        holder.execute(in_schema(rig, "LOCK TABLE {}.app_schema IN ACCESS EXCLUSIVE MODE"))
        with pytest.raises(AppStoreUnavailable, match="QueryCanceled"):
            store.schema_supported()
    assert store.schema_supported() is True
