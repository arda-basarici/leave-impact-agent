"""A stated fact holds at construction everything that needs no read, refuses the rest with the
reason it is counted under, and its three statuses cannot be mistaken for one another."""

import pytest

from leaveimpact.core import (
    PredicateName,
    Requirement,
    SkillCriterion,
    Source,
    component_ref,
    document_ref,
)
from leaveimpact.core.anchors import ANCHOR_ROWS
from leaveimpact.core.ids import document_id, skill_id
from leaveimpact.core.stated import (
    CONSTRUCTION_REFUSALS,
    STATED_PREDICATES,
    Admitted,
    FactRefusal,
    PlacementState,
    Refused,
    RefusedInput,
    SpanPlacement,
    StatedFact,
    Unstatable,
)
from tests.unit import stated_fixture as f

ONE_KAFKA = Requirement(1, (SkillCriterion(skill_id("kafka")),))


def skill(**changes: object) -> StatedFact:
    fields: dict[str, object] = {
        "predicate": PredicateName.HAS_SKILL,
        "subject": f.DENIZ_REF,
        "value": "kafka",
        "carrier": f.COMMENT_REF,
        "quote": "I ran the Kafka migration",
    }
    return StatedFact(**(fields | changes))  # type: ignore[arg-type]


def requirement(**changes: object) -> StatedFact:
    fields: dict[str, object] = {
        "predicate": PredicateName.REQUIRES,
        "subject": f.CLAUSE_REF,
        "value": ONE_KAFKA,
        "carrier": f.CLAUSE_REF,
        "quote": f"The {f.TITLE} release needs two people",
        "target_span": f.TITLE,
    }
    return StatedFact(**(fields | changes))  # type: ignore[arg-type]


def refusal(build: object, **changes: object) -> Unstatable:
    with pytest.raises(Unstatable) as raised:
        build(**changes)  # type: ignore[operator]
    return raised.value


def test_the_stated_vocabulary_is_the_five_predicates_prose_can_carry() -> None:
    assert frozenset(STATED_PREDICATES) == frozenset(ANCHOR_ROWS)
    assert len(STATED_PREDICATES) == 5


def test_a_predicate_a_structured_record_owns_is_never_stated() -> None:
    problem = refusal(skill, predicate=PredicateName.MEMBER_OF_TEAM)
    assert problem.reason is FactRefusal.UNDECODABLE
    assert "member_of_team is not a predicate a model states" in str(problem)


def test_the_subject_and_the_value_are_the_registry_rows() -> None:
    assert refusal(skill, subject=f.TICKET_REF).reason is FactRefusal.UNDECODABLE
    problem = refusal(skill, value="Kafka")
    assert problem.reason is FactRefusal.UNDECODABLE
    assert "has_skill: expected a skill, got 'Kafka'" in str(problem)


def test_a_carrier_is_a_comment_or_a_section() -> None:
    problem = refusal(skill, carrier=f.TICKET_REF)
    assert problem.reason is FactRefusal.MALFORMED_CARRIER
    assert refusal(skill, carrier=document_ref(document_id(3))).reason is (
        FactRefusal.MALFORMED_CARRIER
    )


def test_a_carrier_outside_the_predicates_evidence_domain_carries_nothing() -> None:
    # Component membership is the tracker's alone: a section cannot state it.
    payments = component_ref(f.PAYMENTS.id)
    problem = refusal(
        skill, predicate=PredicateName.MEMBER_OF_COMPONENT, value=payments, carrier=f.CLAUSE_REF
    )
    assert problem.reason is FactRefusal.UNDECODABLE
    assert "a clause cannot carry member_of_component: corpus is outside" in str(problem)
    # Ownership may be asserted by a runbook, so a section carries it and a comment does too.
    for carrier in (f.CLAUSE_REF, f.COMMENT_REF):
        StatedFact(
            PredicateName.OWNS_WORK_ITEM, f.TICKET_REF, f.DENIZ_REF, carrier, "Deniz Kaya owns it"
        )


