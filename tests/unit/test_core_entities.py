"""Entities: frozen by construction, the two absences of a skills record are distinct
values, and each dated entity states its interval convention through ``span``."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime

import pytest

from leaveimpact.core import (
    CalendarEvent,
    Employee,
    EmploymentType,
    Grade,
    Leave,
    LeaveKind,
    LeaveStatus,
)
from leaveimpact.core.ids import employee_id, event_id, leave_id, skill_id, team_id


def _employee(skills: tuple[str, ...] | None) -> Employee:
    return Employee(
        id=employee_id(17),
        name="Alice Demir",
        team_id=team_id(2),
        manager_id=employee_id(3),
        skills=None if skills is None else tuple(skill_id(key) for key in skills),
        location="Istanbul",
        country="TR",
        timezone="Europe/Istanbul",
        grade=Grade.SENIOR,
        employment_type=EmploymentType.EMPLOYEE,
    )


def test_an_entity_never_changes_under_a_reader() -> None:
    alice = _employee(("kafka",))
    with pytest.raises(FrozenInstanceError):
        alice.name = "Alice Kaya"  # type: ignore[misc]
    assert replace(alice, name="Alice Kaya").name == "Alice Kaya"
    assert alice.name == "Alice Demir"


def test_a_missing_skills_record_and_an_empty_one_are_different_facts() -> None:
    absent, empty = _employee(None), _employee(())
    assert absent.skills is None
    assert empty.skills == ()
    assert absent != empty


def test_a_leave_reads_as_inclusive_calendar_days() -> None:
    leave = Leave(
        id=leave_id(5),
        employee_id=employee_id(17),
        start=date(2026, 9, 10),
        end=date(2026, 9, 12),
        kind=LeaveKind.ANNUAL,
        status=LeaveStatus.APPROVED,
    )
    assert leave.span.days == 3
    assert leave.span.contains(date(2026, 9, 12))


def test_an_event_reads_as_a_half_open_instant_span() -> None:
    event = CalendarEvent(
        id=event_id(9),
        title="Release planning",
        start=datetime(2026, 9, 14, 9, tzinfo=UTC),
        end=datetime(2026, 9, 14, 10, tzinfo=UTC),
        attendee_ids=(employee_id(17),),
    )
    assert not event.span.contains(event.end)


def test_an_event_with_naive_instants_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        CalendarEvent(
            id=event_id(9),
            title="Release planning",
            start=datetime(2026, 9, 14, 9),
            end=datetime(2026, 9, 14, 10),
            attendee_ids=(),
        )


def test_a_leave_ending_before_it_starts_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="ends on or after it starts"):
        Leave(
            id=leave_id(5),
            employee_id=employee_id(17),
            start=date(2026, 9, 12),
            end=date(2026, 9, 10),
            kind=LeaveKind.ANNUAL,
            status=LeaveStatus.APPROVED,
        )
