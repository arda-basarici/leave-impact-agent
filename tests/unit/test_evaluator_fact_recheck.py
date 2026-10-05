"""The fact recheck: a record written by the gates and the composer has no finding; each way a
record can differ from them has exactly its own; admission is rerun at the answer's
position, so a read logged later rescues nothing; and a composition is rerun only where one
was made."""

from dataclasses import replace

import pytest

from leaveimpact.agent.composer import rules_only_composition
from leaveimpact.core import (
    ClaimAuthor,
    Failure,
    FailureCategory,
    OperationSite,
    PredicateName,
    RecordOutcome,
    RunExport,
    TerminalStatus,
)
from leaveimpact.core.model_calls import ParsedBatch
from leaveimpact.core.read_coverage import supplied_by
from leaveimpact.core.run_ending import RequirementPlacement
from leaveimpact.core.stated import (
    Admitted,
    FactRefusal,
    PlacementState,
    Refused,
    SpanPlacement,
    StatedFact,
)
from leaveimpact.core.stated_view import Excluded, Exclusion
from leaveimpact.evaluator.cells import Preregistered, accounting_of, arms, cells_of
from leaveimpact.evaluator.fact_recheck import RecheckFinding, RecheckKind, recheck_facts
from leaveimpact.evaluator.registered import preregistered
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import evaluate_run
from leaveimpact.world import Scenario
from tests.unit.evaluation_fixture import evaluated
from tests.unit.export_fixture import approval
from tests.unit.registration_fixture import DRAFT, decided, light, named
from tests.unit.stating_fixture import ANSWERED_AT, stating_export
from tests.unit.throwaway_world import loaded_world

CALL = "call-1"


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def scenario(world: SealedWorld) -> Scenario:
    """A scenario of the fragmented tier: its answer needs a requirement and other prose."""
    return world.scenarios[10]


@pytest.fixture(scope="module")
def truthful(world: SealedWorld, scenario: Scenario) -> RunExport:
    return stating_export(world, scenario)


def entries_of(export: RunExport) -> tuple[Admitted | Refused, ...]:
    (batch,) = export.trace.model_calls[0].answer.fact_batches  # type: ignore[union-attr]
    assert isinstance(batch, ParsedBatch)
    return tuple(entry for entry in batch.entries if isinstance(entry, Admitted | Refused))


def kinds(export: RunExport) -> list[RecheckKind]:
    return [finding.kind for finding in recheck_facts(export).findings]


# --- A record the functions wrote ----------------------------------------------------------------


def test_a_record_written_by_the_gates_and_the_composer_has_no_finding(
    world: SealedWorld, scenario: Scenario, truthful: RunExport
) -> None:
    recheck = recheck_facts(truthful)
    assert recheck.findings == ()
    assert recheck.composition_evaluated
    assert recheck.admissions == len(entries_of(truthful)) == 31
    # The baseline states nothing: nothing to decide again, and nothing composed of it.
    baseline = evaluated(world, scenario).metrics.recheck
    assert (baseline.admissions, baseline.composition_evaluated, baseline.findings) == (0, True, ())


# --- Each difference has its own finding ---------------------------------------------------------


def test_an_admission_the_gates_refuse_and_a_refusal_they_admit_are_each_named(
    world: SealedWorld, scenario: Scenario, truthful: RunExport
) -> None:
    recorded = entries_of(truthful)
    refused_at = next(at for at, entry in enumerate(recorded) if isinstance(entry, Refused))
    admitted_at = next(at for at, entry in enumerate(recorded) if isinstance(entry, Admitted))
    flipped = list(recorded)
    flipped[refused_at] = Admitted(recorded[refused_at].fact)
    flipped[admitted_at] = Refused(
        recorded[admitted_at].fact, FactRefusal.QUOTE_NOT_IN_CARRIER, "said to be misquoted"
    )
    export = stating_export(world, scenario, entries=flipped)
    admissions = [
        finding
        for finding in recheck_facts(export).findings
        if finding.kind is RecheckKind.ADMISSION_DIFFERS
    ]
    assert admissions == [
        RecheckFinding(RecheckKind.ADMISSION_DIFFERS, CALL, 0, at)  # type: ignore[arg-type]
        for at in sorted((refused_at, admitted_at))
    ]


def test_a_refusal_under_another_reason_than_the_gates_is_named(
    world: SealedWorld, scenario: Scenario, truthful: RunExport
) -> None:
    recorded = list(entries_of(truthful))
    at = next(at for at, entry in enumerate(recorded) if isinstance(entry, Refused))
    held = recorded[at]
    assert isinstance(held, Refused) and held.reason is FactRefusal.MISSING_ANCHOR
    # A refusal's detail is free text and no part of the comparison.
    reworded: list[Admitted | Refused] = [
        Refused(entry.fact, entry.reason, "worded otherwise")
        if isinstance(entry, Refused)
        else entry
        for entry in recorded
    ]
    assert kinds(stating_export(world, scenario, entries=reworded)) == []
    reworded[at] = Refused(held.fact, FactRefusal.SUBJECT_NOT_READ, "another reason")
    assert recheck_facts(stating_export(world, scenario, entries=reworded)).findings == (
        RecheckFinding(RecheckKind.REFUSAL_REASON_DIFFERS, CALL, 0, at),  # type: ignore[arg-type]
    )


