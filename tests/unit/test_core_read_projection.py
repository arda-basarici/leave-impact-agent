"""The structured projection gives the rules what a run's reads returned and nothing else: each
usable record's facts dated to the run's day and stated once, nothing from a record the reads
disagree about, a record no fact can be made from named and withdrawn, and the coverage and
the condition of the same reads. It holds no fact that only prose states."""

from dataclasses import replace
from datetime import date

from leaveimpact.core import (
    Employee,
    Entity,
    EntityKind,
    Fact,
    KindSlice,
    Observed,
    RecordSlice,
    RunCondition,
    SliceStatus,
    Source,
    derive,
    employee_ref,
    project_reads,
)
from tests.unit import test_core_derivation as records
from tests.unit import world_fixture as w
from tests.unit.test_core_read_coverage import (
    ALICE_RECORD,
    BOB_RECORD,
    RUNBOOK,
    TICKET,
    TICKET_REF,
    as_returned,
    by_id,
    down,
    listing,
    reads,
)

TODAY = date(2026, 3, 2)
ALICE, BOB = employee_ref(w.ALICE), employee_ref(w.BOB)
EVERY_EMPLOYEE = KindSlice(EntityKind.EMPLOYEE)
COVERED, UNREAD, FAILED = SliceStatus.COVERED, SliceStatus.UNREAD, SliceStatus.FAILED


def changed(record: Observed[Entity], **fields: object) -> Observed[Entity]:
    """``record`` as the source would return it after a change to ``fields``."""
    assert isinstance(record.value, Employee)
    return as_returned(Observed(replace(record.value, **fields), record.source))


def about(facts: tuple[Fact, ...], who: object) -> list[Fact]:
    return [fact for fact in facts if fact.subject == who]


def test_a_usable_records_facts_are_its_own_dated_to_the_runs_day() -> None:
    projection = project_reads(reads(listing("employees", ALICE_RECORD, BOB_RECORD)), TODAY)
    assert projection.returned == (ALICE_RECORD, BOB_RECORD)
    assert projection.derived == (*derive(ALICE_RECORD, TODAY), *derive(BOB_RECORD, TODAY))
    assert projection.underivable == ()
    view = projection.view()
    assert view.now == TODAY
    assert view.facts == projection.facts
    assert all(fact.observable_from == TODAY for fact in view.facts)
    assert view.condition == RunCondition.all_reachable()


def test_a_record_returned_again_the_same_way_is_stated_once() -> None:
    once = project_reads(reads(listing("employees", ALICE_RECORD, BOB_RECORD)), TODAY)
    again = project_reads(
        reads(
            by_id("employee", w.ALICE, ALICE_RECORD), listing("employees", ALICE_RECORD, BOB_RECORD)
        ),
        TODAY,
    )
    assert again.returned == (ALICE_RECORD, BOB_RECORD)
    assert again.derived == once.derived
    assert again.reads.unobserved == frozenset()


def test_a_record_returned_two_ways_derives_nothing_and_stays_as_first_returned() -> None:
    moved = changed(ALICE_RECORD, location="Ankara")
    projection = project_reads(
        reads(by_id("employee", w.ALICE, ALICE_RECORD), listing("employees", moved, BOB_RECORD)),
        TODAY,
    )
    assert projection.returned == (ALICE_RECORD, BOB_RECORD)
    assert about(projection.facts, ALICE) == []
    assert about(projection.facts, BOB)
    assert projection.underivable == ()
    assert ALICE in projection.reads.unobserved
    assert projection.view().coverage.status(RecordSlice(ALICE)) is UNREAD


def test_a_record_returned_and_then_found_absent_derives_nothing() -> None:
    projection = project_reads(
        reads(by_id("employee", w.ALICE, ALICE_RECORD), by_id("employee", w.ALICE, None)), TODAY
    )
    assert projection.returned == (ALICE_RECORD,)
    assert projection.derived == ()
    assert projection.view().coverage.status(RecordSlice(ALICE)) is UNREAD


def test_a_record_no_fact_can_be_made_from_is_named_and_withdrawn_here() -> None:
    blank = changed(ALICE_RECORD, location="  ")
    projection = project_reads(reads(listing("employees", blank, BOB_RECORD)), TODAY)
    assert projection.underivable == (ALICE,)
    assert about(projection.facts, ALICE) == []
    assert about(projection.facts, BOB)
    # The reads did enumerate the employees; the view does not let the enumeration, or the
    # record's own return, close a negative about someone nothing could be derived for.
    assert projection.reads.status(EVERY_EMPLOYEE) is COVERED
    assert projection.coverage.status(EVERY_EMPLOYEE) is UNREAD
    assert projection.coverage.status(RecordSlice(ALICE)) is UNREAD
    assert projection.view().coverage.status(RecordSlice(BOB)) is COVERED


def test_what_was_read_before_a_source_failed_stays_and_the_condition_says_it_failed() -> None:
    projection = project_reads(
        reads(by_id("work_item", w.TICKET, TICKET), down("work_items")), TODAY
    )
    assert about(projection.facts, TICKET_REF)
    assert projection.condition.condition == RunCondition.all_reachable().without(Source.JIRA)
    assert projection.condition.mixed == frozenset({Source.JIRA})
    view = projection.view()
    assert view.condition == projection.condition.condition
    assert view.coverage.status(RecordSlice(TICKET_REF)) is COVERED
    assert view.coverage.status(KindSlice(EntityKind.WORK_ITEM)) is FAILED


def test_the_projection_holds_no_fact_a_comment_or_a_section_states() -> None:
    assert records.TICKET.value.comments
    projection = project_reads(
        reads(listing("work_items", TICKET), by_id("document", RUNBOOK.value.id, RUNBOOK)), TODAY
    )
    assert projection.returned == (TICKET, RUNBOOK)
    carriers = (EntityKind.COMMENT, EntityKind.CLAUSE)
    assert not [fact for fact in projection.facts if fact.evidence.target.kind in carriers]
    assert not about(projection.facts, RUNBOOK.ref)
