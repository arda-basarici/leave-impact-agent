"""A five-person fact base the rule tests share: one story, read by the fact-base, closure,
authority, viability and plan-check tests alike.

Alice (``emp_017``) is on leave 15–19 September and owns a Kafka ticket due inside it;
a stale runbook still names Bob (``emp_003``) as the owner. Deniz (``emp_023``) has no
skills field on the HR record — a gap — but a June ticket comment shows Kafka. Can
(``emp_031``) is a contractor whose only skill is PostgreSQL. Bob holds Kafka but is
not in the payments component. Two clauses: one asks for a Kafka engineer, the other
for two Kafka *employees*. A release meeting sits on the 16th; another meeting
overlaps it and Bob attends that one.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from leaveimpact.core import (
    ConstraintKey,
    DateSpan,
    EmploymentType,
    EmploymentTypeCriterion,
    EntityRef,
    EvidenceRef,
    Fact,
    FactBase,
    FactValue,
    Gap,
    ImpactKey,
    ImpactSubtype,
    InstantSpan,
    PredicateName,
    Requirement,
    SkillCriterion,
    Source,
    WorkItemStatus,
    clause_ref,
    comment_ref,
    component_ref,
    employee_ref,
    event_ref,
    leave_ref,
    team_ref,
    work_item_ref,
)
from leaveimpact.core.ids import (
    ClauseId,
    EmployeeId,
    EventId,
    clause_id,
    comment_id,
    component_id,
    employee_id,
    event_id,
    leave_id,
    skill_id,
    team_id,
    work_item_id,
)

WORLD_START = date(2026, 1, 1)
NOW = date(2026, 9, 14)
ISTANBUL = ZoneInfo("Europe/Istanbul")

ALICE = employee_id(17)
BOB = employee_id(3)
DENIZ = employee_id(23)
CAN = employee_id(31)
PAYMENTS = component_id(1)
TEAM = team_id(1)
TICKET = work_item_id(42)
LEAVE = leave_id(5)
RELEASE = event_id(7)
OTHER_MEETING = event_id(8)
KAFKA_CLAUSE = clause_id(11)
STALE_CLAUSE = clause_id(12)
TWO_EMPLOYEES_CLAUSE = clause_id(13)
DENIZ_COMMENT = comment_id(1)
COMMENT_DATE = date(2026, 6, 10)
LEAVE_SPAN = DateSpan(date(2026, 9, 15), date(2026, 9, 19))
RELEASE_SPAN = InstantSpan(
    datetime(2026, 9, 16, 10, 0, tzinfo=ISTANBUL), datetime(2026, 9, 16, 11, 0, tzinfo=ISTANBUL)
)
OTHER_SPAN = InstantSpan(
    datetime(2026, 9, 16, 10, 30, tzinfo=ISTANBUL),
    datetime(2026, 9, 16, 11, 30, tzinfo=ISTANBUL),
)
KAFKA = skill_id("kafka")
POSTGRES = skill_id("postgres")
ONE_KAFKA = Requirement(1, (SkillCriterion(KAFKA),))
TWO_KAFKA_EMPLOYEES = Requirement(
    2, (SkillCriterion(KAFKA), EmploymentTypeCriterion(EmploymentType.EMPLOYEE))
)


def hr(employee: EmployeeId, name: PredicateName, value: FactValue, field: str) -> Fact:
    who = employee_ref(employee)
    return Fact(who, name, value, EvidenceRef(Source.FRAPPE, who, field), WORLD_START)


def in_payments(employee: EmployeeId) -> Fact:
    return Fact(
        employee_ref(employee),
        PredicateName.MEMBER_OF_COMPONENT,
        component_ref(PAYMENTS),
        EvidenceRef(Source.JIRA, component_ref(PAYMENTS), "member_ids"),
        WORLD_START,
    )


def ticket(name: PredicateName, value: FactValue, field: str) -> Fact:
    return Fact(
        work_item_ref(TICKET),
        name,
        value,
        EvidenceRef(Source.JIRA, work_item_ref(TICKET), field),
        WORLD_START,
    )


def attends(event: EventId, employee: EmployeeId) -> Fact:
    return Fact(
        event_ref(event),
        PredicateName.ATTENDS_EVENT,
        employee_ref(employee),
        EvidenceRef(Source.CALENDAR, event_ref(event), "attendee_ids"),
        WORLD_START,
    )


def scheduled(event: EventId, span: InstantSpan) -> Fact:
    return Fact(
        event_ref(event),
        PredicateName.SCHEDULED_AT,
        span,
        EvidenceRef(Source.CALENDAR, event_ref(event), "start"),
        WORLD_START,
    )


def requires(clause: ClauseId, requirement: Requirement) -> Fact:
    return Fact(
        clause_ref(clause),
        PredicateName.REQUIRES,
        requirement,
        EvidenceRef(Source.CORPUS, clause_ref(clause)),
        WORLD_START,
    )


def ticket_owner_in_corpus(owner: EntityRef) -> Fact:
    """A runbook clause naming ``owner`` for the ticket — the stale-source shape."""
    return Fact(
        work_item_ref(TICKET),
        PredicateName.OWNS_WORK_ITEM,
        owner,
        EvidenceRef(Source.CORPUS, clause_ref(STALE_CLAUSE)),
        WORLD_START,
    )


ALICE_ON_LEAVE = Fact(
    employee_ref(ALICE),
    PredicateName.ON_LEAVE,
    LEAVE_SPAN,
    EvidenceRef(Source.FRAPPE, leave_ref(LEAVE)),
    date(2026, 9, 1),
)
DENIZ_KAFKA_IN_COMMENT = Fact(
    employee_ref(DENIZ),
    PredicateName.HAS_SKILL,
    KAFKA,
    EvidenceRef(Source.JIRA, comment_ref(DENIZ_COMMENT), "text"),
    COMMENT_DATE,
)
DENIZ_SKILLS_GAP = Gap(
    employee_ref(DENIZ),
    PredicateName.HAS_SKILL,
    EvidenceRef(Source.FRAPPE, employee_ref(DENIZ), "skills"),
    WORLD_START,
)
LIVE_OWNER = ticket(PredicateName.OWNS_WORK_ITEM, employee_ref(ALICE), "owner_id")
STALE_OWNER = ticket_owner_in_corpus(employee_ref(BOB))

FACTS: tuple[Fact, ...] = (
    *(
        hr(who, PredicateName.MEMBER_OF_TEAM, team_ref(TEAM), "team_id")
        for who in (ALICE, BOB, DENIZ, CAN)
    ),
    hr(ALICE, PredicateName.HAS_SKILL, KAFKA, "skills"),
    hr(BOB, PredicateName.HAS_SKILL, KAFKA, "skills"),
    hr(CAN, PredicateName.HAS_SKILL, POSTGRES, "skills"),
    hr(ALICE, PredicateName.EMPLOYED_AS, EmploymentType.EMPLOYEE, "employment_type"),
    hr(BOB, PredicateName.EMPLOYED_AS, EmploymentType.EMPLOYEE, "employment_type"),
    hr(DENIZ, PredicateName.EMPLOYED_AS, EmploymentType.EMPLOYEE, "employment_type"),
    hr(CAN, PredicateName.EMPLOYED_AS, EmploymentType.CONTRACTOR, "employment_type"),
    ALICE_ON_LEAVE,
    in_payments(ALICE),
    in_payments(DENIZ),
    in_payments(CAN),
    DENIZ_KAFKA_IN_COMMENT,
    LIVE_OWNER,
    STALE_OWNER,
    ticket(PredicateName.WORK_ITEM_STATUS, WorkItemStatus.IN_PROGRESS, "status"),
    ticket(PredicateName.DUE_ON, date(2026, 9, 17), "due_on"),
    ticket(PredicateName.IN_COMPONENT, component_ref(PAYMENTS), "component_id"),
    scheduled(RELEASE, RELEASE_SPAN),
    scheduled(OTHER_MEETING, OTHER_SPAN),
    attends(RELEASE, ALICE),
    attends(RELEASE, CAN),
    attends(OTHER_MEETING, BOB),
    requires(KAFKA_CLAUSE, ONE_KAFKA),
    requires(TWO_EMPLOYEES_CLAUSE, TWO_KAFKA_EMPLOYEES),
)

WORLD = FactBase(FACTS, (DENIZ_SKILLS_GAP,))

REFERENCE_TIMEZONE = "Europe/Istanbul"
DEADLINE = ImpactKey(LEAVE, ImpactSubtype.DEADLINE, work_item_ref(TICKET))
MEETING = ImpactKey(LEAVE, ImpactSubtype.MEETING, event_ref(RELEASE))
CONSTRAINTS = (
    ConstraintKey(KAFKA_CLAUSE, work_item_ref(TICKET)),
    ConstraintKey(TWO_EMPLOYEES_CLAUSE, event_ref(RELEASE)),
)
EVERYONE = (ALICE, BOB, DENIZ, CAN)
