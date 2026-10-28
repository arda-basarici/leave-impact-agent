"""The ``worker``, ``work-one`` and ``worker-health`` commands over the entry's seams: the
composition the service is served with (the sweep composition under a service identity,
the child's command line and the real spawn), the order the child performs once over the
demo's cell (its fields, the ending printed as one line, a refusal answered with 1 and no
line), the environment both refuse without, and the healthcheck's bit from the heartbeat
file."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from leaveimpact.agent.log_store import LogStore
from leaveimpact.agent.log_transition import Rules
from leaveimpact.agent.work_order import WorkOrder
from leaveimpact.agent.worker import HumanApproval, WorkerEnding, WorkerEndingKind
from leaveimpact.app.__main__ import main, work_one_command
from leaveimpact.app.store import AppStore
from leaveimpact.app.worker import (
    SERVICE_PREFIX,
    Heartbeat,
    ServiceComposition,
    decode_ending_line,
    spawn_child,
)
from leaveimpact.core.pricing import PriceTable
from leaveimpact.core.registration import NORMAL_CONDITION, Registration
from leaveimpact.core.run_record import SystemKind
from leaveimpact.core.run_timing import TreeState
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit.app_store_memory import MemoryAppStore
from tests.unit.registration_fixture import COMMITTED, COMMITTED_FILE
from tests.unit.test_app_sweep_command import ENV, Session
from tests.unit.test_app_sweeper import LIVE, Recording

ROOT = Path(__file__).resolve().parents[2]
WORKER_ENV = {
    **ENV,
    "LEAVEIMPACT_REGISTRATION_COMMIT": "d" * 40,
    "LEAVEIMPACT_PRICES_FILE": str(ROOT / "preregistration" / "prices.json"),
}


def run(
    argv: list[str],
    log: Session,
    rows: MemoryAppStore,
    recording: Recording,
    env: dict[str, str],
    served: list[ServiceComposition],
    now: datetime = datetime(2026, 10, 28, 9, 0, tzinfo=UTC),
    performed: list[WorkOrder] | None = None,
    answer: WorkerEnding | Exception | None = None,
) -> int:
    def commands(environment: object, store: LogStore, rules: Rules) -> tuple[object, object]:
        assert store is log, "the service runs over the log the entry opened"
        return recording.publish, recording.inventory

    def serve_fake(
        served_log: LogStore, served_rows: AppStore, composition: ServiceComposition
    ) -> int:
        assert served_log is log and served_rows is rows  # type: ignore[comparison-overlap]
        served.append(composition)
        return 0

    def perform_fake(
        order: WorkOrder,
        registration: Registration,
        prices: PriceTable,
        *,
        store: LogStore,
        rules: Rules,
        env: Mapping[str, str],
    ) -> WorkerEnding:
        assert store is log and rules is histories.RULES and env is env_given
        assert registration == COMMITTED and prices.rows
        if performed is not None:
            performed.append(order)
        if isinstance(answer, Exception):
            raise answer
        assert answer is not None
        return answer

    env_given = env
    return main(
        argv,
        env,
        store=lambda dsn: rows,  # type: ignore[arg-type, return-value]
        restore_log=lambda dsn: cast(LogStore, log),
        configuration=lambda: LIVE,
        registration=lambda path: COMMITTED_FILE.read_bytes(),
        rules=lambda configuration, content: histories.RULES,
        sweep_commands=commands,  # type: ignore[arg-type]
        serve_worker=serve_fake,
        perform_work=perform_fake,
        now=lambda: now,
    )


def test_the_worker_is_served_with_the_sweep_composition_under_a_service_identity(
    tmp_path: Path,
) -> None:
    log, rows, recording = Session(), MemoryAppStore(), Recording()
    served: list[ServiceComposition] = []
    env = {**WORKER_ENV, "LEAVEIMPACT_HEARTBEAT_FILE": str(tmp_path / "beat.json")}
    assert run(["worker"], log, rows, recording, env, served) == 0
    (composition,) = served
    assert composition.identity.startswith(SERVICE_PREFIX)
    assert composition.sweep.launch == composition.identity
    assert composition.sweep.configuration == LIVE
    assert composition.sweep.harness.commit == cases.COMMIT
    assert composition.sweep.reader_commit == cases.COMMIT
    assert composition.heartbeat == tmp_path / "beat.json"
    assert composition.child_command is work_one_command and composition.spawn is spawn_child
    assert log.closed, "the entry closes the log it opened"


REQUEST = ["--run", "run-public-1", "--attempt", "1", "--nonce", "ab" * 16, "--launch", "worker-x"]


def test_work_one_performs_the_order_over_the_demos_cell_once_and_prints_the_ending(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log, rows = Session(), MemoryAppStore()
    performed: list[WorkOrder] = []
    ending = WorkerEnding(WorkerEndingKind.AWAITING_APPROVAL, "run-public-1", 1, 1, "requested")
    status = run(
        ["work-one", *REQUEST],
        log,
        rows,
        Recording(),
        WORKER_ENV,
        [],
        performed=performed,
        answer=ending,
    )
    assert status == 0
    (order,) = performed
    assert (order.attempt.run_id, order.attempt.attempt) == ("run-public-1", 1)
    assert (order.attempt.nonce, order.attempt.launch) == ("ab" * 16, "worker-x")
    assert order.attempt.override is None
    assert order.system is LIVE.system and order.condition == NORMAL_CONDITION
    assert order.level == LIVE.level and order.region == LIVE.region
    assert order.registration_commit == "d" * 40
    assert order.harness.commit == cases.COMMIT and order.harness.tree is TreeState.CLEAN
    assert isinstance(order.approval, HumanApproval)
    assert (order.role is None) == (LIVE.system is SystemKind.RULES_ONLY)
    out = capsys.readouterr()
    assert decode_ending_line(out.out.strip()) == ending and out.err == ""
    assert log.closed


def test_work_one_answers_a_refusal_with_1_on_stderr_and_no_ending_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log, rows = Session(), MemoryAppStore()
    refusal = ValueError("run run-public-1 attempt 1 holds no admission")
    assert run(["work-one", *REQUEST], log, rows, Recording(), WORKER_ENV, [], answer=refusal) == 1
    out = capsys.readouterr()
    assert out.out == "" and "refused: run run-public-1 attempt 1 holds no admission" in out.err
    assert log.closed


def test_work_one_refuses_a_request_that_is_not_one_before_any_store_is_opened(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log, rows = Session(), MemoryAppStore()
    line = ["work-one", "--run", " run-x", "--attempt", "1", "--nonce", "n", "--launch", "l"]
    assert run(line, log, rows, Recording(), WORKER_ENV, [], answer=None) == 2
    assert "a run id" in capsys.readouterr().err and not log.closed


@pytest.mark.parametrize("command", [["worker"], ["work-one", *REQUEST]])
@pytest.mark.parametrize(
    "missing",
    ["LEAVEIMPACT_REGISTRATION_COMMIT", "LEAVEIMPACT_PRICES_FILE", "LEAVEIMPACT_CODE_VERSION"],
)
def test_the_worker_and_its_child_refuse_an_environment_without_what_the_work_needs(
    command: list[str], missing: str, capsys: pytest.CaptureFixture[str]
) -> None:
    log, rows = Session(), MemoryAppStore()
    served: list[ServiceComposition] = []
    env = {name: value for name, value in WORKER_ENV.items() if name != missing}
    assert run(command, log, rows, Recording(), env, served) == 2
    assert missing in capsys.readouterr().err and served == [] and not log.closed


def test_a_short_commit_is_refused_before_any_store_is_opened(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log, rows = Session(), MemoryAppStore()
    served: list[ServiceComposition] = []
    env = {**WORKER_ENV, "LEAVEIMPACT_REGISTRATION_COMMIT": "abc"}
    assert run(["worker"], log, rows, Recording(), env, served) == 2
    assert "the commit the registration was changed at" in capsys.readouterr().err
    assert served == [] and not log.closed


def test_the_health_command_reads_the_heartbeat_against_the_clock(tmp_path: Path) -> None:
    beat = tmp_path / "beat.json"
    now = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)
    env = {**WORKER_ENV, "LEAVEIMPACT_HEARTBEAT_FILE": str(beat)}
    log, rows = Session(), MemoryAppStore()
    served: list[ServiceComposition] = []
    assert run(["worker-health"], log, rows, Recording(), env, served, now) == 1
    Heartbeat("idle", now + timedelta(seconds=6)).write(beat)
    assert run(["worker-health"], log, rows, Recording(), env, served, now) == 0
    assert (
        run(["worker-health"], log, rows, Recording(), env, served, now + timedelta(seconds=6)) == 1
    )
    assert json.loads(beat.read_text(encoding="utf-8"))["state"] == "idle"
    assert served == []
