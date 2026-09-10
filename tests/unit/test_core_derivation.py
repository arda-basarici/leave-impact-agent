"""Derivation: the four-person fixture rebuilt from entities derives exactly the facts and the gap
the hand-written base holds for the same records — two independent sources agreeing — and each
field's absence means what the module says: a gap for a missing skills field, zero facts for a
missing due date or manager, nothing for a requested leave, a comment or a document."""

from dataclasses import replace
from datetime import date

from leaveimpact.core import (
    CalendarEvent,
    Comment,
    Component,
    Document,
    DocumentKind,
    DocumentSection,
    Employee,
    EmploymentType,
    EvidenceRef,
    Fact,
    Gap,
    Grade,
    Leave,
    LeaveKind,
    LeaveStatus,
    Observed,
    PredicateName,
    Source,
    Team,
    WorkItemStatus,
    derive,
    employee_ref,
    event_ref,
)
from leaveimpact.core.entities import WorkItem
from leaveimpact.core.ids import EmployeeId, clause_id, document_id, team_id
from tests.unit import world_fixture as w

# --- the fixture's records, as the systems would hold them -------------------------


def _person(
    id: EmployeeId, skills: tuple[str, ...] | None, employment: EmploymentType
) -> Observed[Employee]:
    return Observed(
        Employee(
            id=id,
            name=f"Person {id}",
            team_id=w.TEAM,
            manager_id=None,
            skills=None if skills is None else tuple(w.skill_id(key) for key in skills),
            location="Istanbul",
            country="TR",
            timezone="Europe/Istanbul",
            grade=Grade.SENIOR,
            employment_type=employment,
        ),
        Source.FRAPPE,
    )


PEOPLE = (
    _person(w.ALICE, ("kafka",), EmploymentType.EMPLOYEE),
    _person(w.BOB, ("kafka",), EmploymentType.EMPLOYEE),
    _person(w.DENIZ, None, EmploymentType.EMPLOYEE),
    _person(w.CAN, ("postgres",), EmploymentType.CONTRACTOR),
)
PAYMENTS = Observed(Component(w.PAYMENTS, "payments", (w.ALICE, w.DENIZ, w.CAN)), Source.JIRA)
TICKET = Observed(
    WorkItem(
        id=w.TICKET,
        title="Kafka upgrade",
        owner_id=w.ALICE,
        status=WorkItemStatus.IN_PROGRESS,
        component_id=w.PAYMENTS,
        opened_on=date(2026, 8, 20),
        resolved_on=None,
        due_on=date(2026, 9, 17),
        # A translated comment keeps its bracketed prefix whole — the entity's contract.
        comments=(
            Comment(
                w.DENIZ_COMMENT,
                w.COMMENT_DATE,
                w.DENIZ,
                f"[{w.COMMENT_DATE.isoformat()}, {w.DENIZ} — Deniz] Deniz led the Kafka work.",
            ),
        ),
    ),
    Source.JIRA,
)
RELEASE = Observed(
    CalendarEvent(w.RELEASE, "Release", w.RELEASE_SPAN.start, w.RELEASE_SPAN.end, (w.ALICE, w.CAN)),
    Source.CALENDAR,
)
OTHER_MEETING = Observed(
    CalendarEvent(w.OTHER_MEETING, "Sync", w.OTHER_SPAN.start, w.OTHER_SPAN.end, (w.BOB,)),
    Source.CALENDAR,
)
ALICE_LEAVE = Observed(
    Leave(
        w.LEAVE,
        w.ALICE,
        w.LEAVE_SPAN.start,
        w.LEAVE_SPAN.end,
        LeaveKind.ANNUAL,
        LeaveStatus.APPROVED,
    ),
    Source.FRAPPE,
)

# The facts the hand-written base holds that derivation cannot know: the skill in a
# comment (prose), the owner a runbook asserts (corpus), what the clauses require (brief),
# and the two employees' location facts the fixture never needed.
PLANTED_ONLY = {
    w.DENIZ_KAFKA_IN_COMMENT,
    w.STALE_OWNER,
    w.requires(w.KAFKA_CLAUSE, w.ONE_KAFKA),
    w.requires(w.TWO_EMPLOYEES_CLAUSE, w.TWO_KAFKA_EMPLOYEES),
}


