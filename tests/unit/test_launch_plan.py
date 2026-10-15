"""The launcher's plan: its frozen inputs for the six live-iteration scenarios equal the
prompt check's byte for byte under the canonical codec (the first live run's step, fork 1's
forecast); the cell flags it writes compose, through the work command's own parser and
provenance, the configuration the admission froze; rules only plans with no role and no
reservation; a registration holding the roles pending and a setting the line cannot state
are refused by name; and the next step is read off an attempt's state: never claimed,
awaiting a human, approval delivered, left open under and past the recovery bound, closed."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from leaveimpact.agent import __main__ as job
from leaveimpact.agent.commands import ApprovalDelivery, CommandRefused, deliver_approval
from leaveimpact.agent.graph import NoPreparation
from leaveimpact.agent.log_events import (
    Admitted,
    ApprovalRequested,
    EventKind,
    SegmentStarted,
    encode_event,
    kind_of,
)
from leaveimpact.agent.log_transition import Rules, fold
from leaveimpact.agent.registered import model_system_provenance, rules_only_configuration
from leaveimpact.agent.worker import (
    AutomaticApproval,
    HumanApproval,
    Worker,
    WorkerConfiguration,
    WorkerEndingKind,
)
from leaveimpact.core.call_settings import CallConfiguration, CallSetting
from leaveimpact.core.jsonshape import canonical_bytes
from leaveimpact.core.pricing import basis_for, encode_price_table
from leaveimpact.core.registration import AgentSystem, Pending
from leaveimpact.core.registration_json import registration_bytes
from leaveimpact.core.run_parts_json import review_payload_digest
from leaveimpact.core.run_record import SystemKind
from leaveimpact.core.run_timing import TreeState
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.launch.plan import (
    RECOVERY_BOUND,
    NextStep,
    RunCell,
    next_step,
    plan_run,
    work_arguments,
)
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit import worker_support as support
from tests.unit.launch_fixture import (
    SealedDevelopment,
    probe_helper,
    registration_commit_or_skip,
    seal_development,
)
from tests.unit.log_store_memory import MemoryLog
from tests.unit.reads_fixture import systems_holding
from tests.unit.registration_fixture import DRAFT
from tests.unit.throwaway_world import loaded_world

RUN, ATTEMPT = "run-12", 1
COMMIT = "c" * 40
"""A registration commit the plan records; nothing here resolves it."""
AGENT_CELL = RunCell(SystemKind.AGENT, "normal", "base")
RULES_ONLY_CELL = RunCell(SystemKind.RULES_ONLY, "normal", "base")


@pytest.fixture(scope="module")
def probe() -> Any:
    return probe_helper()


@pytest.fixture(scope="module")
def development(tmp_path_factory: pytest.TempPathFactory) -> SealedDevelopment:
    return seal_development(tmp_path_factory.mktemp("development-store"))


@pytest.fixture(scope="module")
def commit(probe: Any) -> str:
    return registration_commit_or_skip(probe)


def _admitted_bytes(inputs: Any) -> bytes:
    return canonical_bytes(encode_event(Admitted(inputs)))


# --- The frozen inputs -------------------------------------------------------------------------


def test_the_plans_frozen_inputs_equal_the_live_probes_byte_for_byte(
    probe: Any, development: SealedDevelopment, commit: str
) -> None:
    """For each of the six live-iteration scenarios the helper draws, the plan's inputs under
    the committed registration and price table are the ones the prompt check's helper builds
    for the same scenario, under the canonical codec: the reservation included, which both
    derive through ``run_reservation``."""
    configuration = probe.probe_configuration(tree_state=TreeState.CLEAN)
    registration = probe.registration()
    scenarios = probe.live_iteration_scenarios(development.world)
    assert len(scenarios) == 6
    for scenario in scenarios:
        expected = configuration.frozen_inputs(development.world.context_of(scenario))
        plan = plan_run(
            registration,
            registration_commit=commit,
            prices=probe.price_table(),
            cell=RunCell(SystemKind.AGENT, probe.CONDITION, probe.LEVEL),
            spec=scenario.spec,
            world_version=development.version,
            run_id=expected.run_id,
            attempt=expected.attempt,
            region=probe.REGION,
        )
        assert _admitted_bytes(plan.inputs) == _admitted_bytes(expected), scenario.spec.id
        assert plan.inputs.reservation_pico_usd == configuration.reservation_pico_usd


def test_the_cell_flags_compose_the_admitted_configuration_through_the_work_line(
    probe: Any, development: SealedDevelopment, tmp_path: Path
) -> None:
    """The work line built from the plan's flags, parsed by the agent's entry and composed as
    its work command composes, gives the configuration the admission froze, for the agent
    and for rules only (whose line carries no model flag)."""
    registration, commit = probe.registration(), COMMIT
    scenario = probe.live_iteration_scenarios(development.world)[0]
    registration_file = tmp_path / "registration.json"
    registration_file.write_bytes(registration_bytes(registration))
    prices_file = tmp_path / "prices.json"
    prices_file.write_text(json.dumps(encode_price_table(probe.price_table())), encoding="utf-8")
    execution = [
        "work",
        "--run",
        RUN,
        "--attempt",
        str(ATTEMPT),
        "--nonce",
        "nonce-1",
        "--launch",
        "launch-1",
        "--registration",
        str(registration_file),
        "--prices",
        str(prices_file),
    ]
    for cell in (AGENT_CELL, RULES_ONLY_CELL):
        plan = plan_run(
            registration,
            registration_commit=commit,
            prices=probe.price_table(),
            cell=cell,
            spec=scenario.spec,
            world_version=development.version,
            run_id=RUN,
            attempt=ATTEMPT,
            region=probe.REGION,
        )
        parsed = job.parse_request(
            [*execution, *work_arguments(plan)], {job.CODE_VERSION: "a" * 40}
        )
        line = parsed.request
        assert isinstance(line, job.WorkLine)
        assert (line.system, line.condition, line.level) == (
            cell.system,
            cell.condition,
            cell.level,
        )
        if line.role is None:
            composed = rules_only_configuration(
                registration,
                line.condition,
                line.level,
                preregistration_commit=line.registration_commit,
                pricing=basis_for(probe.price_table(), ()),
            )
        else:
            composed = model_system_provenance(
                registration,
                line.system,
                line.condition,
                line.level,
                preregistration_commit=line.registration_commit,
                pricing=basis_for(probe.price_table(), (line.role.pricing,)),
                role=line.role,
            )
        assert composed == WorkerConfiguration.of(plan.inputs), cell.system


def test_rules_only_plans_no_role_and_no_reservation(
    probe: Any, development: SealedDevelopment
) -> None:
    scenario = probe.live_iteration_scenarios(development.world)[0]
    plan = plan_run(
        probe.registration(),
        registration_commit=COMMIT,
        prices=probe.price_table(),
        cell=RULES_ONLY_CELL,
        spec=scenario.spec,
        world_version=development.version,
        run_id=RUN,
        attempt=ATTEMPT,
        region=probe.REGION,
    )
    assert plan.role is None and plan.inputs.reservation_pico_usd is None
    assert plan.inputs.model_configurations == () and plan.inputs.redispatch is None
    assert "--model" not in work_arguments(plan)


def test_pending_roles_and_an_unstated_setting_are_refused_by_name(
    probe: Any, development: SealedDevelopment
) -> None:
    """A draft holding the roles pending gives the launcher nothing to fill a role from; a
    registered setting the work line has no flag for cannot be restated and is refused. The
    draft fixture, since only a draft can hold a role pending (the committed file is frozen
    since the freeze step)."""
    scenario = probe.live_iteration_scenarios(development.world)[0]
    registration = DRAFT
    agent = registration.system(SystemKind.AGENT)
    assert isinstance(agent, AgentSystem) and not isinstance(agent.roles, Pending)

    def with_agent(system: AgentSystem) -> Any:
        return replace(
            registration,
            systems=tuple(system if held is agent else held for held in registration.systems),
        )

    def planned(under: Any) -> Any:
        return plan_run(
            under,
            registration_commit=COMMIT,
            prices=probe.price_table(),
            cell=AGENT_CELL,
            spec=scenario.spec,
            world_version=development.version,
            run_id=RUN,
            attempt=ATTEMPT,
            region=probe.REGION,
        )

    with pytest.raises(ValueError, match="holds the agent roles pending"):
        planned(with_agent(replace(agent, roles=Pending("unbuilt"))))
    (role,) = agent.roles
    stopping = replace(
        role,
        configuration=CallConfiguration(
            role.configuration.model_id,
            (*role.configuration.settings, CallSetting("stop_sequences", ["x"])),
        ),
    )
    plan = planned(with_agent(replace(agent, roles=(stopping,))))
    with pytest.raises(ValueError, match="the registered role sets stop_sequences"):
        work_arguments(plan)


# --- The next step -----------------------------------------------------------------------------

RULES = Rules(cases.TABLE, cases.POLICY)


@pytest.fixture(scope="module")
def golden() -> SealedWorld:
    return loaded_world("golden")


def _worker(log: MemoryLog, inputs: Any, golden: SealedWorld, script: Any, approval: Any) -> Worker:
    turns, client = script(inputs.context)
    return Worker(
        log,
        WorkerConfiguration.of(inputs),
        cases.REVISION,
        "launch-1",
        RULES,
        turns,
        NoPreparation(),
        client,
        support.ScriptedCounter(),
        systems_holding(golden).ports,
        approval,
        InMemorySaver(),
        sleep=lambda seconds: None,
    )


def test_the_next_step_follows_the_attempts_state_through_a_human_approval(
    golden: SealedWorld,
) -> None:
    """Never claimed: work. Paused for a human: wait, whatever the count. The approval
    delivered: work again, a resume and no recovery. Closed: publish, the log counting no
    recovery across its two generations."""
    inputs = support.admitted_inputs(golden.context_of(golden.scenarios[0]))
    log = MemoryLog()
    log.seed(support.admission(inputs))
    human = HumanApproval()
    admitted = log.load(RUN, ATTEMPT, rules=RULES)
    assert next_step(admitted, approval=human) is NextStep.WORK
    worker = _worker(log, inputs, golden, support.two_call_script, human)
    ending = worker.work(RUN, ATTEMPT, nonce="nonce-1")
    assert ending.kind is WorkerEndingKind.AWAITING_APPROVAL
    waiting = log.load(RUN, ATTEMPT, rules=RULES)
    assert next_step(waiting, approval=human) is NextStep.WAIT
    assert next_step(replace(waiting, recoveries=RECOVERY_BOUND), approval=human) is NextStep.WAIT
    requested = waiting.approval_requested
    assert requested is not None and isinstance(requested.event, ApprovalRequested)
    digest = review_payload_digest(requested.event.claims, requested.event.composition)
    delivered = deliver_approval(
        ApprovalDelivery(RUN, ATTEMPT, "human:test", digest),
        log,  # type: ignore[arg-type]
        rules=RULES,
    )
    assert not isinstance(delivered, CommandRefused)
    approved = log.load(RUN, ATTEMPT, rules=RULES)
    assert next_step(replace(approved, recoveries=RECOVERY_BOUND), approval=human) is NextStep.WORK
    resumed = _worker(log, inputs, golden, support.two_call_script, human)
    assert resumed.work(RUN, ATTEMPT, nonce="nonce-2").kind is WorkerEndingKind.CLOSED
    closed = log.load(RUN, ATTEMPT, rules=RULES)
    assert next_step(closed, approval=human) is NextStep.PUBLISH
    assert (closed.generation, closed.recoveries) == (2, 0)


def test_an_automatic_run_killed_after_its_approval_request_is_recovered_not_waited_for(
    golden: SealedWorld,
) -> None:
    """The group's external read: under the automatic policy an approval requested and not
    given is a process that died between the request and its own approval, which a
    recovering worker completes with no new send; the decision reads it as a recovery, and
    as a wait only under the human policy."""
    inputs = support.admitted_inputs(golden.context_of(golden.scenarios[0]))
    log = MemoryLog()
    log.seed(support.admission(inputs))
    _worker(log, inputs, golden, support.two_call_script, AutomaticApproval()).work(
        RUN, ATTEMPT, nonce="nonce-1"
    )
    events = log.events(RUN, ATTEMPT)
    requested = next(
        i for i, e in enumerate(events) if kind_of(e.event) is EventKind.APPROVAL_REQUESTED
    )
    killed = MemoryLog()
    killed.seed(events[: requested + 1])
    state = killed.load(RUN, ATTEMPT, rules=RULES)
    assert state.approval_requested is not None and state.approved is None
    automatic = AutomaticApproval()
    assert next_step(state, approval=automatic) is NextStep.RECOVER
    assert next_step(replace(state, recoveries=RECOVERY_BOUND), approval=automatic) is NextStep.HOLD
    assert next_step(state, approval=HumanApproval()) is NextStep.WAIT
    recovering = _worker(killed, inputs, golden, support.two_call_script, automatic)
    ending = recovering.work(RUN, ATTEMPT, nonce="nonce-2")
    assert ending.kind is WorkerEndingKind.CLOSED
    assert isinstance(recovering.client, support.ScriptedClient) and recovering.client.sends == []


def test_an_attempt_left_open_is_recovered_under_the_bound_and_held_past_it(
    golden: SealedWorld,
) -> None:
    """A segment still open with the attempt open is a process that is gone: recover while the
    log's count is under the bound, hold at it. The fixture is the throttled run with its
    closing dropped, the history the terminal path closes; a resumed worker that died after
    an approval reads the same way."""
    inputs = support.admitted_inputs(golden.context_of(golden.scenarios[0]))
    log = MemoryLog()
    log.seed(support.admission(inputs))
    _worker(log, inputs, golden, support.throttled_script, AutomaticApproval()).work(
        RUN, ATTEMPT, nonce="nonce-1"
    )
    events = log.events(RUN, ATTEMPT)
    left_open = MemoryLog()
    left_open.seed(events[:-1])
    state = left_open.load(RUN, ATTEMPT, rules=RULES)
    assert state.closed is None and state.current_segment is not None
    assert not state.current_segment.ended
    automatic = AutomaticApproval()
    assert state.recoveries == 0
    assert next_step(state, approval=automatic) is NextStep.RECOVER
    assert next_step(replace(state, recoveries=RECOVERY_BOUND - 1), approval=automatic) is (
        NextStep.RECOVER
    )
    assert next_step(replace(state, recoveries=RECOVERY_BOUND), approval=automatic) is NextStep.HOLD
    assert RECOVERY_BOUND == 2, "the development protocol states two recoveries"


def test_the_count_is_the_logs_own_and_a_stopped_resumption_is_recovered() -> None:
    """The step-14 review's finding and the external read's history, through the launcher's
    rule: the claims a log holds decide the count, so a continuation starts where the last
    job left it; a worker stopped after the post-approval claim and before its resume event
    is recovered, and its recovery is the first in the count."""
    events = histories.approved_then_stopped_before_resume()
    claims = [i for i, e in enumerate(events) if isinstance(e.event, SegmentStarted)]
    human = HumanApproval()
    before_resumption = fold(events[: claims[1]], histories.RULES)
    assert next_step(before_resumption, approval=human) is NextStep.WORK
    stopped = fold(events[: claims[2]], histories.RULES)
    assert next_step(stopped, approval=human) is NextStep.RECOVER
    assert fold(events[: claims[2] + 1], histories.RULES).recoveries == 1
    past = fold(histories.left_open_claims(RECOVERY_BOUND + 1), histories.RULES)
    assert past.recoveries == RECOVERY_BOUND
    assert next_step(past, approval=AutomaticApproval()) is NextStep.HOLD
