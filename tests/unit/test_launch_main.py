"""The launcher's command line: ``plan`` over the local store writes the admission request
the agent's entry decodes to the plan's inputs and the cell flags its work line parses,
prints identities and counts and never the scenario's leave or instant, and refuses a
scenario the world lacks and a ledger the system's reservation contradicts; ``status`` prints
an attempt's state as fields with the lifecycle's next step."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from leaveimpact.agent import __main__ as job
from leaveimpact.agent.graph import NoPreparation
from leaveimpact.agent.registered import effective_rules
from leaveimpact.agent.worker import AutomaticApproval, Worker, WorkerConfiguration
from leaveimpact.core.attribution import attribution_table_digest
from leaveimpact.core.run_record import SystemKind
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.launch import __main__ as launcher
from leaveimpact.launch.plan import RunCell, plan_run
from tests.unit import format_fixtures as cases
from tests.unit import worker_support as support
from tests.unit.launch_fixture import SealedDevelopment, probe_helper, seal_development
from tests.unit.log_store_memory import LEDGER, MemoryLog
from tests.unit.reads_fixture import systems_holding
from tests.unit.throwaway_world import loaded_world

COMMIT = "c" * 40
RUN, ATTEMPT = "run-12", 1


@pytest.fixture(scope="module")
def probe() -> Any:
    return probe_helper()


@pytest.fixture(scope="module")
def development(tmp_path_factory: pytest.TempPathFactory) -> SealedDevelopment:
    return seal_development(tmp_path_factory.mktemp("development-store"))


def _scenario_id(development: SealedDevelopment) -> str:
    return str(development.world.scenarios[0].spec.id)


def _plan_line(
    probe: Any,
    development: SealedDevelopment,
    out: Path,
    *,
    system: str = "agent",
    **overrides: str,
) -> list[str]:
    fields = {
        "--world-version": str(development.version),
        "--scenario": _scenario_id(development),
        "--system": system,
        "--condition": probe.CONDITION,
        "--level": probe.LEVEL,
        "--registration": str(probe.REGISTRATION_FILE),
        "--registration-commit": COMMIT,
        "--prices": str(probe.PRICES_FILE),
        "--region": probe.REGION,
        "--run": RUN,
        "--attempt": str(ATTEMPT),
        "--request-id": "req-1",
        "--admitter": "launcher:test",
        "--out": str(out),
        **overrides,
    }
    line = ["plan"]
    for flag, value in fields.items():
        line += [flag, value]
    if system != "rules_only":
        line += ["--ledger", "ledger-dev"]
    return line


def _env(development: SealedDevelopment) -> dict[str, str]:
    return {"LEAVE_IMPACT_OBJECT_STORE_ROOT": str(development.root)}


def test_plan_writes_the_request_the_entry_decodes_and_the_flags_its_work_line_parses(
    probe: Any, development: SealedDevelopment, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The request file decodes, under the registration's rules, to the admission request
    whose inputs are the plan's for the same scenario read from the store; the flags file
    completes a work line the entry parses to that cell; the log holds the ids and nothing
    the specification states."""
    out = tmp_path / "run"
    status = launcher.main(_plan_line(probe, development, out), _env(development))
    captured = capsys.readouterr()
    assert status == 0, captured.err
    printed = dict(line.split("=", 1) for line in captured.out.splitlines())
    assert re.fullmatch(r"launch-[0-9a-f]{32}", printed["launch"])
    assert printed["run"] == RUN and printed["attempt"] == "1"
    assert printed["scenario"] == _scenario_id(development) and printed["system"] == "agent"
    registration = probe.registration()
    rules = effective_rules(registration)
    request = job.admission_request_of((out / launcher.REQUEST_FILE).read_bytes(), rules)
    scenario = development.world.scenarios[0]
    expected = plan_run(
        registration,
        registration_commit=COMMIT,
        prices=probe.price_table(),
        cell=RunCell(SystemKind.AGENT, probe.CONDITION, probe.LEVEL),
        spec=scenario.spec,
        world_version=development.version,
        run_id=RUN,
        attempt=ATTEMPT,
        region=probe.REGION,
    )
    assert request.inputs == expected.inputs
    assert (request.request_id, request.admitter.identity, request.ledger_id) == (
        "req-1",
        "launcher:test",
        "ledger-dev",
    )
    assert printed["reservation_pico_usd"] == str(expected.inputs.reservation_pico_usd)
    for sealed in (str(scenario.spec.leave_id), scenario.spec.now.isoformat()):
        assert sealed not in captured.out and sealed not in captured.err
    flags = (out / launcher.WORK_ARGUMENTS_FILE).read_text(encoding="utf-8").split("\n")
    assert flags[-1] == "" and all(flags[:-1])
    parsed = job.parse_request(
        [
            "work",
            "--run",
            RUN,
            "--attempt",
            "1",
            "--nonce",
            "n",
            "--launch",
            printed["launch"],
            "--registration",
            str(probe.REGISTRATION_FILE),
            "--prices",
            str(probe.PRICES_FILE),
            *flags[:-1],
        ],
        {job.CODE_VERSION: "a" * 40},
    ).request
    assert isinstance(parsed, job.WorkLine) and parsed.system is SystemKind.AGENT
    assert (
        parsed.role is not None
        and parsed.role.configuration == expected.inputs.model_configurations[0][1]
    )


