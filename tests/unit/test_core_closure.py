"""Closure follows the five-step order — positive fact, unreachable domain source, gap, open
domain, false — with inaccessible ahead of absent ahead of insufficient, derives exactly
three unknown reasons, and answers subject-free questions keyed to the entity they are
about. A single-valued predicate is read through the authority table: the record's value
stands, a lower-authority fact is never promoted when the record is unreachable, and
multi-valued predicates keep the plain order.

Over what a run read, observed is asked slice by slice and a sixth step sits between the
unreachable source and the gap: a slice that was not read is insufficient, never false.
The tests from "an unread slice" on state a run's reads by hand and hold the rule to them."""

from dataclasses import replace
from datetime import date

import pytest

from leaveimpact.core import (
    REGISTRY,
    Closure,
    EntityKind,
    EntityRef,
    Fact,
    FactView,
    KindSlice,
    KnownFalse,
    KnownTrue,
    PredicateName,
    RecordSlice,
    RunCondition,
    Slice,
    SliceStatus,
    Source,
    UnknownReason,
    Unresolved,
    WindowSlice,
    any_true,
    component_ref,
    employee_ref,
    establish,
    establish_any,
    event_ref,
    work_item_ref,
)
from tests.unit import world_fixture as w

ALICE = employee_ref(w.ALICE)
BOB = employee_ref(w.BOB)
DENIZ = employee_ref(w.DENIZ)
CAN = employee_ref(w.CAN)
RELEASE = event_ref(w.RELEASE)
TICKET = work_item_ref(w.TICKET)
OWNS = PredicateName.OWNS_WORK_ITEM
SKILL = PredicateName.HAS_SKILL
NORMAL = RunCondition.all_reachable()
VIEW = w.WORLD.at(w.NOW, NORMAL)

COVERED, FAILED = SliceStatus.COVERED, SliceStatus.FAILED
UNCLOSABLE = SliceStatus.UNCLOSABLE
EVERY_TICKET = KindSlice(EntityKind.WORK_ITEM)
EVERY_DOCUMENT = KindSlice(EntityKind.DOCUMENT)
INSUFFICIENT = UnknownReason.INSUFFICIENT
INACCESSIBLE = UnknownReason.INACCESSIBLE


def test_a_positive_fact_is_known_true_with_the_facts_that_established_it() -> None:
    assert establish(VIEW, ALICE, PredicateName.HAS_SKILL, w.KAFKA) == KnownTrue(
        (w.hr(w.ALICE, PredicateName.HAS_SKILL, w.KAFKA, "skills"),)
    )
    # Without a value the question is existential: any skill at all.
    assert isinstance(establish(VIEW, CAN, PredicateName.HAS_SKILL), KnownTrue)


def test_no_evidence_in_a_fully_observed_closed_domain_is_known_false() -> None:
    assert establish(VIEW, CAN, PredicateName.HAS_SKILL, w.KAFKA) == KnownFalse()
    assert establish(VIEW, BOB, PredicateName.MEMBER_OF_COMPONENT) == KnownFalse()


def test_a_gap_blocks_the_closed_world_inference() -> None:
    before_the_comment = w.WORLD.at(date(2026, 5, 1), NORMAL)
    assert establish(before_the_comment, DENIZ, PredicateName.HAS_SKILL, w.KAFKA) == Unresolved(
        DENIZ, PredicateName.HAS_SKILL, UnknownReason.ABSENT
    )
    # The June comment is positive evidence from inside the domain: known true from then on.
    assert establish(VIEW, DENIZ, PredicateName.HAS_SKILL, w.KAFKA) == KnownTrue(
        (w.DENIZ_KAFKA_IN_COMMENT,)
    )


def test_an_unreachable_domain_source_is_inaccessible_and_outranks_absent() -> None:
    jira_down = w.WORLD.at(w.NOW, NORMAL.without(Source.JIRA))
    assert establish(jira_down, DENIZ, PredicateName.HAS_SKILL, w.KAFKA) == Unresolved(
        DENIZ, PredicateName.HAS_SKILL, UnknownReason.INACCESSIBLE
    )
    # Can's known false turns into inaccessible: the tracker could have held a comment.
    assert establish(jira_down, CAN, PredicateName.HAS_SKILL, w.KAFKA) == Unresolved(
        CAN, PredicateName.HAS_SKILL, UnknownReason.INACCESSIBLE
    )
    # A predicate whose domain the outage does not touch is unaffected.
    assert isinstance(establish(jira_down, ALICE, PredicateName.MEMBER_OF_TEAM), KnownTrue)


