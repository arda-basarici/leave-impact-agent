"""What the standing requirements of a run scope to: the histories between "one span placed"
and "two spans placed on two artifacts", a document of one section and of two, and the join
leaving the withheld statements out."""

from datetime import date
from itertools import permutations

import pytest

from leaveimpact.core import ConstraintKey, PredicateName, WorkItem, WorkItemStatus
from leaveimpact.core.entities import Document, DocumentSection
from leaveimpact.core.enums import DocumentKind
from leaveimpact.core.ids import ClauseId, clause_id, document_id, skill_id, work_item_id
from leaveimpact.core.refs import EntityRef, clause_ref, document_ref, work_item_ref
from leaveimpact.core.scoping import scope_requirements
from leaveimpact.core.stated import PlacementState, StatedFact
from leaveimpact.core.stated_view import Excluded, Exclusion, view_with_stated
from leaveimpact.core.values import Requirement, SkillCriterion
from tests.unit import stated_fixture as f

TWO_WITH_KAFKA = Requirement(2, (SkillCriterion(skill_id("kafka")),))

OTHER_TITLE = "Payments: retire the endpoint"
OTHER = WorkItem(
    work_item_id(44), OTHER_TITLE, f.ALICE.id, WorkItemStatus.TO_DO, f.PAYMENTS.id,
    date(2026, 1, 5), None, None, (),
)  # fmt: skip
OTHER_REF = work_item_ref(OTHER.id)


def procedure(number: int, text: str, *more: str) -> Document:
    """A procedure whose first section is clause ``number`` with ``text``."""
    sections = tuple(
        DocumentSection(clause_id(number + offset), body)
        for offset, body in enumerate((text, *more))
    )
    return Document(
        document_id(number), f"Procedure {number}", DocumentKind.PROCEDURE, date(2026, 1, 1),
        sections,
    )  # fmt: skip


def requires(clause: EntityRef, quote: str, span: str) -> StatedFact:
    return StatedFact(PredicateName.REQUIRES, clause, TWO_WITH_KAFKA, clause, quote, span)


ONE_TICKET = f"The {f.TITLE} release needs two people with Kafka experience."
TWO_TICKETS = (
    f"The {f.TITLE} release and the {OTHER_TITLE} release each need two people with Kafka "
    "experience."
)
CLAUSE = clause_ref(clause_id(20))


def test_one_placed_span_gives_the_clause_one_constraint() -> None:
    reads = f.reads_of(documents=(procedure(20, ONE_TICKET),))
    scoped = scope_requirements(reads, (requires(CLAUSE, ONE_TICKET, f.TITLE),))
    assert scoped.constraints == (ConstraintKey(ClauseId(CLAUSE.id), f.TICKET_REF),)
    assert [entry.placement.state for entry in scoped.placements] == [PlacementState.PLACED]
    assert scoped.withheld == ()


def test_no_placed_span_gives_no_constraint_and_withholds_nothing() -> None:
    # The ticket the clause names was never read.
    reads = f.reads_of(work_items=(), documents=(procedure(20, ONE_TICKET),))
    scoped = scope_requirements(reads, (requires(CLAUSE, ONE_TICKET, f.TITLE),))
    assert scoped.constraints == ()
    assert [entry.placement.state for entry in scoped.placements] == [PlacementState.UNPLACED]
    assert scoped.withheld == ()


def test_a_span_that_ran_long_beside_a_placed_one_does_not_cost_the_constraint() -> None:
    reads = f.reads_of(documents=(procedure(20, ONE_TICKET),))
    long = requires(CLAUSE, ONE_TICKET, f"{f.TITLE} release")
    right = requires(CLAUSE, ONE_TICKET, f.TITLE)
    for order in permutations((long, right)):
        scoped = scope_requirements(reads, order)
        assert scoped.constraints == (ConstraintKey(ClauseId(CLAUSE.id), f.TICKET_REF),)
        assert scoped.withheld == ()
        assert {entry.fact: entry.placement.state for entry in scoped.placements} == {
            long: PlacementState.UNPLACED,
            right: PlacementState.PLACED,
        }


def test_two_spans_placed_on_two_artifacts_use_neither_whatever_the_order() -> None:
    reads = f.reads_of(work_items=(f.TICKET, OTHER), documents=(procedure(20, TWO_TICKETS),))
    first = requires(CLAUSE, TWO_TICKETS, f.TITLE)
    second = requires(CLAUSE, TWO_TICKETS, OTHER_TITLE)
    long = requires(CLAUSE, TWO_TICKETS, f"{f.TITLE} release")
    for order in permutations((first, second, long)):
        scoped = scope_requirements(reads, order)
        assert scoped.constraints == ()
        # Every statement of the clause's requirement is withheld, the unplaced one too,
        # and both bindings stay on record as placed.
        assert scoped.withheld == tuple(
            Excluded(stated, Exclusion.CONFLICTING_SCOPES) for stated in order
        )
        assert {entry.fact: entry.placement.artifact for entry in scoped.placements} == {
            first: f.TICKET_REF,
            second: OTHER_REF,
            long: None,
        }