def test_plan_refuses_what_the_world_or_the_cell_contradicts(
    probe: Any, development: SealedDevelopment, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A scenario the world lacks is refused by id; a model system with no ledger and rules
    only with one are configuration faults before any store is read; an unreadable
    registration is reported by its name and the exception's type."""
    out = tmp_path / "run"
    env = _env(development)
    line = _plan_line(probe, development, out, **{"--scenario": "scenario_999"})
    assert launcher.main(line, env) == 1
    assert "has no scenario scenario_999" in capsys.readouterr().err
    assert not out.exists()
    full = _plan_line(probe, development, out)
    without_ledger = [f for f in full if f != "--ledger" and f != "ledger-dev"]
    assert launcher.main(without_ledger, env) == 2
    assert "agent reserves against a ledger" in capsys.readouterr().err
    rules_only = _plan_line(probe, development, out, system="rules_only")
    assert launcher.main([*rules_only, "--ledger", "l"], env) == 2
    assert "rules only reserves nothing" in capsys.readouterr().err
    broken = tmp_path / "registration.json"
    broken.write_text('{"format_version": "SECRET-MARKER-2026"}', encoding="utf-8")
    line = _plan_line(probe, development, out, **{"--registration": str(broken)})
    assert launcher.main(line, env) == 2
    err = capsys.readouterr().err
    assert "SECRET-MARKER" not in err and "the registration" in err


def test_plan_for_rules_only_reserves_nothing_against_no_ledger(
    probe: Any, development: SealedDevelopment, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "run"
    line = _plan_line(probe, development, out, system="rules_only")
    assert launcher.main(line, _env(development)) == 0, capsys.readouterr().err
    printed = dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines())
    assert printed["reservation_pico_usd"] == "None"
    request = json.loads((out / launcher.REQUEST_FILE).read_text(encoding="utf-8"))
    assert request["ledger_id"] is None
    flags = (out / launcher.WORK_ARGUMENTS_FILE).read_text(encoding="utf-8").split()
    assert "--model" not in flags and flags[:2] == ["--system", "rules_only"]


# --- status ----------------------------------------------------------------------------------


class _Log(MemoryLog):
    def close(self) -> None:
        pass


@pytest.fixture(scope="module")
def golden() -> SealedWorld:
    return loaded_world("golden")


def _status(log: _Log, probe: Any) -> list[str]:
    return [
        "status",
        "--run",
        RUN,
        "--attempt",
        str(ATTEMPT),
        "--registration",
        str(probe.REGISTRATION_FILE),
        "--approval",
        "automatic",
    ]


def test_status_prints_the_attempts_fields_and_the_next_step(
    probe: Any, golden: SealedWorld, capsys: pytest.CaptureFixture[str]
) -> None:
    """An admitted attempt: open, no segment, work next. The throttled run with its closing
    dropped: open, segment open, a recorded stop, recover next, and hold at the bound, the
    count the log's own and printed. Closed: publish, with its ending named. Every answer
    names the world and the registration commit the attempt was admitted under, the
    inventory's scope."""
    # The attempt is read under the registration file's rules, so the history is made under
    # them: the development table and policy a draft resolves to.
    rules = effective_rules(probe.registration())
    assert rules.table is not None
    inputs = replace(
        support.admitted_inputs(golden.context_of(golden.scenarios[0])),
        attribution_table=attribution_table_digest(rules.table),
        redispatch=rules.redispatch,
    )
    log = _Log()
    log.seed(support.admission(inputs))
    assert launcher.main(_status(log, probe), {}, log) == 0  # type: ignore[arg-type]
    assert capsys.readouterr().out.splitlines() == [
        "attempt=open",
        "ending=none",
        "segment=none",
        "approval=none",
        "stopped=false",
        "generation=0",
        "recoveries=0",
        f"world_version={inputs.context.world_version}",
        f"registration_commit={inputs.preregistration_commit}",
        f"ledger={LEDGER}",
        "next=work",
    ]
    turns, client = support.throttled_script(inputs.context)
    Worker(
        log,
        WorkerConfiguration.of(inputs),
        cases.REVISION,
        "launch-1",
        rules,
        turns,
        NoPreparation(),
        client,
        support.ScriptedCounter(),
        systems_holding(golden).ports,
        AutomaticApproval(),
        InMemorySaver(),
        sleep=lambda seconds: None,
    ).work(RUN, ATTEMPT, nonce="nonce-1")
    left_open = _Log()
    left_open.seed(log.events(RUN, ATTEMPT)[:-1])
    assert launcher.main(_status(left_open, probe), {}, left_open) == 0  # type: ignore[arg-type]
    assert capsys.readouterr().out.splitlines() == [
        "attempt=open",
        "ending=none",
        "segment=open",
        "approval=none",
        "stopped=true",
        "generation=1",
        "recoveries=0",
        f"world_version={inputs.context.world_version}",
        f"registration_commit={inputs.preregistration_commit}",
        f"ledger={LEDGER}",
        "next=recover",
    ]
    state = left_open.load(RUN, ATTEMPT, rules=rules)
    at_bound = launcher.status_lines(
        replace(state, recoveries=2), approval=AutomaticApproval(), ledger=None
    )
    assert "recoveries=2" in at_bound and at_bound[-1] == "next=hold"
    assert "ledger=none" in at_bound, "an attempt that reserved nothing names no ledger"
    assert launcher.main(_status(log, probe), {}, log) == 0  # type: ignore[arg-type]
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "attempt=closed" and out[1] == "ending=failed" and out[-1] == "next=publish"
    assert launcher.main(_status(log, probe), {}) == 2
    assert "DATABASE_URL" in capsys.readouterr().err