def test_an_open_domain_is_insufficient_never_false() -> None:
    open_registry = dict(REGISTRY)
    open_registry[PredicateName.HAS_SKILL] = replace(
        REGISTRY[PredicateName.HAS_SKILL], closed=False
    )
    assert establish(
        VIEW, CAN, PredicateName.HAS_SKILL, w.KAFKA, registry=open_registry
    ) == Unresolved(CAN, PredicateName.HAS_SKILL, UnknownReason.INSUFFICIENT)
    # Precedence: a gap still outranks the open domain, an outage outranks both.
    early = w.WORLD.at(date(2026, 5, 1), NORMAL)
    assert establish(early, DENIZ, PredicateName.HAS_SKILL, registry=open_registry) == Unresolved(
        DENIZ, PredicateName.HAS_SKILL, UnknownReason.ABSENT
    )
    early_jira_down = w.WORLD.at(date(2026, 5, 1), NORMAL.without(Source.JIRA))
    assert establish(
        early_jira_down, DENIZ, PredicateName.HAS_SKILL, registry=open_registry
    ) == Unresolved(DENIZ, PredicateName.HAS_SKILL, UnknownReason.INACCESSIBLE)


def test_a_query_value_the_spec_refuses_raises_instead_of_answering_false() -> None:
    with pytest.raises(ValueError, match="has_skill: expected a skill, got 'Kafka'"):
        establish(VIEW, CAN, PredicateName.HAS_SKILL, "Kafka")
    with pytest.raises(
        ValueError, match="member_of_component: expected an entity_ref to a component"
    ):
        establish(VIEW, CAN, PredicateName.MEMBER_OF_COMPONENT, work_item_ref(w.TICKET))


def test_a_subject_of_the_wrong_kind_is_refused() -> None:
    with pytest.raises(ValueError, match="has_skill is a fact about an employee, got a work_item"):
        establish(VIEW, work_item_ref(w.TICKET), PredicateName.HAS_SKILL)
    with pytest.raises(ValueError, match="attends_event is a fact about an event, got an employee"):
        establish_any(VIEW, PredicateName.ATTENDS_EVENT, lambda fact: True, BOB, scope=None)


def test_a_subject_free_question_is_keyed_to_the_entity_it_is_about() -> None:
    def attended_by_bob(fact: Fact) -> bool:
        return fact.value == BOB

    attends = PredicateName.ATTENDS_EVENT
    answer = establish_any(VIEW, attends, attended_by_bob, RELEASE, scope=None)
    assert isinstance(answer, KnownTrue)
    assert [fact.subject for fact in answer.facts] == [event_ref(w.OTHER_MEETING)]
    nobody = establish_any(VIEW, attends, lambda fact: fact.value == DENIZ, RELEASE, scope=None)
    assert nobody == KnownFalse()
    calendar_down = w.WORLD.at(w.NOW, NORMAL.without(Source.CALENDAR))
    assert establish_any(calendar_down, attends, attended_by_bob, RELEASE, scope=None) == (
        Unresolved(RELEASE, PredicateName.ATTENDS_EVENT, UnknownReason.INACCESSIBLE)
    )


def test_any_true_is_true_over_unresolved_over_false_and_false_when_nothing_was_asked() -> None:
    unresolved = Unresolved(DENIZ, PredicateName.HAS_SKILL, UnknownReason.ABSENT)
    established = KnownTrue((w.DENIZ_KAFKA_IN_COMMENT,))
    assert any_true(()) == KnownFalse()
    assert any_true((KnownFalse(), unresolved)) == unresolved
    assert any_true((unresolved, KnownFalse(), established)) == established
    assert any_true((established, established)) == KnownTrue(
        (w.DENIZ_KAFKA_IN_COMMENT, w.DENIZ_KAFKA_IN_COMMENT)
    )


def test_a_single_valued_predicate_is_read_through_the_authority_table() -> None:
    # The tracker says Alice and a runbook says Bob: the record's value stands, carrying
    # only the facts that agree with it; the stale value is not known true merely because
    # a positive fact states it.
    assert establish(VIEW, TICKET, OWNS, ALICE) == KnownTrue((w.LIVE_OWNER,))
    assert establish(VIEW, TICKET, OWNS) == KnownTrue((w.LIVE_OWNER,))
    assert establish(VIEW, TICKET, OWNS, BOB) == KnownFalse()


def test_a_lower_authority_fact_is_not_promoted_when_the_record_is_unreachable() -> None:
    no_tracker = w.WORLD.at(w.NOW, NORMAL.without(Source.JIRA))
    for asked in (ALICE, BOB, None):
        assert establish(no_tracker, TICKET, OWNS, asked) == Unresolved(
            TICKET, OWNS, UnknownReason.INACCESSIBLE
        )