def test_a_composition_that_is_not_the_rules_is_named_by_what_differs(
    truthful: RunExport,
) -> None:
    composition = truthful.trace.composition
    assert composition.placements and not composition.exclusions

    def with_composition(**changed: object) -> RunExport:
        return replace(
            truthful, trace=replace(truthful.trace, composition=replace(composition, **changed))
        )

    placed = next(
        entry for entry in composition.placements if entry.placement.state is PlacementState.PLACED
    )
    others = tuple(entry for entry in composition.placements if entry is not placed)
    moved = RequirementPlacement(placed.fact, SpanPlacement(PlacementState.UNPLACED))
    assert kinds(with_composition(placements=(moved, *others))) == [RecheckKind.PLACEMENTS_DIFFER]
    assert kinds(with_composition(placements=others)) == [RecheckKind.PLACEMENTS_DIFFER]
    invented = Excluded(placed.fact, Exclusion.CONFLICTING_SCOPES)
    assert kinds(with_composition(exclusions=(invented,))) == [RecheckKind.EXCLUSIONS_DIFFER]
    # The order of what was composed is no part of it.
    assert kinds(with_composition(placements=composition.placements[::-1])) == []


def test_two_readings_the_record_leaves_in_the_view_are_an_exclusion_that_differs(
    world: SealedWorld, scenario: Scenario, truthful: RunExport
) -> None:
    requirement = next(entry.fact for entry in entries_of(truthful) if isinstance(entry, Admitted))
    assert requirement.predicate is PredicateName.REQUIRES
    assert requirement.target_span is not None
    twice = StatedFact(
        requirement.predicate,
        requirement.subject,
        replace(requirement.value, count=requirement.value.count + 1),  # type: ignore[union-attr, type-var]
        requirement.carrier,
        requirement.quote,
        requirement.target_span,
    )
    sound = stating_export(world, scenario, entries=[*entries_of(truthful), Admitted(twice)])
    assert {entry.reason for entry in sound.trace.composition.exclusions} == {
        Exclusion.CONFLICTING_READINGS
    }
    # The second reading is let in by the record alone: the clause does not write its count.
    assert kinds(sound) == [RecheckKind.ADMISSION_DIFFERS]
    unexcluded = replace(sound.trace.composition, exclusions=())
    silent = replace(sound, trace=replace(sound.trace, composition=unexcluded))
    assert kinds(silent) == [RecheckKind.ADMISSION_DIFFERS, RecheckKind.EXCLUSIONS_DIFFER]


# --- Where it is decided -------------------------------------------------------------------------


def test_admission_is_rerun_over_the_reads_logged_before_the_answer(
    world: SealedWorld, scenario: Scenario, truthful: RunExport
) -> None:
    at, requirement = next(
        (at, entry.fact)
        for at, entry in enumerate(entries_of(truthful))
        if isinstance(entry, Admitted)
    )
    # The read that returned the requirement's clause, logged after the answer instead: the
    # record still says admitted, and over the reads the answer could rest on it is refused.
    late = tuple(
        replace(operation, position=ANSWERED_AT + 10 + number)
        if requirement.carrier in supplied_by(operation).returned
        else operation
        for number, operation in enumerate(truthful.trace.operations)
    )
    operations = tuple(sorted(late, key=lambda operation: operation.position or 0))
    reordered = replace(truthful, trace=replace(truthful.trace, operations=operations))
    found = recheck_facts(reordered).findings
    assert RecheckFinding(RecheckKind.ADMISSION_DIFFERS, CALL, 0, at) in found  # type: ignore[arg-type]
    # Composing is over everything the run read, the late read included: the composition
    # recorded is still the one the rules give.
    assert {finding.kind for finding in found} == {RecheckKind.ADMISSION_DIFFERS}


def test_an_admitted_statement_whose_carrier_no_read_returned_cannot_be_composed_again(
    truthful: RunExport,
) -> None:
    requirement = next(entry.fact for entry in entries_of(truthful) if isinstance(entry, Admitted))
    unread = tuple(
        operation
        for operation in truthful.trace.operations
        if requirement.carrier not in supplied_by(operation).returned
    )
    export = replace(truthful, trace=replace(truthful.trace, operations=unread))
    assert RecheckKind.NOT_COMPOSABLE in kinds(export)
    assert RecheckKind.ADMISSION_DIFFERS in kinds(export)


def test_a_composition_is_rerun_only_where_one_was_made(truthful: RunExport) -> None:
    at = next(
        operation.id
        for operation in truthful.trace.operations
        if isinstance(operation.outcome, RecordOutcome)
    )
    failed = replace(
        truthful,
        record=replace(
            truthful.record,
            status=TerminalStatus.FAILED,
            failure=Failure(FailureCategory.DEFECT, OperationSite(at), "a record of no use"),
            approval=approval((), failed=True),
        ),
        trace=replace(truthful.trace, claims=(), composition=rules_only_composition()),
    )
    recheck = recheck_facts(failed)
    # A failed attempt composed nothing; its admissions are decided again all the same.
    assert (recheck.composition_evaluated, recheck.findings) == (False, ())
    assert recheck.admissions == 31
    authored = replace(truthful.trace.composition, author=ClaimAuthor.MODEL, placements=())
    by_a_model = replace(truthful, trace=replace(truthful.trace, composition=authored))
    assert not recheck_facts(by_a_model).composition_evaluated


# --- Counted ---------------------------------------------------------------------------------


def plan() -> Preregistered:
    return preregistered(light(decided(named(DRAFT), True))).plan


def test_a_run_whose_record_the_rerun_disputes_is_counted_and_stays(
    world: SealedWorld, scenario: Scenario, truthful: RunExport
) -> None:
    disputed = stating_export(world, scenario, gated=False)
    runs = [evaluate_run(world, truthful), evaluate_run(world, replace(disputed, run_id="run-9"))]
    (arm,) = (held for held in arms(world, runs, plan()) if not held.registered)
    accounting = accounting_of(cells_of(arm)[0], plan())
    assert (accounting.made, accounting.graded, accounting.with_fact_findings) == (2, 2, 1)
