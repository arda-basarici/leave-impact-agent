"""Incidents. A run whose own reads contradict each other carries the contradiction on its
evaluation, recomputed from the trace whatever the run then did. The incident is by
scenario: its shapes once each, and every arm with the attempts that met it, the ones that
did not, and its counted runs there. An attempt a retry replaced and one no scenario of the
world could place are read like any other, and so is an export that is out of the tables,
named by its key; with no contradiction there is no incident. An attempt that ran on
more than one harness commit is a provenance incident of its own kind: listed once per
attempt with its commits, in or out of the tables, and no scenario's flag."""

from dataclasses import replace

import pytest

from leaveimpact.core import RunCondition, Source, System, SystemKind, employee_ref, leave_ref
from leaveimpact.core.contradictions import Contradiction, ContradictionKind
from leaveimpact.core.ids import ScenarioId, employee_id
from leaveimpact.core.run_trace import OperationId
from leaveimpact.evaluator.attempts import CountedAttempt
from leaveimpact.evaluator.cells import MissingRepeat, Preregistered, arms
from leaveimpact.evaluator.grading import Excluded, ExcludedReason, Graded
from leaveimpact.evaluator.incidents import (
    Incident,
    IncidentArm,
    ProvenanceIncident,
    RunRef,
    Shape,
    incident_scenarios,
    incidents_of,
    provenance_incidents_of,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import Evaluation
from tests.unit.evaluation_fixture import BASE, NORMAL, REFERENCE, evaluated, relabelled
from tests.unit.reads_fixture import Recorder, fakes_holding, full_read
from tests.unit.throwaway_world import loaded_world

OTHER = System(SystemKind.AGENT, "graph")
DIFFER = ContradictionKind.RETURNS_DIFFER


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def plan(*registered: tuple[System, RunCondition, str]) -> Preregistered:
    held = registered or ((REFERENCE, NORMAL, BASE),)
    return Preregistered(
        0.95, 7, 1_000, 1, CountedAttempt.EARLIEST_NOT_INFRASTRUCTURE, MissingRepeat.NOT_PASSED,
        held, 3,
    )  # fmt: skip


def contradicting(evaluation: Evaluation, kind: ContradictionKind = DIFFER) -> Evaluation:
    """``evaluation`` as a run whose reads disagreed about an employee."""
    found = Contradiction(
        kind, employee_ref(employee_id(1)), OperationId("op-1"), OperationId("op-2"),
        OperationId("op-2"),
    )  # fmt: skip
    return replace(evaluation, contradictions=(*evaluation.contradictions, found))


def on_commits(evaluation: Evaluation, *commits: str) -> Evaluation:
    """``evaluation`` as an attempt whose segments ran on ``commits``."""
    ending = replace(evaluation.metrics.ending, commits=commits)
    return replace(evaluation, metrics=replace(evaluation.metrics, ending=ending))


def test_an_attempt_on_two_commits_is_a_provenance_incident_in_or_out_of_the_tables(
    world: SealedWorld,
) -> None:
    first, second = world.scenarios[:2]
    old, new = "c" * 40, "d" * 40
    retried = relabelled(on_commits(evaluated(world, first), old, new), run_id="run-a")
    retried = replace(
        retried, outcome=replace(retried.outcome, header=replace(retried.outcome.header, attempt=2))
    )
    runs = [
        relabelled(evaluated(world, first), run_id="run-a"),
        retried,
        relabelled(evaluated(world, second), run_id="run-b"),
    ]
    (arm,) = arms(world, runs, plan())
    outside = [
        ("runs/z", relabelled(on_commits(evaluated(world, first), new, old), run_id="run-z")),
        ("runs/y", relabelled(evaluated(world, second), run_id="run-y")),
    ]
    assert provenance_incidents_of([arm]) == (
        ProvenanceIncident(first.spec.id, "run-a", 2, None, (old, new)),
    )
    assert provenance_incidents_of([arm], outside) == (
        ProvenanceIncident(first.spec.id, "run-a", 2, None, (old, new)),
        ProvenanceIncident(first.spec.id, "run-z", 1, "runs/z", (new, old)),
    )
    # Another kind than a source contradicting itself: no scenario carries a flag for it.
    assert incidents_of([arm], outside) == ()
    (clean,) = arms(world, [evaluated(world, first)], plan())
    assert provenance_incidents_of([clean]) == ()


def test_a_run_whose_reads_contradict_each_other_carries_it_on_its_evaluation(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    assert evaluated(world, scenario).contradictions == ()
    # The same full read, then the leaver's record returned a second time with another
    # location: the trace holds two reads of one record that cannot both be true.
    systems = fakes_holding(world)
    reads = Recorder(systems)
    full_read(reads, world, scenario)
    leaver = scenario.investigated_leave.employee_id
    systems.people.people[leaver] = replace(systems.people.people[leaver], location="Elsewhere")
    reads.read("employee", {"id": leaver})
    run = evaluated(world, scenario, operations=reads.operations)
    assert run.contradictions
    assert {(found.kind, found.record) for found in run.contradictions} == {
        (DIFFER, employee_ref(leaver))
    }
    # Recomputed from the trace, not read off a failure: this run did not fail.
    assert isinstance(run.outcome, Graded)
    (arm,) = arms(world, [run], plan())
    (incident,) = incidents_of([arm])
    assert incident.scenario_id == scenario.spec.id
    assert incident.shapes == (Shape(Source.FRAPPE, DIFFER),)


def test_an_incident_lists_every_arm_with_the_attempts_that_met_it_and_those_that_did_not(
    world: SealedWorld,
) -> None:
    first, second = world.scenarios[:2]
    good = evaluated(world, first)
    failed = replace(
        contradicting(good),
        outcome=Excluded(good.outcome.header, ExcludedReason.FAILED_BY_DEFECT),
    )
    runs = [
        # The reference's run met it and failed there; nothing replaced the attempt.
        relabelled(failed, run_id="run-a"),
        # The other system ran the scenario twice: one run met it on its first attempt,
        # failed by infrastructure and was retried clean; the other never met it.
        relabelled(
            replace(
                contradicting(good, ContradictionKind.RETURNED_AND_ABSENT),
                outcome=Excluded(good.outcome.header, ExcludedReason.FAILED_BY_INFRASTRUCTURE),
            ),
            run_id="run-b",
            attempt=1,
            system=OTHER,
        ),
        relabelled(good, run_id="run-b", attempt=2, system=OTHER),
        relabelled(good, run_id="run-c", system=OTHER),
        # Another scenario, untouched.
        evaluated(world, second),
    ]
    both = plan((OTHER, NORMAL, BASE), (REFERENCE, NORMAL, BASE))
    built = arms(world, runs, both)
    (incident,) = incidents_of(built)
    assert incident == Incident(
        first.spec.id,
        (
            Shape(Source.FRAPPE, ContradictionKind.RETURNED_AND_ABSENT),
            Shape(Source.FRAPPE, DIFFER),
        ),
        (
            # Every attempt is read, the one a retry replaced included; the counted runs
            # are the ones the arm's estimates rest on at this scenario.
            IncidentArm(
                "agent/graph normal at base",
                (RunRef("run-b", 1),),
                (RunRef("run-b", 2), RunRef("run-c", 1)),
                2,
            ),
            IncidentArm("rules_only/reference normal at base", (RunRef("run-a", 1),), (), 1),
        ),
        (),
    )
    assert incident_scenarios([incident]) == {first.spec.id}
    assert incidents_of(arms(world, runs[2:], both)) == ()


def test_a_shape_is_listed_once_and_an_unplaced_attempt_is_read_like_any_other(
    world: SealedWorld,
) -> None:
    first = world.scenarios[0]
    good = evaluated(world, first)
    twice = contradicting(contradicting(good))
    on_a_leave = replace(
        good,
        contradictions=(
            Contradiction(
                ContradictionKind.OMITTED_BY_WINDOW,
                leave_ref(first.investigated_leave.id),
                OperationId("op-3"),
                OperationId("op-4"),
                OperationId("op-4"),
            ),  # fmt: skip
        ),
    )
    stray_header = replace(good.outcome.header, scenario_id=ScenarioId("scn_999"), run_id="run-x")
    stray = contradicting(replace(good, outcome=replace(good.outcome, header=stray_header)))
    (arm,) = arms(
        world, [relabelled(twice, run_id="run-a"), relabelled(on_a_leave, run_id="run-b"), stray],
        plan(),
    )  # fmt: skip
    assert len(arm.unplaced) == 1
    placed, unplaced = incidents_of([arm])
    assert (placed.scenario_id, unplaced.scenario_id) == (first.spec.id, "scn_999")
    assert placed.shapes == (
        Shape(Source.FRAPPE, ContradictionKind.OMITTED_BY_WINDOW),
        Shape(Source.FRAPPE, DIFFER),
    )
    assert placed.arms[0].met == (RunRef("run-a", 1), RunRef("run-b", 1))
    # No scenario of the world holds it, so no counted run rests there; it is reported.
    assert unplaced.arms == (IncidentArm(arm.name, (RunRef("run-x", 1),), (), 0),)


def test_an_export_outside_the_tables_is_read_for_a_contradiction_like_any_other(
    world: SealedWorld,
) -> None:
    first, second, third = world.scenarios[:3]
    (arm,) = arms(world, [evaluated(world, first), evaluated(world, second)], plan())
    outside = [
        # Out of the tables for whatever reason, and its reads met a contradiction: on a
        # scenario the arm rests on, and on one no eligible run was made of.
        ("runs/z", contradicting(evaluated(world, first))),
        ("runs/b", contradicting(evaluated(world, first), ContradictionKind.RETURNED_AND_ABSENT)),
        ("runs/c", contradicting(evaluated(world, third))),
        # One that met none says nothing.
        ("runs/d", evaluated(world, second)),
    ]
    assert incidents_of([arm]) == ()
    on_first, on_third = incidents_of([arm], outside)
    assert (on_first.scenario_id, on_first.outside) == (first.spec.id, ("runs/b", "runs/z"))
    assert on_first.shapes == (
        Shape(Source.FRAPPE, ContradictionKind.RETURNED_AND_ABSENT),
        Shape(Source.FRAPPE, DIFFER),
    )
    # The arm's own run did not meet it, and its estimate rests on the scenario all the same.
    (held,) = on_first.arms
    assert (held.met, len(held.not_met), held.counted) == ((), 1, 1)
    assert (on_third.scenario_id, on_third.outside) == (third.spec.id, ("runs/c",))
    assert on_third.arms == (IncidentArm(arm.name, (), (), 0),)
    assert incident_scenarios([on_first, on_third]) == {first.spec.id, third.spec.id}
