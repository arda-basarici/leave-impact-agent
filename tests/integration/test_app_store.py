"""The demo surface's store over the real PostgreSQL: the app schema applied beside the log's
in one schema, idempotent and versioned, read as unsupported before the bootstrap and after
a version the code does not know; the publishable table's reference to the log's attempt
row refusing a row for an attempt the log does not hold; the statement bound cancelling a
read a lock holds past three seconds, the next read clean; the publication's five outcomes
over admitted attempts, the identical repeat keeping the first timestamp, two publications
racing on one name and on one attempt decided by the constraints; the listing's reads; and
the publish command end to end over a closed run replayed into the log."""

from __future__ import annotations

import io
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import psycopg
import pytest
from psycopg import sql

from leaveimpact.adapters.wiring import run_export_publisher_over
from leaveimpact.agent.commands import PublishRequest, publish
from leaveimpact.agent.inventory import PublicationRecord
from leaveimpact.agent.ledger import EntryKind
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
from leaveimpact.core.ids import ScenarioId, WorldVersion
from tests.integration.log_store_support import Rig, rig
from tests.integration.test_log_store import AUTHORITY, LEDGER, PLENTY, opened, replay
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit.in_memory_object_store import InMemoryObjectStore
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
        # The view dropped, so a refused bootstrap that still ran the DDL would show here.
        observer.execute(in_schema(rig, "DROP VIEW {}.ledger_capture"))
    assert store.schema_supported() is False
    with pytest.raises(AppStoreInvariantBroken, match=f"holds version {SCHEMA_VERSION + 1}"):
        store.ensure_schema()
    with rig.observer() as observer:
        views = observer.execute(
            "SELECT table_name FROM information_schema.views WHERE table_schema = %s",
            (rig.schema,),
        ).fetchall()
    assert views == [], "the refusal applied nothing"
    # Every read and write of the publishable table refuses too, on its own connection
    # (the step's external read: an unhealthy readiness stops no request).
    with pytest.raises(AppStoreInvariantBroken, match=f"holds {SCHEMA_VERSION + 1}"):
        store.rows_for(SERVED)
    with pytest.raises(AppStoreInvariantBroken, match=f"holds {SCHEMA_VERSION + 1}"):
        store.row_of(PublicId("anyone"))
    with pytest.raises(AppStoreInvariantBroken, match=f"holds {SCHEMA_VERSION + 1}"):
        store.publish(draft("example", "run-12"))


def test_a_version_one_database_is_advanced_by_the_bootstrap_and_gains_the_view(rig: Rig) -> None:
    """The instance's database was bootstrapped at version 1 (the publishability step) and
    version 2 added the view only, so the same DDL brings it forward; a version the set
    does not name stays refused (the test above)."""
    store = app_store(rig)
    store.ensure_schema()
    with rig.observer() as observer:
        observer.execute(in_schema(rig, "DROP VIEW {}.ledger_capture"))
        observer.execute(in_schema(rig, "UPDATE {}.app_schema SET version = 1"))
    assert store.schema_supported() is False
    store.ensure_schema()
    assert store.schema_supported() is True
    with rig.observer() as observer:
        views = observer.execute(
            "SELECT table_name FROM information_schema.views WHERE table_schema = %s",
            (rig.schema,),
        ).fetchall()
        versions = observer.execute(in_schema(rig, "SELECT version FROM {}.app_schema")).fetchall()
    assert views == [("ledger_capture",)] and versions == [(SCHEMA_VERSION,)]


CAPTURE_STATEMENT = (
    "SELECT coalesce(jsonb_agg(c ORDER BY c.ledger_id), '[]'::jsonb) FROM {}.ledger_capture c"
)
"""The backup script's read of the view, verbatim but for the schema qualification the rig
needs (the exchange with the platform, 2026-10-23): the capture it records on the dump."""


