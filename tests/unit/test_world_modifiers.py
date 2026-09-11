"""The four Tier 1 modifiers over every Tier 1 class and a sweep of seeds: each plants what it
promises and names it, leaves the class's outcome alone, changes exactly the verdicts it
declares, fails by name when the affordance is missing; and the declared compatibility holds
both ways — every compatible pair composes with its class, every declared incompatibility is
an empty affordance — which is what the world plan relies on."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import date, timedelta
from itertools import combinations
from random import Random

import pytest

from leaveimpact.core import AssessmentReason, EntityKind, LeaveKind, Verdict
from leaveimpact.core.ids import scenario_id
from leaveimpact.core.worldtime import local_date
from leaveimpact.world import (
    COMPATIBLE_MODIFIERS,
    DEFAULT_PARAMS,
    MODIFIERS,
    AlreadyResolved,
    ConcurrentLeave,
    DistractorReason,
    Draft,
    Minting,
    MissingAffordance,
    Modifier,
    ModifierName,
    OrgSpec,
    OutsideWindow,
    Scenario,
    ScenarioClass,
    StructuredDeadline,
    StructuredMeeting,
    StructuredMixed,
    TimezoneBoundary,
    WrongTeam,
    allocate_slices,
    construct,
    gap_at,
    generate_org,
)

ORG = generate_org(7, DEFAULT_PARAMS)
WORLD_START = date(2026, 1, 1)
SLICES = allocate_slices(Random(0), 30, WORLD_START)
TZ = ORG.params.reference_timezone
SEEDS = range(1, 21)
CLASSES: tuple[ScenarioClass, ...] = (StructuredDeadline(), StructuredMeeting(), StructuredMixed())
BY_ID = {employee.id: employee for employee in ORG.employees}
COMPATIBLE_PAIRS = [
    (scenario_class, MODIFIERS[first], MODIFIERS[second])
    for scenario_class in CLASSES
    for first, second in combinations(sorted(COMPATIBLE_MODIFIERS[scenario_class.name]), 2)
]
COMPATIBLE_PAIR_IDS = [
    f"{c.name.value}:{a.name.value}+{b.name.value}" for c, a, b in COMPATIBLE_PAIRS
]


def _scenario(
    seed: int, scenario_class: ScenarioClass, modifiers: Sequence[Modifier] = (), org: OrgSpec = ORG
) -> Scenario:
    return construct(
        scenario_class,
        modifiers,
        org,
        scenario_id=scenario_id(seed),
        window=SLICES[seed % len(SLICES)],
        world_start=WORLD_START,
        reference_timezone=org.params.reference_timezone,
        ids=Minting(),
        rng=Random(seed),
    )


def _class_and_seed() -> list[tuple[ScenarioClass, int]]:
    return [(scenario_class, seed) for scenario_class in CLASSES for seed in SEEDS]


CLASS_AND_SEED = _class_and_seed()
CLASS_AND_SEED_IDS = [f"{c.name.value}-{seed}" for c, seed in CLASS_AND_SEED]


@pytest.mark.parametrize(("scenario_class", "seed"), CLASS_AND_SEED, ids=CLASS_AND_SEED_IDS)
def test_outside_window_shadows_the_artifact_a_day_outside_the_leave(
    scenario_class: ScenarioClass, seed: int
) -> None:
    plain = _scenario(seed, scenario_class)
    shadowed = _scenario(seed, scenario_class, (OutsideWindow(),))
    assert shadowed.key.impacts == plain.key.impacts
    (distractor,) = shadowed.key.distractors
    assert distractor.reason is DistractorReason.OUTSIDE_WINDOW
    leave = shadowed.investigated_leave
    edges = {leave.start - timedelta(days=1), leave.end + timedelta(days=1)}
    if distractor.entity.kind is EntityKind.WORK_ITEM:
        look_alike = next(
            p.entity for p in shadowed.owned.work_items if p.entity.id == distractor.entity.id
        )
        assert look_alike.owner_id == leave.employee_id and look_alike.due_on in edges
        original = next(p.entity for p in plain.owned.work_items)
        assert look_alike.component_id == original.component_id
    else:
        event = next(p.entity for p in shadowed.owned.events if p.entity.id == distractor.entity.id)
        assert leave.employee_id in event.attendee_ids
        assert local_date(event.start, TZ) in edges


@pytest.mark.parametrize(("scenario_class", "seed"), CLASS_AND_SEED, ids=CLASS_AND_SEED_IDS)
def test_wrong_team_shadows_the_artifact_with_another_teams(
    scenario_class: ScenarioClass, seed: int
) -> None:
    plain = _scenario(seed, scenario_class)
    shadowed = _scenario(seed, scenario_class, (WrongTeam(),))
    assert shadowed.key.impacts == plain.key.impacts
    (distractor,) = shadowed.key.distractors
    assert distractor.reason is DistractorReason.WRONG_TEAM
    leave = shadowed.investigated_leave
    leaver = BY_ID[leave.employee_id]
    if distractor.entity.kind is EntityKind.WORK_ITEM:
        look_alike = next(
            p.entity for p in shadowed.owned.work_items if p.entity.id == distractor.entity.id
        )
        original = next(p.entity for p in plain.owned.work_items)
        assert look_alike.component_id == original.component_id
        assert BY_ID[look_alike.owner_id].team_id != leaver.team_id
        assert leave.span.contains(look_alike.due_on or date.min)
    else:
        event = next(p.entity for p in shadowed.owned.events if p.entity.id == distractor.entity.id)
        assert leave.employee_id not in event.attendee_ids
        assert leaver.team_id not in {BY_ID[a].team_id for a in event.attendee_ids}
        assert leave.span.contains(local_date(event.start, TZ))


@pytest.mark.parametrize(("scenario_class", "seed"), CLASS_AND_SEED, ids=CLASS_AND_SEED_IDS)
def test_concurrent_leave_sends_a_viable_candidate_away_and_declares_every_verdict_it_changes(
    scenario_class: ScenarioClass, seed: int
) -> None:
    plain = _scenario(seed, scenario_class)
    pressed = _scenario(seed, scenario_class, (ConcurrentLeave(),))
    assert pressed.key.distractors == ()
    investigated, concurrent = (p.entity for p in pressed.owned.leaves)
    assert concurrent.kind is LeaveKind.SICK and concurrent.span == investigated.span
    away = concurrent.employee_id
    plain_by_key = {expected.key: expected for expected in plain.key.impacts}
    was_viable_somewhere = False
    for expected in pressed.key.impacts:
        before = plain_by_key[expected.key]
        assert expected.outcome is before.outcome
        for authored in expected.must_assess:
            previous = next(a for a in before.must_assess if a.employee_id == authored.employee_id)
            if authored.employee_id != away:
                assert authored == previous
                continue
            was_viable_somewhere |= previous.verdict is Verdict.VIABLE
            assert authored.verdict is Verdict.NON_VIABLE
            assert AssessmentReason.AVAILABILITY in authored.reasons
            assert set(previous.reasons) <= set(authored.reasons)
            assert authored.reasons == tuple(sorted(authored.reasons, key=lambda r: r.value))
    assert was_viable_somewhere


def test_concurrent_leave_needs_a_fallback_in_the_tickets_component() -> None:
    scenario = _scenario(1, StructuredDeadline())
    ticket = scenario.owned.work_items[0].entity
    (expected,) = scenario.key.impacts
    cover = next(a.employee_id for a in expected.must_assess if a.verdict is Verdict.VIABLE)
    two_members = tuple(
        replace(c, member_ids=(scenario.investigated_leave.employee_id, cover))
        if c.id == ticket.component_id
        else c
        for c in ORG.components
    )
    thin = replace(ORG, components=two_members)
    draft = Draft(scenario.owned, scenario.spec.leave_id, scenario.key.impacts)
    assert ConcurrentLeave().admissible(thin, draft) == ()


@pytest.mark.parametrize(("scenario_class", "seed"), CLASS_AND_SEED, ids=CLASS_AND_SEED_IDS)
def test_timezone_boundary_dates_the_event_outside_the_leave_only_in_the_reference_zone(
    scenario_class: ScenarioClass, seed: int
) -> None:
    plain = _scenario(seed, scenario_class)
    edged = _scenario(seed, scenario_class, (TimezoneBoundary(),))
    assert edged.key.impacts == plain.key.impacts
    (distractor,) = edged.key.distractors
    assert distractor.reason is DistractorReason.TIMEZONE_BOUNDARY
    leave = edged.investigated_leave
    event = next(p.entity for p in edged.owned.events if p.entity.id == distractor.entity.id)
    assert leave.employee_id in event.attendee_ids
    # The far attendee is the other one, or the leaver alone when the leaver is the far seat.
    others = [a for a in event.attendee_ids if a != leave.employee_id]
    colleague = BY_ID[others[0]] if others else BY_ID[leave.employee_id]
    reference_day = local_date(event.start, TZ)
    assert not leave.span.contains(reference_day)
    assert reference_day in {leave.start - timedelta(days=1), leave.end + timedelta(days=1)}
    assert leave.span.contains(local_date(event.start, colleague.timezone))
    assert gap_at(colleague.timezone, TZ, event.start) >= timedelta(
        hours=ORG.params.timezone_gap_hours
    )


def test_timezone_boundary_fails_by_name_when_nobody_is_far() -> None:
    home = tuple(replace(e, timezone=TZ, location="Istanbul", country="TR") for e in ORG.employees)
    everyone_home = replace(ORG, employees=home)
    with pytest.raises(MissingAffordance, match="timezone_boundary"):
        _scenario(1, StructuredDeadline(), (TimezoneBoundary(),), org=everyone_home)


def test_the_compatibility_declaration_covers_every_class_and_modifier() -> None:
    assert set(COMPATIBLE_MODIFIERS) == {scenario_class.name for scenario_class in CLASSES}
    assert set(MODIFIERS) == set(ModifierName)
    assert all(modifiers <= set(MODIFIERS) for modifiers in COMPATIBLE_MODIFIERS.values())


@pytest.mark.parametrize(
    ("scenario_class", "first", "second"), COMPATIBLE_PAIRS, ids=COMPATIBLE_PAIR_IDS
)
def test_every_compatible_pair_composes_with_its_class(
    scenario_class: ScenarioClass, first: Modifier, second: Modifier
) -> None:
    pair = (first, second)
    for seed in range(1, 11):
        scenario = _scenario(seed, scenario_class, pair)
        assert scenario.key.modifiers == tuple(modifier.name for modifier in pair)
        distracting = sum(modifier.name is not ModifierName.CONCURRENT_LEAVE for modifier in pair)
        assert len(scenario.key.distractors) == distracting


@pytest.mark.parametrize("seed", SEEDS)
def test_a_declared_incompatibility_is_an_empty_affordance(seed: int) -> None:
    # The one exclusion today: the meeting class plants no ticket for the leaver to have
    # closed, so already_resolved is incompatible by design, never a failed composition.
    assert ModifierName.ALREADY_RESOLVED not in COMPATIBLE_MODIFIERS[StructuredMeeting().name]
    scenario = _scenario(seed, StructuredMeeting())
    draft = Draft(scenario.owned, scenario.spec.leave_id, scenario.key.impacts)
    assert AlreadyResolved().admissible(ORG, draft) == ()
