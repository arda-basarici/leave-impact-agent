"""The Frappe adapter against the site, recorded once and replayed on every push.

One scenario end to end: the cassette company reset, the site prepared, two teams and
three people written (a manager, a contractor with no skill record, a senior with two
skills), two leaves (approved, requested), then everything read back through the
reader's five questions — including the identities the site does not hold, which are
``None`` and not a fault. The claims are the port's: what the writer added, the reader
returns as the same entity; the blank skill record stays blank; a span selects by
overlap and any status; a select-by-identity outside the company is ``None``.

Recording (``just test-record``) needs the site and its credential in the
environment; replay needs neither and the cassette host is a placeholder. The
company is the cassette scope, so the world that lands in step 10 never reads these.
"""

from __future__ import annotations

import os
from datetime import date

import pytest

from leaveimpact.adapters.frappe import FrappeAdapter, FrappeConfig, FrappeCredential
from leaveimpact.adapters.transport import Transport
from leaveimpact.core.entities import Employee, Leave, Team
from leaveimpact.core.enums import EmploymentType, Grade, LeaveKind, LeaveStatus, Source
from leaveimpact.core.ids import employee_id, leave_id, skill_id, team_id
from leaveimpact.core.worldtime import DateSpan
from tests.integration.frappe_support import reset_company
from tests.recording import FRAPPE

pytestmark = [pytest.mark.integration, pytest.mark.vcr]

CONFIG = FrappeConfig("Cassette Org", "CAS")

PLATFORM = Team(team_id(901), "Platform")
DATA = Team(team_id(902), "Data")
SEDA = Employee(
    employee_id(901),
    "Seda Aksoy",
    PLATFORM.id,
    None,
    (skill_id("kafka"),),
    "Istanbul",
    "TR",
    "Europe/Istanbul",
    Grade.LEAD,
    EmploymentType.EMPLOYEE,
)
BARAN = Employee(
    employee_id(902),
    "Baran Demir",
    DATA.id,
    SEDA.id,
    None,
    "Berlin",
    "DE",
    "Europe/Berlin",
    Grade.MID,
    EmploymentType.CONTRACTOR,
)
DENIZ = Employee(
    employee_id(903),
    "Deniz Yılmaz",
    PLATFORM.id,
    SEDA.id,
    (skill_id("kafka"), skill_id("sql")),
    "Istanbul",
    "TR",
    "Europe/Istanbul",
    Grade.SENIOR,
    EmploymentType.EMPLOYEE,
)
APPROVED = Leave(
    leave_id(901),
    DENIZ.id,
    date(2026, 9, 14),
    date(2026, 9, 18),
    LeaveKind.ANNUAL,
    LeaveStatus.APPROVED,
)
REQUESTED = Leave(
    leave_id(902),
    BARAN.id,
    date(2026, 9, 17),
    date(2026, 9, 17),
    LeaveKind.SICK,
    LeaveStatus.REQUESTED,
)


def credential() -> FrappeCredential:
    if FRAPPE.recording:
        return FrappeCredential(
            os.environ["LEAVE_IMPACT_FRAPPE_W1_API_KEY"],
            os.environ["LEAVE_IMPACT_FRAPPE_W1_API_SECRET"],
        )
    return FrappeCredential("replay", "replay")


def test_people_written_are_read_back() -> None:
    cred = credential()
    with Transport(
        base_url=FRAPPE.base_url,
        source=Source.FRAPPE,
        headers={"Authorization": cred.authorization, "Accept": "application/json"},
        sleep=lambda _: None,
    ) as raw:
        reset_company(raw, CONFIG.company)

    adapter = FrappeAdapter(
        base_url=FRAPPE.base_url, credential=cred, config=CONFIG, sleep=lambda _: None
    )
    adapter.ensure_site_schema()
    adapter.ensure_company()
    adapter.ensure_skills([skill_id("kafka"), skill_id("sql")])

    locators = [adapter.add_team(PLATFORM), adapter.add_team(DATA)]
    locators += [
        adapter.add_employee(SEDA),
        adapter.add_employee(BARAN),
        adapter.add_employee(DENIZ),
    ]
    locators += [adapter.add_leave(APPROVED), adapter.add_leave(REQUESTED)]
    assert all(locators) and len(set(locators)) == len(locators)

    observed = adapter.employees()
    assert all(item.source is Source.FRAPPE for item in observed)
    assert {item.value for item in observed} == {SEDA, BARAN, DENIZ}

    deniz = adapter.employee(DENIZ.id)
    assert deniz is not None and deniz.value == DENIZ
    baran = adapter.employee(BARAN.id)
    assert baran is not None and baran.value.skills is None, "no skill map is the blank record"
    assert adapter.employee(employee_id(999)) is None

    platform = adapter.team(PLATFORM.id)
    assert platform is not None and platform.value == PLATFORM
    assert adapter.team(team_id(999)) is None

    approved = adapter.leave(APPROVED.id)
    assert approved is not None and approved.value == APPROVED
    assert adapter.leave(leave_id(999)) is None

    week = DateSpan(date(2026, 9, 14), date(2026, 9, 18))
    assert {item.value for item in adapter.leaves_within(week)} == {APPROVED, REQUESTED}
    assert {
        item.value for item in adapter.leaves_within(DateSpan(date(2026, 9, 17), date(2026, 9, 17)))
    } == {APPROVED, REQUESTED}
    assert adapter.leaves_within(DateSpan(date(2026, 9, 19), date(2026, 9, 25))) == ()
    adapter.close()
