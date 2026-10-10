"""Two reads of a structured source that cannot both be true, each shape beside the reads
that look like it and establish nothing."""

from dataclasses import replace
from datetime import UTC, date, datetime

from leaveimpact.core import Leave, LeaveKind, LeaveStatus, employee_ref, leave_ref
from leaveimpact.core.contradictions import (
    Contradiction,
    ContradictionKind,
    self_contradictions,
)
from leaveimpact.core.ids import employee_id, leave_id
from leaveimpact.core.refs import document_ref, event_ref
from leaveimpact.core.run_trace import AbsentOutcome, Operation, OperationId, PrefetchOrigin
from leaveimpact.core.timeshape import encode_date_span, encode_instant
from leaveimpact.core.worldtime import DateSpan, InstantSpan
from tests.unit import stated_fixture as f
from tests.unit.reads_fixture import FakeSystems, Recorder

LEAVE = Leave(
    leave_id(5), f.ALICE.id, date(2026, 3, 9), date(2026, 3, 13), LeaveKind.ANNUAL,
    LeaveStatus.APPROVED,
)  # fmt: skip
LEAVE_REF = leave_ref(LEAVE.id)
OVER_THE_LEAVE = {"span": encode_date_span(DateSpan(date(2026, 3, 9), date(2026, 3, 13)))}
BEFORE_THE_LEAVE = {"span": encode_date_span(DateSpan(date(2026, 3, 1), date(2026, 3, 8)))}


def systems() -> FakeSystems:
    held = FakeSystems()
    for employee in (f.ALICE, f.DENIZ):
        held.people.add_employee(employee)
    held.people.add_leave(LEAVE)
    held.work.add_component(f.PAYMENTS)
    held.work.add_work_item(f.TICKET)
    held.calendar.add_event(f.MEETING)
    held.documents.add_document(f.RUNBOOK)
    return held


def instants(start_day: int, end_day: int) -> dict[str, object]:
    span = InstantSpan(
        datetime(2026, 3, start_day, tzinfo=UTC), datetime(2026, 3, end_day, tzinfo=UTC)
    )
    return {"span": {"start": encode_instant(span.start), "end": encode_instant(span.end)}}


def found(reads: Recorder) -> tuple[Contradiction, ...]:
    return self_contradictions(reads.operations)


def test_reads_that_agree_hold_no_contradiction() -> None:
    reads = Recorder(systems())
    reads.read("leave", {"id": LEAVE.id})
    reads.read("employees")
    reads.read("employee", {"id": f.ALICE.id})
    reads.read("leaves_within", OVER_THE_LEAVE)
    reads.read("work_items")
    reads.read("work_item", {"id": f.TICKET.id})
    reads.read("events_within", instants(9, 12))
    reads.read("event", {"id": f.MEETING.id})
    assert found(reads) == ()


def test_one_record_returned_with_two_contents_whatever_the_reads() -> None:
    held = systems()
    reads = Recorder(held)
    reads.read("employee", {"id": f.ALICE.id})
    held.people.people[f.ALICE.id] = replace(f.ALICE, location="Berlin")
    reads.read("employee", {"id": f.ALICE.id})
    reads.read("employees")
    first, second, third = (operation.id for operation in reads.operations)
    alice = employee_ref(f.ALICE.id)
    # The repeated read by id, and the enumeration against the first return; the second and
    # the third agree with each other.
    assert found(reads) == (
        Contradiction(ContradictionKind.RETURNS_DIFFER, alice, first, second, second),
        Contradiction(ContradictionKind.RETURNS_DIFFER, alice, first, third, third),
    )


