"""The Tier 1 classes and the first modifier through the framework: over a sweep of seeds each
structured scenario has the shape its class promises — the deadline's component trap, the
meeting's availability trap, the mixed class's one person authored both ways — the
already-resolved near-miss lands in the key with its reason and leaves the outcome alone, an
org without a class's affordance fails by name, and the whole construction is equal for equal
inputs."""

from collections.abc import Sequence
from dataclasses import replace
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
    MissingAffordance,
    Modifier,
    ModifierName,
    OrgSpec,
    OwnedEntities,
    Planted,
    Scenario,
    ScenarioClass,
    allocate_slices,
    construct,
    generate_org,
)
from leaveimpact.world.modifiers import AlreadyResolved
from leaveimpact.world.structured import (
    MEETING_HOURS,
    MEETING_TITLES,
    TICKET_TITLES,
    StructuredDeadline,
    StructuredMeeting,
    StructuredMixed,
)

ORG = generate_org(7, DEFAULT_PARAMS)
WORLD_START = date(2026, 1, 1)
SLICES = allocate_slices(Random(0), 30, WORLD_START)
TZ = "Europe/Istanbul"
SEEDS = range(1, 21)
DEADLINE = StructuredDeadline()
CLASSES: tuple[ScenarioClass, ...] = (DEADLINE, StructuredMeeting(), StructuredMixed())


def _scenario(
    seed: int,
    scenario_class: ScenarioClass = DEADLINE,
    modifiers: Sequence[Modifier] = (),
    org: OrgSpec = ORG,
) -> Scenario:
    return construct(
        scenario_class,
        modifiers,
        org,
        scenario_id=scenario_id(seed),
        window=SLICES[seed % len(SLICES)],
        world_start=WORLD_START,
        reference_timezone=TZ,
        ids=Minting(),
        rng=Random(seed),
    )


@pytest.mark.parametrize("scenario_class", CLASSES, ids=lambda c: c.name.value)
def test_the_org_affords_each_class_in_a_canonical_order(scenario_class: ScenarioClass) -> None:
    constructions = scenario_class.admissible(ORG)
    assert len(constructions) > 1
    assert len(scenario_class.admissible(ORG)) == len(constructions)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_deadline_scenario_has_the_shape_the_class_promises(seed: int) -> None:
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


def test_the_deadline_near_miss_is_a_teammate_outside_the_component() -> None:
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


@pytest.mark.parametrize("seed", SEEDS)
def test_the_meeting_scenario_has_the_shape_the_class_promises(seed: int) -> None:
    scenario = _scenario(seed, StructuredMeeting())
    (expected,) = scenario.key.impacts
    assert expected.key.subtype is ImpactSubtype.MEETING
    assert expected.outcome is CoverageActionKind.ASSIGN
    verdicts = {authored.verdict: authored for authored in expected.must_assess}
    assert set(verdicts) == {Verdict.VIABLE, Verdict.NON_VIABLE}
    assert verdicts[Verdict.NON_VIABLE].reasons == (AssessmentReason.AVAILABILITY,)
    by_id = {e.id: e for e in ORG.employees}
    leaver = by_id[scenario.investigated_leave.employee_id]
    meeting, overlap = (p.entity for p in scenario.owned.events)
    assert scenario.owned.work_items == ()
    assert expected.key.artifact.id == meeting.id
    # The meeting sits on a leave day at a working hour, read in the reference zone; the
    # leaver attends it and so does someone from another team, never a teammate.
    day = meeting.span.local_dates(TZ)
    assert day.days == 1 and scenario.investigated_leave.span.contains(day.start)
    assert meeting.start.hour in MEETING_HOURS and meeting.span.duration == timedelta(hours=1)
    assert leaver.id in meeting.attendee_ids
    assert all(by_id[a].team_id != leaver.team_id for a in meeting.attendee_ids if a != leaver.id)
    team = next(t for t in ORG.teams if t.id == leaver.team_id)
    assert meeting.title in {template.format(team=team.name) for template in MEETING_TITLES}
    # The busy teammate attends the overlapping event and nothing else makes them busy;
    # the free teammate attends neither.
    busy, cover = verdicts[Verdict.NON_VIABLE].employee_id, verdicts[Verdict.VIABLE].employee_id
    assert by_id[busy].team_id == leaver.team_id and by_id[cover].team_id == leaver.team_id
    assert overlap.attendee_ids == (busy,) and overlap.span.overlaps(meeting.span)
    assert cover not in meeting.attendee_ids
    assert {Source.FRAPPE, Source.CALENDAR} <= set(scenario.key.required_sources)
    assert scenario.key.stable_interval.contains(scenario.spec.today)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_mixed_scenario_authors_one_teammate_both_ways(seed: int) -> None:
    scenario = _scenario(seed, StructuredMixed())
    by_subtype = {expected.key.subtype: expected for expected in scenario.key.impacts}
    assert set(by_subtype) == {ImpactSubtype.DEADLINE, ImpactSubtype.MEETING}
    deadline, meeting = by_subtype[ImpactSubtype.DEADLINE], by_subtype[ImpactSubtype.MEETING]
    assert {deadline.outcome, meeting.outcome} == {CoverageActionKind.ASSIGN}
    (leave,) = scenario.owned.leaves
    assert deadline.key.leave_id == leave.entity.id == meeting.key.leave_id
    (ticket,) = (p.entity for p in scenario.owned.work_items)
    target, overlap = (p.entity for p in scenario.owned.events)
    assert deadline.key.artifact.id == ticket.id and meeting.key.artifact.id == target.id
    # The teammate outside the component fails the ticket for the component criterion and
    # is the meeting's free cover: the same person, two verdicts, keyed by impact.
    outsider = next(a for a in deadline.must_assess if a.verdict is Verdict.NON_VIABLE)
    assert outsider.reasons == (AssessmentReason.COMPONENT,)
    free = next(a for a in meeting.must_assess if a.verdict is Verdict.VIABLE)
    assert free.employee_id == outsider.employee_id
    busy = next(a for a in meeting.must_assess if a.verdict is Verdict.NON_VIABLE)
    assert busy.reasons == (AssessmentReason.AVAILABILITY,)
    assert overlap.attendee_ids == (busy.employee_id,)
    assert {Source.FRAPPE, Source.JIRA, Source.CALENDAR} <= set(scenario.key.required_sources)
    assert scenario.key.stable_interval.contains(scenario.spec.today)


