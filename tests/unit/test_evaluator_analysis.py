"""The registered analysis. Under the draft it scores the rules-only arm of each
answer-quality cell at its level, describes the degraded-condition arms, and keeps every
comparison that needs a system still pending, saying which cell could not be built and what
the registration holds pending for it. With the agent and full context named it computes
the one primary at the padded level with its tier breakdowns, the descriptive pairs at each
named place and the level contrasts, a pair whose cell sits in a group that is not run kept
with that reason. The headroom is two counts per place and names no scenario. A scenario
on which one run met a contradiction is an incident for every arm, counted on each
comparison that paired it, and no run leaves a table for it. Repeated runs are classified
per scenario only where every repeat can be compared. The degraded table puts each counted
run in one row, a failed attempt never an empty report."""

from collections.abc import Container
from dataclasses import fields, replace

import pytest

from leaveimpact.core import (
    CheckReading,
    Comparison,
    CoverageAction,
    Operation,
    Registration,
    ReportingScope,
    Source,
    StratumLevel,
    System,
    SystemKind,
    employee_ref,
)
from leaveimpact.core.contradictions import Contradiction, ContradictionKind
from leaveimpact.core.run_trace import OperationId
from leaveimpact.evaluator.analysis import Analysis, ArmAnalysis, analyse
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
from leaveimpact.evaluator.headroom import Headroom
from leaveimpact.evaluator.incidents import RunRef, Shape
from leaveimpact.evaluator.intervals import Unresolved
from leaveimpact.evaluator.registered import preregistered
from leaveimpact.evaluator.run_checks import CORRECT_WHOLE
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.tables import Reading
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from leaveimpact.world import Scenario
from leaveimpact.world.scenario import Tier
from tests.unit.evaluation_fixture import (
    BASE,
    NORMAL,
    PADDED,
    REFERENCE,
    evaluated,
    relabelled,
    truthful,
)
from tests.unit.export_fixture import provider_failed_export, reads, unreachable
from tests.unit.registration_fixture import DRAFT as COMMITTED
from tests.unit.registration_fixture import decided, light, named
from tests.unit.report_fixture import of_type, without
from tests.unit.throwaway_world import loaded_world

DRAFT = light(COMMITTED)
AGENT = System(SystemKind.AGENT, "graph")
FULL_CONTEXT = System(SystemKind.FULL_CONTEXT, "all-documents")
GROUP = "full_context_under_outage"


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def truthful_runs(world: SealedWorld) -> list[Evaluation]:
    return [evaluated(world, scenario) for scenario in world.scenarios]


def systems_named(run_group: bool = True) -> Registration:
    """The draft with the agent and full context named and the conditional group decided."""
    return decided(named(DRAFT, agent=AGENT.variant, full_context=FULL_CONTEXT.variant), run_group)


def arm_of(held: Analysis, kind: SystemKind, condition: str, level: str = BASE) -> ArmAnalysis:
    return next(
        a for a in held.arms if (a.system.kind, a.condition, a.level) == (kind, condition, level)
    )


def lacking_its_action(world: SealedWorld, scenario: Scenario) -> Evaluation:
    report = truthful(world, scenario, NORMAL)
    return evaluated(world, scenario, claims=without(report, of_type(report, CoverageAction)[0]))


def missing_on(
    world: SealedWorld, truthful_runs: list[Evaluation], missed: Container[str]
) -> list[Evaluation]:
    """A reference run per scenario, lacking its action on the scenarios in ``missed``."""
    return [
        lacking_its_action(world, scenario) if scenario.spec.id in missed else run
        for scenario, run in zip(world.scenarios, truthful_runs, strict=True)
    ]


# --- Under the draft ---------------------------------------------------------------------------


