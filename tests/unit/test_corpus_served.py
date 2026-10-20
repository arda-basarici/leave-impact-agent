"""The readiness read on the corpus adapter's read side: the served versions over one
bounded connection, a refused connection and a cancelled statement both the port's
unreachable (so the next read starts clean and the route answers 503), the default
connection bounded on the connect and on the statement under the probes' client timeout."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

from leaveimpact.adapters.corpus import served_versions
from leaveimpact.adapters.corpus.adapter import (
    READINESS_CONNECT_TIMEOUT_S,
    READINESS_STATEMENT_TIMEOUT_MS,
)
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.ports.errors import SourceUnreachable

DSN = "postgresql://nobody@localhost/none"
GOLDEN = WorldVersion("7" * 64)
OTHER = WorldVersion("8" * 64)


class Serving:
    """A connection answering the select with the ready rows."""

    def __init__(self, versions: tuple[str, ...]) -> None:
        self.versions = versions
        self.closed = False

    def __enter__(self) -> Serving:
        return self

    def __exit__(self, *_: object) -> None:
        self.closed = True

    def execute(self, statement: Any, params: Any = None) -> Any:
        assert "WHERE ready" in statement
        return self

    def fetchall(self) -> list[tuple[str]]:
        return [(version,) for version in self.versions]


class Blocked(Serving):
    """A connection whose select the server cancels at the statement timeout."""

    def execute(self, statement: Any, params: Any = None) -> Any:
        raise psycopg.errors.QueryCanceled("canceling statement due to statement timeout")


def test_the_served_versions_are_the_ready_rows_and_the_connection_is_closed() -> None:
    made = Serving((GOLDEN, OTHER))
    assert served_versions(DSN, connect=lambda dsn: made) == {GOLDEN, OTHER}  # type: ignore[arg-type, return-value]
    assert made.closed


def test_a_cancelled_statement_and_a_refused_connection_are_unreachable_then_recover() -> None:
    """The route's 503 for a blocked query and its 200 once the store answers again come
    from the same code path with no state between reads: each read connects afresh."""
    answers: list[Any] = [Blocked(()), Serving((GOLDEN,))]

    def connect(dsn: str) -> Any:
        return answers.pop(0)

    with pytest.raises(SourceUnreachable, match="did not complete: QueryCanceled"):
        served_versions(DSN, connect=connect)
    assert served_versions(DSN, connect=connect) == {GOLDEN}

    def refused(dsn: str) -> Any:
        raise psycopg.OperationalError("connection refused")

    with pytest.raises(SourceUnreachable, match="OperationalError"):
        served_versions(DSN, connect=refused)


def test_the_default_connection_is_bounded_on_the_connect_and_the_statement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Under the eight-second client timeout of the compose healthcheck and the deploy's
    read, so the route answers before the probe gives up."""
    seen: dict[str, Any] = {}

    def recording(dsn: str, **kwargs: Any) -> Any:
        seen.update(kwargs, dsn=dsn)
        return Serving(())

    monkeypatch.setattr(psycopg, "connect", recording)
    assert served_versions(DSN) == frozenset()
    assert seen == {
        "dsn": DSN,
        "connect_timeout": READINESS_CONNECT_TIMEOUT_S,
        "options": f"-c statement_timeout={READINESS_STATEMENT_TIMEOUT_MS}",
        "autocommit": True,
    }
    assert READINESS_CONNECT_TIMEOUT_S + READINESS_STATEMENT_TIMEOUT_MS / 1000 < 8
