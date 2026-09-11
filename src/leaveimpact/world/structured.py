"""The structured tier's scenario classes: every answer-relevant fact sits in a structured field.

Tier 1 tests tool use, temporal filtering, joins across systems and the deterministic
candidate check, with no prose to read (DESIGN, "The first golden set"). Three classes:
``structured_deadline`` (a ticket the leaver owns falls due during the leave),
``structured_meeting`` (a meeting the leaver attends falls inside it) and
``structured_mixed`` (both, on one leave).

A class here is deliberately the smallest real thing: no policy clause, no prose, no
conflict, no planted unknown. Its near-misses are structural, and each class has the one
its impact kind affords. For a deadline the rule asks a component question, so a fellow
member of the ticket's component is the obvious cover and is authored viable, while a
teammate of the leaver outside that component is authored non-viable for the component
criterion — the "same team against relevant component" trap the world's shape section
names. For a meeting the rule asks no component question — anyone available on the
meeting's day can stand in — so the trap is availability: a teammate who attends another
event overlapping the meeting is authored non-viable, beside a free teammate authored
viable. Being on leave over that day is the concurrent-leave modifier's business, not a
class's. The mixed class composes the two and authors exactly one person both ways —
non-viable for the ticket, viable for the meeting — which is the point of planting both
on one leave: an assessment keys on the impact, and a grader that scored per person
would miss it.

Anything that makes the cover harder (a concurrent leave, a resolved look-alike, a
meeting on a timezone boundary) is a modifier's business, so the classes stay orthogonal
to them. Titles are templates, not vocabulary: structured-shaped text the generator
writes from a fixed phrase and a component's or team's name, exactly as DESIGN says
nothing is learned from paying a model for "Release planning — Payments API".
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from random import Random
from types import MappingProxyType

from leaveimpact.core.claims import (
    AssessmentReason,
    CoverageActionKind,
    ImpactKey,
    ImpactSubtype,
    Verdict,
)
from leaveimpact.core.entities import CalendarEvent, Component, Employee, Leave, Team, WorkItem
from leaveimpact.core.enums import LeaveKind, LeaveStatus, WorkItemStatus
from leaveimpact.core.refs import event_ref, work_item_ref
from leaveimpact.core.worldtime import zone
from leaveimpact.world.construction import Construction, Draft, Frame, ScenarioClass
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.scenario import (
    AuthoredVerdict,
    ExpectedImpact,
    OwnedEntities,
    Planted,
    ScenarioClassName,
    Tier,
)

TICKET_TITLES: tuple[str, ...] = (
    "{component}: upgrade the client library",
    "{component}: rotate the signing keys",
    "{component}: migrate the retry queue",
    "{component}: close the audit findings",
    "{component}: cut over to the new gateway",
)

MEETING_TITLES: tuple[str, ...] = (
    "{team}: release go/no-go",
    "{team}: sprint review",
    "{team}: customer escalation sync",
    "{team}: quarterly planning",
    "{team}: incident retrospective",
)

OVERLAP_TITLES: tuple[str, ...] = (
    "Vendor security review",
    "Hiring panel",
    "Architecture forum",
    "Budget review with finance",
)

MEETING_HOURS: tuple[int, ...] = (9, 10, 11, 13, 14, 15, 16)
"""Working-hour starts in the reference zone; a meeting lasts one hour."""

MEETING_LENGTH = timedelta(hours=1)
OVERLAP_OFFSET = timedelta(minutes=30)


# --- The classes ----------------------------------------------------------------------


class StructuredDeadline:
    """A ticket the leaver owns falls due during the leave; who in its component can take it over?

    Admissible constructions, in canonical order: for each component (org order), for
    each member as leaver (id order), for each other member as the viable cover (id
    order), with the first teammate of the leaver outside the component as the
    structural near-miss. The organization affords the class whenever some component
    holds two people one of whom has a teammate outside it — an org without that shape
    fails by name.
    """

    name = ScenarioClassName.STRUCTURED_DEADLINE
    tier = Tier.STRUCTURED
    affordance = "a component with two members, one of whom has a teammate outside the component"

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        return tuple(_deadline_construction(*roles) for roles in _deadline_roles(org))


class StructuredMeeting:
    """A meeting the leaver attends falls during the leave; which teammate can stand in?

    Admissible constructions, in canonical order: for each team (org order), for each
    member as leaver (id order), for each other member as the free cover (id order),
    with the first remaining teammate as the busy near-miss, who attends an overlapping
    event the class plants. A colleague from another team attends the meeting too, so it
    reads as a meeting and not as a one-person calendar entry; that colleague is not
    authored. The organization affords the class whenever some team has three members —
    an org without one fails by name.
    """

    name = ScenarioClassName.STRUCTURED_MEETING
    tier = Tier.STRUCTURED
    affordance = "a team with three members"

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        return tuple(
            _meeting_construction(team, leaver, cover, busy, _outside(org, team))
            for team, leaver, cover, busy in _meeting_roles(org)
        )


class StructuredMixed:
    """A ticket falls due and a meeting falls during the same leave: two impacts, one leaver.

    A two-impact scenario in which exactly one authored person is non-viable for one
    impact and viable for the other, proving that an assessment is identified by the pair
    of impact and employee. That person is the deadline's near-miss, the teammate outside
    the component, who is the meeting's free cover; the deadline's roles are the deadline
    class's and the busy near-miss is the first further teammate who is neither the
    outsider nor the ticket's cover. Exactly one, not at least one: a cover who is also
    the busy teammate would be a second cross-impact person, a composite interaction the
    composite classes own, and with two mixed rows in Tier 1 the class must not acquire
    it by incidental team topology (the step 8 part 1 review ruling). Canonical order is
    the deadline class's, so the organization affords the class whenever it affords a
    deadline whose leaver has a further teammate besides the outsider and the cover.
    """

    name = ScenarioClassName.STRUCTURED_MIXED
    tier = Tier.STRUCTURED
    affordance = (
        "a component with two members, one of whom has a teammate outside the component "
        "and a further teammate who is neither that outsider nor the cover"
    )

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        constructions: list[Construction] = []
        for component, leaver, cover, outsider in _deadline_roles(org):
            further = [
                teammate
                for teammate in org.members_of(leaver.team_id)
                if teammate.id not in (leaver.id, outsider.id, cover.id)
            ]
            if not further:
                continue
            team = _team_of(org, leaver)
            constructions.append(
                _mixed_construction(
                    component, team, leaver, cover, outsider, further[0], _outside(org, team)
                )
            )
        return tuple(constructions)


SCENARIO_CLASSES: Mapping[ScenarioClassName, ScenarioClass] = MappingProxyType(
    {
        ScenarioClassName.STRUCTURED_DEADLINE: StructuredDeadline(),
        ScenarioClassName.STRUCTURED_MEETING: StructuredMeeting(),
        ScenarioClassName.STRUCTURED_MIXED: StructuredMixed(),
    }
)
"""Every built class by name, the instances the world plan constructs from."""


# --- Role selection: the queries over the static organization ---------------------------


def _deadline_roles(org: OrgSpec) -> list[tuple[Component, Employee, Employee, Employee]]:
    """(component, leaver, viable cover, teammate outside the component), canonical order."""
    by_id = {employee.id: employee for employee in org.employees}
    roles: list[tuple[Component, Employee, Employee, Employee]] = []
    for component in org.components:
        members = set(component.member_ids)
        for leaver_id in component.member_ids:
            leaver = by_id[leaver_id]
            outsiders = [
                teammate
                for teammate in org.members_of(leaver.team_id)
                if teammate.id not in members
            ]
            if not outsiders:
                continue
            for cover_id in component.member_ids:
                if cover_id != leaver_id:
                    roles.append((component, leaver, by_id[cover_id], outsiders[0]))
    return roles


def _meeting_roles(org: OrgSpec) -> list[tuple[Team, Employee, Employee, Employee]]:
    """(team, leaver, free cover, busy teammate), canonical order."""
    roles: list[tuple[Team, Employee, Employee, Employee]] = []
    for team in org.teams:
        members = org.members_of(team.id)
        if len(members) < 3:
            continue
        for leaver in members:
            for cover in members:
                if cover.id == leaver.id:
                    continue
                busy = next(m for m in members if m.id not in (leaver.id, cover.id))
                roles.append((team, leaver, cover, busy))
    return roles


def _team_of(org: OrgSpec, employee: Employee) -> Team:
    return next(team for team in org.teams if team.id == employee.team_id)


def _outside(org: OrgSpec, team: Team) -> tuple[Employee, ...]:
    """Everyone not on ``team``, in id order — the pool a meeting's other attendee comes from."""
    return tuple(employee for employee in org.employees if employee.team_id != team.id)


