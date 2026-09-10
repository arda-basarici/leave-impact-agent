"""The first real class and modifier through the framework: over a sweep of seeds the
structured-deadline scenario has the shape its class promises, the already-resolved near-miss
lands in the key with its reason and leaves the outcome alone, and the whole construction is
equal for equal inputs."""

from collections.abc import Sequence
from datetime import date, timedelta
from random import Random

import pytest

from leaveimpact.core import (
    AssessmentReason,
    CoverageActionKind,
    ImpactSubtype,
    Source,
    Verdict,
    WorkItemStatus,
)
from leaveimpact.core.ids import scenario_id
from leaveimpact.world import (
    DEFAULT_PARAMS,
    DistractorReason,
    Draft,
    Minting,
    Modifier,
    ModifierName,
    OrgSpec,
    OwnedEntities,
    Scenario,
    allocate_slices,
    construct,
    generate_org,
)
from leaveimpact.world.modifiers import AlreadyResolved
from leaveimpact.world.structured import TICKET_TITLES, StructuredDeadline

ORG = generate_org(7, DEFAULT_PARAMS)
WORLD_START = date(2026, 1, 1)
SLICES = allocate_slices(Random(0), 30, WORLD_START)
TZ = "Europe/Istanbul"
SEEDS = range(1, 21)


def _scenario(seed: int, modifiers: Sequence[Modifier] = (), org: OrgSpec = ORG) -> Scenario:
    return construct(
        StructuredDeadline(),
        modifiers,
        org,
        scenario_id=scenario_id(seed),
        window=SLICES[seed % len(SLICES)],
        world_start=WORLD_START,
        reference_timezone=TZ,
        ids=Minting(),
        rng=Random(seed),
    )


def test_the_org_affords_the_class_in_a_canonical_order() -> None:
    constructions = StructuredDeadline().admissible(ORG)
    assert len(constructions) > 1
    assert len(StructuredDeadline().admissible(ORG)) == len(constructions)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_scenario_has_the_shape_the_class_promises(seed: int) -> None:
    scenario = _scenario(seed)
    (expected,) = scenario.key.impacts
    assert expected.key.subtype is ImpactSubtype.DEADLINE
    assert expected.outcome is CoverageActionKind.ASSIGN
    verdicts = {authored.verdict: authored for authored in expected.must_assess}
    assert set(verdicts) == {Verdict.VIABLE, Verdict.NON_VIABLE}
    assert verdicts[Verdict.NON_VIABLE].reasons == (AssessmentReason.COMPONENT,)
    leaver = scenario.investigated_leave.employee_id
    (ticket,) = [p.entity for p in scenario.owned.work_items]
    assert ticket.owner_id == leaver and ticket.status is WorkItemStatus.IN_PROGRESS
    assert scenario.investigated_leave.span.contains(ticket.due_on or date.min)
    assert {Source.FRAPPE, Source.JIRA} <= set(scenario.key.required_sources)
    assert scenario.key.stable_interval.contains(scenario.spec.today)
    component = next(c for c in ORG.components if c.id == ticket.component_id)
    assert ticket.title in {template.format(component=component.name) for template in TICKET_TITLES}


def test_the_near_miss_is_a_teammate_outside_the_component() -> None:
    scenario = _scenario(3)
    (expected,) = scenario.key.impacts
    ticket = scenario.owned.work_items[0].entity
    component = next(c for c in ORG.components if c.id == ticket.component_id)
    by_id = {e.id: e for e in ORG.employees}
    leaver = by_id[scenario.investigated_leave.employee_id]
    for authored in expected.must_assess:
        person = by_id[authored.employee_id]
        if authored.verdict is Verdict.VIABLE:
            assert person.id in component.member_ids
        else:
            assert person.id not in component.member_ids
            assert person.team_id == leaver.team_id


def test_the_same_inputs_give_an_equal_scenario() -> None:
    assert _scenario(4) == _scenario(4)
    assert _scenario(4) != _scenario(5)


@pytest.mark.parametrize("seed", SEEDS)
def test_already_resolved_plants_a_named_look_alike_and_the_outcome_survives(seed: int) -> None:
    plain, shadowed = _scenario(seed), _scenario(seed, (AlreadyResolved(),))
    assert shadowed.key.modifiers == (ModifierName.ALREADY_RESOLVED,)
    (distractor,) = shadowed.key.distractors
    assert distractor.reason is DistractorReason.ALREADY_RESOLVED
    (expected,) = shadowed.key.impacts
    assert expected.outcome is plain.key.impacts[0].outcome
    assert expected.must_assess == plain.key.impacts[0].must_assess
    open_ticket, done = (p.entity for p in shadowed.owned.work_items)
    assert distractor.entity.id == done.id and done.id != expected.key.artifact.id
    assert done.status is WorkItemStatus.DONE and done.resolved_on is not None
    assert done.resolved_on < shadowed.spec.today
    assert done.owner_id == open_ticket.owner_id and done.component_id == open_ticket.component_id
    assert shadowed.investigated_leave.span.contains(done.due_on or date.min)


def test_a_draft_without_an_open_ticket_affords_no_resolved_look_alike() -> None:
    scenario = _scenario(1)
    only_the_leave = OwnedEntities(leaves=scenario.owned.leaves)
    draft = Draft(only_the_leave, scenario.spec.leave_id, scenario.key.impacts)
    assert AlreadyResolved().admissible(ORG, draft) == ()


def test_slices_keep_scenarios_apart_in_time() -> None:
    first, second = _scenario(1), _scenario(2)
    gap = second.spec.window.start - first.spec.window.end
    assert gap >= timedelta(days=1)
