"""Coverage: the placement table names one home per predicate and source of the registry and
agrees with where every fact of the shared fixture was read; a question becomes the slices
that close its negative, the record's first and the corpus's prose alone waivable; a view
cut from a base by a run condition covers a slice exactly when its source is reachable."""

from dataclasses import replace
from datetime import date

import pytest

from leaveimpact.core import (
    PLACEMENTS,
    REGISTRY,
    DateSpan,
    EntityKind,
    Fact,
    Gap,
    KindSlice,
    Needed,
    PredicateName,
    RecordSlice,
    RunCondition,
    Slice,
    SliceStatus,
    Source,
    SourceCoverage,
    WindowSlice,
    closing_slices,
    closing_slices_of_any,
    component_ref,
    employee_ref,
    event_ref,
    leave_ref,
    predicate,
    work_item_ref,
)
from leaveimpact.core.ids import clause_id
from leaveimpact.core.predicates import ROWS
from leaveimpact.core.refs import clause_ref
from tests.unit import world_fixture as w

ALICE = employee_ref(w.ALICE)
NORMAL = RunCondition.all_reachable()

# The kind of record each prose placement is read from, and the kind its slice enumerates.
HOLDER_OF = {EntityKind.COMMENT: EntityKind.WORK_ITEM, EntityKind.CLAUSE: EntityKind.DOCUMENT}


def test_the_placement_table_has_one_entry_per_predicate_and_source_of_its_domain() -> None:
    declared = {(row.name, source) for row in ROWS for source in row.evidence_domain}
    assert set(PLACEMENTS) == declared


def _holds(where: Slice, item: Fact | Gap) -> bool:
    """Whether the record ``item`` was read from lies inside ``where``."""
    target = item.evidence.target
    match where:
        case RecordSlice(record):
            return record == target
        case KindSlice(kind):
            return kind in (target.kind, HOLDER_OF.get(target.kind))
        case WindowSlice():
            return False


@pytest.mark.parametrize("item", [*w.WORLD.facts, *w.WORLD.gaps], ids=lambda item: item.predicate)
def test_every_fact_and_gap_of_the_fixture_was_read_from_inside_its_closing_slice(
    item: Fact | Gap,
) -> None:
    # The fixture's facts are derivation's own output for its records (the derivation
    # tests hold the two equal), so this ties the table to derivation as well as to the
    # prose a world plants: a slice that did not hold a fact's provenance could be
    # covered while the fact went unseen.
    value = item.value if isinstance(item, Fact) else None
    needed = closing_slices(predicate(item.predicate), item.subject, value)
    at_the_source = [each.where for each in needed if each.where.source is item.source]
    assert len(at_the_source) == 1
    assert _holds(at_the_source[0], item)


def test_a_question_about_one_subject_names_the_records_slice_first() -> None:
    skill = closing_slices(predicate(PredicateName.HAS_SKILL), ALICE, w.KAFKA)
    assert skill == (
        Needed(RecordSlice(ALICE), waivable=False),
        Needed(KindSlice(EntityKind.DOCUMENT), waivable=True),
        Needed(KindSlice(EntityKind.WORK_ITEM), waivable=False),
    )
    assert [each.where.source for each in skill] == [Source.FRAPPE, Source.CORPUS, Source.JIRA]
    owner = closing_slices(predicate(PredicateName.OWNS_WORK_ITEM), work_item_ref(w.TICKET))
    assert owner == (
        Needed(RecordSlice(work_item_ref(w.TICKET)), waivable=False),
        Needed(KindSlice(EntityKind.DOCUMENT), waivable=True),
    )


def test_membership_lives_on_the_component_and_never_on_the_employee() -> None:
    membership = predicate(PredicateName.MEMBER_OF_COMPONENT)
    payments = component_ref(w.PAYMENTS)
    assert closing_slices(membership, ALICE, payments) == (Needed(RecordSlice(payments), False),)
    # Asked of any component at all, only every component answers.
    assert closing_slices(membership, ALICE) == (Needed(KindSlice(EntityKind.COMPONENT), False),)


