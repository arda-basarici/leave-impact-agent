"""The world plan over a sweep of seeds: every plan satisfies the rule and the compatibility
declaration, is equal for equal inputs, and a rule that cannot be met fails by name instead
of relaxing a constraint."""

from random import Random

import pytest

from leaveimpact.core.ids import scenario_id
from leaveimpact.world import (
    COMPATIBLE_MODIFIERS,
    TIER_ONE_RULES,
    ModifierName,
    PlanInfeasible,
    PlanRow,
    PlanRules,
    ScenarioClassName,
    Tier,
    check_plan,
    plan_world,
)

SEEDS = range(1, 41)


@pytest.mark.parametrize("seed", SEEDS)
def test_every_plan_satisfies_the_tier_one_rule(seed: int) -> None:
    rows = plan_world(Random(seed), TIER_ONE_RULES)
    assert len(rows) == TIER_ONE_RULES.rows == 10
    assert [row.scenario_id for row in rows] == [f"scenario_{n:03d}" for n in range(1, 11)]
    counts = {name: sum(r.scenario_class is name for r in rows) for name in ScenarioClassName}
    assert counts[ScenarioClassName.STRUCTURED_DEADLINE] == 4
    assert counts[ScenarioClassName.STRUCTURED_MEETING] == 4
    assert counts[ScenarioClassName.STRUCTURED_MIXED] == 2
    assert all(row.tier is Tier.STRUCTURED for row in rows)
    for modifier in ModifierName:
        assert sum(modifier in row.modifiers for row in rows) >= 2
    assert all(len(row.modifiers) <= 2 for row in rows)
    assert sum(not row.modifiers for row in rows) >= 2
    for row in rows:
        assert set(row.modifiers) <= COMPATIBLE_MODIFIERS[row.scenario_class]
    check_plan(rows, TIER_ONE_RULES)


def test_the_same_inputs_give_an_equal_plan_and_seeds_differ() -> None:
    assert plan_world(Random(3), TIER_ONE_RULES) == plan_world(Random(3), TIER_ONE_RULES)
    assert plan_world(Random(3), TIER_ONE_RULES) != plan_world(Random(4), TIER_ONE_RULES)


def test_a_rule_that_cannot_be_met_fails_by_name() -> None:
    with pytest.raises(PlanInfeasible, match="min_clean asks 11 clean rows of 10"):
        plan_world(Random(1), PlanRules(TIER_ONE_RULES.class_counts, min_clean=11))
    # already_resolved fits six non-meeting rows however the clean rows fall, so seven
    # appearances cannot fit — named before any search.
    with pytest.raises(PlanInfeasible, match="already_resolved needs 7 rows and at most 6"):
        plan_world(
            Random(1),
            PlanRules(TIER_ONE_RULES.class_counts, min_appearances=7, max_modifiers=7),
        )
    # Every modifier has enough compatible rows on its own, and no assignment fits them
    # all: ten placements over one meeting and two mixed rows, six slots. Search exhausts.
    tight = PlanRules(
        {ScenarioClassName.STRUCTURED_MEETING: 1, ScenarioClassName.STRUCTURED_MIXED: 2},
        min_clean=0,
    )
    with pytest.raises(PlanInfeasible, match="no assignment places every modifier 2 times"):
        plan_world(Random(1), tight)


@pytest.mark.parametrize("seed", range(1, 41))
def test_clean_rows_come_from_the_rows_a_modifier_cannot_use(seed: int) -> None:
    # Five already_resolved appearances on six compatible rows with two clean rows: the
    # clean rows must be meeting rows, which the modifier could not use anyway. A bound
    # of compatible-minus-clean rejected this before the search could find it (review).
    rules = PlanRules(
        TIER_ONE_RULES.class_counts, min_appearances=5, max_modifiers=4, min_clean=2
    )
    rows = plan_world(Random(seed), rules)
    check_plan(rows, rules)
    assert sum(ModifierName.ALREADY_RESOLVED in row.modifiers for row in rows) == 5


@pytest.mark.parametrize("seed", range(1, 201))
def test_a_feasible_rule_never_fails_on_the_seed(seed: int) -> None:
    # The shape a greedy planner failed on thirty-seven times in two hundred: ten
    # placements over exactly ten slots, where the order of irreversible draws decided.
    rules = PlanRules(
        {
            ScenarioClassName.STRUCTURED_DEADLINE: 1,
            ScenarioClassName.STRUCTURED_MEETING: 1,
            ScenarioClassName.STRUCTURED_MIXED: 3,
        },
        min_clean=0,
    )
    check_plan(plan_world(Random(seed), rules), rules)


def test_the_check_refuses_a_plan_that_breaks_the_declaration() -> None:
    rows = plan_world(Random(2), TIER_ONE_RULES)
    meeting = next(
        i
        for i, row in enumerate(rows)
        if row.scenario_class is ScenarioClassName.STRUCTURED_MEETING
    )
    broken = list(rows)
    broken[meeting] = PlanRow(
        rows[meeting].scenario_id,
        rows[meeting].tier,
        rows[meeting].scenario_class,
        (ModifierName.ALREADY_RESOLVED,),
    )
    with pytest.raises(PlanInfeasible, match="does not afford"):
        check_plan(tuple(broken), TIER_ONE_RULES)


def test_a_row_lists_modifiers_once_and_in_canonical_order() -> None:
    with pytest.raises(ValueError, match="canonical order"):
        PlanRow(
            scenario_id(1),
            Tier.STRUCTURED,
            ScenarioClassName.STRUCTURED_DEADLINE,
            (ModifierName.CONCURRENT_LEAVE, ModifierName.WRONG_TEAM),
        )


def test_rules_refuse_what_no_class_can_honour() -> None:
    with pytest.raises(ValueError, match="not a built scenario class"):
        PlanRules({ScenarioClassName.UNCOVERED: 1})
