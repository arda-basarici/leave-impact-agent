"""The modifiers: orthogonal tags that plant a near-miss or press on the candidates, on any class.

A modifier is written once and composes with any class (the modifier ruling at the
scenario-framework step). It has a class's shape minus an outcome: ``admissible`` returns
the amendments the draft affords, in canonical order, and is empty when the draft lacks
the structure it works on; a chosen amendment plants more owned entities and declares
its effect — distractors named with their reason, verdicts amended for a candidate —
and never touches the class's declared outcome, which the framework re-checks after
composition.

Four distractors and one pressure. ``already_resolved`` shadows a ticket the leaver
owns with a closed look-alike; ``outside_window`` shadows an impact's artifact with the
same shape just outside the leave, the day before or after; ``wrong_team`` shadows it
with an artifact that belongs to another team's person; ``timezone_boundary`` plants an
event at the leave's edge whose calendar date differs between the reference zone, where
truth is read, and an attendee's zone. Each is named in the key with its reason, so a
false positive is graded into the bucket of the mistake that produced it. The one
pressure, ``concurrent_leave``, sends an authored viable candidate on leave over the same
days and declares the verdict it changes, on every impact that candidate is authored for.

Look-alike titles are templates like the classes' own: structured-shaped text from a
fixed phrase and a name, never learned from a model.

``COMPATIBLE_MODIFIERS`` is the class-by-modifier compatibility the world plan reads
(the plan ruling at step 8): a modifier is compatible with a class when every draft the
class produces affords it, and a pair is compatible when both members are — there is no
pair-level table until a pair proves it needs one. The declaration is static because no
draft exists when the plan is made; the seed sweep over every compatible pair and class
is what makes it true, and a declared incompatibility is checked the other way, as an
empty affordance. Today the one exclusion is ``already_resolved`` on the meeting class,
which plants no ticket for the leaver to have closed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from random import Random
from types import MappingProxyType

from leaveimpact.core.claims import AssessmentReason, Verdict
from leaveimpact.core.entities import CalendarEvent, Employee, Leave, Team, WorkItem
from leaveimpact.core.enums import EntityKind, LeaveKind, LeaveStatus, WorkItemStatus
from leaveimpact.core.ids import EmployeeId
from leaveimpact.core.refs import event_ref, work_item_ref
from leaveimpact.core.worldtime import local_date, zone
from leaveimpact.world.construction import Amendment, Draft, Frame, Modifier
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.scenario import (
    AuthoredVerdict,
    DistractorReason,
    ExpectedImpact,
    ModifierEffect,
    ModifierName,
    NamedDistractor,
    OwnedEntities,
    Planted,
    ScenarioClassName,
    VerdictOverride,
)
from leaveimpact.world.zones import gap_at, offset_of

RESOLVED_TITLE_SUFFIX = ", phase one"
OUTSIDE_TICKET_SUFFIXES = {"before": ", groundwork", "after": ", follow-up"}
OUTSIDE_MEETING_SUFFIXES = {"before": " (prep)", "after": " (debrief)"}
WRONG_TEAM_TICKET_TITLES: tuple[str, ...] = (
    "{component}: triage the backlog",
    "{component}: refresh the dashboards",
    "{component}: review the alert thresholds",
)
WRONG_TEAM_MEETING_TITLES: tuple[str, ...] = (
    "{team}: weekly sync",
    "{team}: design review",
    "{team}: on-call handover",
)
BOUNDARY_EVENT_TITLE = "Cross-region sync"
EARLIEST_WORKING_HOUR = time(9, 0)
EVENT_LENGTH = timedelta(hours=1)
MEETING_HOURS: tuple[int, ...] = (9, 10, 11, 13, 14, 15, 16)


# --- Shared readings of a draft ---------------------------------------------------------


def _investigated(draft: Draft) -> Leave:
    return next(p.entity for p in draft.owned.leaves if p.entity.id == draft.investigated)


def _ticket_of(draft: Draft, expected: ExpectedImpact) -> WorkItem | None:
    if expected.key.artifact.kind is not EntityKind.WORK_ITEM:
        return None
    return next(p.entity for p in draft.owned.work_items if p.entity.id == expected.key.artifact.id)


def _meeting_of(draft: Draft, expected: ExpectedImpact) -> CalendarEvent | None:
    if expected.key.artifact.kind is not EntityKind.EVENT:
        return None
    return next(p.entity for p in draft.owned.events if p.entity.id == expected.key.artifact.id)


def _on_day(event: CalendarEvent, day: date, timezone: str) -> CalendarEvent:
    """``event`` moved to ``day`` at the same clock time in ``timezone``."""
    local = event.start.astimezone(zone(timezone))
    start = datetime.combine(day, local.time(), tzinfo=zone(timezone))
    return replace(event, start=start, end=start + event.span.duration)


# --- already_resolved -----------------------------------------------------------------


class AlreadyResolved:
    """A look-alike ticket the leaver already closed: same component, due during the leave, done.

    The near-miss reads as an impact to anyone who filters by owner and due date without
    checking status, and the key names it with the reason so that false positive lands in
    the already-resolved bucket. Admissible over every open ticket the leaver owns in the
    draft, in draft order — a ticket someone else owns is not the leaver's work and would
    make a weak near-miss — so a draft without such a ticket affords nothing.
    """

    name = ModifierName.ALREADY_RESOLVED
    affordance = "an open ticket owned by the leaver"

    def admissible(self, org: OrgSpec, draft: Draft) -> tuple[Amendment, ...]:
        leaver = _investigated(draft).employee_id
        return tuple(
            _resolved_amendment(planted.entity)
            for planted in draft.owned.work_items
            if planted.entity.resolved_on is None and planted.entity.owner_id == leaver
        )


def _resolved_amendment(open_ticket: WorkItem) -> Amendment:
    def amend(draft: Draft, frame: Frame, rng: Random) -> tuple[Draft, ModifierEffect]:
        visible = frame.window.start
        # Resolved before the run's day, so the status and the resolution date agree and
        # no reading of ``now`` inside the stable interval can make it open again. The
        # frame guarantees a day of slice history before now; a frame without one is a
        # placement bug and fails here by name.
        history = (frame.today - visible).days
        if history < 1:
            raise ValueError(
                f"an already-resolved ticket needs a day before now, today is {frame.today}"
            )
        resolved_on = visible + timedelta(days=rng.randrange(history))
        done = replace(
            open_ticket,
            id=frame.ids.work_item(),
            title=open_ticket.title + RESOLVED_TITLE_SUFFIX,
            status=WorkItemStatus.DONE,
            resolved_on=resolved_on,
            due_on=frame.leave.start + timedelta(days=rng.randrange(frame.leave.days)),
            comments=(),
        )
        # Observable from the day it was resolved, not from the slice start: derivation
        # stamps every fact of a record, the status included, with the record's date, and
        # a "done" visible before its own resolution would contradict the world. The
        # earlier open state is not modelled — a state transition is more machinery than
        # this near-miss needs — so the record enters the world already closed.
        planted = OwnedEntities(work_items=(Planted(done, resolved_on),))
        near_miss = NamedDistractor(work_item_ref(done.id), DistractorReason.ALREADY_RESOLVED)
        return draft.extended(owned=planted), ModifierEffect(distractors=(near_miss,))

    return amend


# --- outside_window ---------------------------------------------------------------------


class OutsideWindow:
    """A look-alike of an impact's artifact just outside the leave: the day before or after.

    A ticket the leaver owns due the day before or after, or a meeting the leaver attends
    the day before or after, with the same shape as the impact's own artifact. The
    near-miss reads as an impact to anyone whose date filter is off by a day or who never
    narrows to the leave at all, and the key names it with the outside-window reason.
    Admissible over every impact of the draft, each edge in turn (before, then after), so
    a draft with an impact always affords it; both edge days lie inside the slice by the
    leave's placement, and the amendment fails by name if a frame ever breaks that.
    """

    name = ModifierName.OUTSIDE_WINDOW
    affordance = "an impact whose artifact is a ticket or a meeting"

    def admissible(self, org: OrgSpec, draft: Draft) -> tuple[Amendment, ...]:
        return tuple(
            _outside_amendment(expected, edge)
            for expected in draft.impacts
            for edge in ("before", "after")
            if _ticket_of(draft, expected) is not None or _meeting_of(draft, expected) is not None
        )


def _edge_day(frame: Frame, edge: str) -> date:
    day = (
        frame.leave.start - timedelta(days=1)
        if edge == "before"
        else frame.leave.end + timedelta(days=1)
    )
    if not frame.window.contains(day):
        raise ValueError(f"the {edge} edge {day} falls outside the slice {frame.window}")
    return day


def _outside_amendment(expected: ExpectedImpact, edge: str) -> Amendment:
    def amend(draft: Draft, frame: Frame, rng: Random) -> tuple[Draft, ModifierEffect]:
        day = _edge_day(frame, edge)
        visible = frame.window.start
        ticket = _ticket_of(draft, expected)
        if ticket is not None:
            look_alike = replace(
                ticket,
                id=frame.ids.work_item(),
                title=ticket.title + OUTSIDE_TICKET_SUFFIXES[edge],
                due_on=day,
                comments=(),
            )
            planted = OwnedEntities(work_items=(Planted(look_alike, visible),))
            near_miss = NamedDistractor(
                work_item_ref(look_alike.id), DistractorReason.OUTSIDE_WINDOW
            )
        else:
            meeting = _meeting_of(draft, expected)
            assert meeting is not None
            moved = _on_day(meeting, day, frame.reference_timezone)
            look_alike_event = replace(
                moved, id=frame.ids.event(), title=meeting.title + OUTSIDE_MEETING_SUFFIXES[edge]
            )
            planted = OwnedEntities(events=(Planted(look_alike_event, visible),))
            near_miss = NamedDistractor(
                event_ref(look_alike_event.id), DistractorReason.OUTSIDE_WINDOW
            )
        return draft.extended(owned=planted), ModifierEffect(distractors=(near_miss,))

    return amend


# --- wrong_team -------------------------------------------------------------------------


class WrongTeam:
    """A look-alike of an impact's artifact that belongs to another team's person, not the leaver.

    For a ticket: an open ticket in the same component, due during the leave, owned by a
    component member from another team. For a meeting: a meeting on a leave day held
    under another team's name, attended by that team and never by the leaver. The
    near-miss reads as an impact to anyone who searches the component or the calendar
    date instead of the leaver, and the key names it with the wrong-team reason.
    Admissible over every impact whose look-alike has a holder: a component member from
    another team, or any team other than the leaver's; the holder is drawn inside the
    amendment.
    """

    name = ModifierName.WRONG_TEAM
    affordance = (
        "an impact artifact and a person on another team to hold its look-alike: a member "
        "of the ticket's component from another team, or any other team for a meeting"
    )

    def admissible(self, org: OrgSpec, draft: Draft) -> tuple[Amendment, ...]:
        by_id = {employee.id: employee for employee in org.employees}
        leaver = by_id[_investigated(draft).employee_id]
        amendments: list[Amendment] = []
        for expected in draft.impacts:
            ticket = _ticket_of(draft, expected)
            if ticket is not None:
                component = next(c for c in org.components if c.id == ticket.component_id)
                holders = tuple(
                    by_id[member]
                    for member in component.member_ids
                    if by_id[member].team_id != leaver.team_id
                )
                if holders:
                    amendments.append(_wrong_team_ticket(ticket, component.name, holders))
                continue
            meeting = _meeting_of(draft, expected)
            if meeting is not None:
                other_teams = tuple(team for team in org.teams if team.id != leaver.team_id)
                if other_teams:
                    amendments.append(_wrong_team_meeting(org, other_teams))
        return tuple(amendments)


def _wrong_team_ticket(
    ticket: WorkItem, component_name: str, holders: tuple[Employee, ...]
) -> Amendment:
    def amend(draft: Draft, frame: Frame, rng: Random) -> tuple[Draft, ModifierEffect]:
        holder = rng.choice(holders)
        look_alike = WorkItem(
            id=frame.ids.work_item(),
            title=rng.choice(WRONG_TEAM_TICKET_TITLES).format(component=component_name),
            owner_id=holder.id,
            status=WorkItemStatus.IN_PROGRESS,
            component_id=ticket.component_id,
            opened_on=frame.window.start,
            resolved_on=None,
            due_on=frame.leave.start + timedelta(days=rng.randrange(frame.leave.days)),
            comments=(),
        )
        planted = OwnedEntities(work_items=(Planted(look_alike, frame.window.start),))
        near_miss = NamedDistractor(work_item_ref(look_alike.id), DistractorReason.WRONG_TEAM)
        return draft.extended(owned=planted), ModifierEffect(distractors=(near_miss,))

    return amend


def _wrong_team_meeting(org: OrgSpec, other_teams: tuple[Team, ...]) -> Amendment:
    def amend(draft: Draft, frame: Frame, rng: Random) -> tuple[Draft, ModifierEffect]:
        team = rng.choice(other_teams)
        attendees = tuple(member.id for member in org.members_of(team.id))
        day = frame.leave.start + timedelta(days=rng.randrange(frame.leave.days))
        start = datetime.combine(
            day, time(rng.choice(MEETING_HOURS), 0), tzinfo=zone(frame.reference_timezone)
        )
        look_alike = CalendarEvent(
            id=frame.ids.event(),
            title=rng.choice(WRONG_TEAM_MEETING_TITLES).format(team=team.name),
            start=start,
            end=start + EVENT_LENGTH,
            attendee_ids=attendees,
        )
        planted = OwnedEntities(events=(Planted(look_alike, frame.window.start),))
        near_miss = NamedDistractor(event_ref(look_alike.id), DistractorReason.WRONG_TEAM)
        return draft.extended(owned=planted), ModifierEffect(distractors=(near_miss,))

    return amend


# --- concurrent_leave -------------------------------------------------------------------


class ConcurrentLeave:
    """An authored viable candidate is on leave over the same days: candidate pressure, not a
    distractor.

    The amendment plants an approved sick leave over the investigated leave's span and
    declares the verdict it changes on every impact the candidate is authored for — the
    reasons merged in the rules' order, so a teammate already non-viable for a ticket by
    component becomes non-viable by availability and component. A modifier may never
    change the class's declared outcome, so an amendment is admissible only when the
    impact's structural pool still holds another person: for a ticket, a third member of
    its component; for a meeting, anyone else in the organization. That is a query over
    static structure and deliberately weaker than the rule, which verifies the outcome
    after composition. Admissible per impact, per viable candidate in authored order.
    """

    name = ModifierName.CONCURRENT_LEAVE
    affordance = "an authored viable candidate whose impact has another person to fall back on"

    def admissible(self, org: OrgSpec, draft: Draft) -> tuple[Amendment, ...]:
        leaver = _investigated(draft).employee_id
        amendments: list[Amendment] = []
        for expected in draft.impacts:
            for authored in expected.must_assess:
                if authored.verdict is not Verdict.VIABLE:
                    continue
                if _pool_without(org, draft, expected, leaver, authored.employee_id):
                    amendments.append(_concurrent_amendment(authored.employee_id))
        return tuple(amendments)


def _pool_without(
    org: OrgSpec, draft: Draft, expected: ExpectedImpact, leaver: EmployeeId, who: EmployeeId
) -> bool:
    ticket = _ticket_of(draft, expected)
    if ticket is not None:
        component = next(c for c in org.components if c.id == ticket.component_id)
        return any(member not in (leaver, who) for member in component.member_ids)
    return any(employee.id not in (leaver, who) for employee in org.employees)


def _concurrent_amendment(who: EmployeeId) -> Amendment:
    def amend(draft: Draft, frame: Frame, rng: Random) -> tuple[Draft, ModifierEffect]:
        leave = Leave(
            frame.ids.leave(),
            who,
            frame.leave.start,
            frame.leave.end,
            LeaveKind.SICK,
            LeaveStatus.APPROVED,
        )
        planted = OwnedEntities(leaves=(Planted(leave, frame.window.start),))
        overrides = tuple(
            VerdictOverride(expected.key, _away(authored))
            for expected in draft.impacts
            for authored in expected.must_assess
            if authored.employee_id == who
        )
        return draft.extended(owned=planted), ModifierEffect(verdict_overrides=overrides)

    return amend


def _away(authored: AuthoredVerdict) -> AuthoredVerdict:
    """``authored`` with availability added to its failing reasons, in the rules' order."""
    reasons = sorted({*authored.reasons, AssessmentReason.AVAILABILITY}, key=lambda r: r.value)
    return AuthoredVerdict(authored.employee_id, Verdict.NON_VIABLE, tuple(reasons))


