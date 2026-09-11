"""Recording-time support for the Frappe cassettes: the cassette company reset to empty.

A recording writes real documents into the cassette company on the sandbox site, and a
re-recording would write them again — Frappe does not make an employee number unique,
so the second run would leave two documents per person and every select-by-identity
would find both. The reset deletes what a previous run left, in the order the links
allow: the attendance hrms writes when a leave is submitted (it links the application
and blocks its deletion — found at the first re-recording), leave applications
(submitted ones cancelled first), skill maps, employees (later-created first, so a
manager outlives the people who report to them), departments. It runs through the same
transport, inside the cassette, so a replay replays it too and never touches the site.
Test support, not adapter capability: the adapter never deletes.
"""

from __future__ import annotations

import json
from typing import Any

from leaveimpact.adapters.transport import Transport

_PAGE = 100


def _names(
    transport: Transport, doctype: str, filters: list[list[Any]], extra_fields: tuple[str, ...] = ()
) -> list[dict[str, Any]]:
    response = transport.request(
        "GET",
        f"/api/resource/{doctype}",
        replayable=True,
        params={
            "filters": json.dumps(filters),
            "fields": json.dumps(["name", *extra_fields]),
            "limit_page_length": _PAGE,
        },
    )
    rows: list[dict[str, Any]] = response.json()["data"]
    return rows


def _delete(transport: Transport, doctype: str, name: str) -> None:
    transport.request(
        "DELETE", f"/api/resource/{doctype}/{name}", replayable=False, ok=(200, 202, 404)
    )


def _cancel(transport: Transport, doctype: str, name: str) -> None:
    transport.request(
        "POST",
        "/api/method/frappe.client.cancel",
        replayable=False,
        json={"doctype": doctype, "name": name},
    )


def _cancel_and_delete_all(
    transport: Transport, doctype: str, filters: list[list[Any]]
) -> None:
    for row in _names(transport, doctype, filters, ("docstatus",)):
        if row["docstatus"] == 1:
            _cancel(transport, doctype, row["name"])
        _delete(transport, doctype, row["name"])


def reset_company(transport: Transport, company: str) -> None:
    """Delete every people record the cassette company holds; masters and the company stay."""
    employees = sorted(
        (row["name"] for row in _names(transport, "Employee", [["company", "=", company]])),
        reverse=True,
    )
    if employees:
        _cancel_and_delete_all(transport, "Attendance", [["employee", "in", employees]])
    _cancel_and_delete_all(transport, "Leave Application", [["company", "=", company]])
    for name in employees:
        _delete(transport, "Employee Skill Map", name)
        _delete(transport, "Employee", name)
    for department in _names(
        transport, "Department", [["company", "=", company], ["is_group", "=", 0]]
    ):
        _delete(transport, "Department", department["name"])
