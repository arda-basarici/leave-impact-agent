"""The public start over the real stores: an admission by the demo's admitter with both
rows read back from the app's tables and the request recorded in the log under the key's
digest, a repeat the same row; two starts at the cap on two connections admitting exactly
the cap, the second serialized on the log's session lock and refused by its own count
(history 8), and the same with the first held inside its admission's transaction and its
app side dying, the external read's history, where a lock on the app's connection had
admitted a sixth; a crash between the log's commit and the section's leaving the admission
with no rows, counted by the next start as busy and given its rows by the repeat
(history 7); the day's window on the log's clock, the sixth start refused and the first of
the next UTC day admitted; and the ledger's refusal recorded under the key and answered as
recorded."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from leaveimpact.agent.log_events import Abandoned, Admitted
from leaveimpact.agent.log_store import LogStore
from leaveimpact.agent.log_transition import Appended
from leaveimpact.app.live import key_digest_of, public_id_for, run_id_for
from leaveimpact.app.start import (
    DEMO_START,
    StartComposition,
    Started,
    StartRefusalKind,
    StartRefused,
    StartRequest,
    start,
)
from leaveimpact.app.store import STATEMENT_TIMEOUT_MS, AppStore
from leaveimpact.core import AbandonmentReason
from leaveimpact.core.ids import ScenarioId
from tests.integration.log_store_support import Hold, Rig, Scripted, rig, wait_until_blocked
from tests.integration.test_log_store import AUTHORITY, PLENTY
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit.publishable_fixture import CONFIGURATION, SCENARIO, SERVED, admission_only
from tests.unit.test_app_start import SWEEPER, key, never_planned

pytestmark = pytest.mark.integration

_ = rig  # the fixture, imported for pytest to find

RULES = histories.RULES
LEDGER = "ledger-demo-test"
LIVE = replace(CONFIGURATION, ledger_id=LEDGER, live_runs=True)
OTHER_SCENARIO = ScenarioId("scenario_004")

_base = admission_only(SERVED, run_id="run-base")[0].event
assert isinstance(_base, Admitted)
BASE = _base.inputs


def plan(scenario_id: ScenarioId, run_id: str, attempt: int) -> object:
    return replace(
        BASE, run_id=run_id, attempt=attempt, context=replace(BASE.context, scenario_id=scenario_id)
    )


def composition(**changes: object) -> StartComposition:
    fields: dict[str, object] = {
        "configuration": LIVE,
        "rules": RULES,
        "scenarios": frozenset({SCENARIO, OTHER_SCENARIO}),
        "plan": plan,
        "world_served": lambda: True,
    }
    fields.update(changes)
    return StartComposition(**fields)  # type: ignore[arg-type]


def app_store(rig: Rig, *, boundary: Callable[[str], None] | None = None) -> AppStore:
    """The store over the rig's schema with the production statement bound."""

    def connect(dsn: str) -> psycopg.Connection[Any]:
        return psycopg.connect(
            dsn,
            connect_timeout=10,
            autocommit=True,
            options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS} -c search_path={rig.schema}",
        )

    extra: dict[str, Any] = {} if boundary is None else {"boundary": boundary}
    return AppStore(dsn=rig.url, connect=connect, **extra)


def prepared(rig: Rig, *, threshold: int = PLENTY) -> tuple[LogStore, AppStore]:
    """The app schema applied and the demo's test ledger given a threshold."""
    log = rig.store()
    log.set_threshold(
        LEDGER,
        threshold,
        authority=AUTHORITY,
        registration_commit=cases.COMMIT,
        limit_pico_usd=PLENTY,
    )
    store = app_store(rig)
    store.ensure_schema()
    return log, store


def closed(log: LogStore, run_id: str) -> None:
    state = log.load(run_id, 1, rules=RULES)
    result = log.close_attempt(
        run_id,
        1,
        SWEEPER,
        Abandoned(state.generation, AbandonmentReason.CANCELLED, None),
        rules=RULES,
    )
    assert isinstance(result, Appended), result


def started(outcome: object) -> Started:
    assert isinstance(outcome, Started), outcome
    return outcome


def refused(outcome: object, kind: StartRefusalKind) -> StartRefused:
    assert isinstance(outcome, StartRefused) and outcome.kind is kind, outcome
    return outcome


