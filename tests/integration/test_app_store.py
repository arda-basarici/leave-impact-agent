"""The demo surface's store over the real PostgreSQL: the app schema applied beside the log's
in one schema, idempotent and versioned, read as unsupported before the bootstrap and after
a version the code does not know; the publishable table's reference to the log's attempt
row refusing a row for an attempt the log does not hold; the statement bound cancelling a
read a lock holds past three seconds, the next read clean; the publication's five outcomes
over admitted attempts, the identical repeat keeping the first timestamp, two publications
racing on one name and on one attempt decided by the constraints; the listing's reads; and
the publish command end to end over a closed run replayed into the log."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import psycopg
import pytest
from psycopg import sql

from leaveimpact.agent.log_store import LogStore
from leaveimpact.agent.log_transition import Rules
from leaveimpact.app.__main__ import main
from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.public import PublicationDraft, PublicId, PublishableRow
from leaveimpact.app.store import (
    SCHEMA_VERSION,
    STATEMENT_TIMEOUT_MS,
    AlreadyPublished,
    AppStore,
    AppStoreInvariantBroken,
    AppStoreUnavailable,
    AttemptPublished,
    PublicationConflict,
    Published,
    SlugTaken,
)
from leaveimpact.core.ids import ScenarioId
from tests.integration.log_store_support import Rig, rig
from tests.integration.test_log_store import opened, replay
from tests.unit import log_histories as histories
from tests.unit.publishable_fixture import (
    CLOSED,
    CONFIGURATION,
    OTHER_WORLD,
    SERVED,
    admission_only,
    history_in_world,
)
from tests.unit.registration_fixture import COMMITTED_FILE

pytestmark = pytest.mark.integration

_ = rig  # the fixture, imported for pytest to find

SCENARIO = ScenarioId("scenario_003")
BY = "operator:test"


def app_store(rig: Rig) -> AppStore:
    """The store over the rig's schema with the production statement bound, since the rig's
    own connector carries none; the connect bound is the rig's, since a loaded machine (the
    unit suite running beside this level) took the production three seconds to connect once
    and these tests say nothing about connecting."""

    def connect(dsn: str) -> psycopg.Connection[Any]:
        return psycopg.connect(
            dsn,
            connect_timeout=10,  # the rig's: the statement bound is what these tests exercise
            autocommit=True,
            options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS} -c search_path={rig.schema}",
        )

    return AppStore(dsn=rig.url, connect=connect)


def in_schema(rig: Rig, statement: str) -> sql.Composed:
    """``statement`` with its one ``{}`` filled by the rig's schema name, quoted."""
    return sql.SQL(statement).format(sql.Identifier(rig.schema))  # type: ignore[arg-type]


def draft(public_id: str, run_id: str, title: str | None = None, by: str = BY) -> PublicationDraft:
    return PublicationDraft(PublicId(public_id), run_id, 1, SERVED, SCENARIO, title, by)


def admitted_runs(rig: Rig) -> AppStore:
    """The app schema applied and two runs admitted (open) in the log, ``run-12`` and
    ``run-13``, so publishable rows have attempt rows to reference."""
    store = app_store(rig)
    store.ensure_schema()
    log = opened(rig)
    for name, run_id in ((CLOSED, "run-12"), (CLOSED, "run-13")):
        replay(log, history_in_world(name, SERVED, run_id=run_id), upto=1)
    log.close()
    return store


# --- the schema --------------------------------------------------------------------------------


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
    # Every read and write of the publishable table refuses too, on its own connection
    # (the step's external read: an unhealthy readiness stops no request).
    with pytest.raises(AppStoreInvariantBroken, match=f"holds {SCHEMA_VERSION + 1}"):
        store.rows_for(SERVED)
    with pytest.raises(AppStoreInvariantBroken, match=f"holds {SCHEMA_VERSION + 1}"):
        store.row_of(PublicId("anyone"))
    with pytest.raises(AppStoreInvariantBroken, match=f"holds {SCHEMA_VERSION + 1}"):
        store.publish(draft("example", "run-12"))


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


# --- the publication ---------------------------------------------------------------------------


