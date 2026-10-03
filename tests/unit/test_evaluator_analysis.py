"""The registered analysis. Under the draft it scores the rules-only arm of each
answer-quality condition, describes the degraded-condition arms, keeps every comparison that
needs a pending system and says why it has no result, and reports the primary set as
unavailable. With every system named and the development scenarios registered it computes
the two primaries over the twenty-four held-out scenarios and the descriptive product over
both sets. Repeated runs are classified per scenario only where every repeat can be
compared. The degraded table puts each counted run in one row, a failed attempt never an
empty report."""

from dataclasses import replace
from pathlib import Path

import pytest

from leaveimpact.core import (
    AgentSystem,
    CoverageAction,
    Operation,
    Pending,
    Registration,
    ReportingScope,
    ScenarioSetName,
    SingleShotSystem,
    Source,
    System,
    SystemKind,
    decode_registration_bytes,
)
from leaveimpact.evaluator.analysis import ArmAnalysis, SetAnalysis, analyse
from leaveimpact.evaluator.cells import StratumKind, arms, cells_of
from leaveimpact.evaluator.diagnostics import (
    DegradedRow,
    Exposure,
    OutcomeKind,
    ReplayState,
    ReportState,
    degraded_table,
    repeat_consistency,
)
from leaveimpact.evaluator.grading import ExcludedReason, LimitedReason
from leaveimpact.evaluator.registered import development_selection, preregistered
from leaveimpact.evaluator.run_checks import CORRECT_WHOLE
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.tables import Reading
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from leaveimpact.world import Scenario
from tests.unit.evaluation_fixture import NORMAL, REFERENCE, evaluated, relabelled, truthful
from tests.unit.export_fixture import provider_failed_export, reads, unreachable
from tests.unit.report_fixture import of_type, without
from tests.unit.throwaway_world import loaded_world

_DRAFT = decode_registration_bytes(
    (Path(__file__).resolve().parents[2] / "preregistration" / "registration.json").read_bytes()
)
# The registered count buys precision these tests do not need.
DRAFT = replace(_DRAFT, statistics=replace(_DRAFT.statistics, resamples=200))
AGENT = System(SystemKind.AGENT, "graph")
SINGLE_SHOT = System(SystemKind.SINGLE_SHOT, "one-call")


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def truthful_runs(world: SealedWorld) -> list[Evaluation]:
    return [evaluated(world, scenario) for scenario in world.scenarios]


def named(world: SealedWorld) -> Registration:
    """The draft with the two model systems named and the development scenarios registered."""
    systems = tuple(
        replace(system, variant=AGENT.variant)
        if isinstance(system, AgentSystem)
        else replace(system, variant=SINGLE_SHOT.variant)
        if isinstance(system, SingleShotSystem)
        else system
        for system in DRAFT.systems
    )
    sets = replace(DRAFT.scenario_sets, development=development_selection(world, DRAFT))
    return replace(DRAFT, systems=systems, scenario_sets=sets)


def selection_pending(registration: Registration) -> Registration:
    """``registration`` as it stood before its development scenarios were selected."""
    sets = replace(registration.scenario_sets, development=Pending("not yet selected"))
    return replace(registration, scenario_sets=sets)


def arm_of(held: SetAnalysis, kind: SystemKind, condition: str) -> ArmAnalysis:
    return next(a for a in held.arms if (a.system.kind, a.condition) == (kind, condition))


def lacking_its_action(world: SealedWorld, scenario: Scenario) -> Evaluation:
    report = truthful(world, scenario, NORMAL)
    return evaluated(world, scenario, claims=without(report, of_type(report, CoverageAction)[0]))


# --- Under the draft ---------------------------------------------------------------------------