# --- timezone_boundary ------------------------------------------------------------------


class TimezoneBoundary:
    """An event at the leave's edge whose calendar date differs between the reference zone and an
    attendee's zone.

    Truth is read in the reference zone, where the event falls on the day before or the
    day after the leave; in the far attendee's zone — and, for a zone behind the
    reference, in UTC too — it falls inside the leave. An agent that dates calendar
    instants in the wrong zone reports it as an impact, and the key names it with the
    timezone reason. The far colleague makes the instant plausible working time: a
    colleague behind the reference zone gets the after-edge in their late afternoon, a
    colleague ahead the before-edge in the reference zone's late afternoon (the edge
    arithmetic is in the tests; the amendment asserts both readings by name). The leaver
    attends; the colleague is chosen independently of the class's roles (the timezone
    affordance ruling at step 8). Admissible over every employee whose gap from the
    reference zone at the edge is at least the organization's parameterized hours, in id
    order, the leaver included: when the far person is the leaver, their own calendar
    dates the event inside their leave and they attend alone. The organization
    guarantees one far person exists, so a draft always affords this.
    """

    name = ModifierName.TIMEZONE_BOUNDARY
    affordance = "an employee at least the parameterized hours from the reference zone at the edge"

    def admissible(self, org: OrgSpec, draft: Draft) -> tuple[Amendment, ...]:
        leave = _investigated(draft)
        reference = org.params.reference_timezone
        least = timedelta(hours=org.params.timezone_gap_hours)
        amendments: list[Amendment] = []
        for colleague in org.employees:
            behind = _behind(colleague.timezone, reference, leave.end + timedelta(days=1))
            edge = leave.end + timedelta(days=1) if behind else leave.start - timedelta(days=1)
            probe = datetime.combine(edge, time(12, 0), tzinfo=zone(reference))
            if gap_at(colleague.timezone, reference, probe) >= least:
                amendments.append(_boundary_amendment(colleague, behind))
        return tuple(amendments)


