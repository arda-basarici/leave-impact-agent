"""Grading a run end to end against a throwaway world loaded through the in-memory store: every
export gets exactly one outcome. A correct report is graded right in every row with no finding,
and the same holds after the export has been through its byte codec; a claimless one misses every
required key; a structurally invalid one is graded with zero credit and its checks not evaluated;
an invalid plan surfaces as a finding. A run under an outage is graded against that condition's
answer, read off the trace and not the record. A run that could not read the leave, or in which a
source both answered and failed, is limited; a failed run and a run of another context are
excluded and never read further."""

from dataclasses import replace
from datetime import timedelta

import pytest

from leaveimpact.core import (
    CandidateAssessment,
    CoverageAction,
    CoverageActionKind,
    EntityKind,
    Impact,
    RunCondition,
    RunExport,
    Source,
    TerminalStatus,
    Verdict,
    ViolationKind,
)
from leaveimpact.core.ids import LeaveId, ScenarioId, WorldVersion
from leaveimpact.core.plans import Violation
from leaveimpact.core.run_export_json import decode_export_bytes, export_bytes
from leaveimpact.evaluator.grading import (
    Excluded,
    ExcludedReason,
    Graded,
    Limited,
    LimitedReason,
    grade_run,
)
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.plan_checks import CheckFamily
from leaveimpact.evaluator.rows import (
    ActionRow,
    AssessmentRow,
    ConflictRow,
    ConstraintRow,
    Expectation,
    ImpactRow,
    ImpactStanding,
    UnknownRow,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.export_fixture import (
    NORMAL,
    answered,
    malformed,
    provider_failed_export,
    reads,
    run_export,
    unreachable,
)
from tests.unit.report_fixture import of_type, renumbered, swapped, truthful_report
from tests.unit.throwaway_world import loaded_world

JIRA_DOWN = NORMAL.without(Source.JIRA)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def answer(world: SealedWorld, scenario: Scenario, condition: RunCondition = NORMAL) -> Answerable:
    oracle = oracle_for(world, scenario, condition)
    assert isinstance(oracle, Answerable)
    return oracle


def graded(world: SealedWorld, export: RunExport) -> Graded:
    outcome = grade_run(world, export)
    assert isinstance(outcome, Graded)
    return outcome


Row = ImpactRow | ConstraintRow | AssessmentRow | ActionRow | ConflictRow | UnknownRow


def every_row(outcome: Graded) -> list[Row]:
    rows = outcome.rows
    return [
        *rows.impacts,
        *rows.constraints,
        *rows.assessments,
        *rows.actions,
        *rows.conflicts,
        *rows.unknowns,
    ]


# --- Graded -------------------------------------------------------------------------------


def test_a_correct_report_is_graded_right_in_every_row_with_no_finding(
    world: SealedWorld,
) -> None:
    for scenario in world.scenarios:
        report = truthful_report(answer(world, scenario))
        outcome = graded(world, run_export(world, scenario, report))
        assert outcome.condition == NORMAL and outcome.harness_findings == ()
        assert (outcome.oracle_findings, outcome.report_findings) == ((), ())
        assert all(row.claim_id is not None and row.standing is None for row in every_row(outcome))
        assert all(row.payload_correct for row in outcome.rows.assessments)
        assert all(row.outcome_matches for row in outcome.rows.actions)
        header = outcome.header
        assert (header.run_id, header.attempt, header.scenario_id) == ("run-7", 1, scenario.spec.id)
        assert header.status is TerminalStatus.COMPLETED


def test_an_export_read_back_from_its_bytes_is_graded_the_same(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    export = run_export(
        world, scenario, truthful_report(answer(world, scenario)), operations=reads()
    )
    assert grade_run(world, decode_export_bytes(export_bytes(export))) == grade_run(world, export)


def test_a_claimless_report_is_graded_through_its_misses(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    outcome = graded(world, run_export(world, scenario, ()))
    rows = every_row(outcome)
    assert rows and all(row.claim_id is None for row in rows)
    assert all(row.expectation is Expectation.REQUIRED for row in rows)
    # Nothing was planned, so there is nothing for the plan checks to find.
    assert (outcome.oracle_findings, outcome.report_findings) == ((), ())


def test_a_run_that_reported_at_its_cap_is_graded_on_what_it_had(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    report = truthful_report(answer(world, scenario))
    partial = tuple(of_type(report, Impact))
    outcome = graded(
        world, run_export(world, scenario, partial, status=TerminalStatus.CAP_EXHAUSTED)
    )
    assert outcome.header.status is TerminalStatus.CAP_EXHAUSTED
    assert all(row.claim_id is not None for row in outcome.rows.impacts)
    assert all(row.claim_id is None for row in outcome.rows.actions)
    # An impact with no action is the chain's to say.
    assert outcome.report_findings is not None
    assert {finding.family for finding in outcome.report_findings} == {CheckFamily.CHAIN}


def test_a_structurally_invalid_report_is_graded_with_no_credit_and_its_checks_unevaluated(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    report = truthful_report(answer(world, scenario))
    twice = (*report, renumbered(of_type(report, Impact)[0], 9_000))
    outcome = graded(world, run_export(world, scenario, twice))
    assert outcome.rows.structural_problems
    assert (outcome.oracle_findings, outcome.report_findings) == (None, None)
    reported = [row for row in every_row(outcome) if row.claim_id is not None]
    assert len(reported) == len(twice)
    assert all(row.expectation is Expectation.NOT_MATCHED for row in reported)


def test_an_invalid_plan_reaches_the_outcome_as_a_finding(world: SealedWorld) -> None:
    scenario, oracle = next(
        (s, answer(world, s))
        for s in world.scenarios
        if answer(world, s).impacts[0].outcome is CoverageActionKind.ASSIGN
    )
    truth = oracle.impacts[0]
    report = truthful_report(oracle)
    unfit = next(a for a in truth.assessments if a.verdict is Verdict.NON_VIABLE).employee_id
    believed = next(
        a
        for a in of_type(report, CandidateAssessment)
        if a.impact_key == truth.key and a.employee_id == unfit
    )
    action = next(a for a in of_type(report, CoverageAction) if a.key == truth.key)
    mistaken = swapped(
        swapped(report, believed, replace(believed, verdict=Verdict.VIABLE, reasons=())),
        action,
        replace(action, assignee_ids=(unfit,)),
    )
    outcome = graded(world, run_export(world, scenario, mistaken))
    assert outcome.oracle_findings is not None
    violations = [f.result for f in outcome.oracle_findings if isinstance(f.result, Violation)]
    # The one person named is not viable, so the plan also names no viable person at all.
    assert [violation.kind for violation in violations] == [
        ViolationKind.NON_VIABLE_ASSIGNEE,
        ViolationKind.INSUFFICIENT_CARDINALITY,
    ]
    assert all(f.family is CheckFamily.ORACLE_PLAN for f in outcome.oracle_findings)
    # The outcome kind is still right, and the row says so: the two judgments are apart.
    [row] = [row for row in outcome.rows.actions if row.key == truth.key]
    assert row.outcome_matches is True


# --- The condition is the trace's -----------------------------------------------------------


def test_a_run_under_an_outage_is_graded_against_that_conditions_answer(
    world: SealedWorld,
) -> None:
    # A scenario whose impact is a ticket: the tracker alone establishes it.
    scenario = next(
        s
        for s in world.scenarios
        if any(e.key.artifact.kind is EntityKind.WORK_ITEM for e in s.key.impacts)
    )
    operations = reads(answered(Source.FRAPPE), unreachable(Source.JIRA))
    degraded = truthful_report(answer(world, scenario, JIRA_DOWN))
    outcome = graded(
        world, run_export(world, scenario, degraded, operations=operations, recorded=JIRA_DOWN)
    )
    assert outcome.condition == JIRA_DOWN and outcome.harness_findings == ()
    assert all(row.claim_id is not None and row.standing is None for row in every_row(outcome))
    assert (outcome.oracle_findings, outcome.report_findings) == ((), ())
    # The normal condition's answer, given under the outage, is no longer right: what the
    # tracker alone could establish is unsupported, not confirmed.
    confident = truthful_report(answer(world, scenario))
    overreach = graded(
        world, run_export(world, scenario, confident, operations=operations, recorded=JIRA_DOWN)
    )
    lost = [row for row in overreach.rows.impacts if row.standing is not None]
    assert lost and all(
        row.standing is ImpactStanding.UNSUPPORTED_UNDER_THE_CONDITION for row in lost
    )
    assert all(row.key.artifact.kind is EntityKind.WORK_ITEM for row in lost)


def test_the_trace_decides_the_condition_and_a_disagreeing_record_is_a_harness_finding(
    world: SealedWorld,
) -> None:
    scenario = next(s for s in world.scenarios if Source.JIRA in s.key.required_sources)
    # The record says nothing failed; a read of the tracker came back unreachable.
    unrecorded = graded(
        world,
        run_export(
            world, scenario, (), operations=reads(unreachable(Source.JIRA)), recorded=NORMAL
        ),
    )
    assert unrecorded.condition == JIRA_DOWN
    assert unrecorded.harness_findings == (
        "the record states nothing unreachable and the trace shows jira unreachable; the "
        "trace stands",
    )
    # The record says the tracker was down; no read of it failed, so the run ran under no
    # outage, whatever was scheduled.
    unexercised = graded(
        world,
        run_export(
            world, scenario, (), operations=reads(answered(Source.FRAPPE)), recorded=JIRA_DOWN
        ),
    )
    assert unexercised.condition == NORMAL and len(unexercised.harness_findings) == 1
    # An outage nobody registered is still graded mechanically.
    both = NORMAL.without(Source.JIRA, Source.CALENDAR)
    unregistered = graded(
        world,
        run_export(
            world,
            scenario,
            (),
            operations=reads(unreachable(Source.JIRA), unreachable(Source.CALENDAR)),
            recorded=both,
        ),
    )
    assert unregistered.condition == both


# --- Limited --------------------------------------------------------------------------------


def test_a_run_that_could_not_read_the_leave_is_limited_and_its_report_still_checked(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    frappe_down = NORMAL.without(Source.FRAPPE)
    operations = reads(unreachable(Source.FRAPPE))
    silent = grade_run(
        world, run_export(world, scenario, (), operations=operations, recorded=frappe_down)
    )
    assert isinstance(silent, Limited)
    assert (silent.reason, silent.mixed, silent.condition) == (
        LimitedReason.UNREADABLE_LEAVE,
        frozenset(),
        frappe_down,
    )
    # Nothing to compare against, and the report's own checks ran and found nothing.
    assert (silent.structural_problems, silent.report_findings) == ((), ())
    # A report that goes on to claim impacts with no action is incoherent, and that shows.
    impacts = tuple(of_type(truthful_report(answer(world, scenario)), Impact))
    talkative = grade_run(
        world, run_export(world, scenario, impacts, operations=operations, recorded=frappe_down)
    )
    assert isinstance(talkative, Limited) and talkative.report_findings
    # A structurally invalid one cannot be checked at all, which is said and not hidden.
    twice = (*impacts, renumbered(impacts[0], 9_000))
    broken = grade_run(
        world, run_export(world, scenario, twice, operations=operations, recorded=frappe_down)
    )
    assert isinstance(broken, Limited)
    assert broken.structural_problems and broken.report_findings is None


def test_a_run_in_which_a_source_both_answered_and_failed_is_limited_as_mixed(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    operations = reads(answered(Source.FRAPPE), answered(Source.JIRA), unreachable(Source.JIRA))
    report = truthful_report(answer(world, scenario))
    outcome = grade_run(
        world, run_export(world, scenario, report, operations=operations, recorded=JIRA_DOWN)
    )
    assert isinstance(outcome, Limited)
    assert (outcome.reason, outcome.mixed) == (
        LimitedReason.MIXED_CONDITION,
        frozenset({Source.JIRA}),
    )
    assert outcome.condition == JIRA_DOWN and outcome.report_findings is not None


# --- Excluded -------------------------------------------------------------------------------


def test_a_failed_run_is_excluded_by_its_failure_category(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    defect = grade_run(
        world,
        run_export(
            world,
            scenario,
            (),
            operations=reads(answered(Source.FRAPPE), malformed(Source.JIRA)),
            status=TerminalStatus.FAILED,
        ),
    )
    assert isinstance(defect, Excluded) and defect.reason is ExcludedReason.FAILED_BY_DEFECT
    assert defect.header.status is TerminalStatus.FAILED
    infrastructure = grade_run(world, provider_failed_export(world, scenario))
    assert isinstance(infrastructure, Excluded)
    assert infrastructure.reason is ExcludedReason.FAILED_BY_INFRASTRUCTURE


def test_a_run_of_another_context_is_excluded_before_anything_else_is_read(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    sealed = world.context_of(scenario)
    report = truthful_report(answer(world, scenario))
    for context in (
        replace(sealed, world_version=WorldVersion("f" * 64)),
        replace(sealed, now=sealed.now + timedelta(days=1)),
        replace(sealed, leave_id=LeaveId("leave_999")),
        replace(sealed, reference_timezone="UTC"),
        replace(sealed, scenario_id=ScenarioId("scenario_999")),
    ):
        outcome = grade_run(world, run_export(world, scenario, report, context=context))
        assert isinstance(outcome, Excluded), context
        assert outcome.reason is ExcludedReason.CONTEXT_MISMATCH
    # The context is checked first: a failed run of another context is a context mismatch.
    failed_elsewhere = grade_run(
        world,
        run_export(
            world,
            scenario,
            (),
            operations=reads(malformed(Source.JIRA)),
            status=TerminalStatus.FAILED,
            context=replace(sealed, world_version=WorldVersion("f" * 64)),
        ),
    )
    assert isinstance(failed_elsewhere, Excluded)
    assert failed_elsewhere.reason is ExcludedReason.CONTEXT_MISMATCH


# --- The outcomes refuse what means nothing --------------------------------------------------


def test_an_outcome_keeps_not_evaluated_apart_from_nothing_found(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    outcome = graded(world, run_export(world, scenario, ()))
    with pytest.raises(ValueError, match="evaluated exactly when the claim set is structurally"):
        replace(outcome, oracle_findings=None)
    limited = grade_run(
        world,
        run_export(
            world,
            scenario,
            (),
            operations=reads(unreachable(Source.FRAPPE)),
            recorded=NORMAL.without(Source.FRAPPE),
        ),
    )
    assert isinstance(limited, Limited)
    with pytest.raises(ValueError, match="a mixed condition names its mixed sources"):
        replace(limited, mixed=frozenset({Source.JIRA}))
    with pytest.raises(ValueError, match="evaluated exactly when the claim set is structurally"):
        replace(limited, report_findings=None)
