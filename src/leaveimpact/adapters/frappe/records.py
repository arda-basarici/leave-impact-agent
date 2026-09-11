"""Frappe HR record shapes, both directions: vendor dictionaries to domain entities and back.

Pure: every function here takes dictionaries and returns entities or payloads, so the
translation — where each domain fact lives on a Frappe document, and what a document
must carry to be read back — is testable without a site. The adapter (``adapter``)
owns the wire.

**Where the facts live.** The employee's id is ``employee_number``, a native field; the
team's id and the leave's id are custom fields the site schema adds (``custom_team_id``
on Department, ``custom_leave_id`` on Leave Application), as are the office city, the
country code and the zone on Employee, because hrms has no home for them and a text
address would be a fact the domain could not read back exactly. Grade and employment
type ride the Link fields hrms already has, through masters the site schema creates or
that ship with hrms. A leave's kind is its Leave Type, four masters named after the
kinds and flagged leave-without-pay so an application needs no allocation — balances are
not in the truth model. A leave's status is the pair of Frappe's ``status`` and
``docstatus``: an approved leave is submitted, a requested one is a draft.

**Vendor plumbing.** A Frappe employee needs a gender, a birth date and a joining
date; the values written are constants, not world facts, and nothing reads them back.
A leave application needs a posting date and an approver; the posting date is the
leave's own start, the approver the company's single service user.

**Malformed means untranslatable.** A document missing the field its identity lives in,
a date that does not parse, a master name outside the tables, a link to a person or a
team the read did not see — each raises ``MalformedRecord`` with the document's name as
locator, never a silent skip, because a dropped record would be graded as absence.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from leaveimpact.core.entities import Employee, Leave, Team
from leaveimpact.core.enums import EmploymentType, Grade, LeaveKind, LeaveStatus, Source
from leaveimpact.core.ids import EmployeeId, LeaveId, SkillId, TeamId
from leaveimpact.core.ports.errors import MalformedRecord

# --- the tables: domain enum <-> Frappe master name -----------------------------------

LEAVE_TYPE_BY_KIND: dict[LeaveKind, str] = {kind: kind.value.title() for kind in LeaveKind}
KIND_BY_LEAVE_TYPE: dict[str, LeaveKind] = {name: kind for kind, name in LEAVE_TYPE_BY_KIND.items()}

GRADE_NAME_BY_GRADE: dict[Grade, str] = {grade: grade.value.title() for grade in Grade}
GRADE_BY_GRADE_NAME: dict[str, Grade] = {name: grade for grade, name in GRADE_NAME_BY_GRADE.items()}

# hrms ships these two Employment Type masters; nothing is created for them.
EMPLOYMENT_TYPE_BY_KIND: dict[EmploymentType, str] = {
    EmploymentType.EMPLOYEE: "Full-time",
    EmploymentType.CONTRACTOR: "Contract",
}
KIND_BY_EMPLOYMENT_TYPE: dict[str, EmploymentType] = {
    name: kind for kind, name in EMPLOYMENT_TYPE_BY_KIND.items()
}

# (status, docstatus) as Frappe holds a leave application.
LEAVE_STATE_BY_STATUS: dict[LeaveStatus, tuple[str, int]] = {
    LeaveStatus.APPROVED: ("Approved", 1),
    LeaveStatus.REQUESTED: ("Open", 0),
}
STATUS_BY_LEAVE_STATE: dict[tuple[str, int], LeaveStatus] = {
    state: status for status, state in LEAVE_STATE_BY_STATUS.items()
}

# The fields each read asks for, so a list call returns what translation needs and no more.
EMPLOYEE_FIELDS = (
    "name",
    "employee_number",
    "employee_name",
    "department",
    "reports_to",
    "custom_location",
    "custom_country",
    "custom_timezone",
    "grade",
    "employment_type",
)
DEPARTMENT_FIELDS = ("name", "department_name", "custom_team_id")
LEAVE_FIELDS = (
    "name",
    "custom_leave_id",
    "employee",
    "leave_type",
    "from_date",
    "to_date",
    "status",
    "docstatus",
)

# Constants a Frappe document demands that carry no world meaning.
PLUMBING_GENDER = "Other"
PLUMBING_BIRTH_DATE = "1990-01-01"
PLUMBING_JOINING_DATE = "2020-01-01"
PLUMBING_PROFICIENCY = 0.6  # a Rating field holds a fraction; required on every skill row


def _field(record: dict[str, Any], key: str, locator: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise MalformedRecord(Source.FRAPPE, locator, f"no {key}")
    return value


def _date(record: dict[str, Any], key: str, locator: str) -> date:
    raw = _field(record, key, locator)
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise MalformedRecord(Source.FRAPPE, locator, f"{key} {raw!r} is not a date") from exc


def _lookup[T](table: dict[str, T], name: str, what: str, locator: str) -> T:
    try:
        return table[name]
    except KeyError:
        raise MalformedRecord(
            Source.FRAPPE, locator, f"{what} {name!r} is not one the domain knows"
        ) from None


# --- teams -----------------------------------------------------------------------------


def team_payload(team: Team, company: str) -> dict[str, Any]:
    return {"department_name": team.name, "company": company, "custom_team_id": team.id}


def team_from_record(record: dict[str, Any]) -> Team:
    """A Department document, listed with ``DEPARTMENT_FIELDS``, as a team.

    >>> team_from_record({"name": "Platform - CAS", "department_name": "Platform",
    ...                   "custom_team_id": "team_003"})
    Team(id='team_003', name='Platform')
    """
    locator = f"Department/{record.get('name', '?')}"
    return Team(
        TeamId(_field(record, "custom_team_id", locator)),
        _field(record, "department_name", locator),
    )


# --- employees -------------------------------------------------------------------------


def split_name(full_name: str) -> tuple[str, str]:
    """Frappe wants a first and a last name; the last word is the last name.

    >>> split_name("Deniz Yılmaz"), split_name("Madonna")
    (('Deniz', 'Yılmaz'), ('Madonna', ''))
    """
    first, _, last = full_name.strip().rpartition(" ")
    return (first, last) if first else (last, "")


def employee_payload(
    employee: Employee,
    *,
    company: str,
    department_name: str,
    manager_name: str | None,
    holiday_list: str,
    approver_email: str,
) -> dict[str, Any]:
    """The Employee document for ``employee``, links already resolved to vendor names."""
    first, last = split_name(employee.name)
    payload: dict[str, Any] = {
        "employee_number": employee.id,
        "first_name": first,
        "last_name": last,
        "gender": PLUMBING_GENDER,
        "date_of_birth": PLUMBING_BIRTH_DATE,
        "date_of_joining": PLUMBING_JOINING_DATE,
        "company": company,
        "status": "Active",
        "department": department_name,
        "custom_location": employee.location,
        "custom_country": employee.country,
        "custom_timezone": employee.timezone,
        "grade": GRADE_NAME_BY_GRADE[employee.grade],
        "employment_type": EMPLOYMENT_TYPE_BY_KIND[employee.employment_type],
        "holiday_list": holiday_list,
        "leave_approver": approver_email,
    }
    if manager_name is not None:
        payload["reports_to"] = manager_name
    return payload


def skill_map_payload(employee_name: str, skills: tuple[SkillId, ...]) -> dict[str, Any]:
    """The Employee Skill Map for a person whose skill record exists, rows for each skill."""
    return {
        "employee": employee_name,
        "employee_skills": [
            {"skill": skill, "proficiency": PLUMBING_PROFICIENCY} for skill in skills
        ],
    }


def employee_from_record(
    record: dict[str, Any],
    *,
    team_by_department: dict[str, TeamId],
    number_by_name: dict[str, EmployeeId],
    skills_by_name: dict[str, tuple[SkillId, ...]],
) -> Employee:
    """An Employee document, listed with ``EMPLOYEE_FIELDS``, as an employee.

    The three maps are what a single document cannot say: which team its department
    is, which employee its manager's vendor name is, and which skills its skill map
    holds — ``None`` when the person has no skill map at all, the blank record.
    """
    locator = f"Employee/{record.get('name', '?')}"
    name = _field(record, "name", locator)
    department = _field(record, "department", locator)
    manager = record.get("reports_to") or None
    if manager is not None and manager not in number_by_name:
        raise MalformedRecord(
            Source.FRAPPE, locator, f"reports_to {manager!r} is not an employee read"
        )
    return Employee(
        id=EmployeeId(_field(record, "employee_number", locator)),
        name=_field(record, "employee_name", locator),
        team_id=_lookup(team_by_department, department, "department", locator),
        manager_id=number_by_name[manager] if manager is not None else None,
        skills=skills_by_name.get(name),
        location=_field(record, "custom_location", locator),
        country=_field(record, "custom_country", locator),
        timezone=_field(record, "custom_timezone", locator),
        grade=_lookup(GRADE_BY_GRADE_NAME, _field(record, "grade", locator), "grade", locator),
        employment_type=_lookup(
            KIND_BY_EMPLOYMENT_TYPE,
            _field(record, "employment_type", locator),
            "employment type",
            locator,
        ),
    )


def skills_by_employee(rows: list[dict[str, Any]]) -> dict[str, tuple[SkillId, ...]]:
    """Employee Skill Map rows flattened over their child table, grouped by employee name.

    A list call over ``employee`` and ``employee_skills.skill`` yields one row per skill
    and one row with a null skill for a map with no rows, so a person with an empty
    skill record still appears, with an empty tuple.

    >>> skills_by_employee([{"employee": "HR-EMP-1", "skill": "kafka"},
    ...                     {"employee": "HR-EMP-1", "skill": "sql"},
    ...                     {"employee": "HR-EMP-2", "skill": None}])
    {'HR-EMP-1': ('kafka', 'sql'), 'HR-EMP-2': ()}
    """
    grouped: dict[str, list[SkillId]] = {}
    for row in rows:
        locator = f"Employee Skill Map/{row.get('employee', '?')}"
        skills = grouped.setdefault(_field(row, "employee", locator), [])
        skill = row.get("skill")
        if skill is not None:
            skills.append(SkillId(skill))
    return {name: tuple(skills) for name, skills in grouped.items()}


# --- leaves ----------------------------------------------------------------------------


def leave_payload(leave: Leave, *, employee_name: str, approver_email: str) -> dict[str, Any]:
    status, docstatus = LEAVE_STATE_BY_STATUS[leave.status]
    return {
        "custom_leave_id": leave.id,
        "employee": employee_name,
        "leave_type": LEAVE_TYPE_BY_KIND[leave.kind],
        "from_date": leave.start.isoformat(),
        "to_date": leave.end.isoformat(),
        "posting_date": leave.start.isoformat(),
        "status": status,
        "docstatus": docstatus,
        "leave_approver": approver_email,
    }


def leave_from_record(record: dict[str, Any], *, number_by_name: dict[str, EmployeeId]) -> Leave:
    """A Leave Application, listed with ``LEAVE_FIELDS``, as a leave."""
    locator = f"Leave Application/{record.get('name', '?')}"
    employee = _field(record, "employee", locator)
    if employee not in number_by_name:
        raise MalformedRecord(
            Source.FRAPPE, locator, f"employee {employee!r} is not an employee read"
        )
    docstatus = record.get("docstatus")
    state = (_field(record, "status", locator), docstatus if isinstance(docstatus, int) else -1)
    if state not in STATUS_BY_LEAVE_STATE:
        raise MalformedRecord(
            Source.FRAPPE, locator, f"status {state!r} is not a leave state the domain knows"
        )
    return Leave(
        id=LeaveId(_field(record, "custom_leave_id", locator)),
        employee_id=number_by_name[employee],
        start=_date(record, "from_date", locator),
        end=_date(record, "to_date", locator),
        kind=_lookup(
            KIND_BY_LEAVE_TYPE, _field(record, "leave_type", locator), "leave type", locator
        ),
        status=STATUS_BY_LEAVE_STATE[state],
    )
