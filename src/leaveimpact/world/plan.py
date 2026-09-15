"""The world plan: which class and which modifiers each scenario gets, as seeded data.

The plan is data rather than thirty independent draws (the plan ruling at step 8): a
table of tier, class and modifiers per scenario, produced by one planner under a stated
rule and recorded in the sealed world spec, so the audit reads what was intended and the
evaluator's reporting axes have the rows behind them. The rule for the structured tier —
the golden set's counts per class, every modifier on at least two scenarios, at most two
modifiers on any scenario, at least two scenarios with none — lives in ``PlanRules``;
the counts are cheap to change, the rule is lasting, and both are generator semantics
that bump the version. Independent draws per scenario were rejected because at ten rows
a modifier can land zero times, and a distractor measured on no rows is not measured.

The planner is compatibility-aware by construction: it assigns a modifier only to a row
whose class is declared to afford it (``COMPATIBLE_MODIFIERS``, proven over every
admissible construction), because no draft exists when the plan is made. It is a small
deterministic backtracking search, not a greedy draw: the RNG orders the legal
alternatives — which rows stay clean, which rows each modifier lands on — and the search
takes the first complete assignment, so the same seed gives the same plan and
randomness chooses among valid plans without deciding whether one exists. A greedy
planner raised on thirty-seven of two hundred seeds for a rule every one of them could
satisfy (the step 8 review), which made its failure mean "this path got stuck".
``PlanInfeasible`` therefore means what it says: every legal assignment was exhausted
and none satisfies the rule — never a relaxed constraint — and every produced plan is
re-checked against the rule before it is returned, so the check and the search cannot
disagree silently. Modifiers are placed most-constrained first, which keeps the search
shallow; at thirty rows, five modifiers and two per row it is tiny either way.

The clean rows are a baseline, not a causal isolation: ten rows on different scenarios
compare low against higher distractor pressure and do not measure one modifier's effect.

A named plan is a sequence of tables, one per tier, each planned and checked on its own
with the ids continuing (the 15.4 rulings): the coverage minima, the clean-row floor and
the per-row ceiling are tier-local, because the structured tier alone already meets every
minimum and a rule over the union would let every fragmented row stay clean and prove
nothing about that tier. A single-table plan is the planner's own output, so the sealed
worlds' plans reproduce unchanged. Feasibility of the fragmented table was shown by probe
before the ruling, two hundred seeds and none infeasible, with one consequence accepted
on record: only the cardinality rows afford the resolved look-alike, so both always carry
it and the tier has no clean cardinality row.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import combinations
from random import Random
from types import MappingProxyType

from leaveimpact.core.ids import ScenarioId, scenario_id
from leaveimpact.world.classes import SCENARIO_CLASSES
from leaveimpact.world.modifiers import COMPATIBLE_MODIFIERS
from leaveimpact.world.scenario import ModifierName, ScenarioClassName, Tier

_MODIFIER_ORDER = {name: index for index, name in enumerate(ModifierName)}


class PlanInfeasible(Exception):
    """No assignment satisfies the rule over the classes and compatibilities the plan has.

    Raised only after the search has exhausted every legal alternative, or when a
    modifier has fewer compatible rows than appearances before any search — named
    either way.
    """


@dataclass(frozen=True, slots=True)
class PlanRules:
    """The rule a plan satisfies: rows per class, and how modifiers may land on them.

    ``class_counts`` is the stratification; every class named must be a built one, so a
    plan never promises a scenario nothing can construct.

    >>> PlanRules({ScenarioClassName.STRUCTURED_DEADLINE: 0})
    Traceback (most recent call last):
    ...
    ValueError: a class count is at least one, got 0 for structured_deadline
    """

    class_counts: Mapping[ScenarioClassName, int]
    min_appearances: int = 2
    max_modifiers: int = 2
    min_clean: int = 2

    def __post_init__(self) -> None:
        object.__setattr__(self, "class_counts", MappingProxyType(dict(self.class_counts)))
        if not self.class_counts:
            raise ValueError("a plan names at least one class")
        for name, count in self.class_counts.items():
            if name not in SCENARIO_CLASSES:
                raise ValueError(f"{name.value} is not a built scenario class")
            if count < 1:
                raise ValueError(f"a class count is at least one, got {count} for {name.value}")
        for field_name, value in (
            ("min_appearances", self.min_appearances),
            ("max_modifiers", self.max_modifiers),
            ("min_clean", self.min_clean),
        ):
            if value < 0:
                raise ValueError(f"{field_name} is a count, got {value}")

    @property
    def rows(self) -> int:
        return sum(self.class_counts.values())


GOLDEN_SET_ROWS = 30
"""The golden set's size (DESIGN, "The first golden set"): the most rows one world holds, so
the most titles one component's tickets or one team's meetings can need, which the title
vocabulary's capacity per context is tested against."""

