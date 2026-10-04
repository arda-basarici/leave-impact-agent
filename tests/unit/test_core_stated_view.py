"""The view from reads plus stated facts is total: agreeing statements join it, the readings
that cannot stand together are left out with a reason, and no misreading raises."""

from dataclasses import replace
from itertools import combinations

import pytest

from leaveimpact.core import (
    EvidenceRef,
    FactBase,
    Gap,
    PredicateName,
    Requirement,
    SkillCriterion,
    Source,
    conflicts_in,
)
from leaveimpact.core.binding import bind_span, titled_artifacts
from leaveimpact.core.entities import Document, DocumentSection
from leaveimpact.core.enums import DocumentKind
from leaveimpact.core.ids import clause_id, document_id, skill_id
from leaveimpact.core.read_projection import project_reads
from leaveimpact.core.refs import clause_ref
from leaveimpact.core.stated import PlacementState, StatedFact
from leaveimpact.core.stated_view import Excluded, Exclusion, view_with_stated
from tests.unit import stated_fixture as f
from tests.unit.reads_fixture import Recorder, Systems

SECOND = Document(
    document_id(4),
    "Payments handover",
    DocumentKind.RUNBOOK,
    f.RUNBOOK.effective_from,
    (DocumentSection(clause_id(12), f"Alice Demir owns {f.TITLE}."),),
)
SECOND_CLAUSE = clause_ref(clause_id(12))
ONE_KAFKA = Requirement(1, (SkillCriterion(skill_id("kafka")),))
TWO_KAFKA = Requirement(2, (SkillCriterion(skill_id("kafka")),))


def owner(who: object, carrier: object, quote: str = "owns") -> StatedFact:
    return StatedFact(PredicateName.OWNS_WORK_ITEM, f.TICKET_REF, who, carrier, quote)  # type: ignore[arg-type]


def requires(value: Requirement) -> StatedFact:
    return StatedFact(
        PredicateName.REQUIRES, f.CLAUSE_REF, value, f.CLAUSE_REF, f.CLAUSE_TEXT, f.TITLE
    )


SKILL = StatedFact(PredicateName.HAS_SKILL, f.DENIZ_REF, "kafka", f.COMMENT_REF, f.REMARK)


def test_with_no_statement_the_view_is_the_projections_own() -> None:
    reads = f.reads_of()
    joined = view_with_stated(reads, ())
    assert joined.view == reads.view()
    assert (joined.included, joined.excluded) == ((), ())


def test_an_admitted_statement_is_a_fact_of_the_view_read_from_its_carrier() -> None:
    reads = f.reads_of()
    joined = view_with_stated(reads, (SKILL, requires(TWO_KAFKA)))
    assert joined.included == (SKILL, requires(TWO_KAFKA))
    (skill,) = joined.view.facts_about(f.DENIZ_REF, PredicateName.HAS_SKILL)
    assert (skill.source, skill.evidence.target, skill.observable_from) == (
        Source.JIRA,
        f.COMMENT_REF,
        f.TODAY,
    )
    (stated,) = joined.view.facts_about(f.CLAUSE_REF, PredicateName.REQUIRES)
    assert stated.value == TWO_KAFKA
    assert joined.view.coverage == reads.coverage


def test_the_bare_fact_base_refuses_what_the_join_settles() -> None:
    # The premise of the rule: a comment read as naming another owner is the tracker holding
    # two values, which the base refuses outright.
    reads = f.reads_of()
    misread = owner(f.DENIZ_REF, f.COMMENT_REF).as_fact(f.TODAY)
    with pytest.raises(ValueError, match="jira holds two values for owns_work_item"):
        FactBase((*reads.facts, misread), reads.gaps)


def test_a_statement_against_a_structured_field_of_its_source_is_left_out() -> None:
    reads = f.reads_of()
    misread = owner(f.DENIZ_REF, f.COMMENT_REF)
    joined = view_with_stated(reads, (misread, SKILL))
    assert joined.excluded == (Excluded(misread, Exclusion.CONTRADICTS_STRUCTURED),)
    assert joined.included == (SKILL,)
    (field,) = joined.view.facts_about(f.TICKET_REF, PredicateName.OWNS_WORK_ITEM)
    assert field.value == f.ALICE_REF


def test_a_statement_that_agrees_with_the_field_stays_as_corroboration() -> None:
    agreeing = owner(f.ALICE_REF, f.COMMENT_REF)
    joined = view_with_stated(f.reads_of(), (agreeing,))
    assert joined.included == (agreeing,)
    assert len(joined.view.facts_about(f.TICKET_REF, PredicateName.OWNS_WORK_ITEM)) == 2


