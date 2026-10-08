"""Prefetch conformance. The real rules-only harness conforms on every scenario of the throwaway
world under every registered condition, read back from its exported bytes. Each of the four
findings fires alone on a trace changed in one respect, and the reordered rule names every
operation a moved one overtook. A source stop and a malformed record end obligations and a
defect found at a completed read does not; a leave that did not come back ends the plan at
its first call; a long leave's chunks are each obliged. A run under another rule is not
evaluated, the accounting counts both, and the projection refuses a registered prefetch this
code does not plan."""

from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from leaveimpact.agent.registered import rules_only_provenance
from leaveimpact.agent.rules_only import investigate
from leaveimpact.core import (
    Component,
    DefectOutcome,
    HarnessRevision,
    MalformedRecord,
    Observed,
    Operation,
    OperationId,
    PrefetchRule,
    PricingBasis,
    RunExport,
    Source,
    TerminalStatus,
    TreeState,
    UnreachableOutcome,
    calls_after_leave,
    condition_id,
    decode_export_bytes,
    decode_registration_bytes,
    export_bytes,
)
from leaveimpact.core.ids import LeaveId
from leaveimpact.core.run_ending import OperationSite
from leaveimpact.evaluator.cells import accounting_of, arms, attempt_summary_of, cells_of
from leaveimpact.evaluator.prefetch_conformance import (
    PrefetchConformance,
    PrefetchFinding,
    PrefetchFindingKind,
    prefetch_conformance,
)
from leaveimpact.evaluator.registered import preregistered
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import evaluate_run
from leaveimpact.world import Scenario
from tests.unit.export_fixture import export_baseline, logged_in_order
from tests.unit.in_memory_ports import InMemoryWork
from tests.unit.reads_fixture import FakeSystems, Systems, fakes_holding, systems_holding
from tests.unit.throwaway_world import loaded_world

DIGEST = "a" * 64
COMMIT = "b" * 40
CONFORMS = PrefetchConformance(True, ())
MISSING = PrefetchFindingKind.MISSING
WRONG = PrefetchFindingKind.WRONGLY_PARAMETERIZED
REORDERED = PrefetchFindingKind.REORDERED
EXTRA = PrefetchFindingKind.EXTRA
PLAN = ["leave", "employees", "leaves_within", "components", "work_items", "events_within"]
CONDITIONS: tuple[tuple[Source, ...], ...] = (
    (),
    (Source.JIRA,),
    (Source.CALENDAR,),
    (Source.FRAPPE,),
    (Source.CORPUS,),
)

REGISTRATION = decode_registration_bytes(
    (Path(__file__).resolve().parents[2] / "preregistration" / "registration.json").read_bytes()
)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture
def scenario(world: SealedWorld) -> Scenario:
    return world.scenarios[0]


def exported(
    world: SealedWorld,
    scenario: Scenario,
    systems: Systems | FakeSystems,
    *down: Source,
    run_id: str = "run-1",
) -> RunExport:
    """The real baseline's export of ``scenario`` with ``down`` unreachable, read back from
    its bytes, so the arguments compared are the ones the wire carries."""
    for port in (systems.people, systems.work, systems.calendar, systems.documents):
        port.reachable = port.source not in down
    context = world.context_of(scenario)
    provenance = rules_only_provenance(
        REGISTRATION,
        condition_id(down),
        "base",
        harness=HarnessRevision(COMMIT, TreeState.CLEAN),
        preregistration_commit=COMMIT,
        pricing=PricingBasis(DIGEST, "USD", date(2026, 9, 1), ()),
    )
    export = export_baseline(
        investigate(context, systems.ports),
        context,
        provenance,
        run_id=run_id,
        attempt=1,
        duration_ms=1_200,
    )
    return decode_export_bytes(export_bytes(export))


@pytest.fixture
def normal(world: SealedWorld, scenario: Scenario) -> RunExport:
    export = exported(world, scenario, systems_holding(world))
    assert [operation.tool for operation in export.trace.operations] == PLAN
    return export


def with_operations(export: RunExport, *operations: Operation) -> RunExport:
    """``export`` as if its harness had logged ``operations`` in the order given."""
    return replace(
        export, trace=replace(export.trace, operations=logged_in_order(operations))
    )


def again(operation: Operation, number: int) -> Operation:
    """``operation`` as a further read, under an id the trace does not hold."""
    return replace(operation, id=OperationId(f"op-{number}"))


def findings(export: RunExport) -> list[tuple[PrefetchFindingKind, int | None, str | None]]:
    conformance = prefetch_conformance(export)
    assert conformance.evaluated
    return [(f.kind, f.step, f.operation) for f in conformance.findings]


# --- The real harness conforms -----------------------------------------------------------------


@pytest.mark.parametrize("down", CONDITIONS, ids=str)
def test_the_baseline_conforms_on_every_scenario_under_every_registered_condition(
    world: SealedWorld, down: tuple[Source, ...]
) -> None:
    for scenario in world.scenarios:
        export = exported(world, scenario, systems_holding(world), *down)
        assert prefetch_conformance(export) == CONFORMS, scenario.spec.id


