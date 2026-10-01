"""The entity codec: every observable kind round-trips as a value and as an observed record,
the observed wrapper carries kind and source and decodes through the source-holds-kind
check, and a surplus field, a vendor key, a kind read only inside its record, a reversed
span and a non-canonical spelling all refuse at decode naming what was wrong."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import cast
from zoneinfo import ZoneInfo

import pytest

from leaveimpact.core import (
    CalendarEvent,
    Comment,
    Component,
    DateSpan,
    Document,
    DocumentKind,
    DocumentSection,
    Employee,
    EmploymentType,
    Entity,
    EntityKind,
    Grade,
    Leave,
    LeaveKind,
    LeaveStatus,
    Observed,
    Source,
    Team,
    WorkItem,
    WorkItemStatus,
    decode_entity,
    decode_observed,
    encode_entity,
    encode_observed,
)
from leaveimpact.core.ids import (
    clause_id,
    comment_id,
    component_id,
    document_id,
    employee_id,
    event_id,
    leave_id,
    skill_id,
    team_id,
    work_item_id,
)
from leaveimpact.core.jsonshape import JsonObject, canonical_json
from leaveimpact.core.timeshape import (
    decode_date_span,
    decode_instant,
    encode_date_span,
    encode_instant,
)

ISTANBUL = ZoneInfo("Europe/Istanbul")

EMPLOYEE = Employee(
    id=employee_id(17),
    name="Alice Demir",
    team_id=team_id(2),
    manager_id=employee_id(3),
    skills=(skill_id("kafka"), skill_id("postgres")),
    location="Istanbul",
    country="TR",
    timezone="Europe/Istanbul",
    grade=Grade.SENIOR,
    employment_type=EmploymentType.EMPLOYEE,
)
TEAM = Team(team_id(2), "Payments")
COMPONENT = Component(component_id(1), "payments-api", (employee_id(17), employee_id(3)))
WORK_ITEM = WorkItem(
    id=work_item_id(42),
    title="Kafka upgrade",
    owner_id=employee_id(17),
    status=WorkItemStatus.IN_PROGRESS,
    component_id=component_id(1),
    opened_on=date(2026, 9, 1),
    resolved_on=None,
    due_on=date(2026, 9, 30),
    comments=(
        Comment(comment_id(1), date(2026, 9, 10), employee_id(3), "[2026-09-10, emp_003] blocked"),
    ),
)
EVENT = CalendarEvent(
    id=event_id(7),
    title="Release review",
    start=datetime(2026, 9, 16, 10, 0, tzinfo=ISTANBUL),
    end=datetime(2026, 9, 16, 11, 0, tzinfo=ISTANBUL),
    attendee_ids=(employee_id(17),),
)
DOCUMENT = Document(
    id=document_id(4),
    title="Payments runbook",
    kind=DocumentKind.RUNBOOK,
    effective_from=date(2026, 3, 1),
    sections=(DocumentSection(clause_id(11), "Kafka is owned by Alice."),),
)
LEAVE = Leave(
    leave_id(5),
    employee_id(17),
    date(2026, 9, 15),
    date(2026, 9, 19),
    LeaveKind.ANNUAL,
    LeaveStatus.APPROVED,
)

OBSERVED: tuple[Observed[Entity], ...] = (
    Observed(EMPLOYEE, Source.FRAPPE),
    Observed(TEAM, Source.FRAPPE),
    Observed(COMPONENT, Source.JIRA),
    Observed(WORK_ITEM, Source.JIRA),
    Observed(EVENT, Source.CALENDAR),
    Observed(DOCUMENT, Source.CORPUS),
    Observed(LEAVE, Source.FRAPPE),
)


def _reparsed(data: JsonObject) -> object:
    """``data`` after a trip through text, so the decoder sees JSON types and nothing richer."""
    return json.loads(canonical_json(data))


@pytest.mark.parametrize("observed", OBSERVED, ids=[o.kind.value for o in OBSERVED])
def test_every_kind_round_trips_as_a_value_and_as_an_observed_record(
    observed: Observed[Entity],
) -> None:
    value = encode_entity(observed.value)
    assert decode_entity(observed.kind, _reparsed(value)) == observed.value
    assert encode_entity(decode_entity(observed.kind, _reparsed(value))) == value

    record = encode_observed(observed)
    assert record["kind"] == observed.kind.value
    assert record["source"] == observed.source.value
    assert record["value"] == value
    assert decode_observed(_reparsed(record)) == observed
    assert canonical_json(encode_observed(decode_observed(_reparsed(record)))) == canonical_json(
        record
    )


def test_the_two_absences_of_a_skills_record_stay_distinct() -> None:
    absent = encode_entity(replace(EMPLOYEE, skills=None))
    empty = encode_entity(replace(EMPLOYEE, skills=()))
    assert absent["skills"] is None
    assert empty["skills"] == []
    assert cast(Employee, decode_entity(EntityKind.EMPLOYEE, _reparsed(absent))).skills is None
    assert cast(Employee, decode_entity(EntityKind.EMPLOYEE, _reparsed(empty))).skills == ()


def test_a_source_that_holds_no_such_record_is_refused_by_the_wrapper() -> None:
    record = encode_observed(Observed(LEAVE, Source.FRAPPE))
    record["source"] = "jira"
    with pytest.raises(ValueError, match="jira holds no leave record"):
        decode_observed(_reparsed(record))


def test_a_kind_read_only_inside_its_record_is_never_observed_alone() -> None:
    with pytest.raises(ValueError, match="comment is read inside its record"):
        decode_entity(EntityKind.COMMENT, {})
    with pytest.raises(ValueError, match="clause is read inside its record"):
        decode_entity(EntityKind.CLAUSE, {})


def test_a_surplus_field_refuses_naming_the_record() -> None:
    record = encode_observed(Observed(LEAVE, Source.FRAPPE))
    cast(JsonObject, record["value"])["notes"] = "late"
    with pytest.raises(ValueError, match=r"a leave has fields .*surplus \['notes'\]"):
        decode_observed(_reparsed(record))
    record = encode_observed(Observed(LEAVE, Source.FRAPPE))
    record["read_at"] = "2026-09-14"
    with pytest.raises(ValueError, match=r"an observed record has fields .*surplus \['read_at'\]"):
        decode_observed(_reparsed(record))


def test_a_vendor_key_where_a_world_id_belongs_is_refused_naming_the_kind() -> None:
    value = encode_entity(WORK_ITEM)
    value["owner_id"] = "LIA-42"
    with pytest.raises(ValueError, match="an employee id has the form emp_NNN, got 'LIA-42'"):
        decode_entity(EntityKind.WORK_ITEM, _reparsed(value))


def test_a_value_outside_the_vocabulary_is_refused() -> None:
    value = encode_entity(LEAVE)
    value["status"] = "maybe"
    with pytest.raises(ValueError, match="maybe"):
        decode_entity(EntityKind.LEAVE, _reparsed(value))


def test_a_reversed_leave_fails_in_the_constructor() -> None:
    value = encode_entity(LEAVE)
    value["start"], value["end"] = value["end"], value["start"]
    with pytest.raises(ValueError):
        decode_entity(EntityKind.LEAVE, _reparsed(value))


def test_an_instant_keeps_its_zone_and_a_bare_offset_stays_bare() -> None:
    zoned = encode_instant(EVENT.start)
    assert zoned == {"at": "2026-09-16T10:00:00+03:00", "timezone": "Europe/Istanbul"}
    assert decode_instant(_reparsed(zoned), "start").tzinfo is ISTANBUL
    bare = encode_instant(datetime(2026, 9, 16, 7, 0, tzinfo=UTC))
    assert bare == {"at": "2026-09-16T07:00:00+00:00", "timezone": None}
    assert decode_instant(_reparsed(bare), "start") == datetime(2026, 9, 16, 7, 0, tzinfo=UTC)


def test_a_non_canonical_spelling_is_refused_rather_than_normalized() -> None:
    with pytest.raises(ValueError, match="start is spelled '2026-09-16T07:00:00Z'"):
        decode_instant({"at": "2026-09-16T07:00:00Z", "timezone": None}, "start")
    with pytest.raises(ValueError, match="a date is spelled '20260910'"):
        decode_date_span({"start": "20260910", "end": "2026-09-12"}, "a slice")


def test_a_date_span_round_trips_and_a_reversed_pair_fails_in_the_constructor() -> None:
    span = DateSpan(date(2026, 9, 10), date(2026, 9, 12))
    assert decode_date_span(_reparsed(encode_date_span(span)), "a slice") == span
    with pytest.raises(ValueError):
        decode_date_span({"start": "2026-09-12", "end": "2026-09-10"}, "a slice")