def test_a_start_admits_and_both_rows_and_the_recorded_request_are_read_back(rig: Rig) -> None:
    log, store = prepared(rig)
    outcome = started(start(StartRequest(key(1), SCENARIO), log, store, composition()))
    digest = key_digest_of(key(1))
    run_id, public_id = run_id_for(digest), public_id_for(digest)
    assert not outcome.repeated and outcome.row.holds(key(1))
    events = log.events(run_id, 1)
    assert len(events) == 1 and events[0].envelope == DEMO_START
    assert store.live_row_of(public_id) == outcome.row
    assert outcome.row.started_at == events[0].timestamp and outcome.row.decision is None
    publishable = store.row_of(public_id)
    assert publishable is not None and (
        publishable.run_id,
        publishable.attempt,
        publishable.world_version,
        publishable.scenario_id,
        publishable.published_at,
        publishable.published_by,
    ) == (run_id, 1, SERVED, SCENARIO, outcome.row.started_at, DEMO_START.identity)
    recorded = log.recorded_admission(digest)
    assert recorded is not None and recorded.admitted and recorded.run_id == run_id
    again = started(start(StartRequest(key(1), OTHER_SCENARIO), log, store, composition()))
    assert again.repeated and again.row == outcome.row
    assert len(store.rows_for(SERVED)) == 1


def test_two_starts_at_the_cap_on_two_connections_admit_exactly_the_cap(rig: Rig) -> None:
    """History 8: four admitted and closed today; the fifth and the sixth start at once. The
    first holds the log's session lock at ``serialized`` while the server shows the second
    waiting on it; released, the first counts four and admits, the second counts five and
    refuses by the cap. Exactly the cap is admitted, in that order, with no sleep."""
    log, store = prepared(rig)
    for number in range(1, 5):
        outcome = started(start(StartRequest(key(number), SCENARIO), log, store, composition()))
        closed(log, outcome.row.run_id)
    hold = Hold("serialized")
    first_log, second_log = rig.store(boundary=hold), rig.store()
    first_store, second_store = app_store(rig), app_store(rig)
    with ThreadPoolExecutor(max_workers=2) as pool, rig.observer() as observer:
        first = pool.submit(
            start, StartRequest(key(5), SCENARIO), first_log, first_store, composition()
        )
        hold.wait_reached()
        second = pool.submit(
            start, StartRequest(key(6), SCENARIO), second_log, second_store, composition()
        )
        wait_until_blocked(observer, rig.backend_pid(second_log))
        hold.release.set()
        admitted = started(first.result(timeout=10))
        spent = refused(second.result(timeout=10), StartRefusalKind.BUDGET_SPENT)
    assert spent.detail == "today's budget is spent: 5 of 5 starts"
    assert log.recorded_admission(key_digest_of(key(6))) is None, "nothing was asked of the log"
    assert (
        len(store.rows_for(SERVED)) == 5 and store.live_row_of(admitted.row.public_id) is not None
    )
    listed = log.admitted_by(DEMO_START, LEDGER, since=datetime(2000, 1, 1, tzinfo=UTC))
    assert len(listed) == 5 and [each.closed for each in listed] == [True] * 4 + [False]


@dataclass
class DiesOnce:
    at: str
    died: bool = False

    def __call__(self, name: str) -> None:
        if name == self.at and not self.died:
            self.died = True
            raise RuntimeError("the process died")


def test_an_admission_whose_section_was_lost_is_counted_from_the_log_and_repaired(rig: Rig) -> None:
    """History 7 on the real stores: the section's transaction rolls back with the log's
    admission committed; the next start under another key reads the log and is busy; the
    repeat under the first key answers as recorded and writes both rows in a fresh section,
    dated at the admission's instant."""
    log, store = prepared(rig)
    dying = app_store(rig, boundary=DiesOnce("start-before-commit"))
    with pytest.raises(RuntimeError, match="the process died"):
        start(StartRequest(key(1), SCENARIO), log, dying, composition())
    digest = key_digest_of(key(1))
    recorded = log.recorded_admission(digest)
    assert recorded is not None and recorded.admitted
    assert store.row_of(public_id_for(digest)) is None and store.rows_for(SERVED) == ()
    refused(start(StartRequest(key(2), SCENARIO), log, store, composition()), StartRefusalKind.BUSY)
    repaired = started(
        start(StartRequest(key(1), SCENARIO), log, store, composition(plan=never_planned))
    )
    assert repaired.repeated and repaired.row.started_at == recorded.recorded_at
    assert store.live_row_of(public_id_for(digest)) == repaired.row
    publishable = store.row_of(public_id_for(digest))
    assert publishable is not None and publishable.scenario_id == SCENARIO


