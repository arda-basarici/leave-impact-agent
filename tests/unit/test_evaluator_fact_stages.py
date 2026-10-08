"""The fact stages on the throwaway world: a truthful stater reaches every stage on every
needed statement when its statements are let in, and only its requirements when the gates
decide, the stand-in prose naming nobody; each step of the funnel loses exactly what a
hand-built run drops there; every emission falls in one class; and the measure answers
nothing where it does not apply."""

from collections import Counter
from dataclasses import replace

import pytest

from leaveimpact.agent.composer import rules_only_composition
from leaveimpact.core import (
    ClaimAuthor,
    Document,
    Failure,
    FailureCategory,
    Observed,
    Operation,
    OperationSite,
    OutageAssignment,
    PredicateName,
    RecordOutcome,
    Source,
    TerminalStatus,
    WorkItem,
    employee_ref,
    work_item_ref,
)
from leaveimpact.core.model_calls import MalformedBatch, ParsedBatch, RefusedBy
from leaveimpact.core.predicates import predicate
from leaveimpact.core.read_coverage import supplied_by
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.skills import SKILLS
from leaveimpact.core.stated import Admitted, FactRefusal, Refused, RefusedInput, StatedFact
from leaveimpact.core.stated_view import Exclusion
from leaveimpact.evaluator.fact_stages import (
    STAGES,
    EmissionClass,
    FactStages,
    PlacementOutcome,
    TargetStages,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from leaveimpact.evaluator.world_index import parts_of
from leaveimpact.world import Scenario
from tests.unit.evaluation_fixture import evaluated
from tests.unit.export_fixture import DIGEST, approval
from tests.unit.stating_fixture import (
    read_everything,
    stating_export,
    truthful_statements,
    truthful_stater_runs,
)
from tests.unit.throwaway_world import loaded_world

NORMAL: tuple[Source, ...] = ()
TRACKER_DOWN, CALENDAR_DOWN = (Source.JIRA,), (Source.CALENDAR,)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def facts_of(evaluation: Evaluation) -> FactStages:
    facts = evaluation.metrics.facts
    assert facts is not None
    return facts


def reached(runs: tuple[Evaluation, ...]) -> tuple[int, list[int]]:
    """The targets of ``runs`` and how many reached each stage, in the stages' order."""
    targets = [target for run in runs for target in facts_of(run).targets]
    return len(targets), [
        sum(target.reached[position] for target in targets) for position in range(len(STAGES))
    ]


# --- The truthful stater, in two layers ----------------------------------------------------------


@pytest.mark.parametrize(
    ("down", "scenarios", "targets", "disputed"),
    [(NORMAL, 20, 31, 14), (TRACKER_DOWN, 8, 15, 11), (CALENDAR_DOWN, 17, 25, 14)],
    ids=["normal", "tracker down", "calendar down"],
)
def test_let_in_whole_a_truthful_stater_reaches_every_stage_on_every_needed_statement(
    down: tuple[Source, ...], scenarios: int, targets: int, disputed: int
) -> None:
    # The denominators are the needed-statements probe's, forecast before the first run.
    runs = truthful_stater_runs(down, False)
    assert sum(bool(facts_of(run).targets) for run in runs) == scenarios
    assert reached(runs) == (targets, [targets] * 4)
    classes = Counter(row.emission_class for run in runs for row in facts_of(run).emissions)
    assert set(classes) == {EmissionClass.NEEDED, EmissionClass.TRUE_UNNEEDED}
    assert classes[EmissionClass.NEEDED] == targets
    for run in runs:
        facts = facts_of(run)
        assert set(facts.placements) <= {
            PlacementOutcome.ON_THE_SEALED_TARGET,
            PlacementOutcome.UNPLACED,
        }
        assert facts.exclusions == ()
        # The record lets in what the gates refuse, the stand-in prose naming nobody: the
        # recheck disputes exactly those admissions and nothing of the composition.
        kinds = Counter(finding.kind.value for finding in run.metrics.recheck.findings)
        assert kinds == {"admission_differs": disputed}


@pytest.mark.parametrize(
    ("down", "targets", "requirements"),
    [(NORMAL, 31, 17), (TRACKER_DOWN, 15, 8), (CALENDAR_DOWN, 25, 14)],
    ids=["normal", "tracker down", "calendar down"],
)
def test_through_the_gates_only_the_class_written_requirements_are_admitted(
    down: tuple[Source, ...], targets: int, requirements: int
) -> None:
    runs = truthful_stater_runs(down, True)
    assert reached(runs) == (targets, [targets, targets, requirements, requirements])
    for run in runs:
        admitted = [target for target in facts_of(run).targets if target.admitted]
        assert {target.predicate for target in admitted} <= {PredicateName.REQUIRES}
        assert run.metrics.recheck.findings == ()
        assert run.metrics.recheck.composition_evaluated
        level = run.metrics.level
        assert level is not None and (level.level, level.findings) == ("base", ())
        assert level.documents > 0
        assert not run.contradiction_not_failed


def test_the_needed_statements_by_predicate_are_the_probes() -> None:
    by_predicate = Counter(
        target.predicate
        for run in truthful_stater_runs(NORMAL, False)
        for target in facts_of(run).targets
    )
    assert by_predicate == {
        PredicateName.REQUIRES: 17,
        PredicateName.NAMES_RESPONSIBLE: 5,
        PredicateName.HAS_SKILL: 5,
        PredicateName.OWNS_WORK_ITEM: 4,
    }


# --- Where the measure does not apply ------------------------------------------------------------


def test_the_measure_answers_nothing_where_it_does_not_apply(world: SealedWorld) -> None:
    scenario = world.scenarios[10]
    # The rules-only system states no fact.
    assert evaluated(world, scenario).metrics.facts is None
    export = stating_export(world, scenario, gated=False)
    assert evaluate_run(world, export).metrics.facts is not None
    # A claim set a model authored was not composed from stated facts.
    authored = replace(export.trace.composition, author=ClaimAuthor.MODEL)
    by_a_model = replace(export, trace=replace(export.trace, composition=authored))
    assert evaluate_run(world, by_a_model).metrics.facts is None
    # Assigned the HR outage, the scenario has no answer and so no needed statement.
    outage = OutageAssignment(frozenset({Source.FRAPPE}), DIGEST)
    unanswerable = replace(export, record=replace(export.record, outage=outage))
    assert evaluate_run(world, unanswerable).metrics.facts is None


def test_the_denominator_is_the_assigned_conditions_whatever_the_reads_met(
    world: SealedWorld,
) -> None:
    # Assigned the tracker outage and run with every source answering: the needed statements
    # are the outage's, fewer than the normal condition's.
    position, under_outage = next(
        (position, facts_of(run))
        for position, run in enumerate(truthful_stater_runs(TRACKER_DOWN, False))
        if len(facts_of(run).targets)
        < len(facts_of(truthful_stater_runs(NORMAL, False)[position]).targets)
    )
    export = stating_export(world, world.scenarios[position], gated=False)
    outage = OutageAssignment(frozenset(TRACKER_DOWN), DIGEST)
    unexercised = replace(export, record=replace(export.record, outage=outage))
    facts = facts_of(evaluate_run(world, unexercised))
    assert [target.target.statement for target in facts.targets] == [
        target.target.statement for target in under_outage.targets
    ]


# --- One loss at each step of the funnel ---------------------------------------------------------


def a_run_needing(
    world: SealedWorld, wanted: PredicateName
) -> tuple[Scenario, tuple[StatedFact, ...], StatedFact]:
    """A scenario whose answer needs a statement of ``wanted``, the truthful stater's
    statements there, and that statement."""
    for scenario, run in zip(world.scenarios, truthful_stater_runs(NORMAL, False), strict=True):
        for target in facts_of(run).targets:
            if target.predicate is wanted:
                _, reads, _, _ = read_everything(world, scenario, NORMAL)
                statements = truthful_statements(world, reads)
                (needed,) = (s for s in statements if s.statement == target.target.statement)
                return scenario, statements, needed
    raise AssertionError(f"no scenario needs a statement of {wanted.value}")


def the_target(evaluation: Evaluation, needed: StatedFact) -> TargetStages:
    (found,) = (
        target
        for target in facts_of(evaluation).targets
        if target.target.statement == needed.statement
    )
    return found


def the_row(evaluation: Evaluation, stated: StatedFact) -> EmissionClass:
    (found,) = (row for row in facts_of(evaluation).emissions if row.fact == stated)
    return found.emission_class


def others_whole(evaluation: Evaluation, needed: StatedFact) -> bool:
    """Whether every other needed statement of the run still reached every stage."""
    return all(
        all(target.reached)
        for target in facts_of(evaluation).targets
        if target.target.statement != needed.statement
    )


def test_a_carrier_no_read_returned_loses_the_statement_at_the_first_stage(
    world: SealedWorld,
) -> None:
    scenario, _, needed = a_run_needing(world, PredicateName.REQUIRES)
    export = stating_export(world, scenario, gated=False)
    kept = tuple(
        operation
        for operation in export.trace.operations
        if needed.carrier not in supplied_by(operation).returned
    )
    unread = evaluate_run(world, replace(export, trace=replace(export.trace, operations=kept)))
    assert the_target(unread, needed).reached == (False, False, False, False)
    assert the_row(unread, needed) is EmissionClass.UNREAD_CARRIER
    assert others_whole(unread, needed)


def test_a_statement_never_made_is_lost_at_the_second_stage(world: SealedWorld) -> None:
    scenario, statements, needed = a_run_needing(world, PredicateName.HAS_SKILL)
    silent = evaluate_run(
        world,
        stating_export(
            world, scenario, statements=[s for s in statements if s != needed], gated=False
        ),
    )
    assert the_target(silent, needed).reached == (True, False, False, False)
    assert others_whole(silent, needed)


def test_a_refused_statement_is_lost_at_the_third_stage_and_a_repeat_restores_it(
    world: SealedWorld,
) -> None:
    scenario, statements, needed = a_run_needing(world, PredicateName.NAMES_RESPONSIBLE)
    refusal = Refused(needed, FactRefusal.MISSING_ANCHOR, "the quote does not name the person")
    entries = [refusal if s == needed else Admitted(s) for s in statements]
    refused = evaluate_run(world, stating_export(world, scenario, entries=entries))
    assert the_target(refused, needed).reached == (True, True, False, False)
    assert others_whole(refused, needed)
    # A refusal is per emission: the same statement admitted later reaches the stage, once,
    # however often it was stated.
    again = evaluate_run(
        world, stating_export(world, scenario, entries=[*entries, Admitted(needed)])
    )
    assert the_target(again, needed).reached == (True, True, True, True)
    rows = [row for row in facts_of(again).emissions if row.fact == needed]
    assert [(row.admitted, row.refusal) for row in rows] == [
        (False, FactRefusal.MISSING_ANCHOR),
        (True, None),
    ]


def test_a_requirement_bound_to_another_artifact_is_admitted_and_not_usable(
    world: SealedWorld,
) -> None:
    scenario, statements, needed = a_run_needing(world, PredicateName.REQUIRES)
    span = needed.target_span
    assert span is not None
    elsewhere = next(
        record.title
        for record in world.index.records.values()
        if isinstance(record, WorkItem)
        and span not in record.title
        and record.title not in needed.quote
    )
    misbound = replace(needed, quote=f"For {elsewhere}, two people.", target_span=elsewhere)
    run = evaluate_run(
        world,
        stating_export(
            world,
            scenario,
            statements=[misbound if s == needed else s for s in statements],
            gated=False,
        ),
    )
    assert the_target(run, needed).reached == (True, True, True, False)
    assert PlacementOutcome.ELSEWHERE in facts_of(run).placements
    assert others_whole(run, needed)


def test_two_readings_of_one_carrier_are_admitted_and_neither_is_usable(
    world: SealedWorld,
) -> None:
    wanted = next(
        name
        for name in (PredicateName.OWNS_WORK_ITEM, PredicateName.NAMES_RESPONSIBLE)
        if not predicate(name).multi_valued
    )
    scenario, statements, needed = a_run_needing(world, wanted)
    assert isinstance(needed.value, EntityRef)
    someone_else = next(
        employee_ref(employee.id)
        for employee in world.org.employees
        if employee_ref(employee.id) != needed.value
    )
    second = replace(needed, value=someone_else)
    run = evaluate_run(
        world, stating_export(world, scenario, statements=[*statements, second], gated=False)
    )
    assert the_target(run, needed).reached == (True, True, True, False)
    assert set(facts_of(run).exclusions) == {Exclusion.CONFLICTING_READINGS}
    assert the_row(run, second) is EmissionClass.FALSE


def test_a_failed_attempt_keeps_its_denominator_and_nothing_of_it_is_usable(
    world: SealedWorld,
) -> None:
    scenario, _, _ = a_run_needing(world, PredicateName.REQUIRES)
    export = stating_export(world, scenario, gated=False)
    at = next(
        operation.id
        for operation in export.trace.operations
        if isinstance(operation.outcome, RecordOutcome)
    )
    failure = Failure(FailureCategory.DEFECT, OperationSite(at), "a record nothing can be made of")
    failed = replace(
        export,
        record=replace(
            export.record,
            status=TerminalStatus.FAILED,
            failure=failure,
            approval=approval((), failed=True),
        ),
        trace=replace(export.trace, claims=(), composition=rules_only_composition()),
    )
    run = evaluate_run(world, failed)
    whole = facts_of(evaluate_run(world, export))
    assert len(facts_of(run).targets) == len(whole.targets)
    assert {target.reached for target in facts_of(run).targets} == {(True, True, True, False)}
    assert not run.metrics.recheck.composition_evaluated


def test_a_stage_is_reached_only_through_the_one_before_it(world: SealedWorld) -> None:
    target = facts_of(truthful_stater_runs(NORMAL, False)[10]).targets[0]
    with pytest.raises(ValueError, match="only through the one before it"):
        replace(target, returned=False)


# --- Every emission in one class -----------------------------------------------------------------


def test_each_class_of_emission_is_told_apart(world: SealedWorld) -> None:
    scenario, statements, needed = a_run_needing(world, PredicateName.HAS_SKILL)
    index = world.index
    kind = needed.carrier.kind
    nowhere = EntityRef(kind, needed.carrier.id[:-3] + "999")
    assert nowhere not in index.parts
    on_nothing = replace(needed, carrier=nowhere)
    _, reads, _, _ = read_everything(world, scenario, NORMAL)
    read_parts = {
        part for record in reads.returned for part, _ in parts_of(record.value) if part.kind is kind
    }
    another = next(
        part
        for part in sorted(read_parts, key=lambda ref: ref.id)
        if part not in index.statements[needed.statement]
    )
    misplaced = replace(needed, carrier=another)
    # Untrue anywhere: not stated by prose and not in the HR record, which the structured
    # class would otherwise claim (seed 6 held the first unstated skill in the record).
    held = {value for subject, _, value in index.statements if subject == needed.subject}
    recorded = next(
        e.skills or () for e in world.org.employees if employee_ref(e.id) == needed.subject
    )
    untrue_skill = next(
        skill.id for skill in SKILLS if skill.id not in held and skill.id not in recorded
    )
    untrue = replace(needed, value=untrue_skill)
    # The comment read as naming its own ticket's owner: no prose says so, the ticket does.
    ticket = index.records[index.parts[needed.carrier].parent]
    assert isinstance(ticket, WorkItem)
    restated = StatedFact(
        PredicateName.OWNS_WORK_ITEM,
        work_item_ref(ticket.id),
        employee_ref(ticket.owner_id),
        needed.carrier,
        needed.quote,
    )
    unreadable = RefusedInput('{"predicate": 7}', FactRefusal.UNDECODABLE, "no predicate")
    batches = (
        ParsedBatch(
            (
                *(Admitted(s) for s in statements),
                Admitted(on_nothing),
                Admitted(misplaced),
                Admitted(untrue),
                Admitted(restated),
                unreadable,
            )
        ),
        MalformedBatch('{"facts": [', RefusedBy("fact-entries", DIGEST)),
    )
    run = evaluate_run(world, stating_export(world, scenario, batches=batches))
    assert the_row(run, needed) is EmissionClass.NEEDED
    assert the_row(run, on_nothing) is EmissionClass.UNKNOWN_CARRIER
    assert the_row(run, misplaced) is EmissionClass.TRUE_ON_ANOTHER_CARRIER
    assert the_row(run, untrue) is EmissionClass.FALSE
    assert the_row(run, restated) is EmissionClass.TRUE_IN_A_STRUCTURED_RECORD
    malformed = [
        (row.batch, row.entry, row.fact, row.admitted)
        for row in facts_of(run).emissions
        if row.emission_class is EmissionClass.MALFORMED
    ]
    assert malformed == [(0, len(statements) + 4, None, None), (1, None, None, None)]
    # A wrong statement beside the right one costs the needed statement nothing here: the
    # skill predicate holds a set.
    assert the_target(run, needed).reached == (True, True, True, True)


def test_a_carrier_that_came_back_with_other_text_vouches_for_nothing(
    world: SealedWorld,
) -> None:
    scenario, _, needed = a_run_needing(world, PredicateName.REQUIRES)
    export = stating_export(world, scenario, gated=False)

    def reworded(operation: Operation) -> Operation:
        outcome = operation.outcome
        if not isinstance(outcome, RecordOutcome) or not isinstance(outcome.record.value, Document):
            return operation
        document = outcome.record.value
        if all(section.id != needed.carrier.id for section in document.sections):
            return operation
        changed = replace(
            document,
            sections=tuple(
                replace(section, text=section.text + " Unless agreed otherwise.")
                for section in document.sections
            ),
        )
        return replace(operation, outcome=RecordOutcome(Observed(changed, outcome.record.source)))

    operations = tuple(reworded(operation) for operation in export.trace.operations)
    run = evaluate_run(world, replace(export, trace=replace(export.trace, operations=operations)))
    assert the_row(run, needed) is EmissionClass.CARRIER_NOT_AS_SEALED
    # The carrier came back, so the statement was returned; what was stated from a text the
    # sealed world does not hold is not the needed statement emitted.
    assert the_target(run, needed).reached == (True, False, False, False)
