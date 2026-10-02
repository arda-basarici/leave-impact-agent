"""A run that read everything observes what the oracle derives from: over the view built from a
full read, the oracle's own question gets the oracle's own answer, for every scenario, under
the normal condition and under each single-source outage. Two things are held equal that
were built apart, runtime truth from the sealed plantings and the observed view from a
trace's reads, so a grounding failure on a real run is never a disagreement between them."""

import pytest

from leaveimpact.core import RunCondition, Source
from leaveimpact.evaluator.observed_view import ObservedRun, observe
from leaveimpact.evaluator.oracle import (
    Answerable,
    Oracle,
    UnreadableLeave,
    UnreadablePolicy,
    conclusions_in,
    oracle_for,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.export_fixture import run_export
from tests.unit.reads_fixture import Recorder, full_read, systems_holding
from tests.unit.throwaway_world import loaded_world

NORMAL = RunCondition.all_reachable()


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def fully_read(world: SealedWorld, scenario: Scenario, *down: Source) -> ObservedRun:
    """What a run of ``scenario`` observes when it reads everything, with ``down`` unreachable
    for the whole run."""
    systems = systems_holding(world)
    for port in (systems.people, systems.work, systems.calendar, systems.documents):
        port.reachable = port.source not in down
    reads = Recorder(systems)
    full_read(reads, world, scenario)
    return observe(world.index, run_export(world, scenario, operations=reads.operations))


def parts(answer: Oracle) -> object:
    """Everything a report is graded against, comparable between two views of one world: an
    assessment by what it concludes and the facts it read, whatever order the view held
    them in."""
    if not isinstance(answer, Answerable):
        return type(answer)
    return (
        [
            (
                truth.key,
                truth.probe,
                [
                    (
                        each.employee_id,
                        each.verdict,
                        each.reasons,
                        each.unresolved,
                        frozenset(each.evidence),
                    )
                    for each in truth.assessments
                ],
                [(resolved.clause_id, resolved.requirement) for resolved in truth.requirements],
                truth.required,
                truth.outcome,
            )
            for truth in answer.impacts
        ],
        answer.constraints,
        frozenset(answer.conflicts),
        answer.unknowns,
    )


@pytest.mark.parametrize("down", [(), (Source.JIRA,), (Source.CALENDAR,)], ids=str)
def test_a_full_read_reproduces_the_oracles_complete_answer(
    world: SealedWorld, down: tuple[Source, ...]
) -> None:
    condition = NORMAL.without(*down)
    answerable = 0
    for scenario in world.scenarios:
        run = fully_read(world, scenario, *down)
        oracle = oracle_for(world, scenario, condition)
        assert run.findings == (), scenario.spec.id
        assert run.view.condition == condition
        assert isinstance(oracle, Answerable)
        # The same facts, built two ways: from the sealed plantings, and from what the
        # tools returned with the prose gated on its content.
        assert set(run.view.facts) == set(oracle.view.facts), scenario.spec.id
        assert set(run.view.gaps) == set(oracle.view.gaps), scenario.spec.id
        assert parts(conclusions_in(world, scenario, run.view)) == parts(oracle), scenario.spec.id
        answerable += 1
    assert answerable == len(world.scenarios) == 30


def test_a_full_read_without_the_hr_system_or_the_corpus_has_no_answer_either(
    world: SealedWorld,
) -> None:
    for down, state in ((Source.FRAPPE, UnreadableLeave), (Source.CORPUS, UnreadablePolicy)):
        for scenario in world.scenarios:
            run = fully_read(world, scenario, down)
            assert isinstance(conclusions_in(world, scenario, run.view), state)
            assert isinstance(oracle_for(world, scenario, NORMAL.without(down)), state)


def test_a_run_that_stopped_short_of_the_tracker_is_not_the_oracles_answer(
    world: SealedWorld,
) -> None:
    # The equality above is not vacuous: leave the tracker's enumeration out and what the
    # rules conclude over the reads is no longer what they conclude over the truth, in
    # exactly the scenarios whose sealed key says the tracker is a required source.
    differing = 0
    for scenario in world.scenarios:
        systems = systems_holding(world)
        reads = Recorder(systems)
        full_read(reads, world, scenario)
        kept = [operation for operation in reads.operations if operation.tool != "work_items"]
        run = observe(world.index, run_export(world, scenario, operations=kept))
        oracle = oracle_for(world, scenario, NORMAL)
        differs = parts(conclusions_in(world, scenario, run.view)) != parts(oracle)
        assert differs == (Source.JIRA in scenario.key.required_sources), scenario.spec.id
        differing += differs
    assert 0 < differing < len(world.scenarios)
