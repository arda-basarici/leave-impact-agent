"""The fact base validates at the boundary — subject kind, value spec, evidence domain — refuses
incoherent bases, and its view admits only what a run at ``now`` under a condition can see."""

from datetime import date

import pytest

from leaveimpact.core import (
    EvidenceRef,
    Fact,
    FactBase,
    Gap,
    PredicateName,
    RunCondition,
    Source,
    clause_ref,
    component_ref,
    employee_ref,
    event_ref,
    team_ref,
    work_item_ref,
)
from leaveimpact.core.ids import clause_id, component_id, team_id
from tests.unit import world_fixture as w

ALICE = employee_ref(w.ALICE)
DENIZ = employee_ref(w.DENIZ)
TICKET = work_item_ref(w.TICKET)
NORMAL = RunCondition.all_reachable()


def test_a_fact_is_validated_against_its_registry_row() -> None:
    with pytest.raises(ValueError, match="has_skill is a fact about an employee, got a work_item"):
        Fact(TICKET, PredicateName.HAS_SKILL, "kafka", EvidenceRef(Source.JIRA, TICKET), w.NOW)
    with pytest.raises(ValueError, match="has_skill: expected a skill, got 'Kafka'"):
        w.hr(w.ALICE, PredicateName.HAS_SKILL, "Kafka", "skills")
    with pytest.raises(ValueError, match="calendar is outside the evidence domain of has_skill"):
        Fact(
            ALICE,
            PredicateName.HAS_SKILL,
            "kafka",
            EvidenceRef(Source.CALENDAR, event_ref(w.RELEASE), "description"),
            w.NOW,
        )


def test_a_gap_is_validated_like_a_fact_and_never_carries_a_value() -> None:
    with pytest.raises(ValueError, match="due_on is a fact about a work_item, got an employee"):
        Gap(ALICE, PredicateName.DUE_ON, EvidenceRef(Source.FRAPPE, ALICE, "due"), w.NOW)
    with pytest.raises(ValueError, match="corpus is outside the evidence domain of has_skill"):
        Gap(
            ALICE,
            PredicateName.HAS_SKILL,
            EvidenceRef(Source.CORPUS, clause_ref(w.KAFKA_CLAUSE)),
            w.NOW,
        )


def test_the_base_refuses_a_fact_stated_twice_and_a_source_that_both_holds_and_lacks() -> None:
    with pytest.raises(ValueError, match="a fact is stated once"):
        FactBase((w.LIVE_OWNER, w.LIVE_OWNER))
    with pytest.raises(ValueError, match="a gap is stated once"):
        FactBase((), (w.DENIZ_SKILLS_GAP, w.DENIZ_SKILLS_GAP))
    with pytest.raises(ValueError, match="frappe cannot both hold a value and hold none"):
        FactBase(
            (w.hr(w.DENIZ, PredicateName.HAS_SKILL, "kafka", "skills"),), (w.DENIZ_SKILLS_GAP,)
        )


def test_one_source_cannot_give_two_values_to_a_single_valued_predicate() -> None:
    with pytest.raises(ValueError, match="jira holds two values for in_component"):
        FactBase(
            (
                w.ticket(PredicateName.IN_COMPONENT, component_ref(w.PAYMENTS), "component_id"),
                w.ticket(
                    PredicateName.IN_COMPONENT, component_ref(component_id(2)), "component_id"
                ),
            )
        )
    # Two sources disagreeing is a planted conflict, not an incoherent base.
    assert FactBase((w.LIVE_OWNER, w.STALE_OWNER)).facts == (w.LIVE_OWNER, w.STALE_OWNER)
    # A multi-valued predicate holds a set per source.
    FactBase(
        (
            w.hr(w.ALICE, PredicateName.HAS_SKILL, "kafka", "skills"),
            w.hr(w.ALICE, PredicateName.HAS_SKILL, "postgres", "skills"),
        )
    )


def test_the_view_admits_facts_dated_at_or_before_now() -> None:
    before_comment = w.WORLD.at(date(2026, 6, 9), NORMAL)
    on_comment_day = w.WORLD.at(w.COMMENT_DATE, NORMAL)
    assert before_comment.facts_about(DENIZ, PredicateName.HAS_SKILL) == ()
    assert on_comment_day.facts_about(DENIZ, PredicateName.HAS_SKILL) == (w.DENIZ_KAFKA_IN_COMMENT,)
    assert w.WORLD.at(date(2026, 8, 31), NORMAL).facts_about(ALICE, PredicateName.ON_LEAVE) == ()
    assert w.WORLD.at(w.NOW, NORMAL).facts_about(ALICE, PredicateName.ON_LEAVE) == (
        w.ALICE_ON_LEAVE,
    )


def test_the_view_drops_facts_and_gaps_from_unreachable_sources() -> None:
    jira_down = w.WORLD.at(w.NOW, NORMAL.without(Source.JIRA))
    assert jira_down.facts_about(DENIZ, PredicateName.HAS_SKILL) == ()
    assert jira_down.facts_about(TICKET, PredicateName.OWNS_WORK_ITEM) == (w.STALE_OWNER,)
    assert jira_down.gaps_about(DENIZ, PredicateName.HAS_SKILL) == (w.DENIZ_SKILLS_GAP,)
    hr_down = w.WORLD.at(w.NOW, NORMAL.without(Source.FRAPPE))
    assert hr_down.gaps_about(DENIZ, PredicateName.HAS_SKILL) == ()
    assert hr_down.facts_of(PredicateName.MEMBER_OF_TEAM) == ()


def test_facts_of_lists_a_predicate_across_subjects_in_base_order() -> None:
    view = w.WORLD.at(w.NOW, NORMAL)
    assert [fact.value for fact in view.facts_of(PredicateName.ATTENDS_EVENT)] == [
        ALICE,
        employee_ref(w.CAN),
        employee_ref(w.BOB),
    ]
    assert view.facts_about(ALICE, PredicateName.MEMBER_OF_TEAM)[0].value == team_ref(team_id(1))
    assert view.facts_about(ALICE, PredicateName.REQUIRES) == ()


def test_the_run_condition_is_a_set_of_reachable_sources() -> None:
    assert NORMAL.reaches(Source)
    assert not NORMAL.without(Source.CALENDAR).reaches({Source.CALENDAR})
    assert NORMAL.without(Source.CALENDAR).reaches({Source.FRAPPE, Source.JIRA})
    assert NORMAL.without(Source.JIRA, Source.CORPUS) == RunCondition(
        frozenset({Source.FRAPPE, Source.CALENDAR})
    )


def test_a_clause_fact_names_the_corpus_record_it_was_read_from() -> None:
    fact = w.requires(clause_id(11), w.ONE_KAFKA)
    assert fact.source is Source.CORPUS
    assert fact.key == (clause_ref(clause_id(11)), PredicateName.REQUIRES)