def _behind(timezone: str, reference: str, day: date) -> bool:
    probe = datetime.combine(day, time(12, 0), tzinfo=zone(reference))
    return offset_of(timezone, probe) < offset_of(reference, probe)


def _boundary_amendment(colleague: Employee, behind: bool) -> Amendment:
    def amend(draft: Draft, frame: Frame, rng: Random) -> tuple[Draft, ModifierEffect]:
        leaver = _investigated(draft).employee_id
        reference = frame.reference_timezone
        if behind:
            # The colleague's late afternoon on the leave's last day is already the next
            # day in the reference zone.
            outside_day = frame.leave.end + timedelta(days=1)
            start = _late_afternoon(frame.leave.end, colleague.timezone, reference)
            inside_day, inside_zone = frame.leave.end, colleague.timezone
        else:
            # The reference zone's late afternoon on the day before the leave is already
            # the leave's first day for a colleague ahead.
            outside_day = frame.leave.start - timedelta(days=1)
            start = _late_afternoon(outside_day, reference, colleague.timezone)
            inside_day, inside_zone = frame.leave.start, colleague.timezone
        _check_reading(start, reference, outside_day, "the reference zone")
        _check_reading(start, inside_zone, inside_day, f"{colleague.name}'s zone")
        attendees = (leaver,) if colleague.id == leaver else (leaver, colleague.id)
        event = CalendarEvent(
            id=frame.ids.event(),
            title=BOUNDARY_EVENT_TITLE,
            start=start,
            end=start + EVENT_LENGTH,
            attendee_ids=attendees,
        )
        planted = OwnedEntities(events=(Planted(event, frame.window.start),))
        near_miss = NamedDistractor(event_ref(event.id), DistractorReason.TIMEZONE_BOUNDARY)
        return draft.extended(owned=planted), ModifierEffect(distractors=(near_miss,))

    return amend


