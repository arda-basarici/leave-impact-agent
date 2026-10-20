"""The demo surface's store at the unit level: the bounded connection it opens and closes per
operation, a refused connection and a cancelled statement both its named unavailability (so
the readiness route answers 503 and the next read starts clean), a missing table or another
version read as unsupported and never as an exception, and the bootstrap command over a
fake store (the one line it prints, the two refusals, the two exit codes)."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

from leaveimpact.app.__main__ import main
from leaveimpact.app.public import PublicId
from leaveimpact.app.store import (
    CONNECT_TIMEOUT_S,
    SCHEMA_VERSION,
    STATEMENT_TIMEOUT_MS,
    AppStore,
    AppStoreInvariantBroken,
    AppStoreUnavailable,
)
from leaveimpact.core.ids import WorldVersion

DSN = "postgresql://nobody@localhost/none"


class Answering:
    """A connection whose version select answers ``version`` (``None`` for no row), closed on
    exit; ``executed`` records every statement so a test sees the DDL and the insert."""

    def __init__(self, version: int | None) -> None:
        self.version = version
        self.closed = False
        self.executed: list[str] = []

    def __enter__(self) -> Answering:
        return self

    def __exit__(self, *_: object) -> None:
        self.closed = True

    def transaction(self) -> Answering:
        return self

    def execute(self, statement: Any, params: Any = None) -> Any:
        text = statement.decode() if isinstance(statement, bytes) else str(statement)
        self.executed.append(text)
        return self

    def fetchone(self) -> tuple[int] | None:
        return None if self.version is None else (self.version,)


class NoTable(Answering):
    """A database that was never bootstrapped: the select raises the driver's undefined-table."""

    def fetchone(self) -> tuple[int] | None:
        raise psycopg.errors.UndefinedTable('relation "app_schema" does not exist')


class Blocked(Answering):
    """A connection whose statement the server cancels at the statement timeout."""

    def execute(self, statement: Any, params: Any = None) -> Any:
        raise psycopg.errors.QueryCanceled("canceling statement due to statement timeout")


class NoLog(Answering):
    """A database whose run log was never bootstrapped: the DDL's reference to the attempt
    table fails."""

    def execute(self, statement: Any, params: Any = None) -> Any:
        if isinstance(statement, bytes):
            raise psycopg.errors.UndefinedTable('relation "attempt" does not exist')
        return super().execute(statement, params)


def store_over(*answers: Any) -> tuple[AppStore, list[Any]]:
    """A store whose successive operations get the connections in order."""
    queue = list(answers)
    return AppStore(dsn=DSN, connect=lambda dsn: queue.pop(0)), queue


def test_schema_supported_is_this_version_and_nothing_else_closing_the_connection() -> None:
    current = Answering(SCHEMA_VERSION)
    store, _ = store_over(current, Answering(SCHEMA_VERSION + 1), Answering(None), NoTable(0))
    assert store.schema_supported() is True
    assert current.closed
    assert store.schema_supported() is False  # another version
    assert store.schema_supported() is False  # no version row
    assert store.schema_supported() is False  # no table at all


def test_a_cancelled_statement_and_a_refused_connection_are_unavailable_then_recover() -> None:
    store, _ = store_over(Blocked(0), Answering(SCHEMA_VERSION))
    with pytest.raises(AppStoreUnavailable, match="did not answer: QueryCanceled"):
        store.schema_supported()
    assert store.schema_supported() is True

    def refused(dsn: str) -> Any:
        raise psycopg.OperationalError("connection refused")

    with pytest.raises(AppStoreUnavailable, match="OperationalError"):
        AppStore(dsn=DSN, connect=refused).schema_supported()


def test_ensure_schema_applies_the_ddl_writes_the_version_once_and_refuses_another() -> None:
    fresh = Answering(SCHEMA_VERSION)
    store, _ = store_over(fresh, Answering(SCHEMA_VERSION + 1))
    store.ensure_schema()
    ddl, insert, select = fresh.executed
    assert "CREATE TABLE IF NOT EXISTS publishable_attempt" in ddl
    assert insert.startswith("INSERT INTO app_schema") and "DO NOTHING" in insert
    assert select == "SELECT version FROM app_schema"
    assert fresh.closed
    with pytest.raises(AppStoreInvariantBroken, match=f"version {SCHEMA_VERSION}, the database"):
        store.ensure_schema()


