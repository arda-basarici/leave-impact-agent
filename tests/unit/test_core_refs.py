"""Typed references: an id is checked against its kind's namespace, an evidence reference
against what its source holds, and the two tables are complete over their vocabularies
and agree with the id minters."""

from datetime import date

import pytest

from leaveimpact.core import (
    PREFIX_BY_KIND,
    TARGET_KINDS_BY_SOURCE,
    EntityKind,
    EntityRef,
    EvidenceRef,
    Observation,
    Source,
    clause_ref,
    comment_ref,
    component_ref,
    document_ref,
    employee_ref,
    event_ref,
    leave_ref,
    require_id,
    team_ref,
    work_item_ref,
)
from leaveimpact.core.ids import (
    clause_id,
    comment_id,
    component_id,
    document_id,
    employee_id,
    event_id,
    leave_id,
    team_id,
    work_item_id,
)

MINTED_BY_KIND = {
    EntityKind.EMPLOYEE: employee_ref(employee_id(17)),
    EntityKind.TEAM: team_ref(team_id(2)),
    EntityKind.COMPONENT: component_ref(component_id(4)),
    EntityKind.WORK_ITEM: work_item_ref(work_item_id(42)),
    EntityKind.COMMENT: comment_ref(comment_id(9)),
    EntityKind.EVENT: event_ref(event_id(1)),
    EntityKind.DOCUMENT: document_ref(document_id(3)),
    EntityKind.CLAUSE: clause_ref(clause_id(11)),
    EntityKind.LEAVE: leave_ref(leave_id(5)),
}


def test_every_kind_has_a_namespace_and_its_minter_agrees_with_it() -> None:
    assert set(PREFIX_BY_KIND) == set(EntityKind) == set(MINTED_BY_KIND)
    for kind, ref in MINTED_BY_KIND.items():
        assert ref.kind is kind
        assert require_id(kind, ref.id) == ref.id


def test_an_id_from_another_namespace_is_refused_by_kind() -> None:
    with pytest.raises(ValueError, match="an employee id has the form emp_NNN, got 'ticket_042'"):
        EntityRef(EntityKind.EMPLOYEE, "ticket_042")


@pytest.mark.parametrize("bad", ["LIA-42", "emp_42", "emp_", "Emp_017", "emp_017_1"])
def test_a_vendor_key_or_a_malformed_number_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="has the form"):
        require_id(EntityKind.EMPLOYEE, bad)


def test_every_kind_is_held_by_exactly_one_source() -> None:
    assert set(TARGET_KINDS_BY_SOURCE) == set(Source)
    holders = [kind for kinds in TARGET_KINDS_BY_SOURCE.values() for kind in kinds]
    assert sorted(holders) == sorted(EntityKind)


def test_evidence_names_a_record_its_source_holds() -> None:
    assert EvidenceRef(Source.JIRA, comment_ref(comment_id(9))).field is None
    with pytest.raises(ValueError, match="jira holds no clause record"):
        EvidenceRef(Source.JIRA, clause_ref(clause_id(11)))
    with pytest.raises(ValueError, match="calendar holds no employee record"):
        EvidenceRef(Source.CALENDAR, employee_ref(employee_id(17)), "timezone")


def test_an_evidence_field_is_a_name_or_none_never_empty() -> None:
    with pytest.raises(ValueError, match="never empty"):
        EvidenceRef(Source.FRAPPE, employee_ref(employee_id(17)), "")


def test_observed_values_keep_their_type() -> None:
    by_ref = Observation(Source.JIRA, employee_ref(employee_id(17)))
    by_text = Observation(Source.JIRA, "emp_017")
    by_date = Observation(Source.JIRA, date(2026, 9, 14))
    assert by_ref != by_text
    assert by_date.value != "2026-09-14"
    assert hash(by_ref) != hash(by_text)