def test_the_record_alone_settles_a_single_valued_question() -> None:
    no_corpus = w.WORLD.at(w.NOW, NORMAL.without(Source.CORPUS))
    assert establish(no_corpus, TICKET, OWNS, ALICE) == KnownTrue((w.LIVE_OWNER,))
    assert establish(no_corpus, TICKET, OWNS, BOB) == KnownFalse()


def test_a_multi_valued_predicate_keeps_the_plain_order() -> None:
    # Deniz's Kafka lives only in a ticket comment; with HR unreachable it is still evidence.
    no_hr = w.WORLD.at(w.NOW, NORMAL.without(Source.FRAPPE))
    assert establish(no_hr, DENIZ, PredicateName.HAS_SKILL, w.KAFKA) == KnownTrue(
        (w.DENIZ_KAFKA_IN_COMMENT,)
    )


def test_a_subject_free_question_over_a_single_valued_predicate_resolves_per_subject() -> None:
    assert establish_any(
        VIEW, OWNS, lambda f: f.value == ALICE, TICKET, scope=None
    ) == KnownTrue((w.LIVE_OWNER,))
    assert establish_any(VIEW, OWNS, lambda f: f.value == BOB, TICKET, scope=None) == KnownFalse()
    no_tracker = w.WORLD.at(w.NOW, NORMAL.without(Source.JIRA))
    assert establish_any(
        no_tracker, OWNS, lambda f: f.value == BOB, TICKET, scope=None
    ) == Unresolved(TICKET, OWNS, UnknownReason.INACCESSIBLE)


# --- Over what a run read -----------------------------------------------------------------


def test_an_unread_slice_is_insufficient_never_false() -> None:
    # Can's HR record lists no Kafka, and a ticket comment could still show it.
    record_only = w.view_observing({RecordSlice(CAN): COVERED, EVERY_DOCUMENT: UNCLOSABLE})
    assert establish(record_only, CAN, SKILL, w.KAFKA) == Unresolved(CAN, SKILL, INSUFFICIENT)
    with_every_ticket = w.view_observing(
        {RecordSlice(CAN): COVERED, EVERY_TICKET: COVERED, EVERY_DOCUMENT: UNCLOSABLE}
    )
    assert establish(with_every_ticket, CAN, SKILL, w.KAFKA) == KnownFalse()
    # Nothing read at all: nothing is false.
    assert establish(w.view_observing({}, facts=(), gaps=()), CAN, SKILL, w.KAFKA) == Unresolved(
        CAN, SKILL, INSUFFICIENT
    )


def test_a_slice_that_could_not_be_read_outranks_one_that_was_not() -> None:
    tracker_failed = w.view_observing({EVERY_TICKET: FAILED, EVERY_DOCUMENT: UNCLOSABLE})
    assert establish(tracker_failed, CAN, SKILL, w.KAFKA) == Unresolved(CAN, SKILL, INACCESSIBLE)


def test_an_unread_slice_outranks_a_gap_and_a_gap_shows_once_every_slice_was_observed() -> None:
    # Deniz's skills field is blank; nothing anywhere shows PostgreSQL.
    record_only = w.view_observing({RecordSlice(DENIZ): COVERED, EVERY_DOCUMENT: UNCLOSABLE})
    assert establish(record_only, DENIZ, SKILL, w.POSTGRES) == Unresolved(
        DENIZ, SKILL, INSUFFICIENT
    )
    with_every_ticket = w.view_observing(
        {RecordSlice(DENIZ): COVERED, EVERY_TICKET: COVERED, EVERY_DOCUMENT: UNCLOSABLE}
    )
    assert establish(with_every_ticket, DENIZ, SKILL, w.POSTGRES) == Unresolved(
        DENIZ, SKILL, UnknownReason.ABSENT
    )


def test_prose_no_read_enumerates_does_not_hold_a_negative_back_and_an_outage_does() -> None:
    observed: dict[Slice, SliceStatus] = {RecordSlice(CAN): COVERED, EVERY_TICKET: COVERED}
    unclosable = w.view_observing({**observed, EVERY_DOCUMENT: UNCLOSABLE})
    assert establish(unclosable, CAN, SKILL, w.KAFKA) == KnownFalse()
    corpus_down = w.view_observing({**observed, EVERY_DOCUMENT: FAILED})
    assert establish(corpus_down, CAN, SKILL, w.KAFKA) == Unresolved(CAN, SKILL, INACCESSIBLE)