def test_a_content_read_on_another_version_is_refused_before_any_content_statement() -> None:
    """The step's external read: readiness answering 503 does not stop requests reaching the
    process, so every read and write of the publishable table checks the version on its own
    connection first, as the log store does, and a database at another layout or none
    serves no row and takes none."""
    older = Answering(SCHEMA_VERSION + 1)
    never = NoTable(None)
    store, _ = store_over(older, never)
    with pytest.raises(AppStoreInvariantBroken, match=f"holds {SCHEMA_VERSION + 1}; run"):
        store.rows_for(WorldVersion("w" * 64))
    assert older.executed == ["SELECT version FROM app_schema"] and older.closed
    with pytest.raises(AppStoreInvariantBroken, match="holds none; run"):
        store.row_of(PublicId("anyone"))
    assert never.executed == ["SELECT version FROM app_schema"] and never.closed


def test_a_database_without_the_run_log_is_refused_by_name_before_any_version_row() -> None:
    """The deploy runs the log's bootstrap first; a bootstrap on a database that skipped it
    names the order rather than printing the driver's missing-relation traceback."""
    bare = NoLog(None)
    store, _ = store_over(bare)
    with pytest.raises(AppStoreInvariantBroken, match="run log is not bootstrapped.*bootstrap-log"):
        store.ensure_schema()
    assert bare.closed and len(bare.executed) == 0


def test_the_default_connection_is_bounded_on_the_connect_and_the_statement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One operation's bounds sum under the probes' eight-second client timeout, the same
    arithmetic the corpus adapter's readiness read makes."""
    seen: dict[str, Any] = {}

    def recording(dsn: str, **kwargs: Any) -> Any:
        seen.update(kwargs, dsn=dsn)
        return Answering(SCHEMA_VERSION)

    monkeypatch.setattr(psycopg, "connect", recording)
    assert AppStore(dsn=DSN).schema_supported() is True
    assert seen == {
        "dsn": DSN,
        "connect_timeout": CONNECT_TIMEOUT_S,
        "options": f"-c statement_timeout={STATEMENT_TIMEOUT_MS}",
        "autocommit": True,
    }
    assert CONNECT_TIMEOUT_S + STATEMENT_TIMEOUT_MS / 1000 < 8


class FakeStore:
    """The command's seam: records the dsn it was built over and raises what a test scripts."""

    built: list[str] = []

    def __init__(self, dsn: str, failure: Exception | None = None) -> None:
        self.dsn = dsn
        self.failure = failure

    def ensure_schema(self) -> None:
        FakeStore.built.append(self.dsn)
        if self.failure is not None:
            raise self.failure


def test_bootstrap_applies_the_schema_to_the_environments_database_and_prints_the_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    FakeStore.built.clear()
    assert main(["bootstrap"], {"DATABASE_URL": DSN}, store=FakeStore) == 0  # type: ignore[arg-type]
    assert FakeStore.built == [DSN]
    assert capsys.readouterr().out == f"app schema version {SCHEMA_VERSION} established\n"


@pytest.mark.parametrize(
    "failure",
    [
        AppStoreInvariantBroken("this code reads and writes app schema version 1, the database 2"),
        AppStoreUnavailable("the app store did not answer: OperationalError"),
    ],
)
def test_a_refusal_the_store_names_exits_1_with_the_reason(
    failure: Exception, capsys: pytest.CaptureFixture[str]
) -> None:
    def failing(dsn: str) -> FakeStore:
        return FakeStore(dsn, failure)

    assert main(["bootstrap"], {"DATABASE_URL": DSN}, store=failing) == 1  # type: ignore[arg-type]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"leaveimpact.app: refused: {failure}\n"


def test_another_command_line_or_no_database_exits_2_before_any_store(
    capsys: pytest.CaptureFixture[str],
) -> None:
    FakeStore.built.clear()
    assert main([], {"DATABASE_URL": DSN}, store=FakeStore) == 2  # type: ignore[arg-type]
    assert main(["bootstrap", "--force"], {"DATABASE_URL": DSN}, store=FakeStore) == 2  # type: ignore[arg-type]
    assert main(["bootstrap"], {}, store=FakeStore) == 2  # type: ignore[arg-type]
    assert FakeStore.built == []
    err = capsys.readouterr().err
    assert "usage: python -m leaveimpact.app" in err
    assert "DATABASE_URL is not set" in err
