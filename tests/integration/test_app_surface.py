"""The step's acceptance over the real stores: a closed run of the served world replayed into
the log and published through the store, a closed run of another world beside it with an honest
row forced by SQL and a forged row carrying the served world; the application over the real
app store and a real log store per request, read through the test client: the listing names
what the projection holds, the admitted replay answers 200, the honest and the forged rows and
an unknown name answer the same not-found bytes, and a database whose app schema is dropped
answers the unavailable page."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from leaveimpact.agent.log_store import LogStore
from leaveimpact.app.main import Services, create_app
from leaveimpact.app.public import PublicationDraft, PublicId
from leaveimpact.app.store import STATEMENT_TIMEOUT_MS, AppStore, Published
from leaveimpact.core.ids import WorldVersion
from leaveimpact.results.committed import committed_results
from tests.integration.log_store_support import Rig, rig
from tests.integration.test_log_store import opened, replay
from tests.unit import log_histories as histories
from tests.unit.publishable_fixture import (
    CLOSED,
    CONFIGURATION,
    OTHER_WORLD,
    SCENARIO,
    SERVED,
    history_in_world,
)

pytestmark = pytest.mark.integration

_ = rig  # the fixture, imported for pytest to find

CODE = "b" * 40


def app_store(rig: Rig) -> AppStore:
    def connect(dsn: str) -> psycopg.Connection[Any]:
        return psycopg.connect(
            dsn,
            connect_timeout=10,  # the rig's: the statement bound is what these tests exercise
            autocommit=True,
            options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS} -c search_path={rig.schema}",
        )

    return AppStore(dsn=rig.url, connect=connect)


def in_schema(rig: Rig, statement: str) -> sql.Composed:
    return sql.SQL(statement).format(sql.Identifier(rig.schema))  # type: ignore[arg-type]


def force_row(rig: Rig, public_id: str, run_id: str, world: WorldVersion) -> None:
    """A row written past the operator command, as a bypass or a mistake would."""
    with rig.observer() as observer:
        observer.execute(
            in_schema(
                rig,
                "INSERT INTO {}.publishable_attempt (public_id, run_id, attempt, world_version, "
                "scenario_id, published_at, published_by) VALUES (%s, %s, 1, %s, %s, now(), 'sql')",
            ),
            (public_id, run_id, world, SCENARIO),
        )


def client(rig: Rig, store: AppStore, *, served: bool = True) -> TestClient:
    def log_session() -> LogStore:
        return rig.store()

    services = Services(
        code_version=CODE,
        configuration=CONFIGURATION,
        ready_versions=lambda: frozenset({SERVED} if served else {OTHER_WORLD}),
        app_schema=store.schema_supported,
        rows=store,
        log_sessions=log_session,
        rules=histories.RULES,
        results=committed_results,
        walkthroughs=lambda: (),
    )
    return TestClient(create_app(services))


def test_the_embargoed_attempt_is_unreachable_through_every_read_surface(rig: Rig) -> None:
    store = app_store(rig)
    store.ensure_schema()
    log = opened(rig)
    replay(log, history_in_world(CLOSED, SERVED))
    replay(log, history_in_world(CLOSED, OTHER_WORLD, run_id="run-13"))
    replay(log, history_in_world(CLOSED, OTHER_WORLD, run_id="run-15"))
    log.close()
    written = store.publish(
        PublicationDraft(
            PublicId("served"), "run-12", 1, SERVED, SCENARIO, "An example", "operator:test"
        )
    )
    assert isinstance(written, Published)
    force_row(rig, "embargoed", "run-13", OTHER_WORLD)
    # One attempt has one row, so the forged row names a third run of the other world.
    force_row(rig, "forged", "run-15", SERVED)

    with client(rig, store) as web:
        listing = web.get("/replays")
        assert listing.status_code == 200
        assert 'href="/replays/served"' in listing.text and "An example" in listing.text
        assert 'href="/replays/forged"' in listing.text, "the projection lists the forged row"
        assert "embargoed" not in listing.text
        assert "run-1" not in listing.text

        served = web.get("/replays/served")
        assert served.status_code == 200 and ">completed<" in served.text
        unknown = web.get("/replays/nobody")
        for name in ("embargoed", "forged"):
            refused = web.get(f"/replays/{name}")
            assert refused.status_code == 404, name
            assert refused.content == unknown.content, name
        assert OTHER_WORLD not in unknown.text

    with client(rig, store, served=False) as web:
        assert web.get("/replays/served").status_code == 503
        assert web.get("/replays/forged").status_code == 404
        assert web.get("/ready").status_code == 503


def test_a_database_at_another_app_schema_version_serves_no_page(rig: Rig) -> None:
    """Readiness says 503, and so does every page, since each content read checks the
    version on its own connection; a schema the code does not know serves nothing."""
    store = app_store(rig)
    store.ensure_schema()
    with rig.observer() as observer:
        observer.execute(in_schema(rig, "UPDATE {}.app_schema SET version = 99"))
    with client(rig, store) as web:
        assert web.get("/ready").status_code == 503
        assert web.get("/replays").status_code == 503
        assert web.get("/replays/served").status_code == 503


def test_a_database_without_the_app_schema_is_unavailable_not_an_error(rig: Rig) -> None:
    store = app_store(rig)
    store.ensure_schema()
    with rig.observer() as observer:
        # The live table references the publishable one (app schema 3), so it goes first.
        observer.execute(in_schema(rig, "DROP TABLE {}.live_attempt"))
        observer.execute(in_schema(rig, "DROP TABLE {}.publishable_attempt"))
        observer.execute(in_schema(rig, "DROP TABLE {}.app_schema"))
    with client(rig, store) as web:
        ready = web.get("/ready")
        assert ready.status_code == 503 and ready.json()["app_schema"] is False
        assert web.get("/replays").status_code == 503
        assert web.get("/replays/served").status_code == 503
