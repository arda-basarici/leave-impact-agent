"""The executor is total over the six outcomes and records one operation per call with the
arguments as given and the source the method table names; who asked decides what a refusal
is, the model's recorded and the prefetch's raised; a source stops at its first unreachable
answer and a call against it is the caller's error. The prefetch over it makes the plan's
calls in the plan's order and ends at the first operation when the leave asked for did not
come back. The registered outage, injected over the ports, leaves the trace the fixtures'
reachability switch leaves, the reason text aside."""

from dataclasses import dataclass, replace

import pytest

from leaveimpact.agent.execution import (
    SCHEDULED_OUT_REASON,
    Executor,
    ReadPorts,
    ScheduledOut,
    ports_under,
    run_prefetch,
    sequential_ids,
)
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
    Role,
    RunContext,
    Source,
    SourceUnreachable,
    UnreachableOutcome,
    calls_after_leave,
    opening_call,
    role_surface,
)
from leaveimpact.core.ids import LeaveId, employee_id, leave_id
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.in_memory_ports import InMemoryPeople, InMemoryWork
from tests.unit.reads_fixture import FakeSystems, Systems, fakes_holding, systems_holding
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


def ports_of(systems: Systems | FakeSystems) -> ReadPorts:
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
    assert answer == UnreachableOutcome(Source.JIRA, "switched off for this run")
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
        people=dict(systems.people.people),
        leaves=dict(systems.people.leaves),
        teams=dict(systems.people.teams),
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
        tickets=dict(systems.work.tickets),
        components_by_id=dict(systems.work.components_by_id),
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
    world: SealedWorld, scenario: Scenario
) -> None:
    systems = fakes_holding(world)
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


def test_a_models_call_outside_the_executors_surface_is_refused_and_a_prefetchs_raises(
    systems: Systems,
) -> None:
    """The registry step, fork 9: the tools node builds its executor over the role's surface,
    so a known tool the role is not shown is refused at execution, never resolved through
    the fourteen; the prefetch runs over the fourteen and such a call from it is a defect."""
    over_role = Executor(ports_of(systems), surface=role_surface(Role.INVESTIGATOR))
    refused = over_role.call(BY_MODEL, "employees", {})
    assert isinstance(refused, RefusedCallOutcome)
    assert refused.reason == "'employees' is not one of this role's tools"
    assert over_role.operations[-1].source is None
    unknown = over_role.call(BY_MODEL, "leaves", {})
    assert isinstance(unknown, RefusedCallOutcome) and unknown.reason == "no tool named 'leaves'"
    with pytest.raises(ValueError, match="the frozen prefetch made a call the surface refuses"):
        over_role.call(PREFETCH, "employees", {})
    assert isinstance(executor_over(systems).call(BY_MODEL, "employees", {}), RecordsOutcome)


def test_a_harness_call_the_surface_refuses_is_a_harness_defect_and_raises(
    systems: Systems,
) -> None:
    # The baselines step, fork 4: the harness built the arguments from the declarations the
    # validator applies, as the prefetch did, so a refusal is this harness's and never graded.
    from leaveimpact.core import HarnessOrigin

    executor = executor_over(systems)
    by_harness = HarnessOrigin("single_shot_query")
    with pytest.raises(ValueError, match="the harness made a call under 'single_shot_query'"):
        executor.call(by_harness, "search", {"query": "k" * 201, "limit": 5})
    with pytest.raises(ValueError, match="the surface refuses: no tool named 'documentz'"):
        executor.call(by_harness, "documentz", {})
    assert executor.operations == []
    listed = executor.call(HarnessOrigin("full_context_documents"), "documents", {})
    assert isinstance(listed, RecordsOutcome)
    (operation,) = executor.operations
    assert operation.origin == HarnessOrigin("full_context_documents")
    assert (operation.tool, operation.source) == ("documents", Source.CORPUS)


# --- The registered outage, injected over the ports ----------------------------------------------