def test_a_conflict_in_one_clause_leaves_another_clauses_constraint_alone() -> None:
    reads = f.reads_of(
        work_items=(f.TICKET, OTHER),
        documents=(procedure(20, TWO_TICKETS), procedure(30, ONE_TICKET)),
    )
    sound = requires(clause_ref(clause_id(30)), ONE_TICKET, f.TITLE)
    scoped = scope_requirements(
        reads,
        (
            requires(CLAUSE, TWO_TICKETS, f.TITLE),
            sound,
            requires(CLAUSE, TWO_TICKETS, OTHER_TITLE),
        ),
    )
    assert scoped.constraints == (ConstraintKey(clause_id(30), f.TICKET_REF),)
    assert [excluded.fact.subject for excluded in scoped.withheld] == [CLAUSE, CLAUSE]


def test_a_span_naming_a_document_of_one_section_scopes_to_that_section() -> None:
    text = f"Covering the {f.RUNBOOK.title} needs two people with Kafka experience."
    reads = f.reads_of(documents=(f.RUNBOOK, procedure(20, text)))
    scoped = scope_requirements(reads, (requires(CLAUSE, text, f.RUNBOOK.title),))
    assert scoped.placements[0].placement.artifact == document_ref(f.RUNBOOK.id)
    assert scoped.constraints == (ConstraintKey(ClauseId(CLAUSE.id), f.CLAUSE_REF),)


@pytest.mark.parametrize("extra", [(), ("a second section", "a third")])
def test_a_span_naming_a_document_without_exactly_one_section_is_withheld(
    extra: tuple[str, ...],
) -> None:
    # Two sections more than one, or none at all: nothing says which the clause governs.
    named = procedure(40, "the first section", *extra)
    if not extra:
        named = Document(named.id, named.title, named.kind, named.effective_from, ())
    text = f"Covering the {named.title} needs two people with Kafka experience."
    reads = f.reads_of(documents=(named, procedure(20, text)))
    stated = requires(CLAUSE, text, named.title)
    scoped = scope_requirements(reads, (stated,))
    assert scoped.constraints == ()
    assert scoped.withheld == (Excluded(stated, Exclusion.SCOPE_WITHOUT_ONE_SECTION),)
    # The span did bind: the placement says so, and the exclusion says why it is unused.
    assert scoped.placements[0].placement.artifact == document_ref(named.id)


def test_the_join_leaves_a_withheld_requirement_out_of_the_view() -> None:
    reads = f.reads_of(work_items=(f.TICKET, OTHER), documents=(procedure(20, TWO_TICKETS),))
    first = requires(CLAUSE, TWO_TICKETS, f.TITLE)
    second = requires(CLAUSE, TWO_TICKETS, OTHER_TITLE)
    joined = view_with_stated(reads, (first, second))
    assert joined.view.facts_about(CLAUSE, PredicateName.REQUIRES)
    scoped = scope_requirements(reads, joined.included)
    reasons = {excluded.fact: excluded.reason for excluded in scoped.withheld}
    final = view_with_stated(reads, (first, second), reasons)
    assert final.included == ()
    assert final.excluded == scoped.withheld
    assert final.view.facts_about(CLAUSE, PredicateName.REQUIRES) == ()


def test_the_same_span_stated_twice_is_one_placement() -> None:
    reads = f.reads_of(documents=(procedure(20, ONE_TICKET),))
    once = requires(CLAUSE, ONE_TICKET, f.TITLE)
    again = requires(CLAUSE, ONE_TICKET[4:], f.TITLE)
    joined = view_with_stated(reads, (once, again))
    scoped = scope_requirements(reads, joined.included)
    assert len(scoped.placements) == 1
    assert scoped.constraints == (ConstraintKey(ClauseId(CLAUSE.id), f.TICKET_REF),)


def test_a_reason_the_join_found_is_not_replaced_by_a_scope_reason() -> None:
    # Two readings of the clause's requirement that differ in the count: the join's own.
    reads = f.reads_of(documents=(procedure(20, ONE_TICKET),))
    two = requires(CLAUSE, ONE_TICKET, f.TITLE)
    three = StatedFact(
        PredicateName.REQUIRES, CLAUSE, Requirement(3, ()), CLAUSE, ONE_TICKET, f.TITLE
    )
    final = view_with_stated(reads, (two, three), {two: Exclusion.CONFLICTING_SCOPES})
    assert {excluded.reason for excluded in final.excluded} == {Exclusion.CONFLICTING_READINGS}


def test_only_a_scope_reason_can_be_given_and_only_for_a_requirement() -> None:
    reads = f.reads_of(documents=(procedure(20, ONE_TICKET),))
    stated = requires(CLAUSE, ONE_TICKET, f.TITLE)
    with pytest.raises(ValueError, match="the join's to find"):
        view_with_stated(reads, (stated,), {stated: Exclusion.CONFLICTING_CARRIERS})
    owner = StatedFact(
        PredicateName.OWNS_WORK_ITEM, f.TICKET_REF, f.DENIZ_REF, f.CLAUSE_REF, "Deniz Kaya owns"
    )
    with pytest.raises(ValueError, match="only a requirement has a scope"):
        Excluded(owner, Exclusion.CONFLICTING_SCOPES)


def test_scoping_refuses_what_no_join_gives_it() -> None:
    reads = f.reads_of(documents=())
    with pytest.raises(ValueError, match="was not returned"):
        scope_requirements(reads, (requires(CLAUSE, ONE_TICKET, f.TITLE),))
    owner = StatedFact(
        PredicateName.OWNS_WORK_ITEM, f.TICKET_REF, f.DENIZ_REF, f.CLAUSE_REF, "Deniz Kaya owns"
    )
    with pytest.raises(ValueError, match="only a requirement is scoped"):
        scope_requirements(f.reads_of(), (owner,))