# --- Constructions: recipes over the planting helpers ---------------------------------


def _deadline_construction(
    component: Component, leaver: Employee, cover: Employee, outsider: Employee
) -> Construction:
    def plant(frame: Frame, rng: Random) -> Draft:
        leave = _plant_leave(frame, leaver)
        ticket = _plant_ticket(frame, rng, component, leaver)
        owned = OwnedEntities(leaves=(leave,), work_items=(ticket,))
        return Draft(owned, leave.entity.id, (_deadline_impact(leave, ticket, cover, outsider),))

    return plant


def _meeting_construction(
    team: Team, leaver: Employee, cover: Employee, busy: Employee, outside: tuple[Employee, ...]
) -> Construction:
    def plant(frame: Frame, rng: Random) -> Draft:
        leave = _plant_leave(frame, leaver)
        meeting = _plant_meeting(frame, rng, team, leaver, outside)
        overlap = _plant_overlap(frame, rng, meeting, busy)
        owned = OwnedEntities(leaves=(leave,), events=(meeting, overlap))
        return Draft(owned, leave.entity.id, (_meeting_impact(leave, meeting, cover, busy),))

    return plant


def _mixed_construction(
    component: Component,
    team: Team,
    leaver: Employee,
    cover: Employee,
    outsider: Employee,
    busy: Employee,
    outside: tuple[Employee, ...],
) -> Construction:
    def plant(frame: Frame, rng: Random) -> Draft:
        leave = _plant_leave(frame, leaver)
        ticket = _plant_ticket(frame, rng, component, leaver)
        meeting = _plant_meeting(frame, rng, team, leaver, outside)
        overlap = _plant_overlap(frame, rng, meeting, busy)
        owned = OwnedEntities(leaves=(leave,), work_items=(ticket,), events=(meeting, overlap))
        impacts = (
            _deadline_impact(leave, ticket, cover, outsider),
            _meeting_impact(leave, meeting, outsider, busy),
        )
        return Draft(owned, leave.entity.id, impacts)

    return plant