def test_a_team_without_three_members_affords_no_meeting() -> None:
    two_per_team = tuple(
        member for team in ORG.teams for member in ORG.members_of(team.id)[:2]
    )
    thin = replace(ORG, employees=two_per_team)
    assert StructuredMeeting().admissible(thin) == ()
    with pytest.raises(MissingAffordance, match="structured_meeting.*three members"):
        _scenario(1, StructuredMeeting(), org=thin)


@pytest.mark.parametrize("scenario_class", CLASSES, ids=lambda c: c.name.value)
def test_the_same_inputs_give_an_equal_scenario(scenario_class: ScenarioClass) -> None:
    assert _scenario(4, scenario_class) == _scenario(4, scenario_class)
    assert _scenario(4, scenario_class) != _scenario(5, scenario_class)


@pytest.mark.parametrize("seed", SEEDS)
def test_already_resolved_plants_a_named_look_alike_and_the_outcome_survives(seed: int) -> None:
    plain, shadowed = _scenario(seed), _scenario(seed, modifiers=(AlreadyResolved(),))
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
    # The closed record enters the world on the day it was resolved, never before, and the
    # stable interval cannot start before the world held it.
    (_, done_planted) = shadowed.owned.work_items
    assert done_planted.observable_from == done.resolved_on
    assert shadowed.key.stable_interval.start >= done.resolved_on


@pytest.mark.parametrize("seed", SEEDS)
def test_already_resolved_composes_with_the_mixed_class(seed: int) -> None:
    plain = _scenario(seed, StructuredMixed())
    shadowed = _scenario(seed, StructuredMixed(), (AlreadyResolved(),))
    (distractor,) = shadowed.key.distractors
    assert distractor.reason is DistractorReason.ALREADY_RESOLVED
    assert shadowed.key.impacts == plain.key.impacts


def test_only_an_open_ticket_the_leaver_owns_affords_a_resolved_look_alike() -> None:
    scenario = _scenario(1)
    only_the_leave = OwnedEntities(leaves=scenario.owned.leaves)
    no_ticket = Draft(only_the_leave, scenario.spec.leave_id, scenario.key.impacts)
    assert AlreadyResolved().admissible(ORG, no_ticket) == ()
    (planted,) = scenario.owned.work_items
    someone_else = next(e.id for e in ORG.employees if e.id != planted.entity.owner_id)
    theirs = Planted(replace(planted.entity, owner_id=someone_else), planted.observable_from)
    other_owner = Draft(
        OwnedEntities(leaves=scenario.owned.leaves, work_items=(theirs,)),
        scenario.spec.leave_id,
        scenario.key.impacts,
    )
    assert AlreadyResolved().admissible(ORG, other_owner) == ()


def test_slices_keep_scenarios_apart_in_time() -> None:
    first, second = _scenario(1), _scenario(2)
    gap = second.spec.window.start - first.spec.window.end
    assert gap >= timedelta(days=1)