def test_the_evaluation_carries_the_conformance_beside_the_outcome(
    world: SealedWorld, normal: RunExport
) -> None:
    assert evaluate_run(world, normal).metrics.prefetch == CONFORMS
    one, two, *rest = normal.trace.operations
    assert evaluate_run(world, with_operations(normal, one, *rest)).metrics.prefetch == (
        PrefetchConformance(True, (PrefetchFinding(MISSING, 1, None),))
    )
    assert two.tool == "employees"


# --- The four findings, each alone -------------------------------------------------------------


def test_a_call_never_made_is_missing(normal: RunExport) -> None:
    operations = normal.trace.operations
    assert findings(with_operations(normal, *operations[:3], *operations[4:])) == [
        (MISSING, 3, None)
    ]


def test_a_call_made_twice_is_once_the_plans_and_once_extra(normal: RunExport) -> None:
    operations = normal.trace.operations
    twice = with_operations(normal, *operations, again(operations[1], 7))
    assert findings(twice) == [(EXTRA, None, "op-7")]


def test_a_call_with_other_arguments_is_wrongly_parameterized(
    world: SealedWorld, scenario: Scenario, normal: RunExport
) -> None:
    operations = list(normal.trace.operations)
    leave = scenario.investigated_leave
    longer = replace(leave, end=leave.end + timedelta(days=1))
    context = world.context_of(scenario)
    other = next(
        call
        for call in calls_after_leave(longer, context.reference_timezone)
        if call.tool == "leaves_within"
    )
    assert other.arguments != dict(operations[2].arguments)
    operations[2] = replace(operations[2], arguments=other.arguments)
    assert findings(with_operations(normal, *operations)) == [(WRONG, 2, "op-3")]


def test_a_call_made_after_one_the_plan_puts_later_is_reordered(normal: RunExport) -> None:
    leave, employees, within, components, work_items, events = normal.trace.operations
    swapped = with_operations(normal, leave, employees, within, work_items, components, events)
    assert findings(swapped) == [(REORDERED, 3, components.id)]
    # The simple rule: the last call made first marks every call it overtook.
    first = with_operations(normal, leave, events, employees, within, components, work_items)
    assert findings(first) == [
        (REORDERED, 1, employees.id),
        (REORDERED, 2, within.id),
        (REORDERED, 3, components.id),
        (REORDERED, 4, work_items.id),
    ]


def test_a_finding_names_its_step_and_its_operation_where_it_has_them() -> None:
    with pytest.raises(ValueError, match="only an extra operation has none"):
        PrefetchFinding(EXTRA, 3, OperationId("op-1"))
    with pytest.raises(ValueError, match="only a missing call has none"):
        PrefetchFinding(MISSING, 3, OperationId("op-1"))
    with pytest.raises(ValueError, match="carries no finding"):
        PrefetchConformance(False, (PrefetchFinding(MISSING, 3, None),))


# --- What ends an obligation -------------------------------------------------------------------


def test_a_call_against_a_stopped_source_is_extra_and_its_absence_is_no_finding(
    world: SealedWorld, scenario: Scenario, normal: RunExport
) -> None:
    down = exported(world, scenario, systems_holding(world), Source.JIRA)
    operations = down.trace.operations
    assert [operation.tool for operation in operations] == [*PLAN[:4], PLAN[5]]
    assert isinstance(operations[3].outcome, UnreachableOutcome)
    work_items = again(normal.trace.operations[4], 7)
    assert findings(with_operations(down, *operations[:4], work_items, operations[4])) == [
        (EXTRA, None, "op-7")
    ]


@dataclass
class _WorkWithBrokenComponents(InMemoryWork):
    def components(self) -> tuple[Observed[Component], ...]:
        self._reach()
        raise MalformedRecord(self.source, "Component/all", "a member id of the wrong shape")


def test_a_malformed_record_ends_the_plan_and_a_read_after_it_is_extra(
    world: SealedWorld, scenario: Scenario, normal: RunExport
) -> None:
    systems = fakes_holding(world)
    systems.work = _WorkWithBrokenComponents(
        tickets=systems.work.tickets, components_by_id=systems.work.components_by_id
    )
    failed = exported(world, scenario, systems)
    assert failed.record.status is TerminalStatus.FAILED
    assert [operation.tool for operation in failed.trace.operations] == PLAN[:4]
    assert isinstance(failed.trace.operations[3].outcome, DefectOutcome)
    assert prefetch_conformance(failed) == CONFORMS
    later = (again(normal.trace.operations[4], 7), again(normal.trace.operations[5], 8))
    assert findings(with_operations(failed, *failed.trace.operations, *later)) == [
        (EXTRA, None, "op-7"),
        (EXTRA, None, "op-8"),
    ]


