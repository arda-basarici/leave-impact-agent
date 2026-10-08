"""A completed read contributes to a proof when a witness names something it was the first to
supply: the record a fact or a gap was read from, the record or the enumeration that settled a
negative, the part of a window no earlier read had covered. Everything else completed is extra,
a later identical read included, and a failed or refused operation is neither. Over the reads
of a full investigation and a truthful report, the two together are every completed read once."""

from datetime import date, timedelta

import pytest

from leaveimpact.core import (
    AbsentOutcome,
    ClaimType,
    Consulted,
    CoverageAction,
    CoverageActionKind,
    DateSpan,
    EntityKind,
    InstantSpan,
    KindSlice,
    Operation,
    OperationId,
    RecordSlice,
    RecordsOutcome,
    RefusedCallOutcome,
    RunCondition,
    SliceStatus,
    Source,
    WindowSlice,
    Witness,
    comment_ref,
    employee_ref,
    is_completed_read,
)
from leaveimpact.core.ids import ClaimId, employee_id
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.proof_contribution import ProofContribution, proof_contribution
from leaveimpact.evaluator.replay import ClaimGrounding, Standing
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.unit import test_core_read_coverage as trace
from tests.unit import world_fixture as w
from tests.unit.reads_fixture import reads_of_everything
from tests.unit.replay_fixture import replayed
from tests.unit.report_fixture import of_type, truthful_report
from tests.unit.throwaway_world import loaded_world

COVERED = SliceStatus.COVERED
EVERY_TICKET = KindSlice(EntityKind.WORK_ITEM)
EVERY_DOCUMENT = KindSlice(EntityKind.DOCUMENT)
CAN, NOBODY = employee_ref(w.CAN), employee_ref(employee_id(99))


def contribution(operations: tuple[Operation, ...], *proof: Witness) -> ProofContribution:
    """The contribution of ``operations`` to one claim whose proof holds ``proof``."""
    record = ClaimGrounding(ClaimId("claim-1"), ClaimType.IMPACT, Standing.REPRODUCED, proof=proof)
    return proof_contribution(operations, (record,))


def split(*, contributing: tuple[str, ...] = (), extra: tuple[str, ...] = ()) -> ProofContribution:
    """The contribution that names these operations, by their ids as the fixture numbers them."""
    return ProofContribution(
        tuple(OperationId(id) for id in contributing), tuple(OperationId(id) for id in extra)
    )


def test_a_fact_and_a_gap_go_to_the_first_read_that_returned_what_they_were_read_from() -> None:
    operations = trace.reads(
        trace.by_id("employee", w.DENIZ, trace.DENIZ_RECORD),
        trace.listing("work_items", trace.TICKET),
        trace.by_id("work_item", w.TICKET, trace.TICKET),
        trace.listing("employees", trace.DENIZ_RECORD, trace.CAN_RECORD),
    )
    # The ticket's owner, a skill shown in one of its comments, and a blank skills field.
    found = contribution(operations, w.LIVE_OWNER, w.DENIZ_KAFKA_IN_COMMENT, w.DENIZ_SKILLS_GAP)
    assert found == split(contributing=("op-1", "op-2"), extra=("op-3", "op-4"))
    # A comment is read inside its ticket: the read that returned the ticket supplied it.
    assert w.DENIZ_KAFKA_IN_COMMENT.evidence.target == comment_ref(w.DENIZ_COMMENT)
    assert contribution(operations, w.DENIZ_KAFKA_IN_COMMENT).contributing == ("op-2",)


def test_a_record_that_settled_a_negative_goes_to_the_earliest_read_that_observed_it() -> None:
    listed = trace.listing("employees", trace.CAN_RECORD)
    by_id = trace.by_id("employee", w.CAN, trace.CAN_RECORD)
    missing = trace.by_id("employee", "emp_099", None)
    here, not_here = Consulted(RecordSlice(CAN), COVERED), Consulted(RecordSlice(NOBODY), COVERED)
    # Returned by its id, then inside the enumeration: the first.
    assert contribution(trace.reads(by_id, listed), here).contributing == ("op-1",)
    assert contribution(trace.reads(listed, by_id), here).contributing == ("op-1",)
    # Shown absent by the enumeration, or found missing by its id: whichever came first.
    assert contribution(trace.reads(listed, missing), not_here).contributing == ("op-1",)
    assert contribution(trace.reads(missing, listed), not_here).contributing == ("op-1",)
    # The read of another record observed nothing of this one.
    assert contribution(trace.reads(by_id, missing), not_here).contributing == ("op-2",)


def test_an_enumeration_that_closed_a_negative_is_the_first_read_of_its_kind_in_full() -> None:
    operations = trace.reads(
        trace.by_id("work_item", w.TICKET, trace.TICKET),
        trace.listing("work_items", trace.TICKET),
        trace.listing("work_items", trace.TICKET),
    )
    found = contribution(operations, Consulted(EVERY_TICKET, COVERED))
    assert found == split(contributing=("op-2",), extra=("op-1", "op-3"))


