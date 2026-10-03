"""The composing pass over the four-person world, held to conclusions derived by hand from the
story the fixture tells: the need behind each impact, the requirements that count, how many
people they ask for and the coverage outcome, under the normal condition, with the tracker
down and with the calendar down. No expectation here is computed by the pass it tests."""

from leaveimpact.core import (
    AssessmentReason,
    CoverageActionKind,
    DerivedUnknownReason,
    EntityRef,
    Grounded,
    ImpactConclusion,
    PredicateName,
    RunCondition,
    Source,
    UnknownReason,
    Unresolved,
    Verdict,
    component_ref,
    conclude_impacts,
    employee_ref,
    event_ref,
    work_item_ref,
)
from leaveimpact.core.ids import ClauseId, EmployeeId
from leaveimpact.core.viability import Need
from tests.unit import world_fixture as w

NORMAL = RunCondition.all_reachable()
AVAILABILITY = (Verdict.NON_VIABLE, (AssessmentReason.AVAILABILITY,))
VIABLE = (Verdict.VIABLE, ())
UNKNOWN = (Verdict.UNKNOWN, ())

Question = tuple[EntityRef, PredicateName, DerivedUnknownReason]
COMPONENT_UNREAD: Question = (
    work_item_ref(w.TICKET),
    PredicateName.IN_COMPONENT,
    UnknownReason.INACCESSIBLE,
)
SCHEDULE_UNREAD: Question = (
    event_ref(w.RELEASE),
    PredicateName.SCHEDULED_AT,
    UnknownReason.INACCESSIBLE,
)


def skill_unread(who: EmployeeId) -> Question:
    return (employee_ref(who), PredicateName.HAS_SKILL, UnknownReason.INACCESSIBLE)


def concluded(*down: Source) -> tuple[ImpactConclusion, ImpactConclusion]:
    """The deadline's and the meeting's conclusions with the sources in ``down`` unreachable."""
    deadline, meeting = conclude_impacts(
        w.WORLD.at(w.NOW, NORMAL.without(*down)),
        (w.DEADLINE, w.MEETING),
        w.CONSTRAINTS,
        w.ALICE,
        w.LEAVE_SPAN,
        w.REFERENCE_TIMEZONE,
        w.EVERYONE,
    )
    assert (deadline.impact, meeting.impact) == (w.DEADLINE, w.MEETING)
    return deadline, meeting


def judgments(
    conclusion: ImpactConclusion,
) -> dict[EmployeeId, tuple[Verdict, tuple[AssessmentReason, ...]]]:
    return {a.employee_id: (a.verdict, a.reasons) for a in conclusion.reading.assessments}


def questions(conclusion: ImpactConclusion) -> dict[EmployeeId, tuple[Question, ...]]:
    """The open questions behind each candidate's assessment, for those who have any."""
    return {
        a.employee_id: tuple((q.subject, q.predicate, q.reason) for q in a.unresolved)
        for a in conclusion.reading.assessments
        if a.unresolved
    }


def clauses(conclusion: ImpactConclusion) -> tuple[ClauseId, ...]:
    return tuple(requirement.clause_id for requirement in conclusion.requirements)


def test_under_the_normal_condition_the_deadline_is_assigned_and_the_meeting_uncovered() -> None:
    deadline, meeting = concluded()

    # The ticket falls due inside the leave and sits in payments; one Kafka engineer is asked
    # for. Alice is on leave, Bob is outside the component, Can holds PostgreSQL only, and
    # Deniz holds Kafka by the June comment: one viable where one is asked for.
    assert isinstance(deadline.reading.grounding, Grounded)
    assert isinstance(deadline.need, Need)
    assert deadline.need.window == w.LEAVE_SPAN
    assert deadline.need.component == component_ref(w.PAYMENTS)
    assert clauses(deadline) == (w.KAFKA_CLAUSE,)
    assert deadline.required == 1
    assert judgments(deadline) == {
        w.ALICE: AVAILABILITY,
        w.BOB: (Verdict.NON_VIABLE, (AssessmentReason.COMPONENT,)),
        w.DENIZ: VIABLE,
        w.CAN: (Verdict.NON_VIABLE, (AssessmentReason.SKILL,)),
    }
    assert deadline.outcome is CoverageActionKind.ASSIGN

    # The release asks for two Kafka employees. Bob sits in the overlapping meeting, Can is a
    # contractor without Kafka, and Deniz is the only one left: one viable where two are asked
    # for, and nobody whose standing is open, so the meeting is uncovered.
    assert isinstance(meeting.reading.grounding, Grounded)
    assert isinstance(meeting.need, Need)
    assert meeting.need.event_span == w.RELEASE_SPAN
    assert clauses(meeting) == (w.TWO_EMPLOYEES_CLAUSE,)
    assert meeting.required == 2
    assert judgments(meeting) == {
        w.ALICE: AVAILABILITY,
        w.BOB: AVAILABILITY,
        w.DENIZ: VIABLE,
        w.CAN: (Verdict.NON_VIABLE, (AssessmentReason.HARD_RULE, AssessmentReason.SKILL)),
    }
    assert meeting.outcome is CoverageActionKind.UNCOVERED


