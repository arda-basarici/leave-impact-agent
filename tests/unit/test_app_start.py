"""The public start over the in-memory stores: an admission under the demo's admitter with
both rows written at the log's instant; a repeat under the key answered as recorded and
admitting nothing, before the flag, the served world, the scenario, the cap or the
single-open condition can refuse it as new; the flag, the world and the scenario checked
before any rule reads the log; the single-open condition and the cap over the log's
listing by instant and closed flag, an operator's admission on the ledger counting for
neither; the ledger's refusal recorded under the key and answered as such on a repeat;
and the lost rows of a crash between the log's commit and the section's, counted from the
log and written by the repeat."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import pytest

from leaveimpact.agent.log_events import Abandoned, Admitted, Producer
from leaveimpact.agent.log_transition import Appended
from leaveimpact.app.live import StartKey, key_digest_of, public_id_for, run_id_for
from leaveimpact.app.start import (
    DEMO_START,
    StartComposition,
    Started,
    StartRefusalKind,
    StartRefused,
    StartRequest,
    start,
)
from leaveimpact.core import AbandonmentReason
from leaveimpact.core.ids import ScenarioId
from tests.unit import log_histories as histories
from tests.unit.app_store_memory import MemoryAppStore
from tests.unit.log_store_memory import LEDGER, MemoryLog
from tests.unit.publishable_fixture import CONFIGURATION, SCENARIO, SERVED, admission_only

RULES = histories.RULES
LIVE = replace(CONFIGURATION, ledger_id=LEDGER, live_runs=True)
OTHER_SCENARIO = ScenarioId("scenario_004")
SCENARIOS = frozenset({SCENARIO, OTHER_SCENARIO})
SWEEPER = Producer("demo-sweeper")
NOON = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

_base = admission_only(SERVED, run_id="run-base")[0].event
assert isinstance(_base, Admitted)
BASE = _base.inputs
"""The fixtures' frozen inputs under the served world: what the planner re-states."""


def key(number: int) -> StartKey:
    return StartKey(f"{number:032x}")


def plan(scenario_id: ScenarioId, run_id: str, attempt: int) -> object:
    return replace(
        BASE, run_id=run_id, attempt=attempt, context=replace(BASE.context, scenario_id=scenario_id)
    )


def never_planned(scenario_id: ScenarioId, run_id: str, attempt: int) -> object:
    raise AssertionError("the planner was called")


def composition(**changes: object) -> StartComposition:
    fields: dict[str, object] = {
        "configuration": LIVE,
        "rules": RULES,
        "scenarios": SCENARIOS,
        "plan": plan,
        "world_served": lambda: True,
    }
    fields.update(changes)
    return StartComposition(**fields)  # type: ignore[arg-type]


@dataclass
class Instants:
    """A clock answering the given instants in order; the log reads it once at ``now`` and
    once at each admission."""

    instants: list[datetime]

    def __call__(self) -> datetime:
        if not self.instants:
            raise AssertionError("the clock was asked for more instants than it was given")
        return self.instants.pop(0)


def stores(
    clock: Callable[[], datetime] | None = None, threshold: int | None = None
) -> tuple[MemoryLog, MemoryAppStore]:
    extra: dict[str, object] = {}
    if clock is not None:
        extra["clock"] = clock
    if threshold is not None:
        extra["threshold"] = threshold
    return MemoryLog(**extra), MemoryAppStore()  # type: ignore[arg-type]


def closed(log: MemoryLog, run_id: str) -> None:
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


# --- an admission and its repeat ---------------------------------------------------------------


