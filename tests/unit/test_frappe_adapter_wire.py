"""The Frappe adapter's wire behaviour over a scripted transport: what it sends, what it refuses.

The claims the cassette cannot make cheaply: an employee with skills is exactly one
request, both documents in it, and a fault in that request leaves the adapter with
nothing half-written to report; a domain id held by two documents is malformed on a
select and on a link resolution alike, never a silent choice; a successful response
that is not Frappe's envelope — not JSON, no data, an insert with no name — is
malformed with the request as locator, and never leaks a decoding exception.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import date
from typing import Any

import httpx
import pytest

from leaveimpact.adapters.frappe import FrappeAdapter, FrappeConfig, FrappeCredential
from leaveimpact.core.entities import Employee, Leave, Team
from leaveimpact.core.enums import EmploymentType, Grade, LeaveKind, LeaveStatus
from leaveimpact.core.ids import employee_id, leave_id, skill_id, team_id
from leaveimpact.core.ports.errors import MalformedRecord, SourceUnreachable
from leaveimpact.core.worldtime import DateSpan

Outcome = httpx.Response | Exception


class Scripted:
    def __init__(self, *outcomes: Outcome) -> None:
        self.seen: list[httpx.Request] = []
        self._outcomes: Iterator[Outcome] = iter(outcomes)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        outcome = next(self._outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def adapter(script: Scripted) -> FrappeAdapter:
    return FrappeAdapter(
        base_url="https://frappe.invalid",
        credential=FrappeCredential("k", "s"),
        config=FrappeConfig("Cassette Org", "CAS"),
        sleep=lambda _: None,
        httpx_transport=httpx.MockTransport(script.handler),
    )


def data(payload: Any) -> httpx.Response:
    return httpx.Response(200, json={"data": payload})


def message(payload: Any) -> httpx.Response:
    return httpx.Response(200, json={"message": payload})


DENIZ = Employee(
    employee_id(4),
    "Deniz Yılmaz",
    team_id(3),
    employee_id(1),
    (skill_id("kafka"),),
    "Istanbul",
    "TR",
    "Europe/Istanbul",
    Grade.SENIOR,
    EmploymentType.EMPLOYEE,
)


def test_an_employee_with_skills_is_one_request_carrying_both_documents() -> None:
    script = Scripted(
        data([{"name": "Platform - CAS"}]),  # the team resolves
        data([{"name": "emp_001"}]),  # the manager resolves
        message(["emp_004", "emp_004"]),  # insert_many answers with both names
    )
    assert adapter(script).add_employee(DENIZ) == "emp_004"
    batch = script.seen[-1]
    assert batch.url.path == "/api/method/frappe.client.insert_many"
    docs = json.loads(batch.content)["docs"]
    assert [doc["doctype"] for doc in docs] == ["Employee", "Employee Skill Map"]
    assert docs[0]["employee_number"] == "emp_004" and docs[0]["reports_to"] == "emp_001"
    assert docs[1]["employee"] == "emp_004"
    assert [row["skill"] for row in docs[1]["employee_skills"]] == ["kafka"]


def test_an_employee_without_a_skill_record_is_one_document_in_the_batch() -> None:
    top = Employee(
        employee_id(1),
        "Seda Aksoy",
        team_id(3),
        None,
        None,
        "Istanbul",
        "TR",
        "Europe/Istanbul",
        Grade.LEAD,
        EmploymentType.EMPLOYEE,
    )
    script = Scripted(data([{"name": "Platform - CAS"}]), message(["emp_001"]))
    assert adapter(script).add_employee(top) == "emp_001"
    docs = json.loads(script.seen[-1].content)["docs"]
    assert [doc["doctype"] for doc in docs] == ["Employee"]
    assert "reports_to" not in docs[0]


def test_a_fault_in_the_batch_is_one_unknown_outcome_and_no_second_write() -> None:
    script = Scripted(
        data([{"name": "Platform - CAS"}]),
        data([{"name": "emp_001"}]),
        httpx.ReadTimeout("lost"),
        message(["emp_004", "emp_004"]),
    )
    with pytest.raises(SourceUnreachable) as caught:
        adapter(script).add_employee(DENIZ)
    assert "outcome unknown" in caught.value.reason
    assert len(script.seen) == 3, "the batch is sent once; there is no second document to lose"


def test_a_batch_answering_the_wrong_number_of_names_is_malformed() -> None:
    script = Scripted(
        data([{"name": "Platform - CAS"}]), data([{"name": "emp_001"}]), message(["emp_004"])
    )
    with pytest.raises(MalformedRecord) as caught:
        adapter(script).add_employee(DENIZ)
    assert caught.value.locator == "POST /api/method/frappe.client.insert_many"


def _select_team(a: FrappeAdapter) -> object:
    return a.team(team_id(3))


def _select_leave(a: FrappeAdapter) -> object:
    return a.leave(leave_id(7))


def _select_employee(a: FrappeAdapter) -> object:
    return a.employee(employee_id(4))


@pytest.mark.parametrize("call", [_select_team, _select_leave, _select_employee])
def test_a_domain_id_held_by_two_documents_is_malformed_on_select(
    call: Callable[[FrappeAdapter], object],
) -> None:
    script = Scripted(data([{"name": "A"}, {"name": "B"}]))
    with pytest.raises(MalformedRecord) as caught:
        call(adapter(script))
    assert "held by more than one document" in caught.value.reason
    assert caught.value.locator.endswith("/A, B")


def test_a_domain_id_held_by_two_documents_is_malformed_on_enumeration() -> None:
    twice = data([{"name": "emp_004", "employee_number": "emp_004"},
                  {"name": "emp_004-1", "employee_number": "emp_004"}])
    with pytest.raises(MalformedRecord) as caught:
        adapter(Scripted(twice)).employees()
    assert caught.value.locator == "Employee/emp_004, emp_004-1"
    assert caught.value.reason == "employee_number 'emp_004' is held by more than one document"
    leaves = data([{"name": "HR-LAP-1", "custom_leave_id": "leave_001", "employee": "emp_004"},
                   {"name": "HR-LAP-2", "custom_leave_id": "leave_001", "employee": "emp_004"}])
    with pytest.raises(MalformedRecord, match="custom_leave_id 'leave_001' is held by more"):
        adapter(Scripted(leaves)).leaves_within(DateSpan(date(2026, 9, 14), date(2026, 9, 18)))


def test_a_domain_id_held_by_two_documents_is_malformed_on_link_resolution() -> None:
    script = Scripted(data([{"name": "Platform - CAS"}, {"name": "Platform 2 - CAS"}]))
    with pytest.raises(MalformedRecord):
        adapter(script).add_employee(DENIZ)
    assert len(script.seen) == 1, "nothing is written when a link is ambiguous"


def test_a_missing_link_target_is_the_callers_ordering_bug() -> None:
    with pytest.raises(LookupError, match="add teams first"):
        adapter(Scripted(data([]))).add_employee(DENIZ)
    leave = Leave(
        leave_id(7),
        employee_id(4),
        date(2026, 9, 14),
        date(2026, 9, 18),
        LeaveKind.ANNUAL,
        LeaveStatus.APPROVED,
    )
    with pytest.raises(LookupError, match="add them first"):
        adapter(Scripted(data([]))).add_leave(leave)


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx.Response(200, text="<html>maintenance</html>"), "response is not JSON"),
        (httpx.Response(200, json={"message": "ok"}), "response carries no 'data'"),
        (httpx.Response(200, json={"data": {"rows": []}}), "data is not a list"),
        (httpx.Response(200, json={"data": [None]}), "a document in data is not an object"),
    ],
)
def test_a_successful_response_outside_the_envelope_is_malformed(
    response: httpx.Response, reason: str
) -> None:
    with pytest.raises(MalformedRecord) as caught:
        adapter(Scripted(response)).team(team_id(3))
    assert caught.value.locator == "GET /api/resource/Department"
    assert caught.value.reason == reason


def test_an_insert_answering_without_a_name_is_malformed() -> None:
    script = Scripted(data({"department_name": "Platform"}))
    with pytest.raises(MalformedRecord) as caught:
        adapter(script).add_team(Team(team_id(3), "Platform"))
    assert caught.value.locator == "POST /api/resource/Department"
    assert caught.value.reason == "insert returned no name"


# --- The employee-number scope query --------------------------------------------------------


def test_held_employee_numbers_looks_past_the_company_then_returns_what_it_holds() -> None:
    script = Scripted(data([]), data([{"name": "emp_004", "employee_number": "emp_004"}]))
    held = adapter(script).held_employee_numbers([employee_id(4), employee_id(5)])
    assert held == {employee_id(4)}
    foreign, own = script.seen
    assert json.loads(foreign.url.params["filters"]) == [
        ["employee_number", "in", ["emp_004", "emp_005"]],
        ["company", "!=", "Cassette Org"],
    ]
    assert json.loads(own.url.params["filters"]) == [["company", "=", "Cassette Org"]]


def test_a_world_number_held_by_another_company_refuses_before_the_company_is_read() -> None:
    foreign = data([{"name": "emp_004", "employee_number": "emp_004", "company": "Other Co"}])
    script = Scripted(foreign)
    with pytest.raises(MalformedRecord) as caught:
        adapter(script).held_employee_numbers([employee_id(4)])
    assert caught.value.locator == "Employee/emp_004"
    assert caught.value.reason == (
        "world employee numbers held by another company on the site: [\"emp_004 in 'Other Co'\"]"
    )
    assert len(script.seen) == 1


def test_a_number_held_twice_in_the_company_is_malformed_on_the_scope_query() -> None:
    twice = data([{"name": "emp_004", "employee_number": "emp_004"},
                  {"name": "emp_004-1", "employee_number": "emp_004"}])
    with pytest.raises(MalformedRecord, match="held by more than one document"):
        adapter(Scripted(data([]), twice)).held_employee_numbers([employee_id(4)])
