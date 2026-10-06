"""The store without a database: construction opens nothing, a connection that cannot be
opened is ``LogStoreUnavailable`` after one attempt, a statement that fails on the wire
discards the connection so the next command reconnects, and an admission request names a
ledger exactly when its inputs reserve."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import psycopg
import pytest

from leaveimpact.agent.log_events import Producer
from leaveimpact.agent.log_store import AdmissionRequest, LogStore, LogStoreUnavailable
from leaveimpact.core.run_record import System, SystemKind
from tests.unit import log_histories as histories


class Refusing:
    """A connect seam that refuses, counting the attempts."""

    def __init__(self) -> None:
        self.attempts = 0

    def __call__(self, dsn: str) -> Any:
        self.attempts += 1
        raise psycopg.OperationalError("connection refused")


class Breaking:
    """A connection whose every statement fails as the wire would; ``closed`` counts discards."""

    closed = 0

    def execute(self, *args: object, **kwargs: object) -> Any:
        raise psycopg.OperationalError("server closed the connection unexpectedly")

    def close(self) -> None:
        Breaking.closed += 1


def test_construction_opens_nothing_and_a_refused_connection_is_unavailable_after_one_attempt() -> (
    None
):
    refusing = Refusing()
    store = LogStore(dsn="postgresql://nobody@localhost/none", connect=refusing)
    assert refusing.attempts == 0
    with pytest.raises(LogStoreUnavailable, match="connection refused: OperationalError"):
        store.open_attempts()
    assert refusing.attempts == 1


def test_a_statement_that_fails_on_the_wire_discards_the_connection() -> None:
    made: list[Breaking] = []
    Breaking.closed = 0

    def connect(dsn: str) -> Any:
        made.append(Breaking())
        return made[-1]

    store = LogStore(dsn="postgresql://nobody@localhost/none", connect=connect)
    for _ in range(2):
        with pytest.raises(LogStoreUnavailable, match="statement failed"):
            store.open_attempts()
    assert len(made) == 2 and Breaking.closed == 2, "a broken connection is dropped, not reused"


def test_an_admission_request_names_a_ledger_exactly_when_the_inputs_reserve() -> None:
    reserving = histories.inputs(reservation=1_000)
    rules_only = histories.inputs(reservation=None, system=System(SystemKind.RULES_ONLY, "rules"))
    admitter = Producer("admitter")
    AdmissionRequest("req-1", reserving, admitter, "ledger-1", histories.RULES)
    with pytest.raises(ValueError, match="exactly when the inputs reserve"):
        AdmissionRequest("req-1", reserving, admitter, None, histories.RULES)
    with pytest.raises(ValueError, match="exactly when the inputs reserve"):
        AdmissionRequest("req-1", rules_only, admitter, "ledger-1", histories.RULES)
    AdmissionRequest("req-1", replace(rules_only), admitter, None, histories.RULES)