def test_a_record_found_by_one_read_and_missing_by_id_in_either_order() -> None:
    held = systems()
    reads = Recorder(held)
    reads.read("work_items")
    del held.work.tickets[f.TICKET.id]
    reads.read("work_item", {"id": f.TICKET.id})
    enumerated, by_id = (operation.id for operation in reads.operations)
    # The later read answered "no such record", and an absent answer anchors no defect:
    # the failure is sited at the read that returned the ticket.
    assert found(reads) == (
        Contradiction(
            ContradictionKind.RETURNED_AND_ABSENT, f.TICKET_REF, enumerated, by_id, enumerated
        ),
    )

    held = systems()
    del held.work.tickets[f.TICKET.id]
    reads = Recorder(held)
    reads.read("work_item", {"id": f.TICKET.id})
    held.work.add_work_item(f.TICKET)
    reads.read("work_items")
    by_id, enumerated = (operation.id for operation in reads.operations)
    assert found(reads) == (
        Contradiction(
            ContradictionKind.RETURNED_AND_ABSENT, f.TICKET_REF, by_id, enumerated, enumerated
        ),
    )


def test_an_enumeration_that_omits_a_record_read_by_id_in_either_order() -> None:
    for by_id_first in (True, False):
        held = systems()
        reads = Recorder(held)
        if by_id_first:
            reads.read("employee", {"id": f.DENIZ.id})
            del held.people.people[f.DENIZ.id]
            reads.read("employees")
        else:
            del held.people.people[f.DENIZ.id]
            reads.read("employees")
            held.people.add_employee(f.DENIZ)
            reads.read("employee", {"id": f.DENIZ.id})
        earlier, later = (operation.id for operation in reads.operations)
        assert found(reads) == (
            Contradiction(
                ContradictionKind.OMITTED_BY_ENUMERATION, f.DENIZ_REF, earlier, later, later
            ),
        )


def test_two_enumerations_that_differ_in_who_they_hold() -> None:
    held = systems()
    reads = Recorder(held)
    reads.read("employees")
    del held.people.people[f.DENIZ.id]
    reads.read("employees")
    first, second = (operation.id for operation in reads.operations)
    assert found(reads) == (
        Contradiction(ContradictionKind.OMITTED_BY_ENUMERATION, f.DENIZ_REF, first, second, second),
    )


def test_a_window_that_omits_a_leave_read_by_id_the_prefetchs_own_two_reads() -> None:
    held = systems()
    reads = Recorder(held)
    reads.read("leave", {"id": LEAVE.id})
    del held.people.leaves[LEAVE.id]
    reads.read("leaves_within", OVER_THE_LEAVE)
    by_id, window = (operation.id for operation in reads.operations)
    assert found(reads) == (
        Contradiction(ContradictionKind.OMITTED_BY_WINDOW, LEAVE_REF, by_id, window, window),
    )


def test_a_window_the_records_own_span_does_not_overlap_establishes_nothing() -> None:
    reads = Recorder(systems())
    reads.read("leave", {"id": LEAVE.id})
    reads.read("leaves_within", BEFORE_THE_LEAVE)
    assert found(reads) == ()


def test_an_event_window_speaks_by_half_open_instants() -> None:
    # The meeting is on the 10th from nine to ten. A window ending at its start does not
    # overlap it; one covering the day owes it.
    for window, owed in ((instants(9, 10), False), (instants(10, 11), True)):
        held = systems()
        reads = Recorder(held)
        reads.read("event", {"id": f.MEETING.id})
        del held.calendar.events[f.MEETING.id]
        reads.read("events_within", window)
        kinds = [contradiction.kind for contradiction in found(reads)]
        assert kinds == ([ContradictionKind.OMITTED_BY_WINDOW] if owed else [])
        if owed:
            assert found(reads)[0].record == event_ref(f.MEETING.id)


def test_a_failed_read_establishes_nothing() -> None:
    held = systems()
    reads = Recorder(held)
    reads.read("employee", {"id": f.DENIZ.id})
    held.people.reachable = False
    reads.read("employees")
    assert found(reads) == ()