def test_a_start_admits_under_the_demo_admitter_and_writes_both_rows_at_the_logs_instant() -> None:
    log, rows = stores()
    outcome = started(start(StartRequest(key(1), SCENARIO), log, rows, composition()))
    digest = key_digest_of(key(1))
    run_id, public_id = run_id_for(digest), public_id_for(digest)
    assert not outcome.repeated
    logged = log.events(run_id, 1)
    assert len(logged) == 1 and logged[0].envelope == DEMO_START
    assert isinstance(logged[0].event, Admitted)
    assert logged[0].event.inputs == plan(SCENARIO, run_id, 1)
    row = outcome.row
    assert (row.public_id, row.run_id, row.attempt, row.key_digest) == (
        public_id,
        run_id,
        1,
        digest,
    )
    assert row.started_at == logged[0].timestamp and row.decision is None
    assert row.holds(key(1)) and rows.live_row_of(public_id) == row
    publishable = rows.row_of(public_id)
    assert publishable is not None
    assert (
        publishable.world_version,
        publishable.scenario_id,
        publishable.title,
        publishable.published_at,
        publishable.published_by,
    ) == (SERVED, SCENARIO, None, row.started_at, DEMO_START.identity)
    recorded = log.recorded_admission(digest)
    assert recorded is not None and (recorded.run_id, recorded.attempt, recorded.admitted) == (
        run_id,
        1,
        True,
    )


def test_a_repeat_under_the_key_is_the_same_attempt_whatever_else_the_form_says() -> None:
    """A double submit or a resent form carries the same key, and the key decides: the same
    row comes back, nothing new is admitted, and a scenario the repeat names is ignored,
    since the recorded request is resolved before any input is read."""
    log, rows = stores()
    first = started(start(StartRequest(key(1), SCENARIO), log, rows, composition()))
    again = started(start(StartRequest(key(1), OTHER_SCENARIO), log, rows, composition()))
    assert again.repeated and again.row == first.row
    assert len(log.logs) == 1 and len(rows.rows) == 1 and len(rows.live) == 1


def test_a_recorded_request_is_answered_before_the_flag_the_world_and_the_rules() -> None:
    """History 17: after a deploy that turned the flag off, changed what the planner would
    build and even stopped serving the world, a repeat under a recorded key is answered
    as recorded and the planner is never asked; a new key is refused by the flag."""
    log, rows = stores()
    first = started(start(StartRequest(key(1), SCENARIO), log, rows, composition()))
    later = composition(
        configuration=replace(LIVE, live_runs=False),
        plan=never_planned,
        world_served=lambda: False,
    )
    again = started(start(StartRequest(key(1), SCENARIO), log, rows, later))
    assert again.repeated and again.row == first.row
    refused(start(StartRequest(key(2), SCENARIO), log, rows, later), StartRefusalKind.LIVE_RUNS_OFF)
    assert len(log.logs) == 1


# --- the checks before the rules -----------------------------------------------------------------


def test_the_flag_the_served_world_and_the_scenario_refuse_before_any_rule_reads_the_log() -> None:
    log, rows = stores(clock=Instants([]))  # a rule would read the clock; none may
    off = composition(configuration=replace(LIVE, live_runs=False), plan=never_planned)
    refused(start(StartRequest(key(1), SCENARIO), log, rows, off), StartRefusalKind.LIVE_RUNS_OFF)
    unserved = composition(world_served=lambda: False, plan=never_planned)
    refused(
        start(StartRequest(key(1), SCENARIO), log, rows, unserved),
        StartRefusalKind.WORLD_NOT_SERVED,
    )
    unknown = refused(
        start(
            StartRequest(key(1), ScenarioId("scenario_099")),
            log,
            rows,
            composition(plan=never_planned),
        ),
        StartRefusalKind.UNKNOWN_SCENARIO,
    )
    assert "scenario_099" in unknown.detail
    assert not log.logs and not rows.rows and not log.requests


# --- the rules -----------------------------------------------------------------------------------


def test_a_second_start_while_one_is_open_is_busy_and_an_operators_open_run_is_not_counted() -> (
    None
):
    """History 9: the single-open condition counts open attempts admitted by the demo's
    admitter; an operator's open attempt on the same ledger is not a public one."""
    log, rows = stores()
    log.seed(admission_only(SERVED, run_id="run-operator"))  # the fixtures' admitter, open
    first = started(start(StartRequest(key(1), SCENARIO), log, rows, composition()))
    busy = refused(
        start(StartRequest(key(2), OTHER_SCENARIO), log, rows, composition()), StartRefusalKind.BUSY
    )
    assert "replays" in busy.detail
    closed(log, first.row.run_id)
    second = started(start(StartRequest(key(2), OTHER_SCENARIO), log, rows, composition()))
    assert not second.repeated and second.row.run_id != first.row.run_id