TIER_ONE_RULES = PlanRules(
    {
        ScenarioClassName.STRUCTURED_DEADLINE: 4,
        ScenarioClassName.STRUCTURED_MEETING: 4,
        ScenarioClassName.STRUCTURED_MIXED: 2,
    }
)
"""The golden set's structured tier: four deadline, four meeting, two mixed."""

MEASUREMENT_RULES = PlanRules(
    {**TIER_ONE_RULES.class_counts, ScenarioClassName.FREE_TEXT_QUALIFICATION: 3}
)
"""The measurement world of the step 15 rulings: the structured tier plus three qualification
rows — the first real materialization, sealed as an ordinary version and never one of the
thirty."""

TIER_TWO_RULES = PlanRules(
    {
        ScenarioClassName.FREE_TEXT_QUALIFICATION: 3,
        ScenarioClassName.FREE_TEXT_RESPONSIBILITY: 3,
        ScenarioClassName.RELEASE_CARDINALITY_CONSTRAINT: 2,
        ScenarioClassName.FRAGMENTED_COMPOSITE: 2,
    }
)
"""The golden set's fragmented tier (the 15.4 rulings): three qualification, three
responsibility, two cardinality, two composite. Cardinality's two is the construction's own
count, one row per holder of the paired skill as the leaver; the composite's two is DESIGN's
sentence; the six between the prose primitives split evenly, repetition for both."""

PLANS: Mapping[str, tuple[PlanRules, ...]] = MappingProxyType(
    {
        "tier1": (TIER_ONE_RULES,),
        "tier1-plus-qualification": (MEASUREMENT_RULES,),
        "tier1-plus-tier2": (TIER_ONE_RULES, TIER_TWO_RULES),
    }
)
"""The plans a world can be generated under, by the name the recipe records: a semantic
input on the world-defining side of the boundary, unlike a model id, so a sealed world
names the rule it was planned under and a resume reassembles under the same one. A plan
is one table per tier, planned in order (``plan_tiers``); the two single-table names are
the sealed worlds' and stay single tables."""


@dataclass(frozen=True, slots=True)
class PlanRow:
    """One planned scenario: id, tier, class and the modifiers to compose, in canonical order."""

    scenario_id: ScenarioId
    tier: Tier
    scenario_class: ScenarioClassName
    modifiers: tuple[ModifierName, ...]

    def __post_init__(self) -> None:
        if len(set(self.modifiers)) != len(self.modifiers):
            raise ValueError(f"a row lists each modifier once, got {self.modifiers}")
        if self.modifiers != _canonical(self.modifiers):
            raise ValueError(f"a row lists modifiers in canonical order, got {self.modifiers}")


def plan_world(rng: Random, rules: PlanRules) -> tuple[PlanRow, ...]:
    """The plan ``rules`` and ``rng`` produce: classes dealt over the rows, modifiers assigned.

    Same rules, same RNG state, same plan. Raises ``PlanInfeasible`` when no assignment
    satisfies the rule, naming what could not be met.
    """
    classes = [name for name, count in rules.class_counts.items() for _ in range(count)]
    rng.shuffle(classes)
    if rules.min_clean > len(classes):
        raise PlanInfeasible(
            f"min_clean asks {rules.min_clean} clean rows of {len(classes)} rows in total"
        )
    for modifier in ModifierName:
        # A necessary condition only, and a true one: clean rows can be drawn from the
        # rows this modifier cannot use, so the bound is the compatible rows or the
        # non-clean rows, whichever is fewer — never compatible-minus-clean, which the
        # review showed rejects a plan the search would find. Sufficiency is the search's.
        compatible = sum(modifier in COMPATIBLE_MODIFIERS[name] for name in classes)
        available = min(compatible, len(classes) - rules.min_clean)
        if available < rules.min_appearances:
            raise PlanInfeasible(
                f"{modifier.value} needs {rules.min_appearances} rows and at most "
                f"{available} compatible rows can be non-clean"
            )
    assigned = _search(rng, classes, rules)
    if assigned is None:
        raise PlanInfeasible(
            f"no assignment places every modifier {rules.min_appearances} times on "
            f"{len(classes)} rows with {rules.min_clean} clean and at most "
            f"{rules.max_modifiers} modifiers each"
        )
    rows = tuple(
        PlanRow(scenario_id(index + 1), SCENARIO_CLASSES[name].tier, name, _canonical(modifiers))
        for index, (name, modifiers) in enumerate(zip(classes, assigned, strict=True))
    )
    check_plan(rows, rules)
    return rows