# --- Planting helpers: one record each, visible from the slice start ---------------------


def _plant_leave(frame: Frame, leaver: Employee) -> Planted[Leave]:
    leave = Leave(
        frame.ids.leave(),
        leaver.id,
        frame.leave.start,
        frame.leave.end,
        LeaveKind.ANNUAL,
        LeaveStatus.APPROVED,
    )
    return Planted(leave, frame.window.start)


def _plant_ticket(
    frame: Frame, rng: Random, component: Component, leaver: Employee
) -> Planted[WorkItem]:
    ticket = WorkItem(
        id=frame.ids.work_item(),
        title=rng.choice(TICKET_TITLES).format(component=component.name),
        owner_id=leaver.id,
        status=WorkItemStatus.IN_PROGRESS,
        component_id=component.id,
        opened_on=frame.window.start,
        resolved_on=None,
        due_on=_day_in_leave(frame, rng),
        comments=(),
    )
    return Planted(ticket, frame.window.start)


def _plant_meeting(
    frame: Frame, rng: Random, team: Team, leaver: Employee, outside: tuple[Employee, ...]
) -> Planted[CalendarEvent]:
    """A one-hour meeting on a working hour of a leave day, read in the reference zone."""
    start = datetime.combine(
        _day_in_leave(frame, rng),
        datetime.min.time().replace(hour=rng.choice(MEETING_HOURS)),
        tzinfo=zone(frame.reference_timezone),
    )
    attendees = (leaver.id, rng.choice(outside).id) if outside else (leaver.id,)
    meeting = CalendarEvent(
        id=frame.ids.event(),
        title=rng.choice(MEETING_TITLES).format(team=team.name),
        start=start,
        end=start + MEETING_LENGTH,
        attendee_ids=attendees,
    )
    return Planted(meeting, frame.window.start)


def _plant_overlap(
    frame: Frame, rng: Random, meeting: Planted[CalendarEvent], busy: Employee
) -> Planted[CalendarEvent]:
    """The event that makes ``busy`` unavailable: half an hour into the meeting, one hour long."""
    start = meeting.entity.start + OVERLAP_OFFSET
    overlap = CalendarEvent(
        id=frame.ids.event(),
        title=rng.choice(OVERLAP_TITLES),
        start=start,
        end=start + MEETING_LENGTH,
        attendee_ids=(busy.id,),
    )
    return Planted(overlap, frame.window.start)


def _day_in_leave(frame: Frame, rng: Random) -> date:
    return frame.leave.start + timedelta(days=rng.randrange(frame.leave.days))


# --- Expectations: what the key authors for each impact ---------------------------------


def _deadline_impact(
    leave: Planted[Leave], ticket: Planted[WorkItem], cover: Employee, outsider: Employee
) -> ExpectedImpact:
    impact = ImpactKey(leave.entity.id, ImpactSubtype.DEADLINE, work_item_ref(ticket.entity.id))
    must_assess = (
        AuthoredVerdict(cover.id, Verdict.VIABLE),
        AuthoredVerdict(outsider.id, Verdict.NON_VIABLE, (AssessmentReason.COMPONENT,)),
    )
    return ExpectedImpact(impact, CoverageActionKind.ASSIGN, must_assess)


def _meeting_impact(
    leave: Planted[Leave], meeting: Planted[CalendarEvent], cover: Employee, busy: Employee
) -> ExpectedImpact:
    impact = ImpactKey(leave.entity.id, ImpactSubtype.MEETING, event_ref(meeting.entity.id))
    must_assess = (
        AuthoredVerdict(cover.id, Verdict.VIABLE),
        AuthoredVerdict(busy.id, Verdict.NON_VIABLE, (AssessmentReason.AVAILABILITY,)),
    )
    return ExpectedImpact(impact, CoverageActionKind.ASSIGN, must_assess)