READS_OF_EVERY_METHOD: tuple[tuple[str, tuple[object, ...], dict[str, object]], ...] = (
    ("employee", (employee_id(1),), {}),
    ("employees", (), {}),
    ("team", ("team-1",), {}),
    ("leave", (leave_id(1),), {}),
    ("leaves_within", (None,), {}),
    ("work_item", ("item-1",), {}),
    ("work_items", (), {}),
    ("component", ("component-1",), {}),
    ("components", (), {}),
    ("event", ("event-1",), {}),
    ("events_within", (None,), {}),
    ("document", ("document-1",), {}),
    ("search", ("handover",), {"limit": 5}),
    ("documents", (), {}),
)
"""Every method of the four read protocols, with arguments of the shape it takes; the reader
under test never reads them, so an id's spelling is not checked here."""


def test_a_scheduled_out_reader_refuses_every_method_of_the_four_protocols() -> None:
    """Fork 3: one class for the four protocols, every method written out and raising the
    one fixed reason; the list above is the fourteen, so a protocol method missing from the
    class would fail here as it fails typing."""
    reader = ScheduledOut(Source.CALENDAR)
    for method, positional, keyword in READS_OF_EVERY_METHOD:
        with pytest.raises(SourceUnreachable) as raised:
            getattr(reader, method)(*positional, **keyword)
        assert (raised.value.source, raised.value.reason) == (
            Source.CALENDAR,
            SCHEDULED_OUT_REASON,
        ), method
    assert len(READS_OF_EVERY_METHOD) == 14


def test_ports_under_replaces_the_scheduled_sources_readers_and_keeps_the_rest(
    systems: Systems,
) -> None:
    """Fork 1: under the normal condition the readers are the given ports' own; under an
    outage exactly the scheduled source's family reads through ``ScheduledOut``, by the
    function's own source-to-port mapping; the given ports are not changed."""
    given = ports_of(systems)
    normal = ports_under(given, ())
    assert (normal.people, normal.work, normal.calendar, normal.documents) == (
        given.people,
        given.work,
        given.calendar,
        given.documents,
    )
    for source, family in (
        (Source.FRAPPE, "people"),
        (Source.JIRA, "work"),
        (Source.CALENDAR, "calendar"),
        (Source.CORPUS, "documents"),
    ):
        under = ports_under(given, {source})
        for name in ("people", "work", "calendar", "documents"):
            reader = getattr(under, name)
            if name == family:
                assert reader == ScheduledOut(source), name
            else:
                assert reader is getattr(given, name), name
    assert ports_of(systems) == given, "the given ports are read, never changed"


@pytest.mark.parametrize("source", [Source.FRAPPE, Source.JIRA, Source.CALENDAR])
def test_an_injected_outage_leaves_the_trace_the_fixtures_switch_leaves(
    world: SealedWorld, scenario: Scenario, source: Source
) -> None:
    """Fork 1's claim: an injected outage and a vendor's own failure are the same trace. The
    prefetch under ``ports_under`` and under the planted store's reachability switch make the
    same calls with the same outcome kinds and stop the same source; only the reason text
    differs, the wrapper's constant against the fixture's."""
    context = world.context_of(scenario)
    injected = Executor(ports_under(ports_of(systems_holding(world)), {source}))
    run_prefetch(injected, context)
    switched_systems = systems_holding(world)
    for port in (switched_systems.people, switched_systems.work, switched_systems.calendar):
        port.reachable = port.source is not source
    switched = executor_over(switched_systems)
    run_prefetch(switched, context)
    assert made(injected) == made(switched)
    assert injected.stopped == switched.stopped == {source}
    outcomes = [op.outcome for op in injected.operations]
    reasons = {o.reason for o in outcomes if isinstance(o, UnreachableOutcome)}
    assert reasons == {SCHEDULED_OUT_REASON}


def test_an_injected_corpus_outage_is_not_met_by_the_prefetch(
    world: SealedWorld, scenario: Scenario
) -> None:
    """The prefetch reads no document, so the corpus scheduled out leaves its trace the
    normal one and stops nothing: the outage is met, if at all, by a later read."""
    executor = Executor(ports_under(ports_of(systems_holding(world)), {Source.CORPUS}))
    run_prefetch(executor, world.context_of(scenario))
    assert executor.stopped == set()
    assert all(isinstance(op.outcome, RecordOutcome | RecordsOutcome) for op in executor.operations)
