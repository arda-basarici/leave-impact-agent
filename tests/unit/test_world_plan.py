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
    # Five appearances each for five modifiers need twenty-five slots; eight non-clean
    # rows with room for one modifier each hold eight. Which modifier hits the wall
    # depends on the draw; that the wall is named does not.
    with pytest.raises(PlanInfeasible, match="needs 5 rows and only \\d compatible rows"):
        plan_world(
            Random(1),
            PlanRules(TIER_ONE_RULES.class_counts, min_appearances=5, max_modifiers=1),
        )


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