def test_the_draft_scores_the_rules_only_arms_and_keeps_what_it_cannot_compute(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    analysis = analyse(world, truthful_runs, DRAFT)
    assert len(analysis.plan.arms) == 6 and len(analysis.unbuilt) == 18
    assert len(analysis.scenarios) == 30
    assert [(arm.condition, arm.level) for arm in analysis.arms] == [
        ("normal", "base"),
        ("normal", "padded"),
        ("calendar_down", "base"),
        ("corpus_down", "base"),
        ("frappe_down", "base"),
        ("jira_down", "base"),
    ]
    normal = arm_of(analysis, SystemKind.RULES_ONLY, "normal")
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
    assert whole.measures[0].arm == "rules_only/reference normal at base"
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

    # The same system at the padded level is its own arm, scored, and here it never ran:
    # the runs were made at the base level and one export is one cell's.
    padded = arm_of(analysis, SystemKind.RULES_ONLY, "normal", PADDED)
    assert padded.reporting is ReportingScope.ANSWER_QUALITY
    assert (padded.cells[0].accounting.made, padded.cells[0].accounting.missing) == (0, 30)

    # A degraded-condition arm is described and never scored; here it never ran.
    hr_down = arm_of(analysis, SystemKind.RULES_ONLY, "frappe_down")
    assert hr_down.reporting is ReportingScope.DEGRADED_CONDITION
    described = hr_down.cells[0]
    assert (described.checks, described.measures, described.degraded) == (None, None, ())
    assert (described.accounting.made, described.accounting.missing) == (0, 30)

    # Nothing registered is dropped: the primary, both secondaries, every descriptive pair
    # at every place and each level contrast are kept and say which arm could not be built
    # and what the registration holds pending for it.
    primary = analysis.primary
    assert primary.registered == DRAFT.statistics.primary
    assert (primary.overall, primary.breakdowns) == (None, ())
    assert primary.unavailable is not None
    assert "agent under normal at padded (system_pending: systems.agent.variant" in (
        primary.unavailable
    )
    assert " and full_context under normal at padded (system_pending: " in primary.unavailable
    assert len(analysis.secondary) == 2
    assert all(
        each.overall is None and "single_shot" in (each.unavailable or "")
        for each in analysis.secondary
    )
    assert len(analysis.descriptive) == 4 * 6
    assert all(
        row.unavailable and not row.checks and not row.measures for row in analysis.descriptive
    )
    # Only the arm that is missing is named: rules only is built.
    against_rules = next(
        row
        for row in analysis.descriptive
        if row.systems == (SystemKind.AGENT, SystemKind.RULES_ONLY) and row.condition == "normal"
    )
    assert "rules_only" not in (against_rules.unavailable or "")
    assert [c.registered.system for c in analysis.level_contrasts] == [
        SystemKind.AGENT,
        SystemKind.SINGLE_SHOT,
        SystemKind.FULL_CONTEXT,
    ]
    assert all(c.overall is None and c.unavailable for c in analysis.level_contrasts)
    assert analysis.mechanism_pending == (
        "resolved when the evaluator's fact-stage measures are built"
    )
    assert analysis.incidents == ()


def test_an_arm_that_arrived_unregistered_is_described_and_never_scored(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    stranger = System(SystemKind.RULES_ONLY, "other")
    runs = [relabelled(run, system=stranger) for run in truthful_runs[:3]]
    # A registered system at a level nobody registered is no registered arm either.
    runs += [relabelled(run, level="doubled") for run in truthful_runs[:2]]
    analysis = analyse(world, runs, DRAFT)
    for arm, made in (
        (next(a for a in analysis.arms if a.system == stranger), 3),
        (next(a for a in analysis.arms if a.level == "doubled"), 2),
    ):
        assert arm.reporting is None
        assert arm.cells[0].checks is None and arm.cells[0].degraded is not None
        assert sum(row.runs for row in arm.cells[0].degraded) == made


# --- With the agent and full context named ------------------------------------------------------


def test_the_primary_is_at_the_padded_level_with_its_breakdowns_and_the_rest_beside_it(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    registration = systems_named()
    # The agent is right at both levels. Full context is right at the base level and
    # misses the action on the first six scenarios once the corpus is padded.
    missed = {scenario.spec.id for scenario in world.scenarios[:6]}
    runs = [
        relabelled(run, system=AGENT, level=level)
        for run in truthful_runs
        for level in (BASE, PADDED)
    ]
    runs += [relabelled(run, system=FULL_CONTEXT) for run in truthful_runs]
    runs += [
        relabelled(run, system=FULL_CONTEXT, level=PADDED)
        for run in missing_on(world, truthful_runs, missed)
    ]
    analysis = analyse(world, runs, registration)
    # Eighteen arms: the group is decided as run. Single-shot's six cells stay unbuilt.
    assert len(analysis.plan.arms) == 18
    assert {left.cell.system for left in analysis.unbuilt} == {SystemKind.SINGLE_SHOT}
    assert arm_of(analysis, SystemKind.AGENT, "normal", PADDED).cells[0].accounting.made == 30

    primary = analysis.primary
    assert primary.unavailable is None and primary.overall is not None
    overall = primary.overall
    assert (overall.check, overall.reading) == ("correct_whole", Reading.END_TO_END)
    assert (overall.first_arm, overall.second_arm) == (
        "agent/graph normal at padded",
        "full_context/all-documents normal at padded",
    )
    assert (overall.paired, overall.two_by_two) == (30, (24, 6, 0, 0))
    assert overall.interval is not None and overall.interval.low > 0
    # The tier contrasts named in advance, beside the claim and never in its place.
    assert [each.stratum.name for each in primary.breakdowns] == [tier.value for tier in Tier]
    assert sum(each.two_by_two[1] for each in primary.breakdowns if each.two_by_two) == 6

    # The agent against single-shot is registered and kept; this format cannot resolve the
    # single-shot system, and the reason names what it waits on.
    assert all(
        s.overall is None and "systems.single_shot.query_protocol" in (s.unavailable or "")
        for s in analysis.secondary
    )

    # Padded less base, one system against itself: full context loses six, the agent none,
    # and a contrast that is the same in every scenario resolves no interval.
    by_system = {c.registered.system: c for c in analysis.level_contrasts}
    lost = by_system[SystemKind.FULL_CONTEXT].overall
    assert lost is not None and lost.two_by_two == (24, 0, 6, 0)
    assert (lost.first_arm, lost.second_arm) == (
        "full_context/all-documents normal at padded",
        "full_context/all-documents normal at base",
    )
    assert lost.interval is not None and lost.interval.high < 0
    assert len(by_system[SystemKind.FULL_CONTEXT].breakdowns) == 3
    steady = by_system[SystemKind.AGENT].overall
    assert steady is not None and steady.two_by_two == (30, 0, 0, 0)
    assert steady.unresolved is Unresolved.EVERY_RESAMPLE_EQUAL
    assert by_system[SystemKind.SINGLE_SHOT].unavailable is not None

    # Every pair at every place: four places, six pairs.
    assert len(analysis.descriptive) == 24
    row = next(
        r
        for r in analysis.descriptive
        if r.systems == (SystemKind.AGENT, SystemKind.FULL_CONTEXT)
        and (r.condition, r.level) == ("normal", PADDED)
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
    assert row.checks[0].stratum.kind is StratumKind.OVERALL and row.checks[0].paired == 30
    assert row.measures[0].measure == "strict precision: all claims"
    # A place is one level: the same pair at the base level is another row, with no loss.
    at_base = next(
        r
        for r in analysis.descriptive
        if r.systems == row.systems and (r.condition, r.level) == ("normal", BASE)
    )
    assert at_base.checks[0].two_by_two == (30, 0, 0, 0)
    under_outage = [
        r
        for r in analysis.descriptive
        if SystemKind.FULL_CONTEXT in r.systems and r.condition == "jira_down"
    ]
    assert under_outage and all(
        r.unavailable is None or "single_shot" in r.unavailable for r in under_outage
    )


def test_a_pair_whose_cell_is_in_a_group_that_is_not_run_is_kept_and_says_so(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    for registration in (systems_named(run_group=False), named(DRAFT, agent=AGENT.variant)):
        analysis = analyse(world, truthful_runs, registration)
        assert len(analysis.plan.arms) == 14
        row = next(
            r
            for r in analysis.descriptive
            if r.systems == (SystemKind.AGENT, SystemKind.FULL_CONTEXT)
            and r.condition == "jira_down"
        )
        assert row.unavailable == (
            "no arm could be built for full_context under jira_down at base "
            f"(group_not_run: {GROUP})"
        )
        # Under the normal condition full context is in no group, and the pair is compared.
        normal = next(
            r
            for r in analysis.descriptive
            if r.systems == row.systems and (r.condition, r.level) == ("normal", BASE)
        )
        assert normal.unavailable is None


def test_a_secondary_between_two_built_systems_is_computed_like_the_primary(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    registration = systems_named()
    against_rules = Comparison(
        "correct_whole",
        CheckReading.END_TO_END,
        "normal",
        BASE,
        (SystemKind.AGENT, SystemKind.RULES_ONLY),
        (StratumLevel.TIER,),
    )
    registration = replace(
        registration, statistics=replace(registration.statistics, secondary=(against_rules,))
    )
    missed = {scenario.spec.id for scenario in world.scenarios[:6]}
    runs = [relabelled(run, system=AGENT) for run in truthful_runs]
    runs += missing_on(world, truthful_runs, missed)
    (secondary,) = analyse(world, runs, registration).secondary
    assert secondary.registered == against_rules and secondary.unavailable is None
    assert secondary.overall is not None and secondary.overall.two_by_two == (24, 6, 0, 0)
    assert len(secondary.breakdowns) == 3


# --- The headroom ------------------------------------------------------------------------------


def test_the_headroom_is_two_counts_per_place_and_names_no_scenario(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    missed = {scenario.spec.id for scenario in world.scenarios[:6]}
    runs = missing_on(world, truthful_runs, missed)
    # At the padded level the reference ran on five scenarios, right on each: the
    # twenty-five it never ran did not pass end to end, and are headroom.
    runs += [relabelled(run, level=PADDED) for run in truthful_runs[:5]]
    analysis = analyse(world, runs, DRAFT)
    # One row per place the reference has a cell under an answer-quality condition.
    unrun = "the reference's arm has no counted run"
    assert analysis.headroom == (
        Headroom("normal", BASE, 30, 6, None),
        Headroom("normal", PADDED, 30, 25, None),
        Headroom("jira_down", BASE, None, None, unrun),
        Headroom("calendar_down", BASE, None, None, unrun),
    )
    assert [field.name for field in fields(Headroom)] == [
        "condition",
        "level",
        "scenarios",
        "not_passed",
        "unavailable",
    ]
    # It enters no estimate and selects nothing: every arm holds every scenario still.
    assert all(arm.cells[0].accounting.scenarios == 30 for arm in analysis.arms)


def test_a_reference_that_passes_some_repeats_has_not_passed_the_scenario(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    repeated = replace(DRAFT, run_accounting=replace(DRAFT.run_accounting, repeats=2))
    first = world.scenarios[0]
    runs = [relabelled(run, run_id="run-a") for run in truthful_runs]
    runs += [
        relabelled(
            lacking_its_action(world, scenario) if scenario is first else run, run_id="run-b"
        )
        for scenario, run in zip(world.scenarios, truthful_runs, strict=True)
    ]
    headroom = analyse(world, runs, repeated).headroom[0]
    assert (headroom.scenarios, headroom.not_passed) == (30, 1)


# --- Incidents ---------------------------------------------------------------------------------


def test_a_contradiction_one_run_met_is_an_incident_for_every_arm_and_excludes_nothing(
    world: SealedWorld, truthful_runs: list[Evaluation]
) -> None:
    registration = systems_named()
    struck = world.scenarios[3]
    contradiction = Contradiction(
        ContradictionKind.RETURNS_DIFFER,
        employee_ref(struck.investigated_leave.employee_id),
        OperationId("op-2"),
        OperationId("op-9"),
        OperationId("op-9"),
    )
    runs = [relabelled(run, system=FULL_CONTEXT, level=PADDED) for run in truthful_runs]
    # The agent reads more, and is the one that met it.
    runs += [
        replace(agent, contradictions=(contradiction,))
        if agent.outcome.header.scenario_id == struck.spec.id
        else agent
        for agent in (relabelled(run, system=AGENT, level=PADDED) for run in truthful_runs)
    ]
    analysis = analyse(world, runs, registration)
    (incident,) = analysis.incidents
    assert incident.scenario_id == struck.spec.id
    assert incident.shapes == (Shape(Source.FRAPPE, ContradictionKind.RETURNS_DIFFER),)
    # Every arm is listed, and each says which of its runs met it and which did not: an
    # incident at a scenario is no statement that every arm observed it.
    assert len(incident.arms) == len(analysis.arms) == 18
    by_arm = {held.arm: held for held in incident.arms}
    header = truthful_runs[3].outcome.header
    the_run = RunRef(header.run_id, header.attempt)
    met = by_arm["agent/graph normal at padded"]
    assert (met.met, met.not_met, met.counted) == ((the_run,), (), 1)
    spared = by_arm["full_context/all-documents normal at padded"]
    assert (spared.met, spared.not_met, spared.counted) == ((), (the_run,), 1)
    silent = by_arm["rules_only/reference normal at base"]
    assert (silent.met, silent.not_met, silent.counted) == ((), (), 0)

    # No run and no scenario leaves a table; each comparison says how many of the
    # scenarios it paired carry the incident.
    agent = arm_of(analysis, SystemKind.AGENT, "normal", PADDED).cells[0]
    assert (agent.accounting.made, agent.accounting.graded) == (30, 30)
    primary = analysis.primary
    assert primary.overall is not None
    assert (primary.overall.paired, primary.overall.paired_with_incident) == (30, 1)
    assert [each.paired_with_incident for each in primary.breakdowns] == [
        int(struck.key.tier is tier) for tier in Tier
    ]
    row = next(
        r
        for r in analysis.descriptive
        if r.systems == (SystemKind.AGENT, SystemKind.FULL_CONTEXT)
        and (r.condition, r.level) == ("normal", PADDED)
    )
    assert row.measures[0].paired_with_incident == 1
    assert analyse(world, [], registration).incidents == ()


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
    arm = next(a for a in arms(world, runs, two_runs) if (a.assigned, a.level) == (NORMAL, BASE))
    found = repeat_consistency(cells_of(arm)[0], CORRECT_WHOLE, two_runs)
    assert found is not None and found.check == "correct_whole"
    assert (found.all_pass, found.disagree, found.all_fail) == (1, 1, 1)
    # One run short, one run unverifiable, and twenty-five scenarios never run.
    assert (found.scenarios, found.incomplete) == (30, 27)

    one_run = preregistered(DRAFT).plan
    arm = next(a for a in arms(world, runs[:1], one_run) if (a.assigned, a.level) == (NORMAL, BASE))
    assert repeat_consistency(cells_of(arm)[0], CORRECT_WHOLE, one_run) is None

    # The analysis carries the diagnostic on the primary check of a scored arm.
    repeated = replace(DRAFT, run_accounting=replace(DRAFT.run_accounting, repeats=2))
    analysis = analyse(world, runs, repeated)
    normal = arm_of(analysis, SystemKind.RULES_ONLY, "normal")
    assert normal.consistency == (found,)
    # A degraded-condition arm is not scored, so it carries no diagnostic.
    assert arm_of(analysis, SystemKind.RULES_ONLY, "frappe_down").consistency == ()


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
