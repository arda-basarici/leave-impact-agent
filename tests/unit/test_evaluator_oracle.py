"""The oracle over a throwaway golden-plan world: under the normal condition it is the sealed key,
and an answer that is not is a defect named without the key's content; an unreadable leave is a
state and not an empty answer; under an outage a source the key does not require moves nothing
and one it requires moves something, every moved verdict or outcome going to unknown or losing
reasons; a lost impact carries no assessment and its constraint is not expected; a candidate
outside the probe set still has a verdict."""

from dataclasses import replace

import pytest

from leaveimpact.core import (
    CoverageActionKind,
    EntityKind,
    RunCondition,
    Source,
    Verdict,
)
from leaveimpact.core.ids import EmployeeId
from leaveimpact.evaluator.oracle import (
    Answerable,
    OracleDisagrees,
    UnreadableLeave,
    oracle_for,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.throwaway_world import loaded_world

NORMAL = RunCondition.all_reachable()
OUTAGES = (Source.JIRA, Source.CALENDAR, Source.CORPUS)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def answer(world: SealedWorld, scenario: Scenario, condition: RunCondition) -> Answerable:
    oracle = oracle_for(world, scenario, condition)
    assert isinstance(oracle, Answerable)
    return oracle


def conclusions(oracle: Answerable) -> tuple[object, ...]:
    """Everything the oracle concluded, in a form two conditions can be compared by."""
    return (
        tuple(
            (
                truth.key,
                truth.outcome,
                tuple(
                    (a.employee_id, a.verdict, a.reasons, a.unresolved) for a in truth.assessments
                ),
            )
            for truth in oracle.impacts
        ),
        oracle.constraints,
        oracle.conflicts,
    )


# --- The normal condition: the sealed key ---------------------------------------------------


def test_under_the_normal_condition_the_oracle_is_the_sealed_key(world: SealedWorld) -> None:
    universe = tuple(employee.id for employee in world.org.employees)
    for scenario in world.scenarios:
        key = scenario.key
        oracle = answer(world, scenario, NORMAL)
        assert [truth.key for truth in oracle.impacts] == [e.key for e in key.impacts]
        for expected, truth in zip(key.impacts, oracle.impacts, strict=True):
            assert truth.outcome is expected.outcome
            assert truth.probe == tuple(a.employee_id for a in expected.must_assess)
            assert tuple(a.employee_id for a in truth.assessments) == universe
            for authored in expected.must_assess:
                derived = truth.assessment_of(authored.employee_id)
                assert derived is not None
                assert (derived.verdict, derived.reasons) == (authored.verdict, authored.reasons)
        assert oracle.constraints == key.constraints
        assert oracle.conflicts == key.expected_conflicts
        assert oracle.unknowns == key.expected_unknowns


def test_a_candidate_outside_the_probe_set_has_a_verdict_and_a_stranger_has_none(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    [truth, *_] = answer(world, scenario, NORMAL).impacts
    outsiders = [employee for employee in world.org.employees if employee.id not in truth.probe]
    assert len(outsiders) > len(truth.probe)
    assert all(truth.assessment_of(employee.id) is not None for employee in outsiders)
    assert truth.assessment_of(EmployeeId("emp_999")) is None


def test_an_answer_that_is_not_the_sealed_key_is_a_defect_named_without_its_content(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    impact, *others = scenario.key.impacts
    wrong = (
        CoverageActionKind.UNCOVERED
        if impact.outcome is not CoverageActionKind.UNCOVERED
        else CoverageActionKind.ASSIGN
    )
    drifted_key = replace(scenario.key, impacts=(replace(impact, outcome=wrong), *others))
    with pytest.raises(OracleDisagrees) as disagreed:
        oracle_for(world, replace(scenario, key=drifted_key), NORMAL)
    message = str(disagreed.value)
    assert message.startswith(f"{scenario.spec.id}: under the normal condition")
    assert "an outcome" in message
    for word in (wrong.value, impact.outcome.value, impact.key.artifact.id):
        assert word not in message
    # The same drifted key under an outage is not anchored: nothing is sealed for it there.
    assert isinstance(
        oracle_for(world, replace(scenario, key=drifted_key), NORMAL.without(Source.CALENDAR)),
        Answerable,
    )


# --- The unreadable leave -------------------------------------------------------------------


def test_a_leave_that_cannot_be_read_is_a_state_and_not_an_empty_answer(
    world: SealedWorld,
) -> None:
    frappe_down = NORMAL.without(Source.FRAPPE)
    for scenario in world.scenarios:
        oracle = oracle_for(world, scenario, frappe_down)
        assert isinstance(oracle, UnreadableLeave)
        assert (oracle.scenario, oracle.condition) == (scenario, frappe_down)
    # With the people system back the same scenario is answerable, whatever else is down.
    others_down = NORMAL.without(Source.JIRA, Source.CALENDAR, Source.CORPUS)
    assert isinstance(oracle_for(world, world.scenarios[0], others_down), Answerable)


# --- Outages --------------------------------------------------------------------------------


def test_an_outage_moves_the_answer_exactly_when_the_key_requires_the_source(
    world: SealedWorld,
) -> None:
    moved = unmoved = 0
    for scenario in world.scenarios:
        normal = conclusions(answer(world, scenario, NORMAL))
        for source in OUTAGES:
            under_outage = conclusions(answer(world, scenario, NORMAL.without(source)))
            if source in scenario.key.required_sources:
                assert under_outage != normal, (scenario.spec.id, source)
                moved += 1
            else:
                assert under_outage == normal, (scenario.spec.id, source)
                unmoved += 1
    # Both arms are exercised: the equality and the inequality are each claimed many times.
    assert moved > 20 and unmoved > 10


def test_what_an_outage_moves_goes_to_unknown_or_keeps_non_viable_with_fewer_reasons(
    world: SealedWorld,
) -> None:
    verdicts_moved = outcomes_moved = 0
    for scenario in world.scenarios:
        for source in OUTAGES:
            oracle = answer(world, scenario, NORMAL.without(source))
            for expected in scenario.key.impacts:
                truth = oracle.impact(expected.key)
                if truth is None:
                    continue
                if truth.outcome is not expected.outcome:
                    assert truth.outcome is CoverageActionKind.UNKNOWN
                    outcomes_moved += 1
                for authored in expected.must_assess:
                    derived = truth.assessment_of(authored.employee_id)
                    assert derived is not None
                    if (derived.verdict, derived.reasons) == (authored.verdict, authored.reasons):
                        continue
                    verdicts_moved += 1
                    if derived.verdict is Verdict.NON_VIABLE:
                        assert authored.verdict is Verdict.NON_VIABLE
                        assert set(derived.reasons) < set(authored.reasons)
                    else:
                        assert derived.verdict is Verdict.UNKNOWN and derived.unresolved
    assert verdicts_moved and outcomes_moved


def test_an_impact_an_outage_loses_carries_nothing_and_its_constraint_is_not_expected(
    world: SealedWorld,
) -> None:
    jira_down, corpus_down = NORMAL.without(Source.JIRA), NORMAL.without(Source.CORPUS)
    ticket_scoped = clause_impacts = 0
    for scenario in world.scenarios:
        key = scenario.key
        without_tracker = answer(world, scenario, jira_down)
        for expected in key.impacts:
            if expected.key.artifact.kind is EntityKind.WORK_ITEM:
                # No visible fact connects the ticket to the leaver: not an expected impact.
                assert without_tracker.impact(expected.key) is None
        for constraint in key.constraints:
            if constraint.applies_to.kind is EntityKind.WORK_ITEM:
                assert constraint not in without_tracker.constraints
                ticket_scoped += 1
        without_corpus = answer(world, scenario, corpus_down)
        # No clause is readable, so no constraint can be established.
        assert without_corpus.constraints == ()
        for expected in key.impacts:
            if expected.key.artifact.kind is EntityKind.CLAUSE:
                assert without_corpus.impact(expected.key) is None
                clause_impacts += 1
        # What remains is a subset of the sealed impacts, in the key's order.
        sealed = [e.key for e in key.impacts]
        for oracle in (without_tracker, without_corpus):
            kept = [truth.key for truth in oracle.impacts]
            assert kept == [impact for impact in sealed if impact in kept]
    assert ticket_scoped and clause_impacts
