"""The dated view against runtime truth on a throwaway golden-plan world: under the normal
condition no probed candidate and no outcome differs, which is assembly's proof restated; a
candidate outside the probe set can differ, each time because evidence about them is planted
after the scenario's run day; and one such candidate is non-viable under the dated view and viable
at run time, the case in which a dated oracle would grade a correct reading wrong."""

import pytest

from leaveimpact.core import (
    AssessmentReason,
    PredicateName,
    RunCondition,
    Source,
    Verdict,
    employee_ref,
)
from leaveimpact.evaluator.characterization import ViewComparison, compare_views
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.unit.throwaway_world import loaded_world

NORMAL = RunCondition.all_reachable()


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def normal(world: SealedWorld) -> ViewComparison:
    return compare_views(world, NORMAL)


def test_every_sealed_impact_is_compared_over_the_whole_organization(
    world: SealedWorld, normal: ViewComparison
) -> None:
    impacts = sum(len(scenario.key.impacts) for scenario in world.scenarios)
    probed = sum(len(e.must_assess) for s in world.scenarios for e in s.key.impacts)
    assert normal.impacts == impacts
    assert normal.probed_pairs == probed
    assert normal.probed_pairs + normal.other_pairs == impacts * len(world.org.employees)


def test_under_the_normal_condition_no_probed_candidate_and_no_outcome_differs(
    normal: ViewComparison,
) -> None:
    # World assembly proved every key under both views; a difference here would say the
    # sealed world should not have sealed.
    assert not [difference for difference in normal.verdict_differences if difference.probed]
    assert normal.outcome_differences == ()


def test_a_difference_outside_the_probe_set_rests_on_evidence_planted_after_the_run_day(
    world: SealedWorld, normal: ViewComparison
) -> None:
    # This seed's world holds such candidates; a generator bump that removes them all
    # needs another seed here, since the claim is about a world that has the case.
    assert normal.verdict_differences
    for difference in normal.verdict_differences:
        scenario = world.scenario(difference.scenario_id)
        assert scenario is not None
        later_skills = [
            fact
            for fact in world.facts.facts
            if fact.subject == employee_ref(difference.employee_id)
            and fact.predicate is PredicateName.HAS_SKILL
            and fact.observable_from > scenario.spec.today
        ]
        # The dated view hides it, the systems hold it, a run can read it.
        assert later_skills, difference
        assert AssessmentReason.SKILL in difference.dated[1]
        assert AssessmentReason.SKILL not in difference.runtime[1]


def test_a_candidate_non_viable_by_date_and_viable_at_run_time_is_what_the_oracle_says(
    world: SealedWorld, normal: ViewComparison
) -> None:
    flipped = [difference for difference in normal.verdict_differences if difference.flips]
    assert flipped, "this world holds a candidate whose verdict the two views flip"
    for difference in flipped:
        assert difference.dated == (Verdict.NON_VIABLE, (AssessmentReason.SKILL,))
        assert difference.runtime == (Verdict.VIABLE, ())
        scenario = world.scenario(difference.scenario_id)
        assert scenario is not None
        oracle = oracle_for(world, scenario, NORMAL)
        assert isinstance(oracle, Answerable)
        truth = oracle.impact(difference.impact)
        assert truth is not None and difference.employee_id not in truth.probe
        assessed = truth.assessment_of(difference.employee_id)
        # A report that read the later comment and called the candidate viable is right.
        assert assessed is not None and assessed.verdict is Verdict.VIABLE


def test_the_comparison_runs_under_an_outage_and_names_its_condition(world: SealedWorld) -> None:
    jira_down = NORMAL.without(Source.JIRA)
    comparison = compare_views(world, jira_down)
    assert comparison.condition == jira_down
    assert (comparison.impacts, comparison.probed_pairs) == (
        compare_views(world, NORMAL).impacts,
        compare_views(world, NORMAL).probed_pairs,
    )
