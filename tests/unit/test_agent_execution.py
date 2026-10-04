"""The executor is total over the six outcomes and records one operation per call with the
arguments as given and the source the method table names; who asked decides what a refusal
is, the model's recorded and the prefetch's raised; a source stops at its first unreachable
answer and a call against it is the caller's error. The prefetch over it makes the plan's
calls in the plan's order and ends at the first operation when the leave asked for did not
come back."""

from dataclasses import dataclass, replace

import pytest

from leaveimpact.agent.execution import Executor, ReadPorts, run_prefetch, sequential_ids
from leaveimpact.core import (
    AbsentOutcome,
    Component,
    DefectOutcome,
    Leave,
    LeaveKind,
    LeaveStatus,
    MalformedRecord,
    ModelCallId,
    ModelOrigin,
    Observed,
    Operation,
    OperationId,
    PrefetchOrigin,
    RecordOutcome,
    RecordsOutcome,
    RefusedCallOutcome,
    RunContext,
    Source,
    UnreachableOutcome,
    calls_after_leave,
    opening_call,
)
from leaveimpact.core.ids import LeaveId, employee_id, leave_id
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.in_memory_ports import InMemoryPeople, InMemoryWork
from tests.unit.reads_fixture import Systems, systems_holding
from tests.unit.throwaway_world import loaded_world

BY_MODEL = ModelOrigin(ModelCallId("call-1"))
PREFETCH = PrefetchOrigin()


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture
def systems(world: SealedWorld) -> Systems:
    return systems_holding(world)


@pytest.fixture
def scenario(world: SealedWorld) -> Scenario:
    return world.scenarios[0]


def ports_of(systems: Systems) -> ReadPorts:
    return ReadPorts(systems.people, systems.work, systems.calendar, systems.documents)


def executor_over(systems: Systems) -> Executor:
    return Executor(ports_of(systems))


def made(executor: Executor) -> list[tuple[str, dict[str, object], type]]:
    return [(op.tool, dict(op.arguments), type(op.outcome)) for op in executor.operations]


@dataclass
class _WorkWithBrokenComponents(InMemoryWork):
    """The tracker fake whose component enumeration cannot be translated."""

    def components(self) -> tuple[Observed[Component], ...]:
        self._reach()
        raise MalformedRecord(self.source, "Component/all", "a member id of the wrong shape")


@dataclass
class _PeopleWithABrokenLeave(InMemoryPeople):
    """The HR fake whose leave records cannot be translated: the adapter's defect."""

    def leave(self, id: LeaveId) -> Observed[Leave] | None:
        self._reach()
        raise MalformedRecord(self.source, f"Leave Application/{id}", "no employee on the record")


# --- The six outcomes --------------------------------------------------------------------------


def test_a_single_read_answers_with_its_record_or_with_absence(
    systems: Systems, scenario: Scenario
) -> None:
    executor = executor_over(systems)
    found = executor.call(PREFETCH, "leave", {"id": scenario.spec.leave_id})
    assert isinstance(found, RecordOutcome) and found.record.value.id == scenario.spec.leave_id
    assert found.record.source is Source.FRAPPE
    missing = executor.call(PREFETCH, "leave", {"id": "leave_999"})
    assert isinstance(missing, AbsentOutcome)
    assert [op.id for op in executor.operations] == [OperationId("op-1"), OperationId("op-2")]
    assert all(op.source is Source.FRAPPE and op.origin == PREFETCH for op in executor.operations)
    assert dict(executor.operations[1].arguments) == {"id": "leave_999"}


def test_an_enumeration_answers_with_its_records_in_the_ports_order(
    world: SealedWorld, systems: Systems
) -> None:
    executor = executor_over(systems)
    answer = executor.call(BY_MODEL, "employees", {})
    assert isinstance(answer, RecordsOutcome)
    assert [record.value.id for record in answer.records] == [e.id for e in world.org.employees]
    assert executor.operations[0].origin == BY_MODEL
    assert executor.operations[0].source is Source.FRAPPE