def test_a_fact_about_a_clause_is_carried_by_that_clause() -> None:
    other = f.COMMENT_REF
    assert refusal(requirement, carrier=other).reason is FactRefusal.UNDECODABLE


def test_a_requirement_names_its_target_inside_its_quote_and_nothing_else_has_a_span() -> None:
    assert refusal(requirement, target_span=None).reason is FactRefusal.SPAN_NOT_IN_QUOTE
    assert refusal(requirement, target_span="").reason is FactRefusal.SPAN_NOT_IN_QUOTE
    assert refusal(requirement, target_span=f.REGIONAL_TITLE).reason is (
        FactRefusal.SPAN_NOT_IN_QUOTE
    )
    assert refusal(skill, target_span="Kafka").reason is FactRefusal.UNDECODABLE
    assert refusal(skill, quote="").reason is FactRefusal.UNDECODABLE


def test_a_stated_fact_reads_its_source_from_its_carrier_and_dates_to_the_runs_day() -> None:
    assert skill().source is Source.JIRA
    assert requirement().source is Source.CORPUS
    fact = skill().as_fact(f.TODAY)
    assert (fact.subject, fact.predicate, fact.value) == skill().statement
    assert (fact.evidence.target, fact.evidence.field, fact.observable_from) == (
        f.COMMENT_REF,
        None,
        f.TODAY,
    )


def test_a_refused_input_holds_a_construction_reason_and_a_refused_fact_never_does() -> None:
    RefusedInput('{"predicate":"owns"}', FactRefusal.UNDECODABLE, "owns is no predicate")
    with pytest.raises(ValueError, match="refuses a stated fact at admission, never an input"):
        RefusedInput("{}", FactRefusal.MISSING_ANCHOR, "")
    Refused(skill(), FactRefusal.QUOTE_NOT_IN_CARRIER, "")
    for reason in CONSTRUCTION_REFUSALS:
        with pytest.raises(ValueError, match="no stated fact can exist under"):
            Refused(skill(), reason, "")
    assert Admitted(skill()).fact == skill()


def test_a_placement_names_one_artifact_none_or_the_ones_it_lay_among() -> None:
    SpanPlacement(PlacementState.PLACED, artifact=f.TICKET_REF)
    SpanPlacement(PlacementState.UNPLACED)
    SpanPlacement(PlacementState.AMBIGUOUS, among=(f.TICKET_REF, f.REGIONAL_REF))
    with pytest.raises(ValueError, match="a placed span names its one artifact"):
        SpanPlacement(PlacementState.PLACED)
    with pytest.raises(ValueError, match="an unplaced span names no artifact"):
        SpanPlacement(PlacementState.UNPLACED, artifact=f.TICKET_REF)
    with pytest.raises(ValueError, match="binds nothing and names the artifacts"):
        SpanPlacement(PlacementState.AMBIGUOUS)
    with pytest.raises(ValueError, match="names each artifact once"):
        SpanPlacement(PlacementState.AMBIGUOUS, among=(f.TICKET_REF, f.TICKET_REF))


def test_a_value_of_the_wrong_python_type_is_refused_under_a_reason_too() -> None:
    # A parser builds the type from a model's entry: nothing it passes may escape as an
    # AttributeError or a TypeError.
    for changes in (
        {"predicate": "has_skill"},
        {"subject": "emp_023"},
        {"carrier": None},
        {"quote": 5},
        {"quote": None},
    ):
        assert refusal(skill, **changes).reason is FactRefusal.UNDECODABLE
    assert refusal(requirement, target_span=7).reason is FactRefusal.UNDECODABLE
    assert refusal(requirement, quote=7).reason is FactRefusal.UNDECODABLE


def test_a_span_binds_only_what_prose_names_by_title() -> None:
    with pytest.raises(
        ValueError, match="binds a ticket, a meeting or a document, got an employee"
    ):
        SpanPlacement(PlacementState.PLACED, artifact=f.DENIZ_REF)
    with pytest.raises(ValueError, match="got a clause"):
        SpanPlacement(PlacementState.AMBIGUOUS, among=(f.TICKET_REF, f.CLAUSE_REF))
