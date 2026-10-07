"""The level check: every document a run was shown is held to the level its record assigns,
whoever asked for it and whatever the operation is; a level the world seals no membership
for is not evaluated, which is not a run with no finding; and both are counted."""

from dataclasses import replace

import pytest

from leaveimpact.core import (
    Document,
    HarnessOrigin,
    Observed,
    Operation,
    OperationId,
    RecordOutcome,
    RecordsOutcome,
    RunExport,
    document_ref,
)
from leaveimpact.core.ids import document_id
from leaveimpact.core.ports.observed import Entity
from leaveimpact.evaluator.cells import accounting_of, arms, attempt_summary_of, cells_of
from leaveimpact.evaluator.level_check import LevelFinding, level_check
from leaveimpact.evaluator.registered import preregistered
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import evaluate_run
from leaveimpact.world import Scenario
from tests.unit.evaluation_fixture import BASE, PADDED
from tests.unit.registration_fixture import DRAFT, decided, light, named
from tests.unit.stating_fixture import stating_export
from tests.unit.throwaway_world import loaded_world

UNSEALED = document_id(999)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def scenario(world: SealedWorld) -> Scenario:
    return world.scenarios[10]


@pytest.fixture(scope="module")
def export(world: SealedWorld, scenario: Scenario) -> RunExport:
    return stating_export(world, scenario)


def documents_read(export: RunExport) -> list[Operation]:
    return [
        operation
        for operation in export.trace.operations
        if isinstance(operation.outcome, RecordOutcome)
        and isinstance(operation.outcome.record.value, Document)
    ]


def with_operations(export: RunExport, operations: tuple[Operation, ...]) -> RunExport:
    return replace(export, trace=replace(export.trace, operations=operations))


def unsealed_copy(operation: Operation) -> Observed[Entity]:
    outcome = operation.outcome
    assert isinstance(outcome, RecordOutcome) and isinstance(outcome.record.value, Document)
    return Observed[Entity](replace(outcome.record.value, id=UNSEALED), outcome.record.source)


# --- The membership ------------------------------------------------------------------------------


def test_a_world_sealed_without_filler_holds_the_base_level_and_no_other(
    world: SealedWorld,
) -> None:
    base = world.level_documents(BASE)
    assert base is not None and len(base) == 26
    assert base == {
        document_ref(planted.entity.id) for s in world.scenarios for planted in s.owned.documents
    }
    # No membership is sealed for another level: that is not an empty level.
    assert world.level_documents(PADDED) is None


# --- The check -----------------------------------------------------------------------------------


def test_a_run_shown_only_its_levels_documents_has_no_finding(
    world: SealedWorld, scenario: Scenario, export: RunExport
) -> None:
    check = level_check(world, export)
    assert check is not None
    assert (check.level, check.documents, check.findings) == (BASE, 26, ())
    # A run that read no document is evaluated, with nothing shown: the frozen prefetch
    # reads none, so every baseline run is this.
    structured = tuple(op for op in export.trace.operations if op not in documents_read(export))
    nothing = level_check(world, with_operations(export, structured))
    assert nothing is not None and (nothing.documents, nothing.findings) == (0, ())


def test_a_document_outside_the_level_is_a_finding_once_per_operation_whoever_asked(
    world: SealedWorld, export: RunExport
) -> None:
    by_id, another, *_ = documents_read(export)
    stray = unsealed_copy(by_id)
    # Read by its id, in place of the sealed document.
    read = replace(by_id, outcome=RecordOutcome(stray))
    # And put in front of the model by the harness, twice in one sequence with a sealed one.
    last = export.trace.operations[-1].position
    assert last is not None and isinstance(another.outcome, RecordOutcome)
    shown = Operation(
        OperationId("op-shown"),
        HarnessOrigin("all-documents"),
        "document",
        by_id.source,
        {},
        RecordsOutcome((stray, another.outcome.record, stray)),
        last + 1,
    )
    operations = tuple(read if op is by_id else op for op in export.trace.operations)
    check = level_check(world, with_operations(export, (*operations, shown)))
    assert check is not None
    assert check.findings == (
        LevelFinding(by_id.id, document_ref(UNSEALED)),
        LevelFinding(shown.id, document_ref(UNSEALED)),
    )
    # The sealed document it replaced is no longer among the distinct documents shown.
    assert check.documents == 26