def _derive_all() -> tuple[set[Fact], set[Gap]]:
    derived = [
        *(item for person in PEOPLE for item in derive(person, w.WORLD_START)),
        *derive(PAYMENTS, w.WORLD_START),
        *derive(TICKET, w.WORLD_START),
        *derive(RELEASE, w.WORLD_START),
        *derive(OTHER_MEETING, w.WORLD_START),
        *derive(ALICE_LEAVE, date(2026, 9, 1)),
    ]
    facts = {item for item in derived if isinstance(item, Fact)}
    gaps = {item for item in derived if isinstance(item, Gap)}
    return facts, gaps


def test_the_fixture_rebuilt_from_records_derives_every_fact_the_hand_written_base_plants() -> None:
    derived, gaps = _derive_all()
    hand_written = set(w.FACTS) - PLANTED_ONLY
    assert hand_written <= derived
    assert gaps == {w.DENIZ_SKILLS_GAP}


def test_derivation_adds_only_the_facts_the_fixture_left_out_because_no_rule_reads_them() -> None:
    derived, _ = _derive_all()
    extra = derived - set(w.FACTS)
    assert {fact.predicate for fact in extra} == {PredicateName.LOCATED_IN}
    assert {fact.subject for fact in extra} == {employee_ref(who.value.id) for who in PEOPLE}


# --- what absence means, field by field ---------------------------------------------


def test_a_missing_skills_field_is_a_gap_and_an_empty_one_is_zero_facts() -> None:
    absent = derive(_person(w.DENIZ, None, EmploymentType.EMPLOYEE), w.WORLD_START)
    empty = derive(_person(w.DENIZ, (), EmploymentType.EMPLOYEE), w.WORLD_START)
    assert [item for item in absent if isinstance(item, Gap)] == [w.DENIZ_SKILLS_GAP]
    assert not any(item.predicate is PredicateName.HAS_SKILL for item in empty)
    assert not any(isinstance(item, Gap) for item in empty)


def test_a_missing_manager_and_a_missing_due_date_are_observed_negatives() -> None:
    root = derive(_person(w.BOB, ("kafka",), EmploymentType.EMPLOYEE), w.WORLD_START)
    assert not any(item.predicate is PredicateName.REPORTS_TO for item in root)
    managed = Observed(replace(PEOPLE[0].value, manager_id=w.BOB), Source.FRAPPE)
    with_manager = derive(managed, w.WORLD_START)
    assert any(item.predicate is PredicateName.REPORTS_TO for item in with_manager)

    undated = Observed(replace(TICKET.value, due_on=None), Source.JIRA)
    predicates = [item.predicate for item in derive(undated, w.WORLD_START)]
    assert PredicateName.DUE_ON not in predicates
    assert not any(isinstance(item, Gap) for item in derive(undated, w.WORLD_START))


def test_a_requested_leave_a_comment_a_team_and_a_document_derive_nothing() -> None:
    requested = Observed(replace(ALICE_LEAVE.value, status=LeaveStatus.REQUESTED), Source.FRAPPE)
    assert derive(requested, w.WORLD_START) == ()
    ticket_predicates = {item.predicate for item in derive(TICKET, w.WORLD_START)}
    assert PredicateName.HAS_SKILL not in ticket_predicates  # the comment's Kafka stays prose
    assert derive(Observed(Team(team_id(1), "payments"), Source.FRAPPE), w.WORLD_START) == ()
    policy = Document(
        document_id(4),
        "Coverage policy",
        DocumentKind.POLICY,
        w.WORLD_START,
        (DocumentSection(clause_id(11), "One Kafka engineer covers."),),
    )
    assert derive(Observed(policy, Source.CORPUS), w.WORLD_START) == ()


def test_a_schedule_cites_the_whole_event_record_because_its_span_needs_both_ends() -> None:
    release = derive(RELEASE, w.WORLD_START)
    scheduled = next(item for item in release if item.predicate is PredicateName.SCHEDULED_AT)
    assert scheduled.evidence == EvidenceRef(Source.CALENDAR, event_ref(w.RELEASE))
    attends = [item for item in release if item.predicate is PredicateName.ATTENDS_EVENT]
    assert {item.evidence.field for item in attends} == {"attendee_ids"}


def test_the_caller_dates_every_fact_and_the_source_is_the_observation_s() -> None:
    planted_on = date(2026, 3, 3)
    derived = derive(PEOPLE[0], planted_on)
    assert {item.observable_from for item in derived} == {planted_on}
    assert {item.source for item in derived} == {Source.FRAPPE}
    assert all(item.evidence.target == employee_ref(w.ALICE) for item in derived)
