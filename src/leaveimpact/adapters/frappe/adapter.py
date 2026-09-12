"""The Frappe HR adapter: the people reader and writer over ``/api/resource``, and site preparation.

One class implements both ports, because the read and the write side share a
transport, a company scope and an identity map; which side a caller holds is the
type it is handed (``PeopleReader`` or ``PeopleWriter``), never a second class.
Construction does no I/O: the credential, the configuration and the transport policy
are three frozen values, and the first request happens on the first call.

**Scope.** Every read filters by the configured company and every write plants it, so
a site can hold the world and the cassette recordings side by side without one reading
the other. The identity map (a domain id to Frappe's document name and back) is not
configured: each document carries its domain id, so the adapter resolves a link by
listing the company's departments or employees when a call needs them, a read and never
a lookup at construction. A domain id matches exactly one document or the record is
malformed — Frappe enforces no uniqueness on an employee number or a custom field, so
the adapter does, on every select, every link resolution and every enumeration alike,
and never picks one of two nor returns both: a domain id has exactly one vendor
representation per place, the rule every adapter applies (the review at the close of
the adapter step).

**One employee is one write.** An employee with a skill record is two Frappe documents,
and two requests would open a window where the first landed and the second did not,
which the projector's find-or-create could never repair: it would find the employee and
skip them, and the reader would report the missing skill map as the blank record.
So ``add_employee`` sends both documents in one ``insert_many`` call, which Frappe runs
as one transaction — a failed second document leaves no first one (probed live at the
step 9 review). The skill map has to name the employee before either exists, so the
site schema sets HR Settings to name employees by their employee number; the document
name is then the domain id. The consequence is that an employee number is unique per
site, not per company, which fits the one-world-per-site hosting shape (``hr-w1``); the
cassette company uses ids above 900 by convention.

**Preparation is not writing.** ``ensure_site_schema``, ``ensure_company`` and
``ensure_skills`` are the Frappe half of the projector's setup — the naming rule, the
custom fields the records live in, the masters the Link fields point at, the company
with its holiday list and its service approver — and they find before they create
because a master that exists is not an error. They are called by the composition root,
the way the corpus's DDL is, and are idempotent; the port writers below them add and
never find.

**Faults.** The transport turns exhausted retries and undeclared statuses into
``SourceUnreachable``. A document the translation cannot read raises
``MalformedRecord`` (``records``), and so does a successful response whose envelope
is not Frappe's — a body that is not JSON, no ``data``, an insert with no name — with
the request as locator: the source answered, so the defect is the source's and belongs
to validation, not to epistemic uncertainty. Every read is replayable; every insert is
not, and the projector restarts find-or-create when an insert's outcome is unknown.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, cast

import httpx

from leaveimpact.adapters.frappe import records
from leaveimpact.adapters.transport import DEFAULT_POLICY, Transport, TransportPolicy
from leaveimpact.core.entities import Employee, Leave, Team
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import EmployeeId, LeaveId, SkillId, TeamId
from leaveimpact.core.ports.errors import MalformedRecord
from leaveimpact.core.ports.observed import Observed
from leaveimpact.core.worldtime import DateSpan

_PAGE = 100
Filters = list[list[Any]]
Record = dict[str, Any]


@dataclass(frozen=True, slots=True)
class FrappeCredential:
    """An API key and secret for a Frappe user; the repr never shows either."""

    api_key: str
    api_secret: str

    def __repr__(self) -> str:
        return "FrappeCredential(api_key=…, api_secret=…)"

    @property
    def authorization(self) -> str:
        return f"token {self.api_key}:{self.api_secret}"


@dataclass(frozen=True, slots=True)
class FrappeConfig:
    """The company the adapter reads and writes under, and the names derived from it.

    The abbreviation is Frappe's suffix on every document name in the company (a
    department is ``Platform - CAS``); the holiday list and the approver are the
    company's plumbing, named from it so two companies never share them.

    >>> FrappeConfig("Cassette Org", "CAS").approver_email
    'approver@cas.leave-impact.invalid'
    """

    company: str
    company_abbr: str

    @property
    def holiday_list(self) -> str:
        return f"{self.company} Holidays"

    @property
    def approver_email(self) -> str:
        return f"approver@{self.company_abbr.lower()}.leave-impact.invalid"


# The custom fields the records live in: (doctype, fieldname, label, insert_after).
CUSTOM_FIELDS: tuple[tuple[str, str, str, str], ...] = (
    ("Employee", "custom_location", "Location", "employee_number"),
    ("Employee", "custom_country", "Country Code", "custom_location"),
    ("Employee", "custom_timezone", "Timezone", "custom_country"),
    ("Department", "custom_team_id", "Team Id", "department_name"),
    ("Leave Application", "custom_leave_id", "Leave Id", "description"),
)
# Employees are named by their employee number, so the name is known before the insert.
EMPLOYEE_NAMING = "Employee Number"
# The holiday list spans every year a world can be dated in, with no holidays: every
# day is a working day until holidays enter the truth model (deferred at step 8).
HOLIDAY_SPAN = ("2020-01-01", "2035-12-31")


class FrappeAdapter:
    """People reader and writer over one Frappe site, scoped to one company."""

    def __init__(
        self,
        *,
        base_url: str,
        credential: FrappeCredential,
        config: FrappeConfig,
        policy: TransportPolicy = DEFAULT_POLICY,
        sleep: Callable[[float], None] | None = None,
        httpx_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        extra: dict[str, Any] = {}
        if sleep is not None:
            extra["sleep"] = sleep
        self._transport = Transport(
            base_url=base_url,
            source=Source.FRAPPE,
            headers={"Authorization": credential.authorization, "Accept": "application/json"},
            policy=policy,
            httpx_transport=httpx_transport,
            **extra,
        )

    @property
    def config(self) -> FrappeConfig:
        return self._config

    def close(self) -> None:
        self._transport.close()

    # --- the read side --------------------------------------------------------------

    def employee(self, id: EmployeeId) -> Observed[Employee] | None:
        record = self._one(
            "Employee", self._company_filter(["employee_number", "=", id]), records.EMPLOYEE_FIELDS
        )
        if record is None:
            return None
        manager = record.get("reports_to") or None
        number_by_name = {record["name"]: id}
        if manager is not None:
            number_by_name.update(self._numbers_by_name([["name", "=", manager]]))
        return self._observed_employee(
            record, number_by_name, self._skills_by_name([record["name"]])
        )

    def employees(self) -> tuple[Observed[Employee], ...]:
        found = self._list("Employee", self._company_filter(), records.EMPLOYEE_FIELDS)
        _held_once(found, "employee_number", "Employee")
        number_by_name = {
            row["name"]: EmployeeId(row["employee_number"])
            for row in found
            if row.get("employee_number")
        }
        skills_by_name = self._skills_by_name([row["name"] for row in found])
        return tuple(self._observed_employee(row, number_by_name, skills_by_name) for row in found)

    def team(self, id: TeamId) -> Observed[Team] | None:
        record = self._one(
            "Department",
            self._company_filter(["custom_team_id", "=", id]),
            records.DEPARTMENT_FIELDS,
        )
        if record is None:
            return None
        return Observed(records.team_from_record(record), Source.FRAPPE)

    def leave(self, id: LeaveId) -> Observed[Leave] | None:
        record = self._one(
            "Leave Application",
            self._leave_filter(["custom_leave_id", "=", id]),
            records.LEAVE_FIELDS,
        )
        if record is None:
            return None
        number_by_name = self._numbers_by_name([["name", "=", record.get("employee", "")]])
        return Observed(
            records.leave_from_record(record, number_by_name=number_by_name), Source.FRAPPE
        )

    def leaves_within(self, span: DateSpan) -> tuple[Observed[Leave], ...]:
        found = self._list(
            "Leave Application",
            self._leave_filter(
                ["from_date", "<=", span.end.isoformat()],
                ["to_date", ">=", span.start.isoformat()],
            ),
            records.LEAVE_FIELDS,
        )
        if not found:
            return ()
        _held_once(found, "custom_leave_id", "Leave Application")
        number_by_name = self._numbers_by_name([])
        return tuple(
            Observed(records.leave_from_record(row, number_by_name=number_by_name), Source.FRAPPE)
            for row in found
        )

    # --- the write side -------------------------------------------------------------

    def add_team(self, team: Team) -> str:
        return self._insert("Department", records.team_payload(team, self._config.company))

    def add_employee(self, employee: Employee) -> str:
        """One request for the employee and their skill record, so neither lands alone."""
        department = self._department_name(employee.team_id)
        manager = (
            self._employee_name(employee.manager_id) if employee.manager_id is not None else None
        )
        documents: list[Record] = [
            {
                "doctype": "Employee",
                **records.employee_payload(
                    employee,
                    company=self._config.company,
                    department_name=department,
                    manager_name=manager,
                    holiday_list=self._config.holiday_list,
                    approver_email=self._config.approver_email,
                ),
            }
        ]
        if employee.skills is not None:
            documents.append(
                {
                    "doctype": "Employee Skill Map",
                    **records.skill_map_payload(employee.id, employee.skills),
                }
            )
        return self._insert_many(documents)[0]

    def add_leave(self, leave: Leave) -> str:
        employee = self._employee_name(leave.employee_id)
        return self._insert(
            "Leave Application",
            records.leave_payload(
                leave, employee_name=employee, approver_email=self._config.approver_email
            ),
        )

    # --- preparation: the site schema, the company, the skill masters ----------------

    def ensure_site_schema(self) -> None:
        """The naming rule, custom fields, grade masters and leave types every company uses."""
        settings = self._get("/api/resource/HR Settings/HR Settings")
        naming = (
            cast(Record, settings).get("emp_created_by") if isinstance(settings, dict) else None
        )
        if naming != EMPLOYEE_NAMING:
            self._call(
                "frappe.client.set_value",
                doctype="HR Settings",
                name="HR Settings",
                fieldname="emp_created_by",
                value=EMPLOYEE_NAMING,
            )
        for doctype, fieldname, label, insert_after in CUSTOM_FIELDS:
            self._ensure(
                "Custom Field",
                [["dt", "=", doctype], ["fieldname", "=", fieldname]],
                {
                    "dt": doctype,
                    "fieldname": fieldname,
                    "label": label,
                    "fieldtype": "Data",
                    "insert_after": insert_after,
                },
            )
        for grade_name in records.GRADE_NAME_BY_GRADE.values():
            self._ensure("Employee Grade", [["name", "=", grade_name]], {"__newname": grade_name})
        for leave_type in records.LEAVE_TYPE_BY_KIND.values():
            self._ensure(
                "Leave Type",
                [["name", "=", leave_type]],
                {"leave_type_name": leave_type, "is_lwp": 1, "max_continuous_days_allowed": 0},
            )

    def ensure_company(self) -> None:
        """The configured company, with the holiday list assignment and approver a leave needs."""
        company = self._config.company
        self._ensure(
            "Company",
            [["name", "=", company]],
            {
                "company_name": company,
                "abbr": self._config.company_abbr,
                "default_currency": "TRY",
                "country": "Türkiye",
            },
        )
        holiday_list = self._config.holiday_list
        self._ensure(
            "Holiday List",
            [["name", "=", holiday_list]],
            {
                "holiday_list_name": holiday_list,
                "from_date": HOLIDAY_SPAN[0],
                "to_date": HOLIDAY_SPAN[1],
            },
        )
        # hrms 16 resolves a holiday list only through a submitted assignment; the legacy
        # fields on Company and Employee are accepted and ignored (frappe-rest probe).
        self._ensure(
            "Holiday List Assignment",
            [
                ["applicable_for", "=", "Company"],
                ["assigned_to", "=", company],
                ["docstatus", "=", 1],
            ],
            {
                "applicable_for": "Company",
                "assigned_to": company,
                "holiday_list": holiday_list,
                "from_date": HOLIDAY_SPAN[0],
                "docstatus": 1,
            },
        )
        approver = self._config.approver_email
        self._ensure(
            "User",
            [["name", "=", approver]],
            {
                "email": approver,
                "first_name": f"{self._config.company_abbr} Approver",
                "send_welcome_email": 0,
                "user_type": "System User",
                "roles": [{"role": "Leave Approver"}, {"role": "HR User"}],
            },
        )

    def held_employee_numbers(self, world_ids: Iterable[EmployeeId]) -> frozenset[EmployeeId]:
        """The employee numbers the company holds, or the call refuses; a site-level inspection.

        Employee names are unique per site, not per company, and the world names employees
        by their number, so a number this world plants that another company on the site
        already holds would make the insert fail with a wrong diagnosis after the teams were
        written. The first query looks past the company scope for exactly that and refuses
        naming the documents; the ordinary reader stays company-scoped, since that scope is
        the world's boundary on the site. The second returns what the company holds, each
        number once, for the composition root to compare with the world: a subset before
        projection, the exact set after it (the employee-number ruling at the projector step).
        A company employee without a number refuses too, since the reader would fail on it and
        an exact set that skipped it would not be exact.
        """
        ids = sorted(world_ids)
        foreign = self._list(
            "Employee",
            [["employee_number", "in", ids], ["company", "!=", self._config.company]],
            ("name", "employee_number", "company"),
        )
        if foreign:
            names = ", ".join(sorted(str(row.get("name")) for row in foreign))
            held = sorted(
                {f"{row.get('employee_number')} in {row.get('company')!r}" for row in foreign}
            )
            raise MalformedRecord(
                Source.FRAPPE,
                f"Employee/{names}",
                f"world employee numbers held by another company on the site: {held}",
            )
        held_rows = self._list("Employee", self._company_filter(), ("name", "employee_number"))
        _held_once(held_rows, "employee_number", "Employee")
        unnumbered = sorted(
            str(row.get("name")) for row in held_rows if not row.get("employee_number")
        )
        if unnumbered:
            # The reader would try to translate such a row and fail; an exact set is exact.
            raise MalformedRecord(
                Source.FRAPPE,
                f"Employee/{', '.join(unnumbered)}",
                "employees of the company without an employee number",
            )
        return frozenset(EmployeeId(str(row["employee_number"])) for row in held_rows)

    def ensure_skills(self, skills: Iterable[SkillId]) -> None:
        """The Skill masters the employees' skill maps link to, named by the domain id."""
        for skill in skills:
            self._ensure("Skill", [["name", "=", skill]], {"skill_name": skill})

    # --- the wire ---------------------------------------------------------------------

    def _company_filter(self, *extra: list[Any]) -> Filters:
        return [["company", "=", self._config.company], *extra]

    def _leave_filter(self, *extra: list[Any]) -> Filters:
        # Rejected and cancelled applications are not leaves in the world model.
        return self._company_filter(
            ["status", "in", ["Open", "Approved"]], ["docstatus", "in", [0, 1]], *extra
        )

    def _list(self, doctype: str, filters: Filters, fields: tuple[str, ...]) -> list[Record]:
        """Every document matching ``filters``, paged to completion."""
        rows: list[Record] = []
        start = 0
        path = f"/api/resource/{doctype}"
        while True:
            page = self._get(
                path,
                params={
                    "filters": json.dumps(filters),
                    "fields": json.dumps(list(fields)),
                    "limit_start": start,
                    "limit_page_length": _PAGE,
                },
            )
            if not isinstance(page, list):
                raise MalformedRecord(Source.FRAPPE, f"GET {path}", "data is not a list")
            documents: list[Record] = []
            for member in cast(list[Any], page):
                if not isinstance(member, dict):
                    raise MalformedRecord(
                        Source.FRAPPE, f"GET {path}", "a document in data is not an object"
                    )
                documents.append(cast(Record, member))
            rows.extend(documents)
            if len(documents) < _PAGE:
                return rows
            start += _PAGE

    def _one(self, doctype: str, filters: Filters, fields: tuple[str, ...]) -> Record | None:
        """The one document a domain id names: ``None`` for none, malformed for more than one."""
        found = self._list(doctype, filters, fields)
        if not found:
            return None
        if len(found) > 1:
            names = ", ".join(sorted(str(row.get("name")) for row in found))
            raise MalformedRecord(
                Source.FRAPPE,
                f"{doctype}/{names}",
                f"{json.dumps(filters[-1])} is held by more than one document",
            )
        return found[0]

    def _get(self, path: str, **kwargs: Any) -> Any:
        response = self._transport.request("GET", path, replayable=True, **kwargs)
        return _envelope(response, f"GET {path}")["data"]

    def _insert(self, doctype: str, payload: Record) -> str:
        path = f"/api/resource/{doctype}"
        response = self._transport.request("POST", path, replayable=False, json=payload)
        data = _envelope(response, f"POST {path}")["data"]
        name = cast(Record, data).get("name") if isinstance(data, dict) else None
        if not isinstance(name, str):
            raise MalformedRecord(Source.FRAPPE, f"POST {path}", "insert returned no name")
        return name

    def _insert_many(self, documents: list[Record]) -> list[str]:
        answer = self._call("frappe.client.insert_many", docs=documents)
        names = cast(list[Any], answer) if isinstance(answer, list) else []
        if len(names) != len(documents) or not all(isinstance(name, str) for name in names):
            raise MalformedRecord(
                Source.FRAPPE,
                "POST /api/method/frappe.client.insert_many",
                f"expected {len(documents)} names, got {answer!r}",
            )
        return [str(name) for name in names]

    def _call(self, method: str, **arguments: Any) -> Any:
        """A whitelisted method; every one the adapter calls mutates, so none is replayable."""
        path = f"/api/method/{method}"
        response = self._transport.request("POST", path, replayable=False, json=arguments)
        return _envelope(response, f"POST {path}", key="message")["message"]

    def _ensure(self, doctype: str, filters: Filters, payload: Record) -> None:
        if not self._list(doctype, filters, ("name",)):
            self._insert(doctype, payload)

    def _numbers_by_name(self, filters: Filters) -> dict[str, EmployeeId]:
        rows = self._list("Employee", self._company_filter(*filters), ("name", "employee_number"))
        _held_once(rows, "employee_number", "Employee")
        return {
            row["name"]: EmployeeId(row["employee_number"])
            for row in rows
            if row.get("employee_number")
        }

    def _skills_by_name(self, employee_names: list[str]) -> dict[str, tuple[SkillId, ...]]:
        if not employee_names:
            return {}
        rows = self._list(
            "Employee Skill Map",
            [["employee", "in", employee_names]],
            ("employee", "employee_skills.skill"),
        )
        return records.skills_by_employee(rows)

    def _teams_by_department(self) -> dict[str, TeamId]:
        rows = self._list("Department", self._company_filter(), records.DEPARTMENT_FIELDS)
        _held_once(rows, "custom_team_id", "Department")
        return {
            row["name"]: TeamId(row["custom_team_id"]) for row in rows if row.get("custom_team_id")
        }

    def _observed_employee(
        self,
        record: Record,
        number_by_name: dict[str, EmployeeId],
        skills_by_name: dict[str, tuple[SkillId, ...]],
    ) -> Observed[Employee]:
        employee = records.employee_from_record(
            record,
            team_by_department=self._teams_by_department(),
            number_by_name=number_by_name,
            skills_by_name=skills_by_name,
        )
        return Observed(employee, Source.FRAPPE)

    def _department_name(self, team_id: TeamId) -> str:
        row = self._one(
            "Department", self._company_filter(["custom_team_id", "=", team_id]), ("name",)
        )
        if row is None:
            raise LookupError(
                f"team {team_id} is not in Frappe under {self._config.company}; add teams first"
            )
        return str(row["name"])

    def _employee_name(self, employee_id: EmployeeId) -> str:
        row = self._one(
            "Employee", self._company_filter(["employee_number", "=", employee_id]), ("name",)
        )
        if row is None:
            raise LookupError(
                f"employee {employee_id} is not in Frappe under {self._config.company}; "
                "add them first"
            )
        return str(row["name"])


def _held_once(rows: list[Record], key: str, doctype: str) -> None:
    """Every non-empty ``key`` value held by one document across ``rows``, or malformed.

    The enumeration's form of the exactly-one rule: two documents carrying one domain
    id are source corruption, and returning both would put one id on two entities.
    """
    names_by_value: dict[Any, list[str]] = {}
    for row in rows:
        value = row.get(key)
        if value:
            names_by_value.setdefault(value, []).append(str(row.get("name")))
    for value, names in names_by_value.items():
        if len(names) > 1:
            raise MalformedRecord(
                Source.FRAPPE,
                f"{doctype}/{', '.join(sorted(names))}",
                f"{key} {value!r} is held by more than one document",
            )


def _envelope(response: httpx.Response, locator: str, *, key: str = "data") -> dict[str, Any]:
    """Frappe's envelope; ``MalformedRecord`` for a 200 that is not JSON or lacks ``key``."""
    try:
        body: Any = response.json()
    except ValueError as exc:
        raise MalformedRecord(Source.FRAPPE, locator, "response is not JSON") from exc
    if not isinstance(body, dict) or key not in body:
        raise MalformedRecord(Source.FRAPPE, locator, f"response carries no {key!r}")
    return cast(dict[str, Any], body)
