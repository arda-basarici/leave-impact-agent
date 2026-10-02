"""The evaluator's observed view is the structured projection of the run's reads plus the sealed
facts it admits through prose, and nothing else: the same structured facts in the same
order, the same gaps, the same condition, and a coverage that differs only by what the
sealed comparison withdraws. A harness that reads no prose concludes from the projection, so
the view the graded concludes from is the structured part of the view the grader replays
over, whatever the reads were: ordinary, repeated, in disagreement, cut short by an outage,
or holding a record no fact can be made from."""

from collections.abc import Sequence
from dataclasses import replace

import pytest

from leaveimpact.core import Operation, Source, StructuredReads, project_reads
from leaveimpact.evaluator.observed_view import IntegrityKind, ObservedRun, observe
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.export_fixture import run_export
from tests.unit.reads_fixture import (
    Recorder,
    Systems,
    full_read,
    reads_of_everything,
    systems_holding,
)
from tests.unit.throwaway_world import loaded_world


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture
def systems(world: SealedWorld) -> Systems:
    """Fresh systems holding the sealed world: a test may make them drift."""
    return systems_holding(world)


@pytest.fixture
def scenario(world: SealedWorld) -> Scenario:
    return world.scenarios[0]


def both(
    world: SealedWorld, scenario: Scenario, operations: Sequence[Operation]
) -> tuple[ObservedRun, StructuredReads]:
    """What the evaluator observes of ``operations`` and their structured projection, held to
    the relation this module is about."""
    export = run_export(world, scenario, operations=operations)
    run = observe(world.index, export)
    projection = project_reads(operations, export.context.today)
    base = projection.view()
    today = export.context.today
    sealed_prose = {
        replace(fact, observable_from=today)
        for carried in world.index.carried.values()
        for fact in carried
    }
    structured = tuple(fact for fact in run.view.facts if fact in set(base.facts))
    overlay = [fact for fact in run.view.facts if fact not in set(base.facts)]
    assert structured == base.facts
    assert all(fact in sealed_prose for fact in overlay)
    assert not sealed_prose & set(base.facts)
    assert run.view.gaps == base.gaps
    assert run.view.condition == base.condition
    assert run.view.now == base.now
    # The evaluator withdraws more only where the sealed comparison calls for it.
    assert replace(run.coverage, unobserved=frozenset()) == replace(
        projection.coverage, unobserved=frozenset()
    )
    assert run.coverage.unobserved >= projection.coverage.unobserved
    return run, projection


def test_over_a_full_read_the_two_differ_by_the_admitted_prose_alone(world: SealedWorld) -> None:
    admitted = 0
    for scenario in world.scenarios:
        run, projection = both(world, scenario, reads_of_everything(world, scenario))
        assert run.findings == ()
        assert run.coverage == projection.coverage
        admitted += len(run.view.facts) - len(projection.facts)
    assert admitted > 0


@pytest.mark.parametrize("down", [Source.JIRA, Source.CALENDAR, Source.FRAPPE, Source.CORPUS])
def test_with_a_source_unreachable_for_the_whole_run(world: SealedWorld, down: Source) -> None:
    for scenario in world.scenarios:
        run, projection = both(world, scenario, reads_of_everything(world, scenario, down))
        assert run.coverage == projection.coverage
        assert down not in projection.condition.condition.reachable
        assert not projection.condition.is_mixed


def test_with_every_read_made_twice(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    reads = Recorder(systems)
    full_read(reads, world, scenario)
    once = project_reads(reads.operations, scenario.spec.today)
    full_read(reads, world, scenario)
    run, projection = both(world, scenario, reads.operations)
    assert projection.derived == once.derived
    assert run.coverage == projection.coverage


def test_with_a_record_returned_two_ways(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    reads = Recorder(systems)
    reads.read("work_items")
    tickets = systems.work.tickets
    id, item = next(iter(tickets.items()))
    tickets[id] = replace(
        item, owner_id=next(e.id for e in world.org.employees if e.id != item.owner_id)
    )
    reads.read("work_item", {"id": id})
    run, projection = both(world, scenario, reads.operations)
    assert [finding.kind for finding in run.findings] == [IntegrityKind.RETURNS_DIFFER]
    assert not [fact for fact in projection.facts if fact.subject.id == id]
    assert run.coverage == projection.coverage


def test_with_a_record_returned_and_then_found_absent(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    reads = Recorder(systems)
    id = next(iter(systems.work.tickets))
    reads.read("work_item", {"id": id})
    del systems.work.tickets[id]
    reads.read("work_item", {"id": id})
    run, projection = both(world, scenario, reads.operations)
    assert projection.derived == ()
    assert IntegrityKind.RETURNS_DIFFER in [finding.kind for finding in run.findings]
    assert run.coverage == projection.coverage


def test_with_a_source_that_answered_and_then_failed(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    reads = Recorder(systems)
    reads.read("work_item", {"id": next(iter(systems.work.tickets))})
    systems.work.reachable = False
    reads.read("work_items")
    reads.read("employees")
    run, projection = both(world, scenario, reads.operations)
    assert projection.condition.mixed == frozenset({Source.JIRA})
    assert run.coverage == projection.coverage


def test_with_a_record_no_fact_can_be_made_from(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    blank = replace(world.org.employees[0], location="  ")
    systems.people.people[blank.id] = blank
    reads = Recorder(systems)
    reads.read("employees")
    run, projection = both(world, scenario, reads.operations)
    assert [ref.id for ref in projection.underivable] == [blank.id]
    assert IntegrityKind.RECORD_NOT_DERIVABLE in [finding.kind for finding in run.findings]
    # The projection withdrew the record itself; the evaluator had nothing more to withdraw.
    assert run.coverage == projection.coverage
