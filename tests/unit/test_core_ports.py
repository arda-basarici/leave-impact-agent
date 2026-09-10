"""The ports: an observed entity carries a source its kind can come from, the in-memory
implementation conforms to both sides and behaves as the contract says — not found is a
plain answer, a dead source raises, a duplicate add is a projector bug — and the two
faults are distinct types with no common base."""

from datetime import UTC, date, datetime

import pytest

from leaveimpact.core import (
    CalendarEvent,
    CalendarReader,
    Component,
    DateSpan,
    Document,
    DocumentKind,
    DocumentReader,
    DocumentSection,
    Employee,
    EmploymentType,
    EntityKind,
    EntityRef,
    Grade,
    InstantSpan,
    Leave,
    LeaveKind,
    LeaveStatus,
    MalformedRecord,
    Observed,
    PeopleReader,
    Source,
    SourceUnreachable,
    WorkItem,
    WorkItemStatus,
    WorkReader,
    employee_ref,
)
from leaveimpact.core.ids import (
    clause_id,
    component_id,
    document_id,
    employee_id,
    event_id,
    leave_id,
    skill_id,
    team_id,
    work_item_id,
)
from leaveimpact.core.ports.write import (
    CalendarWriter,
    DocumentWriter,
    PeopleWriter,
    WorkWriter,
)
from tests.unit.in_memory_ports import (
    InMemoryCalendar,
    InMemoryDocuments,
    InMemoryPeople,
    InMemoryWork,
)

ALICE, BOB = employee_id(17), employee_id(3)
PAYMENTS = component_id(2)


def _employee(id: str, skills: tuple[str, ...] | None = ("kafka",)) -> Employee:
    return Employee(
        id=employee_id(int(id.rsplit("_", 1)[1])),
        name=f"Person {id}",
        team_id=team_id(2),
        manager_id=None,
        skills=None if skills is None else tuple(skill_id(key) for key in skills),
        location="Istanbul",
        country="TR",
        timezone="Europe/Istanbul",
        grade=Grade.SENIOR,
        employment_type=EmploymentType.EMPLOYEE,
    )


def _leave(number: int, employee: str, start: int, end: int) -> Leave:
    return Leave(
        leave_id(number),
        employee_id(int(employee.rsplit("_", 1)[1])),
        date(2026, 9, start),
        date(2026, 9, end),
        LeaveKind.ANNUAL,
        LeaveStatus.APPROVED,
    )


def _work_item(number: int, owner: str, component: str = PAYMENTS) -> WorkItem:
    return WorkItem(
        id=work_item_id(number),
        title=f"Ticket {number}",
        owner_id=employee_id(int(owner.rsplit("_", 1)[1])),
        status=WorkItemStatus.IN_PROGRESS,
        component_id=component_id(int(component.rsplit("_", 1)[1])),
        opened_on=date(2026, 9, 1),
        resolved_on=None,
        due_on=date(2026, 9, 17),
        comments=(),
    )


def _event(number: int, day: int, hour: int, *attendees: str) -> CalendarEvent:
    return CalendarEvent(
        id=event_id(number),
        title=f"Meeting {number}",
        start=datetime(2026, 9, day, hour, tzinfo=UTC),
        end=datetime(2026, 9, day, hour + 1, tzinfo=UTC),
        attendee_ids=tuple(employee_id(int(who.rsplit("_", 1)[1])) for who in attendees),
    )


def _document(number: int, *texts: str) -> Document:
    return Document(
        id=document_id(number),
        title=f"Document {number}",
        kind=DocumentKind.POLICY,
        effective_from=date(2026, 1, 1),
        sections=tuple(
            DocumentSection(clause_id(number * 10 + i), text) for i, text in enumerate(texts)
        ),
    )


# --- the observed wrapper ---------------------------------------------------------


def test_an_observed_entity_knows_its_kind_and_its_reference() -> None:
    seen = Observed(_employee(ALICE), Source.FRAPPE)
    assert seen.kind is EntityKind.EMPLOYEE
    assert seen.ref == employee_ref(ALICE) == EntityRef(EntityKind.EMPLOYEE, "emp_017")


def test_a_source_that_holds_no_such_record_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="jira holds no employee record"):
        Observed(_employee(ALICE), Source.JIRA)
    with pytest.raises(ValueError, match="frappe holds no document record"):
        Observed(_document(4, "text"), Source.FRAPPE)


# --- conformance: the fake is both sides of every port ---------------------------


def test_the_in_memory_implementation_conforms_to_every_reader_and_writer() -> None:
    # The assignments are the test: pyright checks each fake against the Protocol
    # structurally, and the module fails the type gate if a method drifts.
    people_reader: PeopleReader = InMemoryPeople()
    people_writer: PeopleWriter = InMemoryPeople()
    work_reader: WorkReader = InMemoryWork()
    work_writer: WorkWriter = InMemoryWork()
    calendar_reader: CalendarReader = InMemoryCalendar()
    calendar_writer: CalendarWriter = InMemoryCalendar()
    document_reader: DocumentReader = InMemoryDocuments()
    document_writer: DocumentWriter = InMemoryDocuments()
    conformant = (
        people_reader,
        people_writer,
        work_reader,
        work_writer,
        calendar_reader,
        calendar_writer,
        document_reader,
        document_writer,
    )
    assert len(conformant) == 8


