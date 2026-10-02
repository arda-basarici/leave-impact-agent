"""Every answer carries what it rests on. A negative shows the slices that settled it and the
source left unclosed; a positive its facts, and the record authority read it through; an
open answer what was seen and what stopped it. A proof names slices and never reads, so one
question has one proof over the truth and over a run that read enough, and it is no part of
an answer's identity. Grounding and viability carry their questions' proofs through."""

from leaveimpact.core import (
    Assessment,
    Consulted,
    EntityKind,
    FactView,
    Grounded,
    ImpactKey,
    ImpactSubtype,
    KindSlice,
    KnownFalse,
    KnownTrue,
    PredicateName,
    RecordSlice,
    RunCondition,
    Slice,
    SliceStatus,
    Source,
    Ungrounded,
    UnknownReason,
    Unresolved,
    Verdict,
    WindowSlice,
    WorkItemStatus,
    assess,
    assess_impact,
    component_ref,
    employee_ref,
    establish,
    event_ref,
    ground_impact,
    need_of,
    work_item_ref,
)
from leaveimpact.core.viability import Need
from tests.unit import world_fixture as w

ALICE = employee_ref(w.ALICE)
BOB = employee_ref(w.BOB)
DENIZ = employee_ref(w.DENIZ)
CAN = employee_ref(w.CAN)
TICKET = work_item_ref(w.TICKET)
PAYMENTS = component_ref(w.PAYMENTS)
OWNS = PredicateName.OWNS_WORK_ITEM
SKILL = PredicateName.HAS_SKILL
NORMAL = RunCondition.all_reachable()
VIEW = w.WORLD.at(w.NOW, NORMAL)

COVERED, UNREAD = SliceStatus.COVERED, SliceStatus.UNREAD
UNCLOSABLE, FAILED = SliceStatus.UNCLOSABLE, SliceStatus.FAILED
EVERY_TICKET = KindSlice(EntityKind.WORK_ITEM)
EVERY_DOCUMENT = KindSlice(EntityKind.DOCUMENT)
STATUS = w.ticket(PredicateName.WORK_ITEM_STATUS, WorkItemStatus.IN_PROGRESS, "status")
DUE = next(fact for fact in w.FACTS if fact.predicate is PredicateName.DUE_ON)
TICKET_DUTY = ImpactKey(w.LEAVE, ImpactSubtype.RESPONSIBILITY, TICKET)


def observed(where: Slice) -> Consulted:
    return Consulted(where, COVERED)


def meeting_need(view: FactView) -> Need:
    need = need_of(view, w.MEETING, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE)
    assert isinstance(need, Need)
    return need


# --- Closure --------------------------------------------------------------------------------


def test_a_negative_carries_the_slices_that_settled_it_and_the_source_left_unclosed() -> None:
    view = w.view_observing(
        {RecordSlice(CAN): COVERED, EVERY_TICKET: COVERED, EVERY_DOCUMENT: UNCLOSABLE}
    )
    lacks_kafka = establish(view, CAN, SKILL, w.KAFKA)
    assert lacks_kafka == KnownFalse()
    # The exact record a claim can cite, the prose no read enumerates, the enumeration.
    assert lacks_kafka.proof == (
        observed(RecordSlice(CAN)),
        Consulted(EVERY_DOCUMENT, UNCLOSABLE, waived=True),
        observed(EVERY_TICKET),
    )


def test_one_question_has_one_proof_over_the_truth_and_over_a_run_that_read_enough() -> None:
    membership = PredicateName.MEMBER_OF_COMPONENT
    one_component = w.view_observing({RecordSlice(PAYMENTS): COVERED})
    over_truth = establish(VIEW, BOB, membership, PAYMENTS)
    over_reads = establish(one_component, BOB, membership, PAYMENTS)
    assert over_truth.proof == over_reads.proof == (observed(RecordSlice(PAYMENTS)),)


def test_a_proof_is_no_part_of_an_answers_identity() -> None:
    proof = (observed(RecordSlice(CAN)),)
    assert KnownFalse() == KnownFalse(proof)
    assert hash(KnownFalse()) == hash(KnownFalse(proof))
    assert KnownTrue(()) == KnownTrue((), proof)
    bare = Unresolved(CAN, SKILL, UnknownReason.ABSENT)
    assert bare == Unresolved(CAN, SKILL, UnknownReason.ABSENT, proof)
    # One unknown however many questions left it open, which is how an assessment lists them.
    assert len({bare, Unresolved(CAN, SKILL, UnknownReason.ABSENT, proof)}) == 1
    assert Grounded(()) == Grounded((), proof)
    assert Ungrounded() == Ungrounded(proof)


def test_a_positive_answers_proof_holds_its_facts_and_the_record_authority_read_through() -> None:
    kafka = w.hr(w.ALICE, SKILL, w.KAFKA, "skills")
    # A skill is evidence wherever it was read: nothing else was asked.
    assert establish(VIEW, ALICE, SKILL, w.KAFKA).proof == (kafka,)
    assert establish(VIEW, TICKET, OWNS, ALICE).proof == (
        w.LIVE_OWNER,
        observed(RecordSlice(TICKET)),
    )