def test_an_unreachable_source_is_recorded_and_stops_for_the_run(systems: Systems) -> None:
    systems.work.reachable = False
    executor = executor_over(systems)
    answer = executor.call(PREFETCH, "work_items", {})
    assert answer == UnreachableOutcome(Source.JIRA, "switched off in the test")
    assert executor.stopped == {Source.JIRA}
    with pytest.raises(ValueError, match="jira has stopped"):
        executor.call(PREFETCH, "components", {})
    with pytest.raises(ValueError, match="jira has stopped"):
        executor.call(BY_MODEL, "work_item", {"id": next(iter(systems.work.tickets))})
    # Another source is untouched, and the refused calls were never recorded.
    assert isinstance(executor.call(PREFETCH, "employees", {}), RecordsOutcome)
    assert made(executor) == [
        ("work_items", {}, UnreachableOutcome),
        ("employees", {}, RecordsOutcome),
    ]


def test_a_malformed_record_is_a_defect_and_stops_nothing(
    systems: Systems, scenario: Scenario
) -> None:
    broken = _PeopleWithABrokenLeave(
        people=systems.people.people, leaves=systems.people.leaves, teams=systems.people.teams
    )
    executor = Executor(replace(ports_of(systems), people=broken))
    answer = executor.call(PREFETCH, "leave", {"id": scenario.spec.leave_id})
    assert answer == DefectOutcome(
        Source.FRAPPE, f"Leave Application/{scenario.spec.leave_id}", "no employee on the record"
    )
    assert executor.stopped == set()
    assert isinstance(executor.call(PREFETCH, "employees", {}), RecordsOutcome)


def test_a_models_call_the_surface_refuses_is_recorded_as_refused(systems: Systems) -> None:
    executor = executor_over(systems)
    bad_id = executor.call(BY_MODEL, "leave", {"id": "LIA-42"})
    assert isinstance(bad_id, RefusedCallOutcome) and "leave id" in bad_id.reason
    unknown = executor.call(BY_MODEL, "leaves", {})
    assert isinstance(unknown, RefusedCallOutcome) and "no tool named 'leaves'" in unknown.reason
    first, second = executor.operations
    assert (first.tool, first.source) == ("leave", Source.FRAPPE)
    assert (second.tool, second.source) == ("leaves", None)
    assert dict(first.arguments) == {"id": "LIA-42"}


def test_a_prefetch_call_the_surface_refuses_is_a_harness_defect_and_raises(
    systems: Systems,
) -> None:
    executor = executor_over(systems)
    with pytest.raises(ValueError, match="the frozen prefetch made a call the surface refuses"):
        executor.call(PREFETCH, "leave", {"id": "LIA-42"})
    with pytest.raises(ValueError, match="the frozen prefetch made a call the surface refuses"):
        executor.call(PREFETCH, "leaves", {})
    assert executor.operations == []


def test_operation_ids_come_from_the_id_source_given(systems: Systems) -> None:
    executor = Executor(ports_of(systems), next_id=sequential_ids("read"))
    executor.call(PREFETCH, "employees", {})
    executor.call(PREFETCH, "components", {})
    assert [op.id for op in executor.operations] == ["read-1", "read-2"]


# --- The prefetch over it ----------------------------------------------------------------------


def planned(context: RunContext, leave: Leave) -> list[tuple[str, dict[str, object]]]:
    first = opening_call(context)
    rest = calls_after_leave(leave, context.reference_timezone)
    return [(first.tool, dict(first.arguments)), *((c.tool, dict(c.arguments)) for c in rest)]