def test_two_readings_of_one_carrier_are_both_left_out() -> None:
    one, two = requires(ONE_KAFKA), requires(TWO_KAFKA)
    joined = view_with_stated(f.reads_of(), (one, two))
    assert joined.excluded == (
        Excluded(one, Exclusion.CONFLICTING_READINGS),
        Excluded(two, Exclusion.CONFLICTING_READINGS),
    )
    assert joined.view.facts_about(f.CLAUSE_REF, PredicateName.REQUIRES) == ()


def test_two_sections_naming_two_owners_are_both_left_out_and_the_tracker_stands() -> None:
    reads = f.reads_of(documents=(f.RUNBOOK, SECOND))
    stale = owner(f.DENIZ_REF, f.CLAUSE_REF)
    other = owner(f.ALICE_REF, SECOND_CLAUSE)
    joined = view_with_stated(reads, (stale, other))
    assert joined.excluded == (
        Excluded(stale, Exclusion.CONFLICTING_CARRIERS),
        Excluded(other, Exclusion.CONFLICTING_CARRIERS),
    )
    assert conflicts_in(joined.view) == ()


def test_two_sections_that_agree_both_stay_and_conflict_with_the_tracker_as_one_source() -> None:
    reads = f.reads_of(documents=(f.RUNBOOK, SECOND))
    first, second = owner(f.DENIZ_REF, f.CLAUSE_REF), owner(f.DENIZ_REF, SECOND_CLAUSE)
    joined = view_with_stated(reads, (first, second))
    assert joined.included == (first, second)
    # Between sources nothing is settled here: the authority table resolves it.
    (conflict,) = conflicts_in(joined.view)
    assert conflict.resolution.value == f.ALICE_REF
    assert len(conflict.facts) == 3


def test_a_carrier_read_two_ways_does_not_take_another_carriers_reading_with_it() -> None:
    reads = f.reads_of(documents=(f.RUNBOOK, SECOND))
    torn = (owner(f.DENIZ_REF, f.CLAUSE_REF), owner(f.ALICE_REF, f.CLAUSE_REF))
    clean = owner(f.DENIZ_REF, SECOND_CLAUSE)
    joined = view_with_stated(reads, (*torn, clean))
    assert joined.included == (clean,)
    assert {excluded.reason for excluded in joined.excluded} == {Exclusion.CONFLICTING_READINGS}


def test_a_set_valued_predicate_has_nothing_to_settle() -> None:
    go = StatedFact(PredicateName.HAS_SKILL, f.DENIZ_REF, "go", f.COMMENT_REF, f.REMARK)
    joined = view_with_stated(f.reads_of(), (SKILL, go))
    assert joined.included == (SKILL, go)


def test_a_statement_admitted_twice_from_one_carrier_is_one_fact() -> None:
    again = StatedFact(PredicateName.HAS_SKILL, f.DENIZ_REF, "kafka", f.COMMENT_REF, "Kafka")
    joined = view_with_stated(f.reads_of(), (SKILL, again))
    assert joined.included == (SKILL,)
    assert len(joined.view.facts_about(f.DENIZ_REF, PredicateName.HAS_SKILL)) == 1


def test_a_statement_where_the_record_holds_the_field_empty_is_left_out() -> None:
    # No structured record of a prose source derives a gap today; the base would refuse the
    # pair all the same, so the join is held to it.
    reads = f.reads_of(work_items=())
    gap = Gap(
        f.TICKET_REF,
        PredicateName.OWNS_WORK_ITEM,
        EvidenceRef(Source.JIRA, f.TICKET_REF, "owner_id"),
        f.TODAY,
    )
    stated = owner(f.DENIZ_REF, f.COMMENT_REF)
    joined = view_with_stated(replace(reads, derived=(*reads.derived, gap)), (stated,))
    assert joined.excluded == (Excluded(stated, Exclusion.CONTRADICTS_STRUCTURED),)


def test_no_set_of_statements_makes_the_join_raise() -> None:
    reads = f.reads_of(documents=(f.RUNBOOK, SECOND))
    pool = (
        owner(f.ALICE_REF, f.COMMENT_REF),
        owner(f.DENIZ_REF, f.COMMENT_REF),
        owner(f.ALICE_REF, f.CLAUSE_REF),
        owner(f.DENIZ_REF, f.CLAUSE_REF),
        owner(f.ALICE_REF, SECOND_CLAUSE),
        owner(f.DENIZ_REF, SECOND_CLAUSE),
        requires(ONE_KAFKA),
        requires(TWO_KAFKA),
        SKILL,
    )
    for size in range(len(pool) + 1):
        for chosen in combinations(pool, size):
            joined = view_with_stated(reads, chosen)
            left_out = tuple(excluded.fact for excluded in joined.excluded)
            assert set(joined.included) | set(left_out) == set(chosen)
            assert not set(joined.included) & set(left_out)