def test_the_sixth_start_of_a_utc_day_is_refused_and_the_first_of_the_next_admitted(
    rig: Rig,
) -> None:
    """The window is the UTC day of the log's clock: five admissions on one day, each
    closed, then a sixth at the day's last minute refused and a start at the next day's
    first instant admitted. Each start reads the clock once, each admission once more, and
    each closure once."""
    _, store = prepared(rig)
    day = datetime(2026, 10, 26, 0, 0, tzinfo=UTC)
    instants: list[datetime] = []
    for number in range(1, 6):
        at = day + timedelta(hours=number)
        instants.extend([at, at, at + timedelta(minutes=10)])
    next_day = day + timedelta(days=1)
    instants.extend([day + timedelta(hours=23, minutes=59), next_day, next_day])
    scripted = Scripted(instants)
    log = rig.store(clock=scripted)
    for number in range(1, 6):
        outcome = started(start(StartRequest(key(number), SCENARIO), log, store, composition()))
        closed(log, outcome.row.run_id)
    spent = refused(
        start(StartRequest(key(6), SCENARIO), log, store, composition()),
        StartRefusalKind.BUDGET_SPENT,
    )
    assert spent.detail == "today's budget is spent: 5 of 5 starts"
    admitted = started(start(StartRequest(key(6), SCENARIO), log, store, composition()))
    assert admitted.row.started_at == next_day
    assert scripted.given == len(instants), "every instant given was read"


def test_the_ledgers_refusal_is_recorded_under_the_key_and_a_repeat_answers_it(rig: Rig) -> None:
    log, store = prepared(rig, threshold=1)
    first = refused(
        start(StartRequest(key(1), SCENARIO), log, store, composition()),
        StartRefusalKind.RESERVATION_REFUSED,
    )
    assert "exceeds the room of 1" in first.detail and not first.recorded
    assert store.rows_for(SERVED) == () and log.open_attempts() == ()
    again = refused(
        start(StartRequest(key(1), SCENARIO), log, store, composition(plan=never_planned)),
        StartRefusalKind.RESERVATION_REFUSED,
    )
    assert again.recorded and again.detail == first.detail


def test_the_cap_holds_when_a_start_is_held_inside_its_admission_and_its_app_side_dies(
    rig: Rig,
) -> None:
    """The external read's history on the real stores: four admitted and closed today; A
    passes its checks and is held inside its admission's transaction, past the point where
    a lock on the app's connection protected anything; B starts and must wait on A's
    session lock, which lives on the connection committing A's admission. Released, A's
    admission commits, A's app section dies and its rows are lost, and B counts five and
    refuses. Before the fix, B counted four, waited on the ledger head instead, and
    admitted a sixth against a cap of five with two attempts open, reproduced by a probe
    on this rig."""
    log, store = prepared(rig)
    for number in range(1, 5):
        outcome = started(start(StartRequest(key(number), SCENARIO), log, store, composition()))
        closed(log, outcome.row.run_id)
    hold = Hold("before-commit")
    a_log, b_log = rig.store(boundary=hold), rig.store()
    a_store, b_store = app_store(rig, boundary=DiesOnce("start-before-commit")), app_store(rig)
    with ThreadPoolExecutor(max_workers=2) as pool, rig.observer() as observer:
        a = pool.submit(start, StartRequest(key(5), SCENARIO), a_log, a_store, composition())
        hold.wait_reached()
        b = pool.submit(start, StartRequest(key(6), SCENARIO), b_log, b_store, composition())
        wait_until_blocked(observer, rig.backend_pid(b_log))
        hold.release.set()
        with pytest.raises(RuntimeError, match="the process died"):
            a.result(timeout=10)
        spent = refused(b.result(timeout=10), StartRefusalKind.BUDGET_SPENT)
    assert spent.detail == "today's budget is spent: 5 of 5 starts"
    listed = log.admitted_by(DEMO_START, LEDGER, since=datetime(2000, 1, 1, tzinfo=UTC))
    assert len(listed) == 5 and [each.closed for each in listed] == [True] * 4 + [False]
    assert log.recorded_admission(key_digest_of(key(6))) is None, "nothing was asked of the log"
    assert len(store.rows_for(SERVED)) == 4, "A's rows died with its section"