def test_an_absence_lives_on_leave_records_which_only_a_window_narrows() -> None:
    on_leave = predicate(PredicateName.ON_LEAVE)
    assert closing_slices(on_leave, ALICE) == (Needed(KindSlice(EntityKind.LEAVE), False),)
    assert closing_slices_of_any(on_leave, w.LEAVE_SPAN) == (
        Needed(WindowSlice(EntityKind.LEAVE, w.LEAVE_SPAN), False),
    )
    assert closing_slices_of_any(on_leave, None) == (Needed(KindSlice(EntityKind.LEAVE), False),)


def test_a_subject_free_question_is_over_the_records_that_hold_the_fact() -> None:
    attends = predicate(PredicateName.ATTENDS_EVENT)
    assert closing_slices(attends, event_ref(w.RELEASE)) == (
        Needed(RecordSlice(event_ref(w.RELEASE)), False),
    )
    assert closing_slices_of_any(attends, w.RELEASE_SPAN) == (
        Needed(WindowSlice(EntityKind.EVENT, w.RELEASE_SPAN), False),
    )
    assert closing_slices_of_any(predicate(PredicateName.OWNS_WORK_ITEM), None) == (
        Needed(KindSlice(EntityKind.WORK_ITEM), False),
        Needed(KindSlice(EntityKind.DOCUMENT), True),
    )


def test_a_window_is_refused_where_no_read_narrows_by_one() -> None:
    with pytest.raises(ValueError, match="no read narrows a work_item by a window"):
        closing_slices_of_any(predicate(PredicateName.DUE_ON), w.LEAVE_SPAN)
    with pytest.raises(ValueError, match="a window over a leave is a DateSpan, got an InstantSpan"):
        WindowSlice(EntityKind.LEAVE, w.RELEASE_SPAN)


def test_only_prose_in_the_corpus_is_waivable() -> None:
    waivable = {
        (row.name, each.where)
        for row in ROWS
        for each in closing_slices_of_any(row, None)
        if each.waivable
    }
    assert waivable == {
        (PredicateName.HAS_SKILL, KindSlice(EntityKind.DOCUMENT)),
        (PredicateName.OWNS_WORK_ITEM, KindSlice(EntityKind.DOCUMENT)),
    }
    # What a clause requires is on that clause's own record, which a read can return.
    clause = clause_ref(clause_id(11))
    assert closing_slices(predicate(PredicateName.REQUIRES), clause) == (
        Needed(RecordSlice(clause), False),
    )


def test_a_source_added_to_a_domain_without_a_placement_is_refused_by_name() -> None:
    due = REGISTRY[PredicateName.DUE_ON]
    widened = replace(due, evidence_domain=due.evidence_domain | {Source.CORPUS})
    with pytest.raises(ValueError, match="no placement says where corpus keeps due_on"):
        closing_slices(widened, work_item_ref(w.TICKET))


def test_a_slice_has_the_one_source_that_holds_its_kind() -> None:
    week = DateSpan(date(2026, 9, 15), date(2026, 9, 19))
    assert RecordSlice(leave_ref(w.LEAVE)).source is Source.FRAPPE
    assert KindSlice(EntityKind.COMPONENT).source is Source.JIRA
    assert WindowSlice(EntityKind.LEAVE, week).source is Source.FRAPPE
    assert WindowSlice(EntityKind.EVENT, w.RELEASE_SPAN).source is Source.CALENDAR


def test_a_view_cut_by_a_condition_covers_a_slice_exactly_when_its_source_is_reachable() -> None:
    slices: tuple[Slice, ...] = (
        RecordSlice(ALICE),
        KindSlice(EntityKind.WORK_ITEM),
        KindSlice(EntityKind.DOCUMENT),
        WindowSlice(EntityKind.EVENT, w.RELEASE_SPAN),
    )
    normal = w.WORLD.at(w.NOW, NORMAL)
    assert normal.coverage == SourceCoverage(frozenset(Source))
    assert {normal.coverage.status(where) for where in slices} == {SliceStatus.COVERED}
    no_tracker = w.WORLD.at(w.NOW, NORMAL.without(Source.JIRA))
    assert [no_tracker.coverage.status(where) for where in slices] == [
        SliceStatus.COVERED,
        SliceStatus.FAILED,
        SliceStatus.COVERED,
        SliceStatus.COVERED,
    ]
