"""Closure follows the five-step order — positive fact, unreachable domain source, gap, open
domain, false — with inaccessible ahead of absent ahead of insufficient, derives exactly
three unknown reasons, and answers subject-free questions keyed to the entity they are
about. A single-valued predicate is read through the authority table: the record's value
stands, a lower-authority fact is never promoted when the record is unreachable, and
multi-valued predicates keep the plain order."""

from dataclasses import replace
from datetime import date

import pytest

from leaveimpact.core import (
    REGISTRY,
    Fact,
    KnownFalse,
    KnownTrue,
    PredicateName,
    RunCondition,
    Source,
    UnknownReason,
    Unresolved,
    any_true,
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
NORMAL = RunCondition.all_reachable()
VIEW = w.WORLD.at(w.NOW, NORMAL)


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
        establish_any(VIEW, PredicateName.ATTENDS_EVENT, lambda fact: True, BOB)


def test_a_subject_free_question_is_keyed_to_the_entity_it_is_about() -> None:
    def attended_by_bob(fact: Fact) -> bool:
        return fact.value == BOB

    answer = establish_any(VIEW, PredicateName.ATTENDS_EVENT, attended_by_bob, RELEASE)
    assert isinstance(answer, KnownTrue)
    assert [fact.subject for fact in answer.facts] == [event_ref(w.OTHER_MEETING)]
    nobody = establish_any(
        VIEW, PredicateName.ATTENDS_EVENT, lambda fact: fact.value == DENIZ, RELEASE
    )
    assert nobody == KnownFalse()
    calendar_down = w.WORLD.at(w.NOW, NORMAL.without(Source.CALENDAR))
    assert establish_any(calendar_down, PredicateName.ATTENDS_EVENT, attended_by_bob, RELEASE) == (
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
    assert establish_any(VIEW, OWNS, lambda f: f.value == ALICE, TICKET) == KnownTrue(
        (w.LIVE_OWNER,)
    )
    assert establish_any(VIEW, OWNS, lambda f: f.value == BOB, TICKET) == KnownFalse()
    no_tracker = w.WORLD.at(w.NOW, NORMAL.without(Source.JIRA))
    assert establish_any(no_tracker, OWNS, lambda f: f.value == BOB, TICKET) == Unresolved(
        TICKET, OWNS, UnknownReason.INACCESSIBLE
    )
