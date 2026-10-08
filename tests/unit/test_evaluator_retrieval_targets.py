"""A retrieval target is a statement whose removal, on every carrier, moves the oracle's answer
for a scenario under a condition. Measured on a throwaway golden world: every statement is a
target of the scenario that planted it under the normal condition; a few are targets of
another scenario too, and those move only rows no report must hold; a statement carried where
the condition cannot read is no target there. A requirement is removed with its scope pairing,
so no removal is refused, and a removal the rules do refuse is raised with no sealed content."""

import traceback
from collections import Counter

import pytest

from leaveimpact.core import (
    ClaimType,
    ConstraintKey,
    EntityKind,
    PredicateName,
    RunCondition,
    Source,
)
from leaveimpact.core.ids import ClauseId, employee_id, skill_id
from leaveimpact.core.refs import employee_ref
from leaveimpact.evaluator import retrieval_targets as module
from leaveimpact.evaluator.oracle import Answerable, answer_without, oracle_for
from leaveimpact.evaluator.retrieval_targets import (
    RetrievalTarget,
    TargetsNotDerivable,
    retrieval_targets,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.world_index import statement_of
from leaveimpact.world import Scenario
from tests.unit.throwaway_world import loaded_world

NORMAL = RunCondition.all_reachable()
TRACKER_DOWN = NORMAL.without(Source.JIRA)
CALENDAR_DOWN = NORMAL.without(Source.CALENDAR)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def answer(world: SealedWorld, scenario: Scenario, condition: RunCondition) -> Answerable:
    oracle = oracle_for(world, scenario, condition)
    assert isinstance(oracle, Answerable)
    return oracle


_FOUND: dict[RunCondition, list[tuple[Scenario, RetrievalTarget]]] = {}


def targets_of(
    world: SealedWorld, condition: RunCondition
) -> list[tuple[Scenario, RetrievalTarget]]:
    """Every target of every scenario under ``condition``, with the scenario it is a target of;
    derived once per condition, the world being one per process."""
    if condition not in _FOUND:
        _FOUND[condition] = [
            (scenario, target)
            for scenario in world.scenarios
            for target in retrieval_targets(world, answer(world, scenario, condition))
        ]
    return _FOUND[condition]


def is_own(scenario: Scenario, target: RetrievalTarget) -> bool:
    return target.statement in {statement_of(fact) for fact in scenario.authored_facts}


@pytest.mark.parametrize(
    ("condition", "scenarios_with_a_target", "own", "foreign"),
    [(NORMAL, 20, 31, 3), (TRACKER_DOWN, 8, 15, 0), (CALENDAR_DOWN, 17, 25, 3)],
    ids=["normal", "tracker down", "calendar down"],
)
def test_the_targets_of_a_throwaway_golden_world_by_condition(
    world: SealedWorld,
    condition: RunCondition,
    scenarios_with_a_target: int,
    own: int,
    foreign: int,
) -> None:
    # The measurement the design of the trace metrics was made on, regenerated: 30 scenarios,
    # 31 statements each on one carrier.
    assert (len(world.scenarios), len(world.index.statements)) == (30, 31)
    found = targets_of(world, condition)
    assert len({scenario.spec.id for scenario, _ in found}) == scenarios_with_a_target
    mine = sum(is_own(scenario, target) for scenario, target in found)
    assert (mine, len(found) - mine) == (own, foreign)


def test_every_statement_is_a_target_of_the_scenario_that_planted_it(world: SealedWorld) -> None:
    for scenario in world.scenarios:
        planted = {statement_of(fact) for fact in scenario.authored_facts}
        found = {t.statement for t in retrieval_targets(world, answer(world, scenario, NORMAL))}
        assert planted <= found, scenario.spec.id
    # A scenario with no prose of its own and none that reaches it has no target: it stays
    # out of a retrieval denominator and is counted.
    without = [
        scenario
        for scenario in world.scenarios
        if not retrieval_targets(world, answer(world, scenario, NORMAL))
    ]
    assert len(without) == 10


def test_a_target_names_where_it_is_written_and_what_it_moves(world: SealedWorld) -> None:
    for _, target in targets_of(world, NORMAL):
        assert target.moves
        assert [carrier.part for carrier in target.carriers] == list(
            world.index.statements[target.statement]
        )
        for carrier in target.carriers:
            assert carrier.record == world.index.parts[carrier.part].parent
            held_in = {EntityKind.COMMENT: Source.JIRA, EntityKind.CLAUSE: Source.CORPUS}
            assert carrier.source is held_in[carrier.part.kind]


def test_a_requirement_is_removed_with_its_scope_pairing_and_moves_its_constraint(
    world: SealedWorld,
) -> None:
    # A requirement fact removed with its constraint kept is refused by the rules, in every
    # case measured; the pairing goes with the fact, and the constraint is what moves first.
    requirements = [
        (scenario, target)
        for scenario, target in targets_of(world, NORMAL)
        if target.statement[1] is PredicateName.REQUIRES
    ]
    assert len(requirements) == 17
    for scenario, target in requirements:
        clause = ClauseId(target.statement[0].id)
        pairing = next(c for c in scenario.key.constraints if c.clause_id == clause)
        moved = {(moved.claim_type, moved.key): moved.required for moved in target.moves}
        assert moved[(ClaimType.CONSTRAINT, pairing)] is True
        assert target.moves_a_required_key
        assert isinstance(pairing, ConstraintKey)


def test_a_target_of_another_scenarios_planting_moves_only_rows_no_report_must_hold(
    world: SealedWorld,
) -> None:
    foreign = [
        target for scenario, target in targets_of(world, NORMAL) if not is_own(scenario, target)
    ]
    assert len(foreign) == 3
    for target in foreign:
        # A skill shown for a colleague, who is outside this scenario's probe set.
        assert target.statement[1] is PredicateName.HAS_SKILL
        assert not target.moves_a_required_key
        assert {moved.claim_type for moved in target.moves} <= {
            ClaimType.CANDIDATE_ASSESSMENT,
            ClaimType.UNKNOWN,
        }
    # Every target a scenario planted itself moves a row a report must hold.
    own = [target for scenario, target in targets_of(world, NORMAL) if is_own(scenario, target)]
    assert all(target.moves_a_required_key for target in own)


def test_a_statement_carried_where_the_condition_cannot_read_is_no_target_there(
    world: SealedWorld,
) -> None:
    def carrier_kinds(condition: RunCondition) -> Counter[EntityKind]:
        return Counter(
            carrier.part.kind
            for _, target in targets_of(world, condition)
            for carrier in target.carriers
        )

    assert carrier_kinds(NORMAL)[EntityKind.COMMENT] > 0
    # The tracker down: no comment can be read, and removing one moves nothing.
    assert carrier_kinds(TRACKER_DOWN)[EntityKind.COMMENT] == 0
    assert carrier_kinds(TRACKER_DOWN)[EntityKind.CLAUSE] == 15


def test_the_answer_without_a_statement_nobody_makes_is_the_answer(world: SealedWorld) -> None:
    nobody_says = (employee_ref(employee_id(1)), PredicateName.HAS_SKILL, skill_id("falconry"))
    assert nobody_says not in world.index.statements
    for scenario in world.scenarios[:5]:
        oracle = answer(world, scenario, NORMAL)
        reduced = answer_without(world, scenario, NORMAL, nobody_says)
        assert isinstance(reduced, Answerable)
        assert (reduced.impacts, reduced.constraints, reduced.conflicts, reduced.unknowns) == (
            oracle.impacts,
            oracle.constraints,
            oracle.conflicts,
            oracle.unknowns,
        )


def test_a_removal_the_rules_refuse_is_raised_with_no_sealed_content(
    world: SealedWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refusing(*_: object) -> None:
        raise ValueError("clause_011 requires nothing that ticket_042 could be held to")

    monkeypatch.setattr(module, "answer_without", refusing)
    scenario = world.scenarios[0]
    with pytest.raises(TargetsNotDerivable) as raised:
        retrieval_targets(world, answer(world, scenario, NORMAL))
    printed = "".join(traceback.format_exception(raised.value))
    assert scenario.spec.id in printed and "31 statement(s)" in printed
    # The job that would print this logs in public: the whole chain is searched, not the message.
    assert "clause_011" not in printed and "ticket_042" not in printed
    assert "clause_011" in raised.value.detail
