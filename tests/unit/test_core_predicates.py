"""The predicate registry's invariants: complete over the name vocabulary, one record per
predicate and that record inside its own evidence domain, read-only, all domains closed
in the first golden set."""

import pytest

from leaveimpact.core.enums import Source, SubjectKind
from leaveimpact.core.predicates import (
    REGISTRY,
    ROWS,
    Predicate,
    PredicateName,
    index_by_name,
    predicate,
)


def test_every_predicate_name_has_exactly_one_registry_row() -> None:
    assert set(REGISTRY) == set(PredicateName)
    assert len(ROWS) == len(REGISTRY) == len(PredicateName)
    assert all(row.name == name for name, row in REGISTRY.items())


def test_a_name_declared_twice_fails_at_construction_not_by_overwrite() -> None:
    with pytest.raises(ValueError, match="declared twice"):
        index_by_name((ROWS[0], ROWS[0]))


def test_both_qualification_facts_have_a_row() -> None:
    assert predicate(PredicateName.MEMBER_OF_COMPONENT).system_of_record is Source.JIRA
    assert predicate(PredicateName.MEMBER_OF_COMPONENT).subject is SubjectKind.EMPLOYEE


def test_the_system_of_record_is_inside_its_own_evidence_domain() -> None:
    for row in REGISTRY.values():
        assert row.system_of_record in row.evidence_domain, row.name


def test_a_record_outside_its_domain_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="has_skill: the system of record"):
        Predicate(
            PredicateName.HAS_SKILL,
            SubjectKind.EMPLOYEE,
            Source.FRAPPE,
            frozenset({Source.JIRA}),
            True,
        )


def test_a_document_is_never_the_record_for_a_fact_about_a_person_or_a_ticket() -> None:
    for row in REGISTRY.values():
        if row.subject in {SubjectKind.EMPLOYEE, SubjectKind.WORK_ITEM}:
            assert row.system_of_record is not Source.CORPUS, row.name


def test_every_domain_is_closed_in_the_first_golden_set() -> None:
    assert all(row.closed for row in REGISTRY.values())


def test_the_registry_is_read_only() -> None:
    with pytest.raises(TypeError):
        REGISTRY[PredicateName.HAS_SKILL] = predicate(PredicateName.REPORTS_TO)  # type: ignore[index]


def test_the_fragmented_tier_cases_declare_their_second_source() -> None:
    assert predicate(PredicateName.HAS_SKILL).evidence_domain == {Source.FRAPPE, Source.JIRA}
    assert predicate(PredicateName.OWNS_WORK_ITEM).evidence_domain == {Source.JIRA, Source.CORPUS}