def test_the_ledger_capture_states_each_ledgers_head_and_its_open_reservations(rig: Rig) -> None:
    """One settled attempt and one open on the test ledger, a second ledger with a head and
    no entry: the capture's rows equal what the ledger view's entries say under the ledger
    module's own definitions (open is admitted and not settled), ordered by ledger id, the
    empty ledger at zero rather than null."""
    store = app_store(rig)
    store.ensure_schema()
    log = opened(rig)
    log.set_threshold(
        "ledger-empty",
        PLENTY,
        authority=AUTHORITY,
        registration_commit=cases.COMMIT,
        limit_pico_usd=PLENTY,
    )
    replay(log, history_in_world(CLOSED, SERVED, run_id="run-12"))
    replay(log, history_in_world(CLOSED, SERVED, run_id="run-13"), upto=1)
    view = log.ledger_view(LEDGER)
    log.close()
    settled = {(e.run_id, e.attempt) for e in view.entries if e.kind is EntryKind.SETTLED}
    open_entries = [
        e
        for e in view.entries
        if e.kind is EntryKind.ADMITTED and (e.run_id, e.attempt) not in settled
    ]
    assert settled == {("run-12", 1)} and [(e.run_id, e.attempt) for e in open_entries] == [
        ("run-13", 1)
    ]
    assert view.head.total_pico_usd > 0, "the settled attempt charged something"
    with rig.observer() as observer:
        row = observer.execute(in_schema(rig, CAPTURE_STATEMENT)).fetchone()
    assert row is not None
    assert row[0] == [
        {
            "ledger_id": "ledger-empty",
            "total_pico_usd": 0,
            "revision": 1,
            "threshold_pico_usd": PLENTY,
            "open_reservation_pico_usd": 0,
            "open_attempts": 0,
        },
        {
            "ledger_id": LEDGER,
            "total_pico_usd": view.head.total_pico_usd,
            "revision": view.head.revision,
            "threshold_pico_usd": view.head.threshold_pico_usd,
            "open_reservation_pico_usd": open_entries[0].amount_pico_usd,
            "open_attempts": 1,
        },
    ]


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


# --- the restore drill ---------------------------------------------------------------------


