"""The viability rule over the five-person world: each criterion fails for the right reason, a
known failure dominates an unresolved question, an unresolved question makes the verdict
unknown with the fact it rests on, the count never enters, and the need itself is read
from the fact base."""

from datetime import date

import pytest

from leaveimpact.core import (
    AssessmentReason,
    ConstraintKey,
    FactView,
    ImpactKey,
    ImpactSubtype,
    PredicateName,
    Requirement,
    RunCondition,
    SkillCriterion,
    Source,
    UnknownReason,
    Unresolved,
    Verdict,
    applicable_requirements,
    assess,
    assess_impact,
    clause_ref,
    component_ref,
    employee_ref,
    event_ref,
    need_of,
    work_item_ref,
)
from leaveimpact.core.ids import clause_id, employee_id, work_item_id
from leaveimpact.core.viability import Need
from tests.unit import world_fixture as w

NORMAL = RunCondition.all_reachable()
VIEW = w.WORLD.at(w.NOW, NORMAL)


def deadline_need(view: FactView = VIEW) -> Need:
    need = need_of(view, w.DEADLINE, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE)
    assert isinstance(need, Need)
    return need


def meeting_need(view: FactView = VIEW) -> Need:
    need = need_of(view, w.MEETING, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE)
    assert isinstance(need, Need)
    return need


def test_the_need_is_read_from_the_fact_base() -> None:
    deadline = deadline_need()
    assert deadline.window == w.LEAVE_SPAN
    assert deadline.component == component_ref(w.PAYMENTS)
    assert deadline.event_span is None
    meeting = meeting_need()
    assert meeting.window.start == meeting.window.end == date(2026, 9, 16)
    assert meeting.event_span == w.RELEASE_SPAN
    assert meeting.component is None


def test_an_unreadable_need_is_unresolved_and_makes_every_candidate_unknown() -> None:
    calendar_down = w.WORLD.at(w.NOW, NORMAL.without(Source.CALENDAR))
    assert need_of(calendar_down, w.MEETING, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE) == Unresolved(
        event_ref(w.RELEASE), PredicateName.SCHEDULED_AT, UnknownReason.INACCESSIBLE
    )
    assessments = assess_impact(
        calendar_down, w.MEETING, w.EVERYONE, w.CONSTRAINTS, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE
    )
    assert [assessment.verdict for assessment in assessments] == [Verdict.UNKNOWN] * 4
    assert all(
        assessment.unresolved
        == (
            Unresolved(
                event_ref(w.RELEASE), PredicateName.SCHEDULED_AT, UnknownReason.INACCESSIBLE
            ),
        )
        for assessment in assessments
    )


def test_each_deadline_criterion_fails_for_its_own_reason() -> None:
    by_employee = {
        assessment.employee_id: assessment
        for assessment in assess_impact(
            VIEW, w.DEADLINE, w.EVERYONE, w.CONSTRAINTS, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE
        )
    }
    # The leaver fails through the ordinary on-leave check.
    assert by_employee[w.ALICE].verdict is Verdict.NON_VIABLE
    assert by_employee[w.ALICE].reasons == (AssessmentReason.AVAILABILITY,)
    # Bob holds Kafka but is outside the payments component.
    assert by_employee[w.BOB].reasons == (AssessmentReason.COMPONENT,)
    # Can is in the component but holds only PostgreSQL.
    assert by_employee[w.CAN].reasons == (AssessmentReason.SKILL,)
    # Deniz: Kafka by the June comment, in the component, not on leave.
    assert by_employee[w.DENIZ].verdict is Verdict.VIABLE
    assert by_employee[w.DENIZ].reasons == ()
    assert by_employee[w.DENIZ].unresolved == ()
    assert w.DENIZ_KAFKA_IN_COMMENT in by_employee[w.DENIZ].evidence
    assert w.requires(w.KAFKA_CLAUSE, w.ONE_KAFKA) in by_employee[w.DENIZ].evidence


def test_the_policy_criterion_reads_as_hard_rule_and_every_failure_is_listed() -> None:
    can = assess(VIEW, meeting_need(), w.CAN, w.CONSTRAINTS)
    assert can.verdict is Verdict.NON_VIABLE
    assert can.reasons == (AssessmentReason.HARD_RULE, AssessmentReason.SKILL)


def test_a_meeting_overlap_is_an_availability_failure_but_the_target_is_not() -> None:
    bob = assess(VIEW, meeting_need(), w.BOB, w.CONSTRAINTS)
    assert bob.reasons == (AssessmentReason.AVAILABILITY,)
    assert w.scheduled(w.OTHER_MEETING, w.OTHER_SPAN) in bob.evidence
    # Can already attends the release; the target meeting never disqualifies its own attendee.
    can = assess(VIEW, meeting_need(), w.CAN, ())
    assert AssessmentReason.AVAILABILITY not in can.reasons