# --- the read contract ------------------------------------------------------------


def test_a_missing_record_is_a_plain_none_and_a_missing_set_an_empty_tuple() -> None:
    people = InMemoryPeople()
    assert people.employee(ALICE) is None
    assert people.leave(leave_id(5)) is None
    assert people.employees() == ()
    assert InMemoryWork().work_items() == ()


def test_what_is_added_is_read_back_wrapped_with_the_source() -> None:
    people = InMemoryPeople()
    locator = people.add_employee(_employee(ALICE))
    seen = people.employee(ALICE)
    assert seen is not None
    assert seen.value == _employee(ALICE)
    assert seen.source is Source.FRAPPE
    assert locator == "frappe-fake:employee:emp_017"


def test_leaves_within_answers_by_overlap_whoever_is_absent() -> None:
    people = InMemoryPeople()
    people.add_leave(_leave(5, ALICE, 15, 19))
    people.add_leave(_leave(6, ALICE, 1, 2))
    people.add_leave(_leave(7, BOB, 16, 16))
    window = DateSpan(date(2026, 9, 14), date(2026, 9, 20))
    found = people.leaves_within(window)
    assert [seen.value.id for seen in found] == ["leave_005", "leave_007"]
    # Whose leave it is stays on the record: the port selected by the window alone.
    assert [seen.value.employee_id for seen in found] == [ALICE, BOB]


def test_work_items_and_components_are_read_whole_never_by_owner_or_component() -> None:
    work = InMemoryWork()
    work.add_component(Component(PAYMENTS, "payments", (ALICE,)))
    work.add_work_item(_work_item(42, ALICE))
    work.add_work_item(_work_item(43, BOB, component_id(3)))
    assert [seen.value.id for seen in work.work_items()] == ["ticket_042", "ticket_043"]
    assert [seen.value.id for seen in work.components()] == ["comp_002"]
    # Owner and component are relationships the domain derives, so the reader has no
    # method that selects by either — the fact base answers "what does Alice own".
    assert not hasattr(WorkReader, "work_items_owned_by")
    assert not hasattr(WorkReader, "work_items_in")


def test_events_within_answers_by_overlap_whoever_attends() -> None:
    calendar = InMemoryCalendar()
    calendar.add_event(_event(9, 16, 10, ALICE, BOB))
    calendar.add_event(_event(10, 16, 11, BOB))
    calendar.add_event(_event(11, 20, 10, ALICE))
    window = InstantSpan(
        datetime(2026, 9, 16, 9, tzinfo=UTC), datetime(2026, 9, 16, 11, tzinfo=UTC)
    )
    assert [seen.value.id for seen in calendar.events_within(window)] == ["event_009"]


def test_search_ranks_by_hits_and_honours_the_limit() -> None:
    corpus = InMemoryDocuments()
    corpus.add_document(_document(4, "Kafka on-call needs one Kafka engineer."))
    corpus.add_document(_document(5, "Kafka and more Kafka.", "Still Kafka."))
    corpus.add_document(_document(6, "PostgreSQL only."))
    assert [seen.value.id for seen in corpus.search("kafka", limit=5)] == ["doc_005", "doc_004"]
    assert [seen.value.id for seen in corpus.search("kafka", limit=1)] == ["doc_005"]
    assert corpus.search("redis", limit=5) == ()


# --- the faults -------------------------------------------------------------------


def test_a_switched_off_source_raises_unreachable_on_reads_and_writes() -> None:
    people = InMemoryPeople(reachable=False)
    with pytest.raises(SourceUnreachable, match="frappe unreachable") as caught:
        people.employee(ALICE)
    assert caught.value.source is Source.FRAPPE
    with pytest.raises(SourceUnreachable):
        people.add_employee(_employee(ALICE))


def test_a_duplicate_add_is_a_projector_bug_not_an_upsert() -> None:
    people = InMemoryPeople()
    people.add_employee(_employee(ALICE))
    with pytest.raises(ValueError, match="already exists"):
        people.add_employee(_employee(ALICE, skills=None))
    seen = people.employee(ALICE)
    assert seen is not None and seen.value.skills == (skill_id("kafka"),)


def test_the_two_faults_share_no_base_so_one_clause_cannot_catch_both() -> None:
    assert not issubclass(SourceUnreachable, MalformedRecord)
    assert not issubclass(MalformedRecord, SourceUnreachable)
    assert SourceUnreachable.__mro__[1:] == (Exception, BaseException, object)
    malformed = MalformedRecord(Source.JIRA, "LIA-42", "assignee has no world id")
    assert (malformed.source, malformed.locator) == (Source.JIRA, "LIA-42")
    assert str(malformed) == "jira record LIA-42: assignee has no world id"
