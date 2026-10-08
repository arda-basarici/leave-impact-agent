"""What the model sees of its reads: the investigator's ten as Converse sends them under the
pinned digest; every kind of resolution one envelope stamped with the admitted ``now``; a
skip rendered as its unreachable source; a defect never rendered; a recovery's rendering
byte-equal from the decoded log event; the correction shown drawn from the closed set with
the echoing detail left in the log; and the request capture, which renders everything the
registry step produces over a sealed world and finds the scenario id and the world version
in none of it."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from leaveimpact.agent.execution import Executor
from leaveimpact.agent.log_events import (
    LoggedEvent,
    ModelReadKey,
    OperationEvent,
    OperationResult,
    OperationSkip,
    WorkerStamp,
    decode_logged_event,
    encode_logged_event,
)
from leaveimpact.agent.surface import (
    RenderedResult,
    converse_tools,
    correction_for,
    render_result,
    surface_digest,
)
from leaveimpact.core import (
    TOOL_SPECIFICATIONS,
    DefectOutcome,
    ModelCallId,
    ModelOrigin,
    Operation,
    RefusedCallOutcome,
    Role,
    RunContext,
    Source,
    ToolSpecification,
    correction_messages,
    role_surface,
    tool_definition,
)
from leaveimpact.core.jsonshape import JsonObject, canonical_json
from leaveimpact.core.model_calls import UndispatchedReason
from leaveimpact.core.timeshape import encode_instant
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.reads_fixture import Systems, reads_of_everything, systems_holding
from tests.unit.test_core_tools import INVESTIGATOR_SURFACE_DIGEST
from tests.unit.throwaway_world import loaded_world

BY_MODEL = ModelOrigin(ModelCallId("call-1"))
SURFACE = role_surface(Role.INVESTIGATOR)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture
def scenario(world: SealedWorld) -> Scenario:
    return world.scenarios[0]


@pytest.fixture
def context(world: SealedWorld, scenario: Scenario) -> RunContext:
    return world.context_of(scenario)


@pytest.fixture
def systems(world: SealedWorld) -> Systems:
    return systems_holding(world)


def resolution_of(operation: Operation) -> OperationResult:
    return OperationResult(operation.tool, operation.source, operation.arguments, operation.outcome)


def rendered(
    operation: Operation,
    context: RunContext,
    surface: tuple[ToolSpecification, ...] = SURFACE,
) -> RenderedResult:
    return render_result(
        resolution_of(operation), tool=operation.tool, surface=surface, context=context
    )


# --- The definitions ----------------------------------------------------------------------


def test_the_investigators_ten_are_sent_as_converse_tool_specs_in_canonical_order() -> None:
    sent = converse_tools(Role.INVESTIGATOR)
    assert [cast(JsonObject, t["toolSpec"])["name"] for t in sent] == [s.name for s in SURFACE]
    for entry, specification in zip(sent, SURFACE, strict=True):
        spec = cast(JsonObject, entry["toolSpec"])
        definition = tool_definition(specification)
        assert spec["description"] == definition["description"]
        assert spec["inputSchema"] == {"json": definition["input_schema"]}
    assert surface_digest(Role.INVESTIGATOR) == INVESTIGATOR_SURFACE_DIGEST


# --- The envelopes ------------------------------------------------------------------------


def test_every_kind_of_resolution_is_one_envelope_stamped_with_the_admitted_now(
    systems: Systems, context: RunContext
) -> None:
    executor = Executor(systems.ports, surface=SURFACE)
    executor.call(BY_MODEL, "leave", {"id": context.leave_id})
    executor.call(BY_MODEL, "leave", {"id": "leave_999"})
    executor.call(BY_MODEL, "search", {"query": "handover", "limit": 3})
    # The systems are one cached object per world; the outage is undone before the test ends.
    systems.calendar.reachable = False
    try:
        executor.call(BY_MODEL, "event", {"id": "event_001"})
    finally:
        systems.calendar.reachable = True
    executor.call(BY_MODEL, "employee", {"id": "scenario_001"})
    executor.call(BY_MODEL, "employees", {})
    executor.call(BY_MODEL, "scenario_001_tool", {})
    record, absent, records, unreachable, bad_id, enumeration, unknown = (
        rendered(op, context) for op in executor.operations
    )
    stamp = encode_instant(context.now)
    for each in (record, absent, records, unreachable, bad_id, enumeration, unknown):
        assert each.content["observed_at"] == stamp
    assert record.status == "success" and record.content["tool"] == "leave"
    assert cast(JsonObject, record.content["record"])["kind"] == "leave"
    assert record.content["source"] == "frappe"
    assert absent.status == "success" and absent.content["absent"] is True
    assert records.status == "success" and isinstance(records.content["records"], list)
    assert records.content["source"] == "corpus"
    assert unreachable.status == "error"
    assert unreachable.content["unreachable"] == {"source": "calendar"}
    assert "reason" not in canonical_json(unreachable.content)
    assert bad_id.status == "error"
    assert bad_id.content["refused"] == {
        "correction": "employee's id is an employee id of the form emp_NNN"
    }
    assert "scenario_001" not in canonical_json(bad_id.content)
    assert enumeration.content["refused"] == {
        "correction": correction_for(SURFACE, "employees", {})
    }
    assert "tool" not in enumeration.content and "tool" not in unknown.content
    assert "scenario_001" not in canonical_json(unknown.content)
    assert set(record.content) == {"observed_at", "tool", "source", "record"}
    assert set(unknown.content) == {"observed_at", "source", "refused"}


def test_a_skip_renders_as_its_unreachable_source_and_a_cap_skip_as_not_made(
    context: RunContext,
) -> None:
    skipped = render_result(
        OperationSkip(UndispatchedReason.SOURCE_UNREACHABLE),
        tool="work_item",
        surface=SURFACE,
        context=context,
    )
    assert skipped.status == "error"
    assert skipped.content == {
        "observed_at": encode_instant(context.now),
        "tool": "work_item",
        "source": "jira",
        "unreachable": {"source": "jira"},
    }
    capped = render_result(
        OperationSkip(UndispatchedReason.CAP), tool="work_item", surface=SURFACE, context=context
    )
    assert capped.status == "error" and capped.content["not_made"] == {"reason": "cap"}
    with pytest.raises(ValueError, match="a skip of a tool the surface does not declare"):
        render_result(
            OperationSkip(UndispatchedReason.SOURCE_UNREACHABLE),
            tool="employees",
            surface=SURFACE,
            context=context,
        )


def test_a_defect_and_a_mismatched_result_are_never_rendered(context: RunContext) -> None:
    defect = OperationResult(
        "work_item",
        Source.JIRA,
        {"id": "ticket_042"},
        DefectOutcome(Source.JIRA, "Issue/LIA-42", "no assignee field"),
    )
    with pytest.raises(ValueError, match="a defect is never rendered"):
        render_result(defect, tool="work_item", surface=SURFACE, context=context)
    with pytest.raises(ValueError, match="asked to render 'employee'"):
        render_result(defect, tool="employee", surface=SURFACE, context=context)


def test_a_recovery_renders_the_same_bytes_from_the_decoded_log_event(
    systems: Systems, context: RunContext
) -> None:
    executor = Executor(systems.ports, surface=SURFACE)
    executor.call(BY_MODEL, "leave", {"id": context.leave_id})
    executor.call(BY_MODEL, "employee", {"id": "LIA-42"})
    for position, operation in enumerate(executor.operations, start=1):
        logged = LoggedEvent(
            position,
            datetime(2026, 10, 9, 10, 0, tzinfo=UTC),
            WorkerStamp(1, 1, position),
            OperationEvent(ModelReadKey(1, f"tu_{position}"), resolution_of(operation)),
        )
        decoded = decode_logged_event(encode_logged_event(logged))
        event = decoded.event
        assert isinstance(event, OperationEvent) and isinstance(event.resolution, OperationResult)
        first = rendered(operation, context)
        again = render_result(
            event.resolution, tool=operation.tool, surface=SURFACE, context=context
        )
        assert canonical_json(first.block("tu_1")) == canonical_json(again.block("tu_1"))


def test_the_block_is_the_tool_result_converse_sends(context: RunContext) -> None:
    made = render_result(
        OperationSkip(UndispatchedReason.CAP), tool="leave", surface=SURFACE, context=context
    )
    assert made.block("tooluse_leave") == {
        "toolResult": {
            "toolUseId": "tooluse_leave",
            "content": [{"json": made.content}],
            "status": "error",
        }
    }


# --- The corrections ----------------------------------------------------------------------


def test_the_correction_shown_is_from_the_closed_set_and_the_detail_stays_in_the_log(
    systems: Systems, context: RunContext
) -> None:
    executor = Executor(systems.ports, surface=SURFACE)
    executor.call(BY_MODEL, "employee", {"id": "scenario_001"})
    executor.call(BY_MODEL, "search", {"query": " ", "limit": 3})
    executor.call(BY_MODEL, "search", {"query": "handover"})
    executor.call(BY_MODEL, "work_items", {})
    executor.call(BY_MODEL, "scenario_001", {})
    closed = correction_messages(SURFACE)
    for operation in executor.operations:
        assert isinstance(operation.outcome, RefusedCallOutcome)
        shown = rendered(operation, context).content["refused"]
        assert cast(JsonObject, shown)["correction"] in closed
    details = [cast(RefusedCallOutcome, op.outcome).reason for op in executor.operations]
    assert "scenario_001" in details[0] and "'scenario_001'" in details[4]
    with pytest.raises(ValueError, match="the declarations accept"):
        correction_for(SURFACE, "employee", {"id": "emp_001"})


# --- The request capture ------------------------------------------------------------------


def test_the_capture_finds_neither_the_scenario_id_nor_the_world_version_in_the_surface(
    world: SealedWorld, scenario: Scenario, context: RunContext
) -> None:
    """Everything the registry step produces that a request can carry: the definitions, every
    rendered result of a full read of the world under the normal condition and under a
    tracker outage, and every correction; the capture reads the client's blocks."""
    secrets = (str(context.scenario_id), str(context.world_version))
    carried: list[str] = [canonical_json(t) for t in converse_tools(Role.INVESTIGATOR)]
    # The outage pass first: the full read sets every port's reachability from its arguments
    # on the one cached systems object, so the normal pass last leaves every port reachable.
    for down in ((Source.JIRA,), ()):
        for operation in reads_of_everything(world, scenario, *down):
            if isinstance(operation.outcome, DefectOutcome):
                continue
            block = rendered(operation, context, TOOL_SPECIFICATIONS).block("tu")
            carried.append(canonical_json(block))
    carried.extend(correction_messages(SURFACE))
    assert len(carried) > 10 + 2 * 6 + 20
    for text in carried:
        for secret in secrets:
            assert secret not in text, text[:200]


def test_the_executor_over_the_roles_surface_refuses_a_known_tool_outside_it(
    systems: Systems, context: RunContext
) -> None:
    over_role = Executor(systems.ports, surface=SURFACE)
    refused = over_role.call(BY_MODEL, "employees", {})
    assert isinstance(refused, RefusedCallOutcome)
    assert refused.reason == "'employees' is not one of this role's tools"
    assert over_role.operations[-1].source is None
    over_harness = Executor(systems.ports)
    assert not isinstance(over_harness.call(BY_MODEL, "employees", {}), RefusedCallOutcome)
