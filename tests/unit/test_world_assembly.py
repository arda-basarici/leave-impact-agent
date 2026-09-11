"""World assembly: one seed gives one world — organization, plan, slices, scenarios and the
world-level fact base agreeing with each other — equal for equal inputs; and the whole-world
re-verification catches a record one scenario plants that flips another scenario's verdict,
naming the scenario, the candidate and the foreign record with its owner."""

from dataclasses import replace
from datetime import date

import pytest

from leaveimpact.core import LeaveKind, LeaveStatus, Verdict
from leaveimpact.core.entities import Leave
from leaveimpact.core.ids import leave_id
from leaveimpact.world import (
    DEFAULT_PARAMS,
    GENERATOR_VERSION,
    Planted,
    WorldContamination,
    WorldSpec,
    assemble_world,
    verify_world,
    vocabulary_digest,
    world_fact_base,
)

WORLD_START = date(2026, 1, 1)


@pytest.fixture(scope="module")
def world() -> WorldSpec:
    return assemble_world(7, DEFAULT_PARAMS, WORLD_START)


def test_one_seed_gives_one_world_with_its_provenance(world: WorldSpec) -> None:
    assert world.seed == 7 and world.org.seed == 7
    assert world.generator_version == GENERATOR_VERSION
    assert world.vocabulary_digest == vocabulary_digest()
    assert world.interpreter == (3, 13)
    assert len(world.scenarios) == 10


def test_plan_slices_and_scenarios_agree(world: WorldSpec) -> None:
    for row, window, scenario in zip(world.plan, world.slices, world.scenarios, strict=True):
        assert scenario.key.scenario_id == row.scenario_id
        assert scenario.key.scenario_class is row.scenario_class
        assert scenario.key.modifiers == row.modifiers
        assert scenario.spec.window == window
    for earlier, later in zip(world.slices, world.slices[1:], strict=False):
        assert earlier.end < later.start


def test_ids_are_minted_world_wide(world: WorldSpec) -> None:
    leaves = [p.entity.id for s in world.scenarios for p in s.owned.leaves]
    assert len(set(leaves)) == len(leaves)
    tickets = [p.entity.id for s in world.scenarios for p in s.owned.work_items]
    assert len(set(tickets)) == len(tickets)


def test_the_fact_base_holds_every_scenario_and_the_world_is_clean(world: WorldSpec) -> None:
    for scenario in world.scenarios:
        assert any(
            f.evidence.target.id == scenario.spec.leave_id for f in world.facts.facts
        )
    assert verify_world(world.facts, world.scenarios, world.org) == ()


def test_the_same_inputs_give_an_equal_world() -> None:
    assert assemble_world(3, DEFAULT_PARAMS, WORLD_START) == assemble_world(
        3, DEFAULT_PARAMS, WORLD_START
    )


def test_a_foreign_record_that_flips_a_verdict_is_named_with_its_owner(world: WorldSpec) -> None:
    # Scenario 2 plants a leave for scenario 1's viable cover over scenario 1's leave: locally
    # both scenarios are fine, together the cover is away and scenario 1's key is wrong.
    first, second = world.scenarios[0], world.scenarios[1]
    (expected, *_) = first.key.impacts
    cover = next(a.employee_id for a in expected.must_assess if a.verdict is Verdict.VIABLE)
    span = first.investigated_leave.span
    foreign = Leave(
        leave_id(999), cover, span.start, span.end, LeaveKind.SICK, LeaveStatus.APPROVED
    )
    planted = Planted(foreign, first.spec.window.start)
    tampered = replace(
        second, owned=replace(second.owned, leaves=(*second.owned.leaves, planted))
    )
    scenarios = (first, tampered, *world.scenarios[2:])
    facts = world_fact_base(world.org, WORLD_START, scenarios)
    findings = verify_world(facts, scenarios, world.org)
    assert findings
    finding = findings[0]
    assert finding.scenario_id == first.key.scenario_id
    assert finding.subject == cover and finding.expected == "viable"
    assert finding.actual.startswith("non_viable")
    (culprit,) = finding.foreign
    assert culprit.entity_id == "leave_999" and culprit.owner == second.key.scenario_id
    assert culprit.observable_from == first.spec.window.start
    with pytest.raises(WorldContamination, match="leave_999 \\(owned by scenario_002"):
        raise WorldContamination(findings)


def test_a_key_whose_required_sources_no_longer_hold_is_named_with_no_verdict_moved(
    world: WorldSpec,
) -> None:
    # The whole-world check compares the key's required sources with the rule's answer
    # over the assembled world on every stable day, separately from verdicts and outcomes.
    # Under the structured tier's rules no foreign record can move dependence without
    # moving a verdict — the HR record and the tracker are required by every deadline
    # through the leave and the ticket themselves — so the mechanism is pinned on a key
    # whose recorded sources are stale by one; the foreign-fact case joins with the first
    # class whose dependence rests on a source no artifact of its own requires.
    first = world.scenarios[0]
    stale_key = replace(first.key, required_sources=first.key.required_sources[1:])
    stale = replace(first, key=stale_key)
    scenarios = (stale, *world.scenarios[1:])
    findings = verify_world(world.facts, scenarios, world.org)
    assert findings and all(f.subject == "required_sources" for f in findings)
    assert len(findings) == first.key.stable_interval.days
    finding = findings[0]
    assert finding.scenario_id == first.key.scenario_id
    assert finding.expected == "[" + ", ".join(s.value for s in stale_key.required_sources) + "]"
    assert finding.actual == "[" + ", ".join(s.value for s in first.key.required_sources) + "]"
    assert finding.foreign == ()