def plan_tiers(rng: Random, tiers: Sequence[PlanRules]) -> tuple[PlanRow, ...]:
    """The plan ``tiers`` and ``rng`` produce: each table planned and checked on its own in
    order, the rows concatenated with the scenario ids continuing.

    One table is exactly ``plan_world`` on it, so a single-table plan reproduces what the
    sealed worlds were planned under. Raises ``PlanInfeasible`` from the first table that
    cannot meet its rule.
    """
    rows: list[PlanRow] = []
    for rules in tiers:
        offset = len(rows)
        rows.extend(
            replace(row, scenario_id=scenario_id(offset + index + 1))
            for index, row in enumerate(plan_world(rng, rules))
        )
    return tuple(rows)


def _search(
    rng: Random, classes: list[ScenarioClassName], rules: PlanRules
) -> list[list[ModifierName]] | None:
    """The first complete assignment in RNG order: clean rows chosen, then each modifier placed.

    Depth-first over the clean-row choice and then the modifiers most constrained
    first; at each level the legal alternatives are shuffled once by the RNG and tried
    in that order, so the seed decides which valid plan wins and nothing else.
    """
    order = _most_constrained_first(classes)
    clean_choices = list(combinations(range(len(classes)), rules.min_clean))
    rng.shuffle(clean_choices)
    for clean in clean_choices:
        assigned: list[list[ModifierName]] = [[] for _ in classes]
        if _place(rng, classes, rules, set(clean), order, 0, assigned):
            return assigned
    return None


def _place(
    rng: Random,
    classes: list[ScenarioClassName],
    rules: PlanRules,
    clean: set[int],
    order: list[ModifierName],
    depth: int,
    assigned: list[list[ModifierName]],
) -> bool:
    if depth == len(order):
        return True
    modifier = order[depth]
    eligible = [
        index
        for index, name in enumerate(classes)
        if index not in clean
        and modifier in COMPATIBLE_MODIFIERS[name]
        and len(assigned[index]) < rules.max_modifiers
    ]
    if len(eligible) < rules.min_appearances:
        return False
    choices = list(combinations(eligible, rules.min_appearances))
    rng.shuffle(choices)
    for rows in choices:
        for index in rows:
            assigned[index].append(modifier)
        if _place(rng, classes, rules, clean, order, depth + 1, assigned):
            return True
        for index in rows:
            assigned[index].pop()
    return False


def check_plan(rows: tuple[PlanRow, ...], rules: PlanRules) -> None:
    """Refuse ``rows`` unless they satisfy ``rules`` and the compatibility declaration, by name."""
    counts: dict[ScenarioClassName, int] = {}
    appearances: dict[ModifierName, int] = dict.fromkeys(ModifierName, 0)
    clean = 0
    for row in rows:
        counts[row.scenario_class] = counts.get(row.scenario_class, 0) + 1
        if len(row.modifiers) > rules.max_modifiers:
            raise PlanInfeasible(
                f"{row.scenario_id} carries {len(row.modifiers)} modifiers, the cap is "
                f"{rules.max_modifiers}"
            )
        foreign = [m for m in row.modifiers if m not in COMPATIBLE_MODIFIERS[row.scenario_class]]
        if foreign:
            raise PlanInfeasible(
                f"{row.scenario_id} plans {[m.value for m in foreign]} on "
                f"{row.scenario_class.value}, which does not afford them"
            )
        if not row.modifiers:
            clean += 1
        for modifier in row.modifiers:
            appearances[modifier] += 1
    if counts != dict(rules.class_counts):
        raise PlanInfeasible(f"class counts are {counts}, the rule asks {dict(rules.class_counts)}")
    short = [m.value for m, n in appearances.items() if n < rules.min_appearances]
    if short:
        raise PlanInfeasible(f"{short} appear fewer than {rules.min_appearances} times")
    if clean < rules.min_clean:
        raise PlanInfeasible(f"{clean} clean rows, the rule asks at least {rules.min_clean}")


def _most_constrained_first(classes: list[ScenarioClassName]) -> list[ModifierName]:
    def room(modifier: ModifierName) -> tuple[int, int]:
        compatible_rows = sum(modifier in COMPATIBLE_MODIFIERS[name] for name in classes)
        return (compatible_rows, _MODIFIER_ORDER[modifier])

    return sorted(ModifierName, key=room)


def _canonical(modifiers: Sequence[ModifierName]) -> tuple[ModifierName, ...]:
    return tuple(sorted(modifiers, key=lambda m: _MODIFIER_ORDER[m]))
