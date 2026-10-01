"""The dated view's answer against runtime truth's, on throwaway golden-plan worlds. Under the
normal condition every part of the answer the sealed key proves agrees, and only a candidate
outside the probe set can differ, each time because evidence about them is planted after the run
day; one such candidate is non-viable by date and viable at run time, the case in which a dated
oracle would grade a correct reading wrong. Under an outage nothing is proven: a world holds a
probed candidate the two views judge differently, and the unknowns they expect differ with it.
With the leave or the policy unreadable in both views there is no answer to compare."""

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
# The seed whose world holds a probed candidate that a Jira outage splits between the views
# (the forty-seed measurement's trace); a generator bump that moves it needs another seed.
OUTAGE_SEED = 10


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def normal(world: SealedWorld) -> ViewComparison:
    return compare_views(world, NORMAL)


def test_every_scenario_is_answered_and_every_impact_compared_over_the_organization(
    world: SealedWorld, normal: ViewComparison
) -> None:
    impacts = sum(len(scenario.key.impacts) for scenario in world.scenarios)
    probed = sum(len(e.must_assess) for s in world.scenarios for e in s.key.impacts)
    assert (normal.scenarios, normal.answerable) == (len(world.scenarios), len(world.scenarios))
    assert (normal.impacts, normal.probed_pairs) == (impacts, probed)
    assert normal.probed_pairs + normal.other_pairs == impacts * len(world.org.employees)


def test_under_the_normal_condition_every_part_the_key_proves_agrees(
    normal: ViewComparison,
) -> None:
    # World assembly proved every key under both views; a difference in one of these parts
    # would say the sealed world should not have sealed.
    counts = normal.counts()
    assert set(counts) == {
        "answerable in one view only",
        "impact sets",
        "must-assess verdicts",
        "other verdicts",
        "open questions",
        "requirements",
        "outcomes",
        "constraints",
        "conflicts",
        "unknowns",
    }
    differing = {part for part, count in counts.items() if count}
    assert differing == {"other verdicts"}
    assert normal.scenarios_differing == {d.scenario_id for d in normal.verdict_differences}


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


def test_under_an_outage_a_probed_candidate_and_the_expected_unknowns_can_differ() -> None:
    world = loaded_world("golden", OUTAGE_SEED)
    assert compare_views(world, NORMAL).counts()["must-assess verdicts"] == 0
    jira_down = compare_views(world, NORMAL.without(Source.JIRA))
    assert jira_down.condition == NORMAL.without(Source.JIRA)
    # Fewer impacts are compared than the world seals: the tracker's are lost in both views.
    assert jira_down.answerable == len(world.scenarios)
    assert 0 < jira_down.impacts < sum(len(s.key.impacts) for s in world.scenarios)
    [split] = [difference for difference in jira_down.verdict_differences if difference.probed]
    # The scenario's own comment is unreachable; a document a later scenario plants restates
    # the skill, hidden by date and readable at run time.
    assert split.dated == (Verdict.UNKNOWN, ())
    assert split.runtime == (Verdict.VIABLE, ())
    # The dated view expects an unknown claim the runtime view does not: a part of the
    # answer beyond verdicts differs, and the comparison names it.
    assert jira_down.unknown_differences == (split.scenario_id,)
    assert jira_down.scenarios_differing == {split.scenario_id}


def test_with_the_leave_or_the_policy_unreadable_in_both_views_there_is_nothing_to_compare(
    world: SealedWorld,
) -> None:
    for source in (Source.FRAPPE, Source.CORPUS):
        down = compare_views(world, NORMAL.without(source))
        assert (down.scenarios, down.answerable) == (len(world.scenarios), 0)
        assert (down.impacts, down.probed_pairs, down.other_pairs) == (0, 0, 0)
        # No answer under both views is agreement about the state, not a difference.
        assert down.state_differences == ()
        assert not any(down.counts().values())