def test_a_level_the_world_seals_no_membership_for_is_not_evaluated(
    world: SealedWorld, export: RunExport
) -> None:
    padded = replace(export, record=replace(export.record, corpus_level=PADDED))
    assert level_check(world, padded) is None
    assert evaluate_run(world, padded).metrics.level is None


# --- Counted -------------------------------------------------------------------------------------


def test_a_run_outside_its_level_and_a_run_held_to_none_are_counted_apart(
    world: SealedWorld, export: RunExport
) -> None:
    plan = preregistered(light(decided(named(DRAFT), True))).plan
    by_id = documents_read(export)[0]
    strayed = with_operations(
        export,
        tuple(
            replace(op, outcome=RecordOutcome(unsealed_copy(op))) if op is by_id else op
            for op in export.trace.operations
        ),
    )
    padded = replace(export, record=replace(export.record, corpus_level=PADDED))
    runs = [
        evaluate_run(world, export),
        evaluate_run(world, replace(strayed, run_id="run-9")),
        evaluate_run(world, padded),
    ]
    built = {arm.level: arm for arm in arms(world, runs, plan) if not arm.registered}
    at_base = accounting_of(cells_of(built[BASE])[0], plan)
    assert (at_base.made, at_base.with_level_findings, at_base.level_not_evaluated) == (2, 1, 0)
    at_padded = accounting_of(cells_of(built[PADDED])[0], plan)
    assert (at_padded.made, at_padded.with_level_findings, at_padded.level_not_evaluated) == (
        1,
        0,
        1,
    )
    # The attempt summary counts the same things over every attempt.
    attempts = attempt_summary_of(cells_of(built[BASE])[0])
    assert (attempts.with_level_findings, attempts.level_not_evaluated) == (1, 0)


# --- With a pool ---------------------------------------------------------------------------------


def test_a_world_with_a_pool_holds_each_sealed_level_and_no_other() -> None:
    from tests.unit.throwaway_world import loaded_world_with_filler

    padded = loaded_world_with_filler(3)
    owned = {
        document_ref(planted.entity.id)
        for s in padded.scenarios
        for planted in s.owned.documents
    }
    assert len(padded.filler) == 3
    assert padded.level_documents(BASE) == owned
    assert padded.level_documents(PADDED) == owned | set(padded.filler[:2])
    assert padded.level_documents("huge") is None


def test_a_filler_document_beyond_the_run_s_level_is_a_finding(scenario: Scenario) -> None:
    from leaveimpact.core import Source
    from leaveimpact.core.ids import ScenarioId
    from tests.unit.throwaway_world import loaded_world_with_filler

    padded = loaded_world_with_filler(3)
    own = padded.scenario(ScenarioId(scenario.spec.id))
    assert own is not None
    export = stating_export(padded, own)
    beyond = padded.index.records[padded.filler[2]]
    within = padded.index.records[padded.filler[0]]
    by_id = documents_read(export)[0]
    last = export.trace.operations[-1].position
    assert last is not None
    shown = Operation(
        OperationId("op-shown"),
        HarnessOrigin("all-documents"),
        "document",
        by_id.source,
        {},
        RecordsOutcome(
            (Observed[Entity](within, Source.CORPUS), Observed[Entity](beyond, Source.CORPUS))
        ),
        last + 1,
    )
    at_padded = replace(export, record=replace(export.record, corpus_level=PADDED))
    check = level_check(padded, with_operations(at_padded, (*export.trace.operations, shown)))
    assert check is not None
    assert check.findings == (LevelFinding(shown.id, padded.filler[2]),)
    at_base = with_operations(export, (*export.trace.operations, shown))
    base = level_check(padded, at_base)
    assert base is not None
    assert base.findings == (
        LevelFinding(shown.id, padded.filler[0]),
        LevelFinding(shown.id, padded.filler[2]),
    )
