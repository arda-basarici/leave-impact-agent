"""The ``sweep`` command line: one pass over the in-memory stores through the entry, one
line per action and the exit code by whether every action was carried; the environment
without the commit this code runs as, or without the registration, exits 2 before any
store is touched.
"""

from __future__ import annotations

from datetime import timedelta
from typing import cast

import pytest

from leaveimpact.agent.commands import InventoryRequest, PublishRequest
from leaveimpact.agent.log_events import Abandoned
from leaveimpact.agent.log_store import LogStore, SlotHolder
from leaveimpact.agent.log_transition import Rules
from leaveimpact.app.__main__ import main
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit.app_store_memory import MemoryAppStore
from tests.unit.log_store_memory import MemoryLog
from tests.unit.registration_fixture import COMMITTED_FILE
from tests.unit.test_app_decide import FixedClock
from tests.unit.test_app_sweeper import LIVE, WAIT, Recording, awaiting, run_of, seeded, stopped

ENV = {
    "DATABASE_URL": "postgresql://leaveimpact:x@127.0.0.1:5432/leaveimpact",
    "LEAVEIMPACT_REGISTRATION_FILE": "/app/preregistration/registration.json",
    "LEAVEIMPACT_CODE_VERSION": cases.COMMIT,
}


class Session(MemoryLog):
    """The in-memory log with the entry's ``close``."""

    closed: bool = False

    def close(self) -> None:
        self.closed = True


def run(
    argv: list[str], log: Session, rows: MemoryAppStore, recording: Recording, env: dict[str, str]
) -> int:
    def commands(environment: object, store: LogStore, rules: Rules) -> tuple[object, object]:
        assert store is log, "the pass runs over the log the entry opened"
        return recording.publish, recording.inventory

    return main(
        argv,
        env,
        store=lambda dsn: rows,  # type: ignore[arg-type, return-value]
        restore_log=lambda dsn: cast(LogStore, log),
        configuration=lambda: LIVE,
        registration=lambda path: COMMITTED_FILE.read_bytes(),
        rules=lambda configuration, content: histories.RULES,
        sweep_commands=commands,  # type: ignore[arg-type]
    )


def test_a_pass_closes_the_wait_and_prints_one_line_per_action(
    capsys: pytest.CaptureFixture[str],
) -> None:
    clock = FixedClock(cases.ADMITTED)
    log, rows = Session(clock=clock), MemoryAppStore()
    history = seeded(log, rows, 1, awaiting())
    clock.at = history[7].timestamp + WAIT
    code = run(["sweep"], log, rows, Recording(), ENV)
    lines = capsys.readouterr().out.splitlines()
    assert code == 0 and log.closed
    assert lines == [
        f"sweep: CloseWait run_id={run_of(1)} attempt=1: ok: cancelled at position 10",
        "sweep: 1 of 1 actions carried",
    ]
    state = log.load(run_of(1), 1, rules=histories.RULES)
    assert state.closed is not None and isinstance(state.closed.event, Abandoned)


def test_an_action_not_carried_exits_1_and_says_why(capsys: pytest.CaptureFixture[str]) -> None:
    clock = FixedClock(cases.ADMITTED + timedelta(minutes=1))
    log, rows = Session(clock=clock), MemoryAppStore()
    seeded(log, rows, 1, stopped())
    log.slot = SlotHolder("run-other", 1, 1, "launch-9", cases.ADMITTED)
    code = run(["sweep"], log, rows, Recording(), ENV)
    lines = capsys.readouterr().out.splitlines()
    assert code == 1 and log.closed
    assert lines[0].startswith(f"sweep: Finalize run_id={run_of(1)} attempt=1: NOT CARRIED: ")
    assert "run-other" in lines[0]
    assert lines[1] == "sweep: 0 of 1 actions carried"


def test_the_environment_without_the_commit_or_the_registration_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log, rows = Session(), MemoryAppStore()
    without_commit = {name: value for name, value in ENV.items() if "CODE_VERSION" not in name}
    assert run(["sweep"], log, rows, Recording(), without_commit) == 2
    assert "LEAVEIMPACT_CODE_VERSION" in capsys.readouterr().err
    short = {**ENV, "LEAVEIMPACT_CODE_VERSION": "abc123"}
    assert run(["sweep"], log, rows, Recording(), short) == 2
    without_registration = {
        name: value for name, value in ENV.items() if "REGISTRATION" not in name
    }
    assert run(["sweep"], log, rows, Recording(), without_registration) == 2
    assert "LEAVEIMPACT_REGISTRATION_FILE" in capsys.readouterr().err
    assert not log.closed, "no store was opened"


def test_a_pass_with_nothing_to_do_prints_the_count_alone(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log, rows = Session(clock=FixedClock(cases.ADMITTED)), MemoryAppStore()
    seeded(log, rows, 1, awaiting())
    assert run(["sweep"], log, rows, Recording(), ENV) == 0
    assert capsys.readouterr().out.splitlines() == ["sweep: 0 of 0 actions carried"]


def test_the_commands_are_bound_to_the_commit_the_environment_names() -> None:
    """The publications of a pass are built as the commit this code runs as: the entry
    reads it once and the composition carries it to every publish and inventory request."""
    clock = FixedClock(cases.ADMITTED + timedelta(minutes=1))
    log, rows = Session(clock=clock), MemoryAppStore()
    seeded(log, rows, 1, histories.HISTORIES["an approval wait across a restart"]())
    recording = Recording()
    other = {**ENV, "LEAVEIMPACT_CODE_VERSION": "c" * 40}
    assert run(["sweep"], log, rows, recording, other) == 0
    assert recording.published == [PublishRequest(run_of(1), 1, "c" * 40)]
    assert [each.builder_commit for each in recording.inventoried] == ["c" * 40]
    assert isinstance(recording.inventoried[0], InventoryRequest)