def test_with_the_tracker_down_the_deadline_is_unknown_and_the_meeting_still_uncovered() -> None:
    deadline, meeting = concluded(Source.JIRA)

    # The ticket cannot be read, so the leaver holding it is not established; the need still
    # stands over the leave with its component open, and the Kafka clause, a corpus fact,
    # still asks for one. Alice's leave is an HR fact and rules her out. Everyone else waits
    # on the component, Deniz and Can on a skill a tracker comment could still show as well.
    assert not isinstance(deadline.reading.grounding, Grounded)
    assert isinstance(deadline.need, Need) and isinstance(deadline.need.component, Unresolved)
    assert clauses(deadline) == (w.KAFKA_CLAUSE,)
    assert deadline.required == 1
    assert judgments(deadline) == {
        w.ALICE: AVAILABILITY,
        w.BOB: UNKNOWN,
        w.DENIZ: UNKNOWN,
        w.CAN: UNKNOWN,
    }
    assert questions(deadline) == {
        w.BOB: (COMPONENT_UNREAD,),
        w.DENIZ: (COMPONENT_UNREAD, skill_unread(w.DENIZ)),
        w.CAN: (COMPONENT_UNREAD, skill_unread(w.CAN)),
    }
    # Nobody viable, three whose standing is open, one asked for.
    assert deadline.outcome is CoverageActionKind.UNKNOWN

    # The meeting is a calendar fact and reads as before. Deniz's Kafka was the tracker
    # comment, so his skill is open; Can stays ruled out as a contractor, a known failure
    # that leaves his open skill unasked. None viable and one open cannot make two.
    assert isinstance(meeting.reading.grounding, Grounded)
    assert meeting.required == 2
    assert judgments(meeting) == {
        w.ALICE: AVAILABILITY,
        w.BOB: AVAILABILITY,
        w.DENIZ: UNKNOWN,
        w.CAN: (Verdict.NON_VIABLE, (AssessmentReason.HARD_RULE,)),
    }
    assert questions(meeting) == {w.DENIZ: (skill_unread(w.DENIZ),)}
    assert meeting.outcome is CoverageActionKind.UNCOVERED


def test_with_the_calendar_down_an_unreadable_meeting_counts_no_requirement() -> None:
    deadline, meeting = concluded(Source.CALENDAR)

    # No schedule, no day to ask about: the need itself is the open question, every
    # candidate's standing rests on it, and the clause asking for two is not counted, since
    # what it applies to was not read. One person is asked for, and four are open.
    assert meeting.need == Unresolved(*SCHEDULE_UNREAD)
    assert meeting.requirements == ()
    assert meeting.required == 1
    assert judgments(meeting) == dict.fromkeys(w.EVERYONE, UNKNOWN)
    assert questions(meeting) == dict.fromkeys(w.EVERYONE, (SCHEDULE_UNREAD,))
    assert meeting.outcome is CoverageActionKind.UNKNOWN

    # The deadline has no meeting in it and is concluded as under the normal condition.
    assert deadline.required == 1
    assert judgments(deadline)[w.DENIZ] == VIABLE
    assert deadline.outcome is CoverageActionKind.ASSIGN