def test_a_statement_from_a_carrier_the_reads_withdrew_is_left_out() -> None:
    # The ticket came back with two owners in two reads, so the projection derives nothing
    # from it. A statement from its own comment must not stand in for the owner field and
    # then outrank the runbook as the tracker's value.
    systems = Systems()
    for employee in (f.ALICE, f.DENIZ):
        systems.people.add_employee(employee)
    systems.work.add_component(f.PAYMENTS)
    systems.work.add_work_item(f.TICKET)
    systems.documents.add_document(f.RUNBOOK)
    run = Recorder(systems)
    run.read("work_items")
    systems.work.tickets[f.TICKET.id] = replace(f.TICKET, owner_id=f.DENIZ.id)
    run.read("work_item", {"id": f.TICKET.id})
    run.read("document", {"id": f.RUNBOOK.id})
    reads = project_reads(tuple(run.operations), f.TODAY)
    assert f.COMMENT_REF in reads.coverage.unobserved

    from_the_comment = owner(f.DENIZ_REF, f.COMMENT_REF)
    from_the_runbook = owner(f.ALICE_REF, f.CLAUSE_REF)
    joined = view_with_stated(reads, (from_the_comment, SKILL, from_the_runbook))
    assert joined.excluded == (
        Excluded(from_the_comment, Exclusion.CARRIER_WITHDRAWN),
        Excluded(SKILL, Exclusion.CARRIER_WITHDRAWN),
    )
    assert joined.included == (from_the_runbook,)
    assert conflicts_in(joined.view) == ()


def test_an_exclusion_holds_a_reason_its_fact_can_have() -> None:
    with pytest.raises(ValueError, match="an exclusion's reason is a member of Exclusion"):
        Excluded(SKILL, "conflicting_readings")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="has_skill holds a set"):
        Excluded(SKILL, Exclusion.CONFLICTING_CARRIERS)
    Excluded(SKILL, Exclusion.CARRIER_WITHDRAWN)


def test_a_requirement_stated_with_two_spans_keeps_both_whatever_the_order() -> None:
    # The span is the binding's one input. Dropped at the join, the requirement's scope would
    # follow the order the model emitted in.
    text = f"The {f.TITLE} release and {f.REGIONAL_TITLE} need two people with Kafka experience."
    plain = StatedFact(PredicateName.REQUIRES, f.CLAUSE_REF, TWO_KAFKA, f.CLAUSE_REF, text, f.TITLE)
    regional = StatedFact(
        PredicateName.REQUIRES, f.CLAUSE_REF, TWO_KAFKA, f.CLAUSE_REF, text, f.REGIONAL_TITLE
    )
    for order in ((plain, regional), (regional, plain)):
        joined = view_with_stated(f.reads_of(), order)
        assert joined.included == order
        assert joined.excluded == ()
        assert len(joined.view.facts_about(f.CLAUSE_REF, PredicateName.REQUIRES)) == 1


def test_a_span_that_ran_long_does_not_hide_the_right_one_stated_after_it() -> None:
    quote = f"The {f.TITLE} release needs two people"
    overrun = StatedFact(
        PredicateName.REQUIRES, f.CLAUSE_REF, TWO_KAFKA, f.CLAUSE_REF, quote, f"{f.TITLE} release"
    )
    right = StatedFact(
        PredicateName.REQUIRES, f.CLAUSE_REF, TWO_KAFKA, f.CLAUSE_REF, quote, f.TITLE
    )
    joined = view_with_stated(f.reads_of(), (overrun, right))
    assert joined.included == (overrun, right)
    titled = titled_artifacts(f.reads_of())
    spans = [stated.target_span for stated in joined.included]
    assert spans == [f"{f.TITLE} release", f.TITLE]
    assert [bind_span(span, f.CLAUSE_TEXT, titled).state for span in spans if span] == [
        PlacementState.UNPLACED,
        PlacementState.PLACED,
    ]


def test_the_same_span_stated_twice_in_other_words_is_still_one_statement() -> None:
    first = requires(TWO_KAFKA)
    again = StatedFact(
        PredicateName.REQUIRES, f.CLAUSE_REF, TWO_KAFKA, f.CLAUSE_REF, f"The {f.TITLE}", f.TITLE
    )
    assert view_with_stated(f.reads_of(), (first, again)).included == (first,)
