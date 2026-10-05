"""What a record states of its own ending is held to its export: the segments and whether
every one's end was recorded, an active time the wall clock cannot hold, segments on more
than one commit, and an approval digest that is not the exported payload's. The real
baseline's exports, the truthful stater's and the twelve format 2 cases carry no finding,
and the cases show which timings are incomplete. A run with a finding is counted and stays;
a cell's ledger says how many of its durations are lower bounds, with the segments beside."""

from dataclasses import replace
from datetime import date, timedelta

import pytest

from leaveimpact.agent.registered import rules_only_provenance
from leaveimpact.agent.rules_only import investigate
from leaveimpact.core import (
    HarnessRevision,
    PricingBasis,
    RunCondition,
    RunExport,
    Segment,
    Source,
    TreeState,
    condition_id,
)
from leaveimpact.evaluator.cells import accounting_of, arms, attempt_summary_of, cells_of
from leaveimpact.evaluator.ending_check import EndingCheck, EndingFinding, check_ending
from leaveimpact.evaluator.registered import preregistered
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.tables import Spread, cost_ledger
from leaveimpact.evaluator.trace_metrics import evaluate_run
from leaveimpact.world import Scenario
from tests.unit.evaluation_fixture import truthful
from tests.unit.export_fixture import ADMITTED, COMMIT, DIGEST, export_baseline, run_export
from tests.unit.format2_fixtures import (
    FIXTURES,
    approval_wait_across_restart,
    recovered_attempt,
)
from tests.unit.reads_fixture import reads_of_everything, systems_holding
from tests.unit.registration_fixture import DRAFT, light
from tests.unit.stating_fixture import truthful_stater_runs
from tests.unit.throwaway_world import loaded_world

NORMAL = RunCondition.all_reachable()
ANOTHER_COMMIT = "e" * 40


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def baseline(world: SealedWorld, scenario: Scenario, *down: Source) -> RunExport:
    """The real baseline's export of ``scenario`` under the draft, ``down`` unreachable."""
    systems = systems_holding(world)
    for port in (systems.people, systems.work, systems.calendar, systems.documents):
        port.reachable = port.source not in down
    context = world.context_of(scenario)
    provenance = rules_only_provenance(
        DRAFT,
        condition_id(down),
        "base",
        harness=HarnessRevision(COMMIT, TreeState.CLEAN),
        preregistration_commit=COMMIT,
        pricing=PricingBasis(DIGEST, "USD", date(2026, 9, 1), ()),
    )
    return export_baseline(
        investigate(context, systems.ports), context, provenance, run_id="run-1", attempt=1
    )


def retimed(export: RunExport, **changes: object) -> RunExport:
    """``export`` with its record's timing changed."""
    timing = replace(export.record.timing, **changes)
    return replace(export, record=replace(export.record, timing=timing))


# --- The producers there are -----------------------------------------------------------------


@pytest.mark.parametrize("down", [(), (Source.JIRA,), (Source.CALENDAR,)], ids=str)
def test_the_real_baselines_approval_is_over_the_payload_it_exports(
    world: SealedWorld, down: tuple[Source, ...]
) -> None:
    # The run path's approval and the exporter's one recorded segment are the real ones.
    # The instants and the duration are this fixture's, no composition root reading a
    # clock yet, so the elapsed time here shows the arithmetic and no harness's timing.
    for scenario in world.scenarios:
        ending = check_ending(baseline(world, scenario, *down))
        assert ending == EndingCheck(1, True, 1_200, (COMMIT,), ()), scenario.spec.id


def test_the_truthful_staters_approval_is_over_the_payload_it_exports() -> None:
    for run in truthful_stater_runs():
        assert run.metrics.ending.findings == ()


def test_the_format_2_cases_carry_no_finding_and_five_have_an_unknown_tail() -> None:
    endings = {name: check_ending(build()) for name, build in FIXTURES.items()}
    assert all(ending.findings == () for ending in endings.values())
    assert {
        name: ending.segments for name, ending in endings.items() if not ending.timing_complete
    } == {
        "an unresolved dispatch followed by an answered one": 2,
        "a recovered attempt": 2,
        "an abandoned attempt": 1,
        "an approval wait across a restart": 3,
        "a tool call whose result was lost before it was logged": 1,
    }
    assert sum(ending.segments == 1 for ending in endings.values()) == 10


# --- Each finding ----------------------------------------------------------------------------