def test_each_part_of_a_window_goes_to_the_first_read_that_covered_it() -> None:
    week = Consulted(WindowSlice(EntityKind.LEAVE, w.LEAVE_SPAN), COVERED)  # 15 to 19 September
    first = trace.leaves_within(DateSpan(date(2026, 9, 14), date(2026, 9, 16)))
    rest = trace.leaves_within(DateSpan(date(2026, 9, 17), date(2026, 9, 20)))
    whole = trace.leaves_within(w.LEAVE_SPAN)
    elsewhere = trace.leaves_within(DateSpan(date(2026, 10, 1), date(2026, 10, 5)))
    # Two windows close the question between them; a third adds no day and is extra.
    between_them = contribution(trace.reads(first, elsewhere, rest, whole), week)
    assert between_them == split(contributing=("op-1", "op-3"), extra=("op-2", "op-4"))
    # The whole week first: the partial windows after it cover nothing new.
    assert contribution(trace.reads(whole, first, rest), week).contributing == ("op-1",)

    start, end = w.RELEASE_SPAN.start, w.RELEASE_SPAN.end
    half = timedelta(minutes=30)
    hour = Consulted(WindowSlice(EntityKind.EVENT, w.RELEASE_SPAN), COVERED)
    halves = trace.reads(
        trace.events_within(InstantSpan(start, start + half)),
        trace.events_within(InstantSpan(start - half, start + half)),  # nothing new of the hour
        trace.events_within(InstantSpan(start + half, end)),
        trace.events_within(w.RELEASE_SPAN),
    )
    assert contribution(halves, hour) == split(
        contributing=("op-1", "op-3"), extra=("op-2", "op-4")
    )
    # A window of the other read covers no part of this question.
    assert contribution(trace.reads(whole), hour).contributing == ()


def test_a_negative_that_needs_several_reads_attributes_each_and_an_unclosed_slice_none() -> None:
    operations = trace.reads(
        trace.by_id("employee", w.CAN, trace.CAN_RECORD),
        trace.listing("work_items", trace.TICKET),
        trace.by_id("document", "doc_007", trace.RUNBOOK),
    )
    # A skill not held: the HR record, every ticket, and the corpus, which no read closes.
    found = contribution(
        operations,
        Consulted(RecordSlice(CAN), COVERED),
        Consulted(EVERY_TICKET, COVERED),
        Consulted(EVERY_DOCUMENT, SliceStatus.UNCLOSABLE, waived=True),
    )
    assert found == split(contributing=("op-1", "op-2"), extra=("op-3",))


def test_what_stopped_an_answer_names_no_read_and_a_failed_or_refused_one_is_neither() -> None:
    refused: trace.Call = ("employee", {"id": "LIA-42"}, RefusedCallOutcome("not an employee id"))
    operations = trace.reads(
        trace.down("work_items"),
        refused,
        trace.by_id("employee", w.CAN, trace.CAN_RECORD),
    )
    found = contribution(
        operations,
        Consulted(EVERY_TICKET, SliceStatus.FAILED),
        Consulted(RecordSlice(NOBODY), SliceStatus.UNREAD),
    )
    assert found == split(contributing=(), extra=("op-3",))
    # With no claim at all, every completed read is extra, and only those.
    assert proof_contribution(operations, ()) == found


def test_an_operation_that_is_not_what_its_tool_declares_supplied_its_records_only() -> None:
    not_the_employees = Operation(
        trace.OperationId("op-1"),
        trace.PrefetchOrigin(),
        "employees",
        Source.FRAPPE,
        {},
        RecordsOutcome((trace.ALICE_LEAVE,)),
    )
    honest = Operation(
        trace.OperationId("op-2"),
        trace.PrefetchOrigin(),
        "employees",
        Source.FRAPPE,
        {},
        RecordsOutcome(()),
    )
    everyone = Consulted(KindSlice(EntityKind.EMPLOYEE), COVERED)
    assert contribution((not_the_employees, honest), everyone).contributing == ("op-2",)
    # The leave it returned was returned, whatever the call was recorded as.
    assert contribution((not_the_employees, honest), w.ALICE_ON_LEAVE).contributing == ("op-1",)
    absent = Operation(
        trace.OperationId("op-1"),
        trace.PrefetchOrigin(),
        "employee",
        Source.JIRA,
        {"id": w.CAN},
        AbsentOutcome(),
    )
    assert contribution((absent,), Consulted(RecordSlice(CAN), COVERED)).contributing == ()


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.mark.parametrize("down", [(), (Source.JIRA,), (Source.CALENDAR,)], ids=str)
def test_over_a_full_read_every_completed_read_is_contributing_or_extra_once(
    world: SealedWorld, down: tuple[Source, ...]
) -> None:
    condition = RunCondition.all_reachable().without(*down)
    contributing = extra = 0
    for scenario in world.scenarios:
        oracle = oracle_for(world, scenario, condition)
        assert isinstance(oracle, Answerable)
        operations = reads_of_everything(world, scenario, *down)
        claims = truthful_report(oracle)
        replays = replayed(world, scenario, claims, operations)
        groundings = replays.values()
        found = proof_contribution(operations, groundings)
        completed = [op.id for op in operations if is_completed_read(op.outcome)]
        assert sorted((*found.contributing, *found.extra)) == sorted(completed)
        assert not set(found.contributing) & set(found.extra)
        contributing += len(found.contributing)
        extra += len(found.extra)
        # The leave under investigation is read first, and every impact rests on it.
        if groundings:
            assert operations[0].id in found.contributing
        # The documents are read by id, one read each: a document no proof names is extra.
        assert found.extra, scenario.spec.id
        # A conclusion about everyone took its candidates from the enumeration of the
        # employees, and that read is credited for it whatever else consulted an HR record.
        about_everyone = [
            claim
            for claim in of_type(claims, CoverageAction)
            if claim.action is not CoverageActionKind.ASSIGN
        ]
        if about_everyone:
            listing = next(op.id for op in operations if op.tool == "employees")
            alone = proof_contribution(operations, [replays[about_everyone[0]]])
            assert alone.contributing == (listing,)
    # The thirty scenarios together. Nearly all the extra reads are the fixture's read of
    # every document of the world by its id, the corpus having no enumeration.
    measured: dict[tuple[Source, ...], tuple[int, int]] = {
        (): (156, 804),
        (Source.JIRA,): (58, 842),
        (Source.CALENDAR,): (124, 806),
    }
    assert (contributing, extra) == measured[down]