def test_an_unresolved_criterion_makes_the_verdict_unknown_with_its_fact() -> None:
    early = w.WORLD.at(date(2026, 5, 1), NORMAL)
    deniz = assess(early, deadline_need(early), w.DENIZ, w.CONSTRAINTS)
    assert deniz.verdict is Verdict.UNKNOWN
    assert deniz.reasons == ()
    assert deniz.unresolved == (
        Unresolved(employee_ref(w.DENIZ), PredicateName.HAS_SKILL, UnknownReason.ABSENT),
    )


def test_a_known_failure_dominates_an_unresolved_question() -> None:
    jira_down = w.WORLD.at(w.NOW, NORMAL.without(Source.JIRA))
    # The ticket's component is unreadable: the need stands, its component unresolved.
    need = deadline_need(jira_down)
    assert need.component == Unresolved(
        work_item_ref(w.TICKET), PredicateName.IN_COMPONENT, UnknownReason.INACCESSIBLE
    )
    # Alice's leave is a known failure and settles her whatever else is unsettled.
    alice = assess(jira_down, need, w.ALICE, w.CONSTRAINTS)
    assert alice.verdict is Verdict.NON_VIABLE
    assert alice.reasons == (AssessmentReason.AVAILABILITY,)
    assert alice.unresolved == ()
    # Bob's Kafka is on the HR record, so a positive fact settles the skill even with the
    # tracker down; only the component question is open, keyed to the ticket.
    bob = assess(jira_down, need, w.BOB, w.CONSTRAINTS)
    assert bob.verdict is Verdict.UNKNOWN
    assert bob.unresolved == (need.component,)
    # Deniz's Kafka lives only in a ticket comment: both questions are inaccessible.
    deniz = assess(jira_down, need, w.DENIZ, w.CONSTRAINTS)
    assert {(item.predicate, item.reason) for item in deniz.unresolved} == {
        (PredicateName.IN_COMPONENT, UnknownReason.INACCESSIBLE),
        (PredicateName.HAS_SKILL, UnknownReason.INACCESSIBLE),
    }
    # A component-scoped constraint may or may not apply: the unresolved component stands in.
    component_scoped = ConstraintKey(w.KAFKA_CLAUSE, component_ref(w.PAYMENTS))
    assert applicable_requirements(jira_down, need, (component_scoped,)) == (need.component,)


def test_the_count_never_touches_individual_viability() -> None:
    deniz = assess(VIEW, meeting_need(), w.DENIZ, w.CONSTRAINTS)
    assert deniz.verdict is Verdict.VIABLE


def test_constraints_apply_by_artifact_or_component_and_resolve_through_the_clause() -> None:
    component_scoped = ConstraintKey(w.KAFKA_CLAUSE, component_ref(w.PAYMENTS))
    other_ticket = ConstraintKey(w.KAFKA_CLAUSE, work_item_ref(work_item_id(7)))
    resolved = applicable_requirements(VIEW, deadline_need(), (component_scoped, other_ticket))
    assert len(resolved) == 1
    assert not isinstance(resolved[0], Unresolved)
    assert resolved[0].requirement == w.ONE_KAFKA
    assert resolved[0].fact.evidence.target == clause_ref(w.KAFKA_CLAUSE)
    corpus_down = w.WORLD.at(w.NOW, NORMAL.without(Source.CORPUS))
    assert applicable_requirements(corpus_down, deadline_need(), w.CONSTRAINTS) == (
        Unresolved(clause_ref(w.KAFKA_CLAUSE), PredicateName.REQUIRES, UnknownReason.INACCESSIBLE),
    )
    deniz = assess(corpus_down, deadline_need(), w.DENIZ, w.CONSTRAINTS)
    assert deniz.verdict is Verdict.UNKNOWN
    with pytest.raises(ValueError, match="clause_099 states no requirement"):
        applicable_requirements(
            VIEW, deadline_need(), (ConstraintKey(clause_id(99), work_item_ref(w.TICKET)),)
        )


def test_a_responsibility_in_a_runbook_needs_only_the_leave_window() -> None:
    impact = ImpactKey(w.LEAVE, ImpactSubtype.RESPONSIBILITY, clause_ref(w.STALE_CLAUSE))
    need = need_of(VIEW, impact, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE)
    assert isinstance(need, Need)
    assert need == Need(impact, w.LEAVE_SPAN, None, None, ())
    stranger = employee_id(40)
    assessment = assess(VIEW, need, stranger, ())
    assert assessment.verdict is Verdict.VIABLE


def test_a_requirement_about_number_alone_asks_nothing_of_a_person() -> None:
    number_only = w.requires(clause_id(14), Requirement(3, ()))
    view = w.FactBase((*w.FACTS, number_only), (w.DENIZ_SKILLS_GAP,)).at(w.NOW, NORMAL)
    constraint = ConstraintKey(clause_id(14), event_ref(w.RELEASE))
    deniz = assess(view, meeting_need(view), w.DENIZ, (constraint,))
    assert deniz.verdict is Verdict.VIABLE
    kafka_only = Requirement(1, (SkillCriterion(w.KAFKA),))
    assert kafka_only.criteria == w.ONE_KAFKA.criteria