def test_an_active_time_the_wall_clock_cannot_hold_is_a_finding_and_a_wait_is_not_active() -> None:
    # Three segments whose last offsets sum to 10,550 ms, 1,550 of them inside the approval
    # wait: 9,000 ms of evidenced execution.
    waited = approval_wait_across_restart()
    assert check_ending(waited).elapsed_ms == 2 * 60 * 60 * 1_000
    fits = retimed(waited, terminal_at=ADMITTED + timedelta(milliseconds=9_500))
    assert check_ending(fits).findings == ()
    short = retimed(waited, terminal_at=ADMITTED + timedelta(milliseconds=8_999))
    assert check_ending(short).findings == (EndingFinding.ACTIVE_EXCEEDS_ELAPSED,)


def test_segments_on_two_commits_are_a_finding_and_a_tree_state_alone_is_not() -> None:
    recovered = recovered_attempt()
    first, second = recovered.record.timing.segments
    elsewhere = replace(second, harness=HarnessRevision(ANOTHER_COMMIT, TreeState.CLEAN))
    mixed = check_ending(retimed(recovered, segments=(first, elsewhere)))
    assert mixed.findings == (EndingFinding.COMMITS_DIFFER,)
    # Each commit once, in the order the segments first ran on them.
    assert mixed.commits == (first.harness.commit, ANOTHER_COMMIT)
    back = replace(first, number=3, end_recorded=True)
    thrice = check_ending(retimed(recovered, segments=(first, elsewhere, back)))
    assert thrice.commits == (first.harness.commit, ANOTHER_COMMIT)
    # One commit, the second process from uncommitted changes over it: the tree's state is
    # read where eligibility is decided, and the commits agree.
    dirty = replace(second, harness=HarnessRevision(first.harness.commit, TreeState.DIRTY))
    assert check_ending(retimed(recovered, segments=(first, dirty))).findings == ()


def test_an_approval_over_another_payload_than_the_exported_one_is_a_finding(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    report = truthful(world, scenario, NORMAL)
    assert len(report) > 1
    export = run_export(world, scenario, report, operations=reads_of_everything(world, scenario))
    assert check_ending(export).findings == ()
    # The approval was asked over the whole report and the export holds one claim fewer.
    fewer = replace(export, trace=replace(export.trace, claims=export.trace.claims[1:]))
    assert check_ending(fewer).findings == (EndingFinding.APPROVAL_DIGEST_DIFFERS,)
    # An attempt that requested no approval holds no digest to compare.
    unasked = FIXTURES["a multi-tool answer whose first call ends the attempt"]()
    assert unasked.record.approval.payload_digest is None
    assert check_ending(unasked).findings == ()


# --- Counted, and marked in the ledger ---------------------------------------------------------


def test_a_run_with_an_ending_finding_is_counted_and_stays(world: SealedWorld) -> None:
    plan = preregistered(light(DRAFT)).plan
    one, two = world.scenarios[:2]
    disputed = baseline(world, two)
    disputed = replace(disputed, trace=replace(disputed.trace, claims=disputed.trace.claims[1:]))
    runs = [evaluate_run(world, baseline(world, one)), evaluate_run(world, disputed)]
    (arm,) = (
        held
        for held in arms(world, runs, plan)
        if held.registered and held.level == "base" and held.assigned == NORMAL
    )
    whole = cells_of(arm)[0]
    accounting = accounting_of(whole, plan)
    assert (accounting.made, accounting.with_ending_findings) == (2, 1)
    assert attempt_summary_of(whole).with_ending_findings == 1


def test_a_ledger_says_which_durations_are_lower_bounds_with_the_segments_beside(
    world: SealedWorld,
) -> None:
    plan = preregistered(light(DRAFT)).plan
    one, two = world.scenarios[:2]
    whole = baseline(world, one)
    # The same run recovered: a first process killed at 300 ms, its end never recorded, and
    # a second that ran the 1,200 ms to the terminal event, two seconds after admission.
    recovered = baseline(world, two)
    (only,) = recovered.record.timing.segments
    killed = Segment(1, only.harness, 300, False)
    recovered = retimed(
        recovered,
        segments=(killed, replace(only, number=2)),
        terminal_at=ADMITTED + timedelta(seconds=2),
    )
    assert check_ending(recovered).findings == ()
    runs = [evaluate_run(world, whole), evaluate_run(world, recovered)]
    (arm,) = (
        held
        for held in arms(world, runs, plan)
        if held.registered and held.level == "base" and held.assigned == NORMAL
    )
    ledger = cost_ledger(cells_of(arm)[0])
    assert (ledger.runs, ledger.lower_bound_durations) == (2, 1)
    assert ledger.segments == Spread(1.5, 1, 2)
    assert ledger.duration_ms == Spread(1_350.0, 1_200, 1_500)
    (empty,) = (
        held
        for held in arms(world, [], plan)
        if held.registered and held.level == "base" and held.assigned == NORMAL
    )
    nothing = cost_ledger(cells_of(empty)[0])
    assert (nothing.lower_bound_durations, nothing.segments) == (0, None)