def test_the_restore_drill_passes_over_the_real_stores_and_names_the_check_a_bad_ledger_fails(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real log and app stores stand in for the restored scratch database: a closed run
    settled on the ledger, an open admission beside it, one row published; the capture read
    with the backup script's statement. The drill passes every check and writes nothing (the
    ledger's revision and the event count are what they were). Then the ledger's settled
    entry is moved by one pico-dollar with its head and the later total kept consistent, so
    the fold holds and the capture re-read agrees, and the drill fails the settlements check
    naming the run, since the account rule recomputed from the log says otherwise. The cache
    read is a seam here: the rig holds no corpus cache, and the real read has its own tests."""
    store = app_store(rig)
    store.ensure_schema()
    log = opened(rig)
    replay(log, history_in_world(CLOSED, SERVED))
    replay(log, admission_only(SERVED, run_id="run-14"))
    log.close()
    assert isinstance(store.publish(draft("example", "run-12")), Published)
    env = {"DATABASE_URL": rig.url, "LEAVEIMPACT_REGISTRATION_FILE": str(COMMITTED_FILE)}

    def fixture_rules(configuration: DemoConfiguration, content: bytes) -> Rules:
        return histories.RULES

    def app_over(dsn: str) -> AppStore:
        return store

    def log_over(dsn: str) -> LogStore:
        return rig.store()

    def cached(dsn: str) -> frozenset[WorldVersion]:
        return frozenset({SERVED})

    seams: dict[str, Any] = {
        "store": app_over,
        "restore_log": log_over,
        "cache": cached,
        "configuration": lambda: CONFIGURATION,
        "rules": fixture_rules,
    }

    def capture() -> list[dict[str, Any]]:
        with rig.observer() as observer:
            row = observer.execute(in_schema(rig, CAPTURE_STATEMENT)).fetchone()
        assert row is not None
        return row[0]

    def counts() -> tuple[int, int]:
        with rig.observer() as observer:
            events = observer.execute(in_schema(rig, "SELECT count(*) FROM {}.event")).fetchone()
            revision = observer.execute(
                in_schema(rig, "SELECT revision FROM {}.ledger_head WHERE ledger_id = %s"),
                (LEDGER,),
            ).fetchone()
        assert events is not None and revision is not None
        return int(events[0]), int(revision[0])

    before = counts()
    assert main(["verify-restore"], env, stdin=io.StringIO(json.dumps(capture())), **seams) == 0
    out = capsys.readouterr().out
    assert out.startswith("verify-restore: recovery procedure: both bootstraps applied\n")
    for name in (
        "app-schema",
        "served-world-cached",
        "ledger-capture",
        "ledger-fold",
        "settlements",
        "listing",
        "replay",
    ):
        assert f"verify-restore: {name}: ok: " in out, out
    assert "settlements: ok: 1 closed attempts" in out
    assert "replay: ok: example served:" in out
    assert out.endswith("verify-restore: 7 of 7 checks passed\n")
    assert counts() == before, "the drill wrote nothing"

    with rig.observer() as observer:
        observer.execute(
            in_schema(
                rig,
                "UPDATE {}.ledger_entry SET amount_pico_usd = amount_pico_usd + 1, "
                "total_after_pico_usd = total_after_pico_usd + 1 "
                "WHERE ledger_id = %s AND kind = 'settled' AND run_id = 'run-12'",
            ),
            (LEDGER,),
        )
        observer.execute(
            in_schema(
                rig,
                "UPDATE {}.ledger_entry SET total_after_pico_usd = total_after_pico_usd + 1 "
                "WHERE ledger_id = %s AND kind = 'admitted' AND run_id = 'run-14'",
            ),
            (LEDGER,),
        )
        observer.execute(
            in_schema(
                rig,
                "UPDATE {}.ledger_head SET total_pico_usd = total_pico_usd + 1 "
                "WHERE ledger_id = %s",
            ),
            (LEDGER,),
        )
    assert main(["verify-restore"], env, stdin=io.StringIO(json.dumps(capture())), **seams) == 1
    out = capsys.readouterr().out
    assert "verify-restore: ledger-fold: ok: " in out, out
    assert (
        "verify-restore: settlements: FAILED: run run-12 attempt 1: the account rule charges" in out
    )
    assert out.endswith("verify-restore: 6 of 7 checks passed\n")

    stale = io.StringIO(json.dumps([{"ledger_id": "ledger-other"}]))
    assert main(["verify-restore"], env, stdin=stale, **seams) == 1
    out = capsys.readouterr().out
    assert "ledger-capture: FAILED: the capture names ledgers ['ledger-other']" in out


# --- the publication digests ----------------------------------------------------------------


def test_every_published_replays_digests_reproduce_and_a_moved_record_is_named(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    """The production acceptance of a format bump (the live-path step, fork 10 as the external
    read amended it), over the real stores: a closed run published through the publish command
    with its record in the log store and its row in the app store; the check regenerates both
    digests from the log under this code and reports them reproduced, then the record's object
    digest is moved and the check fails that replay naming the kind of difference."""
    store = app_store(rig)
    store.ensure_schema()
    log = opened(rig)
    replay(log, history_in_world(CLOSED, SERVED))
    publisher = run_export_publisher_over(InMemoryObjectStore())
    record = publish(
        PublishRequest("run-12", 1, cases.COMMIT), log, publisher, rules=histories.RULES
    )
    assert isinstance(record, PublicationRecord) and record.object_digest is not None
    log.close()
    assert isinstance(store.publish(draft("example", "run-12")), Published)
    env = {"DATABASE_URL": rig.url, "LEAVEIMPACT_REGISTRATION_FILE": str(COMMITTED_FILE)}

    def app_over(dsn: str) -> AppStore:
        return store

    def log_over(dsn: str) -> LogStore:
        return rig.store()

    def fixture_rules(configuration: DemoConfiguration, content: bytes) -> Rules:
        return histories.RULES

    seams: dict[str, Any] = {
        "store": app_over,
        "restore_log": log_over,
        "configuration": lambda: CONFIGURATION,
        "rules": fixture_rules,
    }
    assert main(["verify-publications"], env, **seams) == 0
    out = capsys.readouterr().out
    assert out.startswith(
        "verify-publications: example: ok: run run-12 attempt 1: log format 4, export format 4, "
    )
    assert "events: both digests reproduced\n" in out
    assert out.endswith("verify-publications: 1 of 1 replays reproduce\n")

    with rig.observer() as observer:
        observer.execute(
            in_schema(rig, "UPDATE {}.publication SET object_digest = %s WHERE run_id = %s"),
            ("0" * 64, "run-12"),
        )
    assert main(["verify-publications"], env, **seams) == 1
    out = capsys.readouterr().out
    assert "verify-publications: example: FAILED: run run-12 attempt 1: " in out
    assert "events: the export digest differs\n" in out
    assert out.endswith("verify-publications: 0 of 1 replays reproduce\n")