def test_the_corpus_is_outside_the_rule() -> None:
    held = systems()
    reads = Recorder(held)
    reads.read("document", {"id": f.RUNBOOK.id})
    held.documents.held[f.RUNBOOK.id] = replace(f.RUNBOOK, title="Another title")
    reads.read("document", {"id": f.RUNBOOK.id})
    reads.read("search", {"query": "no such words anywhere", "limit": 5})
    assert found(reads) == ()
    # The coverage mapping still withdraws the document; that degrade is kept.
    from leaveimpact.core.read_coverage import coverage_from_reads

    assert document_ref(f.RUNBOOK.id) in coverage_from_reads(reads.operations).unobserved


def test_an_operation_that_is_not_what_its_tool_declares_is_no_witness() -> None:
    reads = Recorder(systems())
    reads.read("employees")
    # An ``employee`` call recorded against the tracker and answered "no such record" says
    # nothing about the HR system, here as in the coverage mapping.
    from leaveimpact.core import Source

    misfiled = Operation(
        OperationId("op-misfiled"),
        PrefetchOrigin(),
        "employee",
        Source.JIRA,
        {"id": f.ALICE.id},
        AbsentOutcome(),
        2,
    )
    assert self_contradictions((*reads.operations, misfiled)) == ()
    conforming = replace(misfiled, source=Source.FRAPPE)
    assert [c.kind for c in self_contradictions((*reads.operations, conforming))] == [
        ContradictionKind.RETURNED_AND_ABSENT
    ]


def test_a_record_another_id_was_asked_for_still_counts_as_returned() -> None:
    held = systems()
    reads = Recorder(held)
    reads.read("employees")
    stranger = replace(f.DENIZ, id=employee_id(77), name="Noor Haddad")
    held.people.people[f.DENIZ.id] = stranger
    reads.read("employee", {"id": f.DENIZ.id})
    assert [(c.kind, c.record.id) for c in found(reads)] == [
        (ContradictionKind.OMITTED_BY_ENUMERATION, stranger.id)
    ]


def test_a_failure_is_never_sited_at_a_read_that_answered_no_such_record() -> None:
    # Every history above and its mirror: whatever the order, the site returned records.
    for absent_first in (True, False):
        held = systems()
        reads = Recorder(held)
        if absent_first:
            del held.people.people[f.DENIZ.id]
            reads.read("employee", {"id": f.DENIZ.id})
            held.people.add_employee(f.DENIZ)
            reads.read("employees")
        else:
            reads.read("employees")
            del held.people.people[f.DENIZ.id]
            reads.read("employee", {"id": f.DENIZ.id})
        by_id = {operation.id: operation for operation in reads.operations}
        [contradiction] = found(reads)
        assert contradiction.kind is ContradictionKind.RETURNED_AND_ABSENT
        assert not isinstance(by_id[contradiction.site].outcome, AbsentOutcome)
        assert contradiction.site == next(
            operation.id for operation in reads.operations if operation.tool == "employees"
        )


def test_one_answer_holding_a_record_twice_with_two_contents() -> None:
    from leaveimpact.core import Observed, Source
    from leaveimpact.core.run_trace import RecordsOutcome

    moved = replace(f.ALICE, location="Berlin")
    twice = Operation(
        OperationId("op-1"),
        PrefetchOrigin(),
        "employees",
        Source.FRAPPE,
        {},
        RecordsOutcome((Observed(f.ALICE, Source.FRAPPE), Observed(moved, Source.FRAPPE))),
        1,
    )
    alice = employee_ref(f.ALICE.id)
    assert self_contradictions((twice,)) == (
        Contradiction(
            ContradictionKind.RETURNS_DIFFER,
            alice,
            OperationId("op-1"),
            OperationId("op-1"),
            OperationId("op-1"),
        ),
    )
    same = replace(
        twice,
        outcome=RecordsOutcome(
            (Observed(f.ALICE, Source.FRAPPE), Observed(f.ALICE, Source.FRAPPE))
        ),
    )
    assert self_contradictions((same,)) == ()
