"""A handful of records and the reads that return them, for the tests of what a model states.

Test infrastructure. The stated-fact tests need a run's reads with prose in them and need
no sealed world: two people, one component, a ticket Alice owns with a comment by Deniz, a
second ticket whose title is the first one's with a qualifier, a meeting, and a runbook of
one section that names the ticket by title. ``reads_of`` puts the records given into the
in-memory systems and reads them back through the executor, so the projection the tests
join statements to is the one a harness would build.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from leaveimpact.core import (
    CalendarEvent,
    Comment,
    Component,
    Document,
    DocumentKind,
    DocumentSection,
    Employee,
    EmploymentType,
    Grade,
    WorkItem,
    WorkItemStatus,
    clause_ref,
    comment_ref,
    employee_ref,
    work_item_ref,
)
from leaveimpact.core.comments import comment_text
from leaveimpact.core.ids import (
    clause_id,
    comment_id,
    component_id,
    document_id,
    employee_id,
    event_id,
    skill_id,
    team_id,
    work_item_id,
)
from leaveimpact.core.read_projection import StructuredReads, project_reads
from tests.unit.reads_fixture import FakeSystems, Recorder

TODAY = date(2026, 3, 2)

ALICE = Employee(
    employee_id(17), "Alice Demir", team_id(1), None, (skill_id("go"),),
    "Istanbul", "TR", "Europe/Istanbul", Grade.SENIOR, EmploymentType.EMPLOYEE,
)  # fmt: skip
DENIZ = Employee(
    employee_id(23), "Deniz Kaya", team_id(1), ALICE.id, (),
    "Istanbul", "TR", "Europe/Istanbul", Grade.MID, EmploymentType.EMPLOYEE,
)  # fmt: skip
PAYMENTS = Component(component_id(1), "Payments", (ALICE.id,))

REMARK = "I ran the Kafka migration last year and can take this one."
COMMENT = Comment(
    comment_id(1),
    date(2026, 2, 10),
    DENIZ.id,
    comment_text(comment_id(1), date(2026, 2, 10), DENIZ.id, DENIZ.name, REMARK),
)
TITLE = "Payments: rotate the keys"
TICKET = WorkItem(
    work_item_id(42), TITLE, ALICE.id, WorkItemStatus.IN_PROGRESS, PAYMENTS.id,
    date(2026, 1, 5), None, date(2026, 3, 20), (COMMENT,),
)  # fmt: skip
REGIONAL_TITLE = "Payments: rotate the keys for the EU region"
REGIONAL = WorkItem(
    work_item_id(43), REGIONAL_TITLE, ALICE.id, WorkItemStatus.TO_DO, PAYMENTS.id,
    date(2026, 1, 5), None, None, (),
)  # fmt: skip
MEETING = CalendarEvent(
    event_id(7),
    "Release review",
    datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
    datetime(2026, 3, 10, 10, 0, tzinfo=UTC),
    (ALICE.id,),
)
CLAUSE_TEXT = (
    f"The {TITLE} release needs two people with Kafka experience. Deniz Kaya owns {TITLE}."
)
RUNBOOK = Document(
    document_id(3),
    "Payments runbook",
    DocumentKind.RUNBOOK,
    date(2026, 1, 1),
    (DocumentSection(clause_id(11), CLAUSE_TEXT),),
)

ALICE_REF = employee_ref(ALICE.id)
DENIZ_REF = employee_ref(DENIZ.id)
TICKET_REF = work_item_ref(TICKET.id)
REGIONAL_REF = work_item_ref(REGIONAL.id)
COMMENT_REF = comment_ref(COMMENT.id)
CLAUSE_REF = clause_ref(clause_id(11))


def reads_of(
    *, work_items: tuple[WorkItem, ...] = (TICKET,), documents: tuple[Document, ...] = (RUNBOOK,)
) -> StructuredReads:
    """The projection of a run that enumerated the people, the components and the work items
    and read each of ``documents`` by its id, the systems holding what is given."""
    systems = FakeSystems()
    for employee in (ALICE, DENIZ):
        systems.people.add_employee(employee)
    systems.work.add_component(PAYMENTS)
    for item in work_items:
        systems.work.add_work_item(item)
    for document in documents:
        systems.documents.add_document(document)
    reads = Recorder(systems)
    reads.read("employees")
    reads.read("components")
    reads.read("work_items")
    for document in documents:
        reads.read("document", {"id": document.id})
    return project_reads(tuple(reads.operations), TODAY)