def test_a_slice_no_read_observes_whole_stays_open_where_nothing_waives_it() -> None:
    # Every leave there is: no read lists them, and no placement waives that.
    on_leave = PredicateName.ON_LEAVE
    view = w.view_observing({KindSlice(EntityKind.LEAVE): UNCLOSABLE}, otherwise=COVERED)
    assert establish(view, BOB, on_leave) == Unresolved(BOB, on_leave, INSUFFICIENT)


def test_a_positive_fact_of_a_multi_valued_predicate_is_evidence_whatever_was_observed() -> None:
    # One ticket read by its id, with Deniz's comment on it: his HR record and every other
    # ticket unread, and the comment is evidence all the same.
    one_ticket = w.view_observing(
        {RecordSlice(TICKET): COVERED}, facts=(w.DENIZ_KAFKA_IN_COMMENT,), gaps=()
    )
    assert establish(one_ticket, DENIZ, SKILL, w.KAFKA) == KnownTrue((w.DENIZ_KAFKA_IN_COMMENT,))


def test_non_membership_is_settled_by_the_components_record_and_not_by_the_employees() -> None:
    membership, payments = PredicateName.MEMBER_OF_COMPONENT, component_ref(w.PAYMENTS)
    employee_only = w.view_observing({RecordSlice(BOB): COVERED})
    assert establish(employee_only, BOB, membership, payments) == Unresolved(
        BOB, membership, INSUFFICIENT
    )
    the_component = w.view_observing({RecordSlice(payments): COVERED})
    assert establish(the_component, BOB, membership, payments) == KnownFalse()
    # Asked of any component at all, one component's record is not every component's.
    assert establish(the_component, BOB, membership) == Unresolved(BOB, membership, INSUFFICIENT)


def test_an_unobserved_record_never_lets_a_lower_authority_fact_stand() -> None:
    # A runbook names Bob; the tracker was never asked about the ticket.
    runbook_only = w.view_observing({}, facts=(w.STALE_OWNER,), gaps=())
    for asked in (ALICE, BOB, None):
        assert establish(runbook_only, TICKET, OWNS, asked) == Unresolved(
            TICKET, OWNS, INSUFFICIENT
        )
    tracker_failed = w.view_observing(
        {RecordSlice(TICKET): FAILED}, facts=(w.STALE_OWNER,), gaps=()
    )
    assert establish(tracker_failed, TICKET, OWNS, BOB) == Unresolved(TICKET, OWNS, INACCESSIBLE)


def test_an_observed_record_lets_authority_resolve() -> None:
    ticket_read: dict[Slice, SliceStatus] = {
        RecordSlice(TICKET): COVERED,
        EVERY_DOCUMENT: UNCLOSABLE,
    }
    both = w.view_observing(ticket_read, facts=(w.LIVE_OWNER, w.STALE_OWNER), gaps=())
    assert establish(both, TICKET, OWNS, ALICE) == KnownTrue((w.LIVE_OWNER,))
    assert establish(both, TICKET, OWNS, BOB) == KnownFalse()
    # The record observed and silent: answered is the line, and the runbook's value stands.
    silent = w.view_observing(ticket_read, facts=(w.STALE_OWNER,), gaps=())
    assert establish(silent, TICKET, OWNS, BOB) == KnownTrue((w.STALE_OWNER,))


def test_a_subject_free_negative_needs_its_scope_observed() -> None:
    on_leave = PredicateName.ON_LEAVE
    week = WindowSlice(EntityKind.LEAVE, w.LEAVE_SPAN)

    def asked_of(view: FactView, who: EntityRef) -> Closure:
        return establish_any(
            view,
            on_leave,
            lambda fact: fact.subject == who and fact.value == w.LEAVE_SPAN,
            who,
            scope=w.LEAVE_SPAN,
        )

    # Alice's leave read by its id: evidence that she is away, and nothing about Bob.
    one_leave = w.view_observing({}, facts=(w.ALICE_ON_LEAVE,), gaps=())
    assert asked_of(one_leave, ALICE) == KnownTrue((w.ALICE_ON_LEAVE,))
    assert asked_of(one_leave, BOB) == Unresolved(BOB, on_leave, INSUFFICIENT)
    the_week = w.view_observing({week: COVERED}, facts=(w.ALICE_ON_LEAVE,), gaps=())
    assert asked_of(the_week, BOB) == KnownFalse()
    hr_failed = w.view_observing({week: FAILED}, facts=(), gaps=())
    assert asked_of(hr_failed, BOB) == Unresolved(BOB, on_leave, INACCESSIBLE)