def test_under_the_normal_condition_the_trace_is_the_plan(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    context = world.context_of(scenario)
    executor = executor_over(systems)
    result = run_prefetch(executor, context)
    assert result.leave == scenario.investigated_leave
    assert isinstance(result.opening, RecordOutcome)
    assert [(op.tool, dict(op.arguments)) for op in executor.operations] == planned(
        context, scenario.investigated_leave
    )
    assert all(isinstance(op.outcome, RecordOutcome | RecordsOutcome) for op in executor.operations)
    assert all(op.origin == PREFETCH for op in executor.operations)
    assert executor.stopped == set()


def test_with_the_tracker_down_its_first_call_fails_and_its_second_is_never_made(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    systems.work.reachable = False
    executor = executor_over(systems)
    run_prefetch(executor, world.context_of(scenario))
    assert [op.tool for op in executor.operations] == [
        "leave",
        "employees",
        "leaves_within",
        "components",
        "events_within",
    ]
    assert isinstance(executor.operations[3].outcome, UnreachableOutcome)
    assert executor.stopped == {Source.JIRA}


def test_with_the_calendar_down_its_one_call_fails_and_the_rest_stand(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    systems.calendar.reachable = False
    executor = executor_over(systems)
    run_prefetch(executor, world.context_of(scenario))
    assert len(executor.operations) == 6
    assert isinstance(executor.operations[5].outcome, UnreachableOutcome)
    assert executor.stopped == {Source.CALENDAR}


def test_a_malformed_record_mid_plan_ends_the_prefetch_at_that_operation(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    # The run fails by defect at that operation (DESIGN's runtime policy); the reads the
    # plan would have made after it are not made.
    broken = _WorkWithBrokenComponents(
        tickets=systems.work.tickets, components_by_id=systems.work.components_by_id
    )
    executor = Executor(replace(ports_of(systems), work=broken))
    result = run_prefetch(executor, world.context_of(scenario))
    assert result.leave == scenario.investigated_leave
    assert [op.tool for op in executor.operations] == [
        "leave",
        "employees",
        "leaves_within",
        "components",
    ]
    assert isinstance(executor.operations[-1].outcome, DefectOutcome)
    assert executor.stopped == set()


def test_with_the_hr_system_down_the_plan_ends_at_the_first_operation(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    systems.people.reachable = False
    executor = executor_over(systems)
    result = run_prefetch(executor, world.context_of(scenario))
    assert result.leave is None and isinstance(result.opening, UnreachableOutcome)
    assert [op.tool for op in executor.operations] == ["leave"]


def test_a_leave_absent_or_of_another_id_ends_the_plan_at_the_first_operation(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    context = world.context_of(scenario)
    asked = LeaveId(context.leave_id)
    del systems.people.leaves[asked]
    absent = Executor(ports_of(systems))
    result = run_prefetch(absent, context)
    assert (result.leave, type(result.opening)) == (None, AbsentOutcome)
    assert [op.tool for op in absent.operations] == ["leave"]
    # The HR system answers the id asked with another leave: the record came back, the
    # leave asked for did not, and what that means is the system's to rule.
    systems.people.leaves[asked] = Leave(
        leave_id(998),
        employee_id(1),
        scenario.investigated_leave.start,
        scenario.investigated_leave.end,
        LeaveKind.ANNUAL,
        LeaveStatus.APPROVED,
    )
    another = Executor(ports_of(systems))
    result = run_prefetch(another, context)
    assert result.leave is None and isinstance(result.opening, RecordOutcome)
    assert [op.tool for op in another.operations] == ["leave"]


def test_every_operation_is_the_executors_own_record(systems: Systems, scenario: Scenario) -> None:
    executor = executor_over(systems)
    executor.call(PREFETCH, "leave", {"id": scenario.spec.leave_id})
    (operation,) = executor.operations
    assert isinstance(operation, Operation)
    assert operation == Operation(
        OperationId("op-1"),
        PREFETCH,
        "leave",
        Source.FRAPPE,
        {"id": scenario.spec.leave_id},
        operation.outcome,
        1,
    )