def test_the_draft_scores_the_rules_only_arms_and_keeps_what_it_cannot_compute(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    # As the draft stood before its development scenarios were selected.
    analysis = analyse(world, truthful_runs, selection_pending(DRAFT))
    assert len(analysis.plan.arms) == 5 and len(analysis.pending_arms) == 10
    full, primary = analysis.sets
    assert (full.name, primary.name) == (ScenarioSetName.FULL, ScenarioSetName.PRIMARY)
    assert len(full.scenarios) == 30 and full.unavailable is None
    assert primary.unavailable is not None and "pending" in primary.unavailable
    assert (primary.scenarios, primary.arms, primary.descriptive) == ((), (), ())

    assert [arm.condition for arm in full.arms] == [
        "normal",
        "calendar_down",
        "corpus_down",
        "frappe_down",
        "jira_down",
    ]
    normal = arm_of(full, SystemKind.RULES_ONLY, "normal")
    assert normal.reporting is ReportingScope.ANSWER_QUALITY and normal.consistency == ()
    whole = normal.cells[0]
    assert whole.stratum.kind is StratumKind.OVERALL and whole.degraded is None
    assert whole.checks is not None and whole.measures is not None
    assert (whole.accounting.made, whole.accounting.graded) == (30, 30)
    assert (whole.attempts.attempts, whole.cost.attempts) == (30, 30)
    # Three checks in two readings, and every row of the twenty-five registered measures.
    assert [(e.check, e.reading.value, e.value) for e in whole.checks] == [
        (name, reading, 1.0)
        for name in ("correct_whole", "expected_action", "reproduced_whole")
        for reading in ("conditional", "end_to_end")
    ]
    assert len(whole.measures) == 58
    assert whole.measures[0].measure == "strict precision: all claims"
    assert whole.measures[0].value == 1.0
    by_name = {estimate.measure: estimate for estimate in whole.measures}
    # The evidence side reaches the tables: grounding over graded and limited runs apart,
    # a truthful report over a full read grounded whole, and no limited run to measure.
    grounded = by_name["claims grounded end to end: graded runs"]
    assert (grounded.value, grounded.scenarios) == (1.0, 30)
    assert by_name["claims grounded end to end: limited runs"].scenarios == 0
    # The fixture's truthful report cites nothing: a rate over no citation is not estimable,
    # which is a different statement from a rate of zero.
    resolving = by_name["citations that resolve: graded runs"]
    assert (resolving.value, resolving.denominator, resolving.empty) == (None, 0, 30)
    assert by_name["required sources answered"].value == 1.0
    assert "targets retrieved" in by_name and "conflict observations that hold" in by_name

    # A degraded-condition arm is described and never scored; here it never ran.
    hr_down = arm_of(full, SystemKind.RULES_ONLY, "frappe_down")
    assert hr_down.reporting is ReportingScope.DEGRADED_CONDITION
    described = hr_down.cells[0]
    assert (described.checks, described.measures, described.degraded) == (None, None, ())
    assert (described.accounting.made, described.accounting.missing) == (0, 30)

    # Nothing registered is dropped: both primaries are kept on the set they are registered
    # for and say why they have no result, and all nine descriptive rows say which arm
    # could not be built.
    assert full.primary == ()
    assert [p.registered.systems[1] for p in primary.primary] == [
        SystemKind.RULES_ONLY,
        SystemKind.SINGLE_SHOT,
    ]
    assert all(p.results == () and p.unavailable == primary.unavailable for p in primary.primary)
    assert len(full.descriptive) == 9
    assert all(row.unavailable and not row.checks and not row.measures for row in full.descriptive)
    assert "agent" in (full.descriptive[0].unavailable or "")

    # With the scenarios registered, as the draft is now, the primary set is cut and the
    # rules-only arms are scored on it; the primaries still wait for the agent's arm.
    registered = analyse(world, truthful_runs, DRAFT)
    _, held_out = registered.sets
    assert held_out.unavailable is None and len(held_out.scenarios) == 24
    scored = arm_of(held_out, SystemKind.RULES_ONLY, "normal").cells[0]
    assert (scored.accounting.scenarios, scored.accounting.made) == (24, 24)
    assert all(
        p.results == () and "agent" in (p.unavailable or "") for p in held_out.primary
    )


def test_an_arm_that_arrived_unregistered_is_described_and_never_scored(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    stranger = System(SystemKind.RULES_ONLY, "other")
    runs = [relabelled(run, system=stranger) for run in truthful_runs[:3]]
    analysis = analyse(world, runs, DRAFT)
    arm = next(a for a in analysis.sets[0].arms if a.system == stranger)
    assert arm.reporting is None
    assert arm.cells[0].checks is None and arm.cells[0].degraded is not None
    assert sum(row.runs for row in arm.cells[0].degraded) == 3


# --- With every system named -------------------------------------------------------------------


def test_the_primaries_are_over_the_held_out_scenarios_and_the_descriptive_over_both_sets(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    registration = named(world)
    development = set(development_selection(world, DRAFT))
    # The agent is right everywhere; rules-only misses the action on the first six scenarios.
    missed = {scenario.spec.id for scenario in world.scenarios[:6]}
    runs = [relabelled(run, system=AGENT) for run in truthful_runs]
    runs += [
        lacking_its_action(world, scenario) if scenario.spec.id in missed else run
        for scenario, run in zip(world.scenarios, truthful_runs, strict=True)
    ]
    analysis = analyse(world, runs, registration)
    assert analysis.pending_arms == ()
    full, primary = analysis.sets
    assert len(primary.scenarios) == 24 and not set(primary.scenarios) & development
    assert arm_of(primary, SystemKind.AGENT, "normal").cells[0].accounting.scenarios == 24

    # The primaries are registered on the primary set only.
    assert full.primary == ()
    against_rules, against_single_shot = primary.primary
    assert against_rules.unavailable is None and against_single_shot.unavailable is None
    (result,) = against_rules.results
    held_out_misses = len(missed - development)
    assert (result.check, result.reading) == ("correct_whole", Reading.END_TO_END)
    assert result.two_by_two == (24 - held_out_misses, held_out_misses, 0, 0)
    # The single-shot never ran: every run missing, not passed end to end, paired all the same.
    (unrun,) = against_single_shot.results
    assert unrun.two_by_two == (0, 24, 0, 0)

    for held, size in ((full, 30), (primary, 24)):
        assert len(held.descriptive) == 9
        row = next(
            r
            for r in held.descriptive
            if r.systems == (SystemKind.AGENT, SystemKind.RULES_ONLY) and r.condition == "normal"
        )
        assert row.unavailable is None
        # The whole and three tiers; three checks in two readings; and the four measures
        # registered for comparison, each on its leading row, never the twenty-five.
        assert (len(row.checks), len(row.measures)) == (4 * 3 * 2, 4 * 4)
        assert {comparison.measure for comparison in row.measures} == {
            "strict precision: all claims",
            "type-local precision: all claims",
            "recall: all claims",
            "payload accuracy: all claims",
        }
        overall = row.checks[0]
        assert overall.stratum.kind is StratumKind.OVERALL and overall.paired == size
        assert row.measures[0].measure == "strict precision: all claims"


# --- Repeat consistency ------------------------------------------------------------------------


def test_repeats_are_classified_per_scenario_only_where_every_repeat_can_be_compared(
    world: SealedWorld,
) -> None:
    always, sometimes, never, once, gapped = world.scenarios[:5]

    def run(scenario: Scenario, name: str, passes: bool, attempt: int = 1) -> Evaluation:
        made = evaluated(world, scenario) if passes else lacking_its_action(world, scenario)
        return relabelled(made, run_id=name, attempt=attempt)

    runs = [
        run(always, "run-a", True),
        run(always, "run-b", True),
        run(sometimes, "run-a", True),
        run(sometimes, "run-b", False),
        run(never, "run-a", False),
        run(never, "run-b", False),
        run(once, "run-a", True),
        run(gapped, "run-a", True),
        run(gapped, "run-b", True, attempt=2),
    ]
    two_runs = replace(preregistered(DRAFT).plan, intended_repeats=2)
    arm = next(a for a in arms(world, runs, two_runs) if a.assigned == NORMAL)
    found = repeat_consistency(cells_of(arm)[0], CORRECT_WHOLE, two_runs)
    assert found is not None and found.check == "correct_whole"
    assert (found.all_pass, found.disagree, found.all_fail) == (1, 1, 1)
    # One run short, one run unverifiable, and twenty-five scenarios never run.
    assert (found.scenarios, found.incomplete) == (30, 27)

    one_run = preregistered(DRAFT).plan
    arm = next(a for a in arms(world, runs[:1], one_run) if a.assigned == NORMAL)
    assert repeat_consistency(cells_of(arm)[0], CORRECT_WHOLE, one_run) is None

    # The analysis carries the diagnostic on the primary check of a scored arm.
    repeated = replace(DRAFT, run_accounting=replace(DRAFT.run_accounting, repeats=2))
    analysis = analyse(world, runs, repeated)
    normal = arm_of(analysis.sets[0], SystemKind.RULES_ONLY, "normal")
    assert normal.consistency == (found,)
    # A degraded-condition arm is not scored, so it carries no diagnostic.
    assert arm_of(analysis.sets[0], SystemKind.RULES_ONLY, "frappe_down").consistency == ()


# --- The degraded table ------------------------------------------------------------------------


def test_the_degraded_table_puts_each_counted_run_in_one_row(world: SealedWorld) -> None:
    abstained, unexercised, spoke, failed_one, failed_after = world.scenarios[:5]
    hr_down = (Source.FRAPPE,)

    def provider_failed(scenario: Scenario, *operations: Operation) -> Evaluation:
        """A provider fault under the same assignment, after ``operations``."""
        export = provider_failed_export(world, scenario)
        outage = replace(export.record.outage, scheduled_unreachable=frozenset(hr_down))
        export = replace(
            export,
            record=replace(export.record, outage=outage),
            trace=replace(export.trace, operations=operations),
        )
        return relabelled(evaluate_run(world, export), system=REFERENCE)

    runs = [
        # The outage met, and nothing reported: the abstention.
        evaluated(world, abstained, down=hr_down, claims=()),
        # The outage assigned and never met: every read answered, a truthful report.
        evaluated(world, unexercised, assigned=hr_down),
        # The outage met, and a report written all the same.
        evaluated(world, spoke, down=hr_down, claims=truthful(world, spoke, NORMAL)),
        # A provider fault before any read: no report, and the outage never met.
        provider_failed(failed_one),
        # A provider fault after a read met the outage: an exercised run that failed.
        provider_failed(failed_after, *reads(unreachable(Source.FRAPPE))),
    ]
    plan = preregistered(DRAFT).plan
    arm = next(a for a in arms(world, runs, plan) if a.assigned == NORMAL.without(*hr_down))
    table = degraded_table(cells_of(arm)[0])
    assert sum(row.runs for row in table) == 5
    assert set(table) == {
        DegradedRow(
            Exposure.EXERCISED,
            OutcomeKind.LIMITED,
            LimitedReason.UNREADABLE_LEAVE,
            ReportState.EMPTY,
            ReplayState.NOTHING_TO_REPLAY,
            1,
        ),
        DegradedRow(
            Exposure.UNEXERCISED,
            OutcomeKind.GRADED,
            None,
            ReportState.NON_EMPTY,
            ReplayState.REPRODUCED,
            1,
        ),
        DegradedRow(
            Exposure.EXERCISED,
            OutcomeKind.LIMITED,
            LimitedReason.UNREADABLE_LEAVE,
            ReportState.NON_EMPTY,
            ReplayState.UNSUPPORTED,
            1,
        ),
        DegradedRow(
            Exposure.UNEXERCISED,
            OutcomeKind.EXCLUDED,
            ExcludedReason.FAILED_BY_INFRASTRUCTURE,
            ReportState.NONE,
            ReplayState.NOTHING_TO_REPLAY,
            1,
        ),
        DegradedRow(
            Exposure.EXERCISED,
            OutcomeKind.EXCLUDED,
            ExcludedReason.FAILED_BY_INFRASTRUCTURE,
            ReportState.NONE,
            ReplayState.NOTHING_TO_REPLAY,
            1,
        ),
    }