def _late_afternoon(day: date, in_zone: str, other_zone: str) -> datetime:
    """The earliest instant on ``day`` in ``in_zone`` that ``other_zone`` already dates as the
    next day — midnight less the gap — floored at the earliest working hour."""
    midnight = datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=zone(in_zone))
    gap = gap_at(in_zone, other_zone, midnight)
    earliest = datetime.combine(day, EARLIEST_WORKING_HOUR, tzinfo=zone(in_zone))
    return max(earliest, midnight - gap)


def _check_reading(instant: datetime, timezone: str, expected: date, who: str) -> None:
    actual = local_date(instant, timezone)
    if actual != expected:
        raise ValueError(
            f"a boundary event must read as {expected} in {who}, {instant.isoformat()} reads "
            f"as {actual}"
        )


# --- The declaration the plan and the pair sweep share ------------------------------------


MODIFIERS: Mapping[ModifierName, Modifier] = MappingProxyType(
    {
        ModifierName.WRONG_TEAM: WrongTeam(),
        ModifierName.ALREADY_RESOLVED: AlreadyResolved(),
        ModifierName.OUTSIDE_WINDOW: OutsideWindow(),
        ModifierName.TIMEZONE_BOUNDARY: TimezoneBoundary(),
        ModifierName.CONCURRENT_LEAVE: ConcurrentLeave(),
    }
)
"""Every modifier by name, the instances the plan composes."""

_ALL = frozenset(MODIFIERS)

COMPATIBLE_MODIFIERS: Mapping[ScenarioClassName, frozenset[ModifierName]] = MappingProxyType(
    {
        ScenarioClassName.STRUCTURED_DEADLINE: _ALL,
        ScenarioClassName.STRUCTURED_MEETING: _ALL - {ModifierName.ALREADY_RESOLVED},
        ScenarioClassName.STRUCTURED_MIXED: _ALL,
    }
)
"""The modifiers every draft of each class affords; a pair is compatible when both are."""
