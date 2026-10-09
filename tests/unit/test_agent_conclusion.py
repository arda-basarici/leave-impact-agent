"""The preconditions as pure calls at the three points the graph asks them: after the prefetch
(no defect and no abstention under the normal condition, the universe the enumeration's
employees by code point; the leave not returned with the HR system down; the universe not
covered with the enumeration alone unreachable), after a model's read (a record read twice
with two contents is a defect at the read that completed the contradiction, and none before
it), and at the payload (the same functions over every operation, the leave read off the
opening operation). The baseline's own tests hold the rest of the defect catalogue; this
file holds the shape the graph relies on."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from leaveimpact.agent.conclusion import (
    Abstention,
    abstention_of,
    defect_of,
    leave_of,
    universe_of,
)
from leaveimpact.agent.execution import Executor, ReadPorts, run_prefetch
from leaveimpact.core.ids import EmployeeId, LeaveId
from leaveimpact.core.ports.errors import SourceUnreachable
from leaveimpact.core.read_projection import project_reads
from leaveimpact.core.run_ending import OperationSite
from leaveimpact.core.run_trace import ModelCallId, ModelOrigin, Operation
from leaveimpact.core.worldtime import RunContext
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.in_memory_ports import InMemoryPeople
from tests.unit.reads_fixture import FakeSystems, fakes_holding
from tests.unit.throwaway_world import loaded_world

BY_MODEL = ModelOrigin(ModelCallId("call-1"))


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
def systems(world: SealedWorld) -> FakeSystems:
    return fakes_holding(world)


def prefetched(ports: ReadPorts, context: RunContext) -> Executor:
    executor = Executor(ports)
    run_prefetch(executor, context)
    return executor


def operations_of(executor: Executor) -> tuple[Operation, ...]:
    return tuple(executor.operations)


# --- After the prefetch --------------------------------------------------------------------


def test_the_normal_prefetch_has_no_defect_no_abstention_and_the_orgs_universe(
    world: SealedWorld, systems: FakeSystems, context: RunContext
) -> None:
    operations = operations_of(prefetched(systems.ports, context))
    projection = project_reads(operations, context.today)
    leave = leave_of(operations, context)
    assert leave is not None and leave.id == context.leave_id
    assert defect_of(operations, projection, context, leave) is None
    assert abstention_of(projection, leave) is None
    assert universe_of(projection) == tuple(sorted(e.id for e in world.org.employees))
    assert len(universe_of(projection)) == len(world.org.employees)


def test_the_hr_system_down_is_the_leave_not_returned_after_one_operation(
    systems: FakeSystems, context: RunContext
) -> None:
    systems.people.reachable = False
    operations = operations_of(prefetched(systems.ports, context))
    assert len(operations) == 1
    projection = project_reads(operations, context.today)
    assert leave_of(operations, context) is None
    assert defect_of(operations, projection, context, None) is None
    assert abstention_of(projection, None) is Abstention.LEAVE_NOT_RETURNED
    assert universe_of(projection) == ()


class _PeopleWithoutAnEnumeration(InMemoryPeople):
    def employees(self) -> tuple[object, ...]:  # type: ignore[override]
        raise SourceUnreachable(self.source, "the list endpoint timed out")


def test_the_enumeration_unreachable_is_the_universe_not_covered(
    systems: FakeSystems, context: RunContext
) -> None:
    people = _PeopleWithoutAnEnumeration(
        people=dict(systems.people.people),
        leaves=dict(systems.people.leaves),
        teams=dict(systems.people.teams),
    )
    operations = operations_of(prefetched(replace(systems.ports, people=people), context))
    projection = project_reads(operations, context.today)
    leave = leave_of(operations, context)
    assert leave is not None
    assert defect_of(operations, projection, context, leave) is None
    assert abstention_of(projection, leave) is Abstention.UNIVERSE_NOT_COVERED


# --- After a model's read -----------------------------------------------------------------


def test_a_record_read_twice_with_two_contents_is_a_defect_at_the_read_that_completed_it(
    systems: FakeSystems, context: RunContext
) -> None:
    executor = prefetched(systems.ports, context)
    before = operations_of(executor)
    leave = leave_of(before, context)
    assert leave is not None
    assert defect_of(before, project_reads(before, context.today), context, leave) is None
    # The HR system drifts between the prefetch and the model's read of the same leave.
    drifted = replace(leave, end=leave.end + timedelta(days=1))
    systems.people.leaves[LeaveId(str(leave.id))] = drifted
    executor.call(BY_MODEL, "leave", {"id": str(leave.id)})
    after = operations_of(executor)
    found = defect_of(after, project_reads(after, context.today), context, leave)
    assert found is not None
    assert found.site == OperationSite(after[-1].id)
    assert "disagree about" in found.reason and str(leave.id) in found.reason


def test_a_models_read_of_an_employee_leaves_the_universe_and_the_leave_as_read(
    systems: FakeSystems, context: RunContext
) -> None:
    executor = prefetched(systems.ports, context)
    universe = universe_of(project_reads(operations_of(executor), context.today))
    executor.call(BY_MODEL, "employee", {"id": str(universe[0])})
    executor.call(BY_MODEL, "employee", {"id": str(EmployeeId("emp_999"))})
    after = operations_of(executor)
    projection = project_reads(after, context.today)
    leave = leave_of(after, context)
    assert leave is not None and leave.id == context.leave_id
    assert defect_of(after, projection, context, leave) is None
    assert abstention_of(projection, leave) is None
    assert universe_of(projection) == universe, "a read of a known employee adds nobody"