def test_a_defect_found_at_a_completed_read_ends_nothing(
    world: SealedWorld, scenario: Scenario
) -> None:
    # The enumeration completed without the leaver: the run fails at that read, found after
    # the prefetch has finished, and the reads after it were obliged and made.
    systems = fakes_holding(world)
    del systems.people.people[scenario.investigated_leave.employee_id]
    failed = exported(world, scenario, systems)
    assert failed.record.failure is not None
    assert failed.record.failure.site == OperationSite(OperationId("op-2"))
    assert [operation.tool for operation in failed.trace.operations] == PLAN
    assert prefetch_conformance(failed) == CONFORMS
    stopped_there = with_operations(failed, *failed.trace.operations[:2])
    assert findings(stopped_there) == [(MISSING, step, None) for step in (2, 3, 4, 5)]


def test_a_leave_that_did_not_come_back_ends_the_plan_at_its_first_call(
    world: SealedWorld, scenario: Scenario, normal: RunExport
) -> None:
    systems = fakes_holding(world)
    del systems.people.leaves[LeaveId(scenario.spec.leave_id)]
    absent = exported(world, scenario, systems)
    assert [operation.tool for operation in absent.trace.operations] == ["leave"]
    assert prefetch_conformance(absent) == CONFORMS
    employees = normal.trace.operations[1]
    assert findings(with_operations(absent, *absent.trace.operations, employees)) == [
        (EXTRA, None, employees.id)
    ]


def test_an_opening_read_of_another_leave_obliges_nothing_after_it(
    world: SealedWorld, normal: RunExport
) -> None:
    other = world.scenarios[1].spec.leave_id
    opening, *rest = normal.trace.operations
    assert opening.arguments["id"] != other
    asked_another = with_operations(normal, replace(opening, arguments={"id": other}), *rest)
    assert findings(asked_another) == [
        (WRONG, 0, opening.id),
        *((EXTRA, None, operation.id) for operation in rest),
    ]


def test_every_chunk_of_a_long_leave_is_obliged(world: SealedWorld, scenario: Scenario) -> None:
    systems = fakes_holding(world)
    leave = scenario.investigated_leave
    systems.people.leaves[leave.id] = replace(leave, end=leave.start + timedelta(days=399))
    long = exported(world, scenario, systems)
    operations = long.trace.operations
    chunks = [index for index, operation in enumerate(operations) if operation.tool == PLAN[2]]
    assert len(chunks) > 1
    assert prefetch_conformance(long) == CONFORMS
    kept = [operation for index, operation in enumerate(operations) if index != chunks[1]]
    assert findings(with_operations(long, *kept)) == [(MISSING, 2, None)]


# --- Another rule, the accounting, the registration --------------------------------------------


def test_a_run_planned_under_another_rule_is_not_evaluated(normal: RunExport) -> None:
    record = replace(normal.record, prefetch_rule=PrefetchRule("another-prefetch", DIGEST))
    foreign = replace(with_operations(normal, *normal.trace.operations[:1]), record=record)
    assert prefetch_conformance(foreign) == PrefetchConformance(False, ())


def test_the_accounting_counts_the_runs_with_findings_and_the_ones_not_evaluated(
    world: SealedWorld,
) -> None:
    first, second, third = (
        exported(world, scenario, systems_holding(world), run_id=f"run-{number}")
        for number, scenario in enumerate(world.scenarios[:3], start=1)
    )
    record = replace(third.record, prefetch_rule=PrefetchRule("another-prefetch", DIGEST))
    runs = [
        evaluate_run(world, first),
        evaluate_run(world, with_operations(second, *second.trace.operations[:5])),
        evaluate_run(world, replace(third, record=record)),
    ]
    plan = preregistered(REGISTRATION).plan
    arm = next(arm for arm in arms(world, runs, plan) if any(s.attempts for s in arm.scenarios))
    whole = cells_of(arm)[0]
    accounting = accounting_of(whole, plan)
    assert (accounting.with_prefetch_findings, accounting.prefetch_not_evaluated) == (1, 1)
    summary = attempt_summary_of(whole)
    assert (summary.with_prefetch_findings, summary.prefetch_not_evaluated) == (1, 1)


def test_the_projection_refuses_a_registered_prefetch_this_code_does_not_plan() -> None:
    prefetch = REGISTRATION.prefetch
    for other in (
        replace(prefetch, digest=DIGEST),
        replace(prefetch, protocol_version=prefetch.protocol_version + 1),
        replace(prefetch, identifier="another-prefetch"),
    ):
        with pytest.raises(ValueError, match="this evaluator checks conformance to"):
            preregistered(replace(REGISTRATION, prefetch=other))


def test_a_second_read_of_one_chunk_in_place_of_another_is_missing_and_extra(
    world: SealedWorld, scenario: Scenario
) -> None:
    # The duplicate matches a planned call, the first chunk's, so it is no wrongly
    # parameterized read of the second: that chunk is missing and the duplicate extra.
    systems = fakes_holding(world)
    leave = scenario.investigated_leave
    systems.people.leaves[leave.id] = replace(leave, end=leave.start + timedelta(days=399))
    long = exported(world, scenario, systems)
    operations = list(long.trace.operations)
    first, second, *_ = (i for i, operation in enumerate(operations) if operation.tool == PLAN[2])
    operations[second] = again(operations[first], 99)
    assert findings(with_operations(long, *operations)) == [
        (MISSING, 2, None),
        (EXTRA, None, "op-99"),
    ]
