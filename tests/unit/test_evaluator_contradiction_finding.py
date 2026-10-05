"""A run that met a source contradicting itself and did not fail by defect says so: one that
completed, and one that failed afterwards by infrastructure, each went on past the read the
rule stops a harness at; a run that failed by defect did not; and the runs are counted."""

from dataclasses import replace

import pytest

from leaveimpact.core import (
    Failure,
    FailureCategory,
    HarnessSite,
    HarnessSiteName,
    Observed,
    Operation,
    OperationId,
    OperationSite,
    RecordsOutcome,
    RunCondition,
    RunExport,
    TerminalStatus,
)
from leaveimpact.core.contradictions import ContradictionKind
from leaveimpact.evaluator.cells import accounting_of, arms, attempt_summary_of, cells_of
from leaveimpact.evaluator.grading import Excluded, ExcludedReason, Graded
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.registered import preregistered
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import evaluate_run
from leaveimpact.world import Scenario
from tests.unit.export_fixture import approval, run_export
from tests.unit.reads_fixture import reads_of_everything
from tests.unit.registration_fixture import DRAFT, light
from tests.unit.report_fixture import truthful_report
from tests.unit.throwaway_world import loaded_world

AGAIN = OperationId("op-again")


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def scenario(world: SealedWorld) -> Scenario:
    return world.scenarios[0]


def contradicted(world: SealedWorld, scenario: Scenario) -> list[Operation]:
    """A full read, and the people enumerated once more with one of them renamed: two complete
    reads of one source that cannot both be true."""
    everything = reads_of_everything(world, scenario)
    enumeration = next(operation for operation in everything if operation.tool == "employees")
    outcome = enumeration.outcome
    assert isinstance(outcome, RecordsOutcome)
    first, *rest = outcome.records
    renamed = Observed(replace(first.value, name=f"{first.value.name} the Second"), first.source)  # type: ignore[attr-defined]
    return [*everything, replace(enumeration, id=AGAIN, outcome=RecordsOutcome((renamed, *rest)))]


def completed(world: SealedWorld, scenario: Scenario, operations: list[Operation]) -> RunExport:
    oracle = oracle_for(world, scenario, RunCondition.all_reachable())
    assert isinstance(oracle, Answerable)
    return run_export(world, scenario, truthful_report(oracle), operations=operations)


def failed(export: RunExport, failure: Failure) -> RunExport:
    record = replace(
        export.record,
        status=TerminalStatus.FAILED,
        failure=failure,
        approval=approval((), failed=True),
    )
    return replace(export, record=record, trace=replace(export.trace, claims=()))


def test_a_run_that_met_a_contradiction_and_went_on_says_so(
    world: SealedWorld, scenario: Scenario
) -> None:
    went_on = completed(world, scenario, contradicted(world, scenario))
    evaluation = evaluate_run(world, went_on)
    assert isinstance(evaluation.outcome, Graded)
    assert [found.kind for found in evaluation.contradictions] == [ContradictionKind.RETURNS_DIFFER]
    assert evaluation.contradiction_not_failed

    # The rule's own ending: failed by defect at the read that contradicted the earlier one.
    stopped = failed(
        went_on, Failure(FailureCategory.DEFECT, OperationSite(AGAIN), "a record returned two ways")
    )
    by_defect = evaluate_run(world, stopped)
    assert isinstance(by_defect.outcome, Excluded)
    assert by_defect.outcome.reason is ExcludedReason.FAILED_BY_DEFECT
    assert by_defect.contradictions and not by_defect.contradiction_not_failed

    # Failed afterwards for another reason: it had gone on past the contradiction.
    later = failed(
        went_on,
        Failure(
            FailureCategory.INFRASTRUCTURE,
            HarnessSite(HarnessSiteName.EVENT_APPEND),
            "the log refused an append",
        ),
    )
    by_infrastructure = evaluate_run(world, later)
    assert isinstance(by_infrastructure.outcome, Excluded)
    assert by_infrastructure.contradiction_not_failed

    # No contradiction, no finding.
    clean = evaluate_run(world, completed(world, scenario, reads_of_everything(world, scenario)))
    assert clean.contradictions == () and not clean.contradiction_not_failed


def test_the_runs_that_went_on_are_counted_among_the_counted_and_among_every_attempt(
    world: SealedWorld, scenario: Scenario
) -> None:
    plan = preregistered(light(DRAFT)).plan
    went_on = completed(world, scenario, contradicted(world, scenario))
    stopped = failed(
        went_on, Failure(FailureCategory.DEFECT, OperationSite(AGAIN), "a record returned two ways")
    )
    clean = completed(world, scenario, reads_of_everything(world, scenario))
    runs = [
        evaluate_run(world, replace(export, run_id=name))
        for name, export in (("run-a", went_on), ("run-b", stopped), ("run-c", clean))
    ]
    (arm,) = (
        held
        for held in arms(world, runs, plan)
        if held.registered
        and held.level == "base"
        and held.assigned == RunCondition.all_reachable()
    )
    whole = cells_of(arm)[0]
    assert accounting_of(whole, plan).contradiction_not_failed == 1
    assert attempt_summary_of(whole).contradiction_not_failed == 1