def test_the_sixth_start_of_a_utc_day_is_refused_and_the_first_of_the_next_admitted() -> None:
    """The cap counts admissions whose instant is at or after the UTC day's start on the
    log's clock, closed ones included; the listing's older open entries are not a count.
    Each start reads the clock once and each admission once more; a closure reads it too."""
    day = datetime(2026, 10, 26, 0, 0, tzinfo=UTC)
    instants = Instants([])
    log, rows = stores(clock=instants)
    for number in range(1, 6):
        at = day + timedelta(hours=number)
        instants.instants.extend([at, at, at + timedelta(minutes=10)])
        outcome = started(start(StartRequest(key(number), SCENARIO), log, rows, composition()))
        closed(log, outcome.row.run_id)
    instants.instants.append(day + timedelta(hours=23, minutes=59))
    spent = refused(
        start(StartRequest(key(6), SCENARIO), log, rows, composition()),
        StartRefusalKind.BUDGET_SPENT,
    )
    assert spent.detail == "today's budget is spent: 5 of 5 starts"
    next_day = day + timedelta(days=1)
    instants.instants.extend([next_day, next_day])
    admitted = started(start(StartRequest(key(6), SCENARIO), log, rows, composition()))
    assert admitted.row.started_at == next_day
    assert not instants.instants, "every instant given was read"


def test_the_ledgers_refusal_is_the_logs_recorded_one_and_a_repeat_answers_it() -> None:
    """The log refuses the reservation, records the refusal under the key, and the start
    writes nothing; a repeat under the key finds the recorded refusal and answers it with
    the same reason, marked as recorded, admitting nothing."""
    log, rows = stores(threshold=1)
    first = refused(
        start(StartRequest(key(1), SCENARIO), log, rows, composition()),
        StartRefusalKind.RESERVATION_REFUSED,
    )
    assert "exceeds the room of 1" in first.detail and not first.recorded
    assert not log.logs and not rows.rows and not rows.live
    again = refused(
        start(StartRequest(key(1), SCENARIO), log, rows, composition(plan=never_planned)),
        StartRefusalKind.RESERVATION_REFUSED,
    )
    assert again.recorded and again.detail == first.detail
    assert not log.logs and not rows.rows


# --- the crash between the two commits -----------------------------------------------------------


@dataclass
class DiesOnce:
    """A boundary that raises the first time it reaches ``at``: the process dying with the
    log's admission committed and the section's transaction open."""

    at: str
    died: bool = False

    def __call__(self, name: str) -> None:
        if name == self.at and not self.died:
            self.died = True
            raise RuntimeError("the process died")


def test_an_admission_whose_rows_were_lost_is_counted_from_the_log_and_written_by_the_repeat() -> (
    None
):
    """History 7: the log holds the attempt and no row exists; the next start under another
    key is refused as busy, since the rules read the log; the repeat under the first key
    answers as recorded and writes both rows then, at the admission's instant."""
    log, rows = stores()
    rows.boundary = DiesOnce("start-before-commit")
    with pytest.raises(RuntimeError, match="the process died"):
        start(StartRequest(key(1), SCENARIO), log, rows, composition())
    digest = key_digest_of(key(1))
    assert log.recorded_admission(digest) is not None and not rows.rows and not rows.live
    refused(start(StartRequest(key(2), SCENARIO), log, rows, composition()), StartRefusalKind.BUSY)
    repaired = started(
        start(StartRequest(key(1), SCENARIO), log, rows, composition(plan=never_planned))
    )
    assert repaired.repeated
    assert repaired.row.started_at == log.events(run_id_for(digest), 1)[0].timestamp
    assert rows.live_row_of(public_id_for(digest)) == repaired.row
    publishable = rows.row_of(public_id_for(digest))
    assert publishable is not None and publishable.scenario_id == SCENARIO
    assert len(log.logs) == 1
