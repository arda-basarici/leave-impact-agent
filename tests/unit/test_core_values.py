"""The value spec admits exactly what its kind declares, a requirement is a minimum count over
canonical conjunctive criteria, and a spec's parameters match its kind."""

from datetime import UTC, date, datetime

import pytest

from leaveimpact.core import (
    DATE_SPAN_VALUE,
    DATE_VALUE,
    INSTANT_SPAN_VALUE,
    REQUIREMENT_VALUE,
    SKILL_VALUE,
    TEXT_VALUE,
    DateSpan,
    EmploymentType,
    EmploymentTypeCriterion,
    EntityKind,
    EntityRef,
    InstantSpan,
    Requirement,
    SkillCriterion,
    ValueKind,
    ValueSpec,
    WorkItemStatus,
    entity_value,
    enum_value,
)
from leaveimpact.core.ids import SkillId, skill_id

A_DAY = date(2026, 9, 14)
A_SPAN = DateSpan(A_DAY, date(2026, 9, 16))
AN_HOUR = InstantSpan(datetime(2026, 9, 14, 9, tzinfo=UTC), datetime(2026, 9, 14, 10, tzinfo=UTC))
A_REQUIREMENT = Requirement(1, (SkillCriterion(skill_id("kafka")),))
TEAM = EntityRef(EntityKind.TEAM, "team_001")


STRUCTURED = {
    entity_value(EntityKind.TEAM): TEAM,
    DATE_VALUE: A_DAY,
    DATE_SPAN_VALUE: A_SPAN,
    INSTANT_SPAN_VALUE: AN_HOUR,
    REQUIREMENT_VALUE: A_REQUIREMENT,
}
TEXTUAL = {
    TEXT_VALUE: "Istanbul",
    enum_value(WorkItemStatus): WorkItemStatus.DONE,
    SKILL_VALUE: "kafka",
}


def test_each_structured_kind_admits_its_own_value_and_refuses_every_other() -> None:
    for spec, value in STRUCTURED.items():
        spec.check(value)
        for other_spec, other in (STRUCTURED | TEXTUAL).items():
            if other_spec is spec:
                continue
            with pytest.raises(ValueError, match=f"expected {spec.describe()}"):
                spec.check(other)


def test_the_textual_kinds_refuse_every_structured_value() -> None:
    for spec, value in TEXTUAL.items():
        spec.check(value)
        for other in STRUCTURED.values():
            with pytest.raises(ValueError, match=f"expected {spec.describe()}"):
                spec.check(other)


def test_an_entity_reference_of_the_wrong_kind_is_refused() -> None:
    with pytest.raises(ValueError, match="expected an entity_ref to a team, got an entity_ref to"):
        entity_value(EntityKind.TEAM).check(EntityRef(EntityKind.COMPONENT, "comp_001"))


def test_an_enum_value_outside_its_vocabulary_is_refused() -> None:
    spec = enum_value(WorkItemStatus)
    spec.check("done")
    with pytest.raises(ValueError, match="expected an enum from WorkItemStatus, got 'closed'"):
        spec.check("closed")
    with pytest.raises(ValueError, match="got 'employee'"):
        spec.check(EmploymentType.EMPLOYEE)


def test_a_skill_is_a_slug_not_arbitrary_text() -> None:
    SKILL_VALUE.check("kafka_streams")
    with pytest.raises(ValueError, match="got 'Kafka Streams': a skill id is a lower-case"):
        SKILL_VALUE.check("Kafka Streams")
    with pytest.raises(ValueError, match="expected a text, got '   '"):
        TEXT_VALUE.check("   ")


def test_a_spec_carries_a_parameter_exactly_when_its_kind_needs_one() -> None:
    with pytest.raises(ValueError, match="an entity_ref value names its entity kind"):
        ValueSpec(ValueKind.ENTITY_REF)
    with pytest.raises(ValueError, match="an enum value names its vocabulary"):
        ValueSpec(ValueKind.ENUM)
    with pytest.raises(ValueError, match="a skill value carries no vocabulary"):
        ValueSpec(ValueKind.SKILL, vocabulary=WorkItemStatus)
    with pytest.raises(ValueError, match="a date value carries no entity kind"):
        ValueSpec(ValueKind.DATE, entity_kind=EntityKind.TEAM)


def test_a_requirement_is_a_minimum_over_canonical_unique_criteria() -> None:
    skill = SkillCriterion(SkillId("kafka"))
    employee = EmploymentTypeCriterion(EmploymentType.EMPLOYEE)
    assert Requirement(2, (skill, employee)) == Requirement(2, (employee, skill))
    assert Requirement(2, (skill, employee)).criteria == (employee, skill)
    assert Requirement(3, ()).criteria == ()
    with pytest.raises(ValueError, match="at least one person, got count 0"):
        Requirement(0, ())
    with pytest.raises(ValueError, match="each criterion once"):
        Requirement(1, (skill, skill))
    with pytest.raises(ValueError, match="a skill id is a lower-case vocabulary key"):
        SkillCriterion(SkillId("Kafka"))


def test_a_requirement_that_exists_is_a_valid_requirement() -> None:
    with pytest.raises(ValueError, match="count is an integer, got True"):
        Requirement(True, ())
    with pytest.raises(ValueError, match="count is an integer, got 1.5"):
        Requirement(1.5, ())  # type: ignore[arg-type]


def test_a_date_is_a_day_never_an_instant() -> None:
    DATE_VALUE.check(A_DAY)
    with pytest.raises(ValueError, match="expected a date, got an instant"):
        DATE_VALUE.check(datetime(2026, 9, 14, 9, tzinfo=UTC))