def test_a_negative_decided_by_a_fact_carries_that_fact() -> None:
    # Bob does not own the ticket because the tracker says Alice does.
    assert establish(VIEW, TICKET, OWNS, BOB).proof == (
        w.LIVE_OWNER,
        observed(RecordSlice(TICKET)),
    )


def test_an_open_answer_carries_what_was_seen_and_what_stopped_it() -> None:
    absent = establish(VIEW, DENIZ, SKILL, w.POSTGRES)
    assert absent == Unresolved(DENIZ, SKILL, UnknownReason.ABSENT)
    assert absent.proof == (
        w.DENIZ_SKILLS_GAP,
        observed(RecordSlice(DENIZ)),
        observed(EVERY_DOCUMENT),
        observed(EVERY_TICKET),
    )
    # An unclosable slice in an answer something else stopped is not waived: with the
    # tickets unread the skill question is open, and it does not rest on the corpus.
    record_only = w.view_observing({RecordSlice(CAN): COVERED, EVERY_DOCUMENT: UNCLOSABLE})
    stopped = establish(record_only, CAN, SKILL, w.KAFKA)
    assert Consulted(EVERY_DOCUMENT, UNCLOSABLE) in stopped.proof
    assert not any(isinstance(each, Consulted) and each.waived for each in stopped.proof)
    # The runbook's owner was seen and not promoted: the tracker's record was never read.
    runbook_only = w.view_observing({}, facts=(w.STALE_OWNER,), gaps=())
    assert establish(runbook_only, TICKET, OWNS, BOB).proof == (
        w.STALE_OWNER,
        Consulted(RecordSlice(TICKET), UNREAD),
    )


# --- Grounding ------------------------------------------------------------------------------


def test_a_responsibility_grounded_by_no_due_date_carries_the_tickets_record() -> None:
    undated = w.view_observing(
        {}, otherwise=COVERED, facts=tuple(fact for fact in w.FACTS if fact != DUE)
    )
    duty = ground_impact(undated, TICKET_DUTY, w.ALICE, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE)
    assert duty == Grounded((w.LIVE_OWNER, STATUS))
    # No fact says a date is absent; the ticket's record observed without one is the witness.
    assert duty.proof == (w.LIVE_OWNER, STATUS, observed(RecordSlice(TICKET)))


def test_an_ungrounded_impact_carries_the_fact_that_decided_it() -> None:
    # The ticket has a due date, so it is no undated responsibility.
    duty = ground_impact(VIEW, TICKET_DUTY, w.ALICE, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE)
    assert duty == Ungrounded()
    assert DUE in duty.proof
    # Bob holds no deadline on it: the tracker's owner is what says so.
    deadline = ground_impact(VIEW, w.DEADLINE, w.BOB, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE)
    assert deadline == Ungrounded()
    assert w.LIVE_OWNER in deadline.proof


# --- Viability ------------------------------------------------------------------------------


def test_an_assessment_carries_everything_the_rule_read() -> None:
    deadline = need_of(VIEW, w.DEADLINE, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE)
    assert isinstance(deadline, Need)
    can = assess(VIEW, deadline, w.CAN, w.CONSTRAINTS)
    assert can.verdict is Verdict.NON_VIABLE
    assert can.proof[: len(can.evidence)] == can.evidence
    # What the skill negative rests on, and the window that says he is not away.
    for where in (
        RecordSlice(CAN),
        EVERY_TICKET,
        EVERY_DOCUMENT,
        WindowSlice(EntityKind.LEAVE, w.LEAVE_SPAN),
    ):
        assert observed(where) in can.proof
    # An assessment's identity is its verdict and what it lists, as it was.
    assert can == Assessment(
        can.impact, can.employee_id, can.verdict, can.reasons, can.unresolved, can.evidence
    )


def test_busy_rests_on_who_attends_as_well_as_on_the_schedule() -> None:
    bob = assess(VIEW, meeting_need(VIEW), w.BOB, w.CONSTRAINTS)
    schedule = w.scheduled(w.OTHER_MEETING, w.OTHER_SPAN)
    attendance = w.attends(w.OTHER_MEETING, w.BOB)
    assert schedule in bob.evidence
    assert attendance not in bob.evidence
    assert attendance in bob.proof


def test_free_over_the_meeting_rests_on_its_span_observed() -> None:
    deniz = assess(VIEW, meeting_need(VIEW), w.DENIZ, w.CONSTRAINTS)
    assert deniz.verdict is Verdict.VIABLE
    assert observed(WindowSlice(EntityKind.EVENT, w.RELEASE_SPAN)) in deniz.proof


def test_an_unreadable_need_carries_what_stopped_it() -> None:
    calendar_down = w.WORLD.at(w.NOW, NORMAL.without(Source.CALENDAR))
    everyone = assess_impact(
        calendar_down, w.MEETING, w.EVERYONE, w.CONSTRAINTS, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE
    )
    stopped = Consulted(RecordSlice(event_ref(w.RELEASE)), FAILED)
    assert all(assessment.verdict is Verdict.UNKNOWN for assessment in everyone)
    assert all(assessment.proof == (stopped,) for assessment in everyone)
