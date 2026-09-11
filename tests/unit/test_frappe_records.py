"""The Frappe translation, both directions, without a site.

The claims: a payload carries every domain fact where the read expects it and the
plumbing constants beside them; a listed document translates back to the same entity;
and every way a document can fail translation — a missing identity field, a date
that does not parse, a master outside the tables, a dangling link — raises
``MalformedRecord`` naming the document, never a silent skip.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from leaveimpact.adapters.frappe import records
from leaveimpact.core.entities import Employee, Leave, Team
from leaveimpact.core.enums import EmploymentType, Grade, LeaveKind, LeaveStatus
from leaveimpact.core.ids import employee_id, leave_id, skill_id, team_id
from leaveimpact.core.ports.errors import MalformedRecord

PLATFORM = Team(team_id(3), "Platform")
DENIZ = Employee(
    id=employee_id(4),
    name="Deniz Yılmaz",
    team_id=PLATFORM.id,
    manager_id=employee_id(1),
    skills=(skill_id("kafka"), skill_id("sql")),
    location="Istanbul",
    country="TR",
    timezone="Europe/Istanbul",
    grade=Grade.SENIOR,
    employment_type=EmploymentType.EMPLOYEE,
)
LEAVE = Leave(
    leave_id(7),
    DENIZ.id,
    date(2026, 9, 14),
    date(2026, 9, 18),
    LeaveKind.ANNUAL,
    LeaveStatus.APPROVED,
)


def deniz_record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "name": "HR-EMP-00004",
        "employee_number": "emp_004",
        "employee_name": "Deniz Yılmaz",
        "department": "Platform - CAS",
        "reports_to": "HR-EMP-00001",
        "custom_location": "Istanbul",
        "custom_country": "TR",
        "custom_timezone": "Europe/Istanbul",
        "grade": "Senior",
        "employment_type": "Full-time",
    }
    record.update(overrides)
    return record


TEAMS = {"Platform - CAS": PLATFORM.id}
NUMBERS = {"HR-EMP-00001": employee_id(1), "HR-EMP-00004": DENIZ.id}
SKILLS = {"HR-EMP-00004": (skill_id("kafka"), skill_id("sql"))}


def test_employee_payload_carries_every_fact_and_the_plumbing() -> None:
    payload = records.employee_payload(
        DENIZ,
        company="Cassette Org",
        department_name="Platform - CAS",
        manager_name="HR-EMP-00001",
        holiday_list="Cassette Org Holidays",
        approver_email="approver@cas.leave-impact.invalid",
    )
    assert payload["employee_number"] == "emp_004"
    assert (payload["first_name"], payload["last_name"]) == ("Deniz", "Yılmaz")
    assert payload["department"] == "Platform - CAS" and payload["reports_to"] == "HR-EMP-00001"
    assert payload["custom_timezone"] == "Europe/Istanbul" and payload["custom_country"] == "TR"
    assert payload["grade"] == "Senior" and payload["employment_type"] == "Full-time"
    assert payload["gender"] == records.PLUMBING_GENDER and payload["status"] == "Active"


def test_a_top_of_org_employee_has_no_reports_to() -> None:
    top = replace(DENIZ, manager_id=None)
    payload = records.employee_payload(
        top,
        company="C",
        department_name="D",
        manager_name=None,
        holiday_list="H",
        approver_email="a@b",
    )
    assert "reports_to" not in payload


def test_employee_record_translates_back() -> None:
    got = records.employee_from_record(
        deniz_record(), team_by_department=TEAMS, number_by_name=NUMBERS, skills_by_name=SKILLS
    )
    assert got == DENIZ


def test_a_missing_skill_map_is_the_blank_record_and_an_empty_one_is_no_skills() -> None:
    blank = records.employee_from_record(
        deniz_record(), team_by_department=TEAMS, number_by_name=NUMBERS, skills_by_name={}
    )
    assert blank.skills is None
    empty = records.employee_from_record(
        deniz_record(),
        team_by_department=TEAMS,
        number_by_name=NUMBERS,
        skills_by_name={"HR-EMP-00004": ()},
    )
    assert empty.skills == ()


def test_skill_rows_group_by_employee_and_keep_the_empty_map() -> None:
    rows = [
        {"employee": "HR-EMP-1", "skill": "kafka"},
        {"employee": "HR-EMP-2", "skill": None},
        {"employee": "HR-EMP-1", "skill": "sql"},
    ]
    assert records.skills_by_employee(rows) == {"HR-EMP-1": ("kafka", "sql"), "HR-EMP-2": ()}


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"employee_number": None}, "no employee_number"),
        ({"custom_timezone": ""}, "no custom_timezone"),
        ({"grade": "Principal"}, "grade 'Principal' is not one the domain knows"),
        ({"employment_type": "Intern"}, "employment type 'Intern' is not one the domain knows"),
        ({"department": "Sales - CAS"}, "department 'Sales - CAS' is not one the domain knows"),
        ({"reports_to": "HR-EMP-00099"}, "reports_to 'HR-EMP-00099' is not an employee read"),
    ],
)
def test_an_untranslatable_employee_is_malformed_by_name(
    overrides: dict[str, Any], reason: str
) -> None:
    with pytest.raises(MalformedRecord) as caught:
        records.employee_from_record(
            deniz_record(**overrides),
            team_by_department=TEAMS,
            number_by_name=NUMBERS,
            skills_by_name=SKILLS,
        )
    assert caught.value.locator == "Employee/HR-EMP-00004"
    assert caught.value.reason == reason


def test_leave_payload_and_record_round_trip() -> None:
    payload = records.leave_payload(LEAVE, employee_name="HR-EMP-00004", approver_email="a@b")
    assert payload["custom_leave_id"] == "leave_007" and payload["leave_type"] == "Annual"
    assert (payload["status"], payload["docstatus"]) == ("Approved", 1)
    assert payload["from_date"] == "2026-09-14" and payload["posting_date"] == "2026-09-14"
    record = {
        "name": "HR-LAP-2026-00001",
        "custom_leave_id": "leave_007",
        "employee": "HR-EMP-00004",
        "leave_type": "Annual",
        "from_date": "2026-09-14",
        "to_date": "2026-09-18",
        "status": "Approved",
        "docstatus": 1,
    }
    assert records.leave_from_record(record, number_by_name=NUMBERS) == LEAVE


def test_a_requested_leave_is_an_open_draft() -> None:
    requested = Leave(
        LEAVE.id, LEAVE.employee_id, LEAVE.start, LEAVE.end, LeaveKind.SICK, LeaveStatus.REQUESTED
    )
    payload = records.leave_payload(requested, employee_name="HR-EMP-00004", approver_email="a@b")
    assert (payload["status"], payload["docstatus"], payload["leave_type"]) == ("Open", 0, "Sick")


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"from_date": "14/09/2026"}, "from_date '14/09/2026' is not a date"),
        (
            {"leave_type": "Privilege Leave"},
            "leave type 'Privilege Leave' is not one the domain knows",
        ),
        (
            {"status": "Rejected", "docstatus": 1},
            "status ('Rejected', 1) is not a leave state the domain knows",
        ),
        ({"employee": "HR-EMP-00099"}, "employee 'HR-EMP-00099' is not an employee read"),
        ({"custom_leave_id": None}, "no custom_leave_id"),
    ],
)
def test_an_untranslatable_leave_is_malformed_by_name(
    overrides: dict[str, Any], reason: str
) -> None:
    record: dict[str, Any] = {
        "name": "HR-LAP-2026-00001",
        "custom_leave_id": "leave_007",
        "employee": "HR-EMP-00004",
        "leave_type": "Annual",
        "from_date": "2026-09-14",
        "to_date": "2026-09-18",
        "status": "Approved",
        "docstatus": 1,
        **overrides,
    }
    with pytest.raises(MalformedRecord) as caught:
        records.leave_from_record(record, number_by_name=NUMBERS)
    assert caught.value.locator == "Leave Application/HR-LAP-2026-00001"
    assert caught.value.reason == reason


def test_team_payload_and_record_round_trip() -> None:
    assert records.team_payload(PLATFORM, "Cassette Org") == {
        "department_name": "Platform",
        "company": "Cassette Org",
        "custom_team_id": "team_003",
    }
    got = records.team_from_record(
        {"name": "Platform - CAS", "department_name": "Platform", "custom_team_id": "team_003"}
    )
    assert got == PLATFORM
    with pytest.raises(MalformedRecord) as caught:
        records.team_from_record(
            {"name": "Sales - CAS", "department_name": "Sales", "custom_team_id": None}
        )
    assert caught.value.locator == "Department/Sales - CAS"