def test_a_publication_is_written_once_and_every_repeat_is_classified(rig: Rig) -> None:
    store = admitted_runs(rig)
    first = store.publish(draft("example", "run-12", "A title"))
    assert isinstance(first, Published)
    row = first.row
    assert (row.public_id, row.run_id, row.attempt, row.world_version, row.scenario_id) == (
        "example",
        "run-12",
        1,
        SERVED,
        SCENARIO,
    )
    assert (row.title, row.published_by) == ("A title", BY)
    assert row.published_at.utcoffset() is not None

    again = store.publish(draft("example", "run-12", "A title"))
    assert again == AlreadyPublished(row), "the identical repeat keeps the first timestamp"
    assert store.publish(draft("example", "run-12", "Another title")) == PublicationConflict(row)
    assert store.publish(
        draft("example", "run-12", "A title", by="operator:b")
    ) == PublicationConflict(row)
    assert store.publish(draft("example", "run-13")) == SlugTaken(row)
    assert store.publish(draft("other-name", "run-12", "A title")) == AttemptPublished(row)
    assert store.rows_for(SERVED) == (row,)


def test_two_publications_racing_on_one_name_or_one_attempt_are_decided_by_the_constraints(
    rig: Rig,
) -> None:
    """One wins the insert, the other reads the winner's row back as its refusal; no second
    row, whichever thread the server serialized first."""
    store = admitted_runs(rig)
    with ThreadPoolExecutor(max_workers=2) as pool:
        on_name = list(
            pool.map(store.publish, [draft("shared", "run-12"), draft("shared", "run-13")])
        )
    kinds = sorted(type(outcome).__name__ for outcome in on_name)
    assert kinds == ["Published", "SlugTaken"]
    winner = next(outcome for outcome in on_name if isinstance(outcome, Published)).row
    loser = next(outcome for outcome in on_name if isinstance(outcome, SlugTaken))
    assert loser.existing == winner

    unpublished = "run-13" if winner.run_id == "run-12" else "run-12"
    with ThreadPoolExecutor(max_workers=2) as pool:
        on_attempt = list(
            pool.map(store.publish, [draft("name-a", unpublished), draft("name-b", unpublished)])
        )
    assert sorted(type(outcome).__name__ for outcome in on_attempt) == [
        "AttemptPublished",
        "Published",
    ]
    assert len(store.rows_for(SERVED)) == 2


def test_the_listing_reads_the_served_world_oldest_first_and_a_name_or_none(rig: Rig) -> None:
    store = admitted_runs(rig)
    first = store.publish(draft("later-name", "run-12"))
    second = store.publish(draft("earlier-name", "run-13"))
    assert isinstance(first, Published) and isinstance(second, Published)
    assert store.rows_for(SERVED) == (first.row, second.row), "by time, not by name"
    assert store.rows_for(OTHER_WORLD) == ()
    assert store.row_of(PublicId("later-name")) == first.row
    assert store.row_of(PublicId("nobody")) is None


# --- the command end to end --------------------------------------------------------------------


def test_the_publish_command_writes_a_closed_run_of_the_served_world_and_refuses_an_open_one(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real log store over the rig and the real app store, the closed history replayed
    whole into the log, the committed registration's bytes for the rules."""
    store = app_store(rig)
    store.ensure_schema()
    log = opened(rig)
    replay(log, history_in_world(CLOSED, SERVED))
    replay(log, admission_only(SERVED, run_id="run-14"))
    log.close()
    env = {"DATABASE_URL": rig.url, "LEAVEIMPACT_REGISTRATION_FILE": str(COMMITTED_FILE)}

    def app_over(dsn: str) -> AppStore:
        return store

    def log_over(dsn: str) -> LogStore:
        return rig.store()

    def fixture_rules(configuration: DemoConfiguration, content: bytes) -> Rules:
        return histories.RULES

    # The history was replayed under the fixtures' rules, so the command folds under those.
    seams: dict[str, Any] = {
        "store": app_over,
        "log": log_over,
        "configuration": lambda: CONFIGURATION,
        "rules": fixture_rules,
    }
    closed = ["publish", "--run", "run-12", "--attempt", "1", "--as", "example", "--by", BY]
    assert main(closed, env, **seams) == 0
    out = capsys.readouterr().out
    assert out.startswith(
        f"published example: run run-12 attempt 1, world {SERVED} scenario scenario_003"
    )
    assert main(closed, env, **seams) == 0
    assert capsys.readouterr().out.startswith("already published example at ")
    rows = store.rows_for(SERVED)
    assert len(rows) == 1 and isinstance(rows[0], PublishableRow)

    open_run = ["publish", "--run", "run-14", "--attempt", "1", "--as", "live", "--by", BY]
    assert main(open_run, env, **seams) == 1
    assert "run run-14 attempt 1 is open; a replay is a closed run" in capsys.readouterr().err
    assert store.row_of(PublicId("live")) is None
