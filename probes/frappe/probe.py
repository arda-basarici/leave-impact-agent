"""Frappe HR probe: the three leave doctypes round-trip over REST from outside the box.

Pass criteria (probes/README.md, day 1 "frappe-rest"): Employee, Leave Allocation and
Leave Application created and read back through the public host with an API token; a
documented working path for `leave_approver`. The probe tests the person model the
Jira ruling implies for HR: synthetic employees are `Employee` records only (domain
entities; `reports_to` links Employee → Employee), and the one login identity in play
is a single service `User` that every employee names as `leave_approver` — the
approver is vendor plumbing outside the truth model, like Jira's comment author.
Whether the API principal can submit an *Approved* application it is not the approver
of is the wart under test, recorded either way.

A fresh ERPNext site has no Company until the setup wizard runs, so step 0 completes
it over REST. Every write is find-or-create, so the second run is the no-duplicates
criterion itself; a capture lands on every run, failures included.

Credentials come from the user environment (`LEAVE_IMPACT_FRAPPE_SITE` / `_API_KEY`
/ `_API_SECRET`), read from the Windows User scope when the shell predates them.
Mutable state this principal owns (employee ids, document names) lives in
`%USERPROFILE%\\.config\\leave-impact\\frappe\\manifest.json`, outside the captures.

Run:  uv run --with requests probes/frappe/probe.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests

COMPANY = "Probe Org"
COMPANY_ABBR = "PRB"
HOLIDAY_LIST = "Probe 2026"
LEAVE_TYPE = "Probe Annual Leave"
APPROVER_EMAIL = "probe.approver@leave-impact.invalid"
PEOPLE = {  # employee_number → (first name, reports_to employee_number or None)
    "emp_001": ("Probe Alice", "emp_003"),
    "emp_002": ("Probe Bob", "emp_003"),
    "emp_003": ("Probe Carol", None),
}
ALLOCATION = {"from_date": "2026-01-01", "to_date": "2026-12-31", "new_leaves_allocated": 20}
# (employee_number, from, to, posting_date) — posting_date backdated on purpose: the
# TODO claims leave records take the dates the seed gives; this is the check.
LEAVES = [
    ("emp_001", "2026-09-07", "2026-09-11", "2026-08-01"),
    ("emp_002", "2026-09-10", "2026-09-10", "2026-08-15"),
]

CAPTURE_DIR = Path(__file__).resolve().parents[1] / "captures" / "frappe-rest"
STATE_DIR = Path(os.environ.get("USERPROFILE", "~")).expanduser() / ".config" / "leave-impact" / "frappe"
MANIFEST = STATE_DIR / "manifest.json"


# --- credentials and transport -----------------------------------------------------


def user_env(name: str) -> str:
    """The variable from this process, else from the Windows User scope (a shell born
    before `SetEnvironmentVariable(..., "User")` never sees it)."""
    if value := os.environ.get(name):
        return value
    if sys.platform == "win32":
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            try:
                return str(winreg.QueryValueEx(key, name)[0])
            except FileNotFoundError:
                pass
    sys.exit(f"{name} is not set (user environment variable expected)")


class Frappe:
    """Thin REST client (`/api/resource`, `/api/method`) that records every exchange."""

    def __init__(self) -> None:
        self.base = user_env("LEAVE_IMPACT_FRAPPE_SITE").rstrip("/")
        self.session = requests.Session()
        self.session.headers["Authorization"] = (
            f"token {user_env('LEAVE_IMPACT_FRAPPE_API_KEY')}:{user_env('LEAVE_IMPACT_FRAPPE_API_SECRET')}"
        )
        self.session.headers["Accept"] = "application/json"
        self.log: list[dict[str, Any]] = []

    def call(self, method: str, path: str, *, ok: tuple[int, ...] = (200,), **kw: Any) -> Any:
        response = self.session.request(method, self.base + path, **kw)
        body: Any
        try:
            body = response.json() if response.content else None
        except ValueError:
            body = response.text[:500]
        self.log.append({"method": method, "path": path, "status": response.status_code, "response": body})
        if response.status_code not in ok:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {server_message(body)}")
        return body

    def get_list(self, doctype: str, filters: dict[str, Any], fields: list[str] | None = None) -> list[dict[str, Any]]:
        params = {"filters": json.dumps(filters), "fields": json.dumps(fields or ["name"]), "limit_page_length": 100}
        return self.call("GET", f"/api/resource/{doctype}", params=params)["data"]

    def insert(self, doctype: str, doc: dict[str, Any]) -> dict[str, Any]:
        return self.call("POST", f"/api/resource/{doctype}", json=doc)["data"]

    def method(self, dotted: str, **kwargs: Any) -> Any:
        return self.call("POST", f"/api/method/{dotted}", json=kwargs)["message"]


def server_message(body: Any) -> str:
    """Frappe wraps user-facing errors as a JSON string inside `_server_messages`."""
    if isinstance(body, dict) and body.get("_server_messages"):
        try:
            return "; ".join(json.loads(m).get("message", m) for m in json.loads(body["_server_messages"]))
        except (ValueError, AttributeError):
            pass
    return json.dumps(body)[:400]


# --- the steps, each find-or-create --------------------------------------------------


def ensure_setup(fr: Frappe) -> str:
    """Complete ERPNext's setup wizard if the site is fresh — it creates the Company,
    fiscal year and defaults every HR document needs."""
    done = fr.call("GET", "/api/resource/System Settings/System Settings")["data"].get("setup_complete")
    if done:
        return "already complete"
    fr.method(
        "frappe.desk.page.setup_wizard.setup_wizard.setup_complete",
        args={
            "language": "en",
            "country": "Türkiye",
            "timezone": "Europe/Istanbul",
            "currency": "TRY",
            "company_name": COMPANY,
            "company_abbr": COMPANY_ABBR,
            "chart_of_accounts": "Standard",
            "fy_start_date": "2026-01-01",
            "fy_end_date": "2026-12-31",
            "full_name": "Administrator",
            "email": "admin@leave-impact.invalid",
        },
    )
    return "completed now"


def ensure_holiday_list(fr: Frappe) -> str:
    if not fr.get_list("Holiday List", {"name": HOLIDAY_LIST}):
        fr.insert(
            "Holiday List",
            {
                "holiday_list_name": HOLIDAY_LIST,
                "from_date": "2026-01-01",
                "to_date": "2026-12-31",
                "holidays": [
                    {"holiday_date": "2026-08-30", "description": "Victory Day"},
                    {"holiday_date": "2026-10-29", "description": "Republic Day"},
                ],
            },
        )
    fr.method("frappe.client.set_value", doctype="Company", name=COMPANY, fieldname="default_holiday_list", value=HOLIDAY_LIST)
    # hrms 16 resolves holiday lists through a submitted Holiday List Assignment
    # (company- or employee-level, from a date); `Company.default_holiday_list` and
    # `Employee.holiday_list` are set above but ignored — run 2 proved it.
    if not fr.get_list("Holiday List Assignment", {"applicable_for": "Company", "assigned_to": COMPANY, "docstatus": 1}):
        fr.insert(
            "Holiday List Assignment",
            {"applicable_for": "Company", "assigned_to": COMPANY, "holiday_list": HOLIDAY_LIST, "from_date": "2026-01-01", "docstatus": 1},
        )
    return HOLIDAY_LIST


def ensure_leave_type(fr: Frappe) -> str:
    if not fr.get_list("Leave Type", {"name": LEAVE_TYPE}):
        fr.insert("Leave Type", {"leave_type_name": LEAVE_TYPE, "max_continuous_days_allowed": 30})
    return LEAVE_TYPE


def ensure_approver(fr: Frappe) -> str:
    """One service login that every employee names as approver. `send_welcome_email: 0`
    — the address is synthetic; `Leave Approver` role up front, though hrms grants it
    itself when the field is set (employee_master.update_approver_role)."""
    if not fr.get_list("User", {"name": APPROVER_EMAIL}):
        fr.insert(
            "User",
            {
                "email": APPROVER_EMAIL,
                "first_name": "Probe Approver",
                "send_welcome_email": 0,
                "user_type": "System User",
                "roles": [{"role": "Leave Approver"}, {"role": "HR User"}],
            },
        )
    return APPROVER_EMAIL


def ensure_employees(fr: Frappe, manifest: dict[str, Any]) -> dict[str, str]:
    """Employees keyed by `employee_number` (the generator's id); Frappe's own `name`
    (HR-EMP-0000n) is vendor identity and goes to the manifest. `reports_to` is set in a
    second pass because it links to Employees that may not exist yet."""
    names: dict[str, str] = manifest.setdefault("employees", {})
    for number, (full_name, _) in PEOPLE.items():
        found = fr.get_list("Employee", {"employee_number": number})
        if found:
            names[number] = found[0]["name"]
            continue
        created = fr.insert(
            "Employee",
            {
                "employee_number": number,
                "first_name": full_name.split()[0],
                "last_name": full_name.split()[1],
                "gender": "Other",
                "date_of_birth": "1990-05-05",
                "date_of_joining": "2024-01-15",
                "company": COMPANY,
                "status": "Active",
                "holiday_list": HOLIDAY_LIST,
                "leave_approver": APPROVER_EMAIL,
            },
        )
        names[number] = created["name"]
    for number, (_, manager) in PEOPLE.items():
        if manager:
            fr.method("frappe.client.set_value", doctype="Employee", name=names[number], fieldname="reports_to", value=names[manager])
    return names


def ensure_allocations(fr: Frappe, names: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for number, name in names.items():
        found = fr.get_list("Leave Allocation", {"employee": name, "leave_type": LEAVE_TYPE, "docstatus": 1})
        if found:
            out[number] = found[0]["name"]
            continue
        created = fr.insert("Leave Allocation", {"employee": name, "leave_type": LEAVE_TYPE, "docstatus": 1, **ALLOCATION})
        out[number] = created["name"]
    return out


def ensure_leaves(fr: Frappe, names: dict[str, str]) -> list[dict[str, Any]]:
    """Approved, submitted applications. The submitting principal (Administrator's
    token) is not the approver — whether hrms lets that through is the wart finding."""
    out = []
    for number, from_date, to_date, posting in LEAVES:
        found = fr.get_list("Leave Application", {"employee": names[number], "from_date": from_date, "docstatus": 1}, ["name", "status", "posting_date", "leave_approver"])
        if found:
            out.append({"employee": number, "existing": True, **found[0]})
            continue
        try:
            created = fr.insert(
                "Leave Application",
                {
                    "employee": names[number],
                    "leave_type": LEAVE_TYPE,
                    "from_date": from_date,
                    "to_date": to_date,
                    "posting_date": posting,
                    "status": "Approved",
                    "leave_approver": APPROVER_EMAIL,
                    "description": "probe",
                    "docstatus": 1,
                },
            )
            out.append({"employee": number, "existing": False, "name": created["name"], "status": created["status"], "posting_date": created["posting_date"], "leave_approver": created["leave_approver"]})
        except RuntimeError as exc:
            out.append({"employee": number, "existing": False, "error": str(exc)})
    return out


def read_back(fr: Frappe, names: dict[str, str]) -> dict[str, Any]:
    """What the agent's adapter would ask: who reports to whom, what leave stands, the
    balance that remains — all through `/api/resource` and one whitelisted method."""
    employees = fr.get_list("Employee", {"employee_number": ["in", list(names)]}, ["employee_number", "employee_name", "reports_to", "leave_approver", "holiday_list", "status"])
    leaves = fr.get_list("Leave Application", {"employee": ["in", list(names.values())], "docstatus": 1}, ["name", "employee", "from_date", "to_date", "total_leave_days", "status", "posting_date"])
    balances = {
        number: fr.method("hrms.hr.doctype.leave_application.leave_application.get_leave_balance_on", employee=name, date="2026-09-30", leave_type=LEAVE_TYPE)
        for number, name in names.items()
    }
    return {"employees": employees, "leave_applications": leaves, "balance_on_2026-09-30": balances}


def redact(text: str, fr: Frappe) -> str:
    """The site host stays out of the public repo; synthetic names and document ids are
    evidence. The API key never appears in a response body, but guard anyway."""
    text = text.replace(fr.base, "https://<site>")
    return re.sub(r'"api_key": "[^"]+"', '"api_key": "<api_key>"', text)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    run_no = len(list(CAPTURE_DIR.glob("run-*.json"))) + 1
    capture: dict[str, Any] = {"run": run_no, "outcome": "failed"}
    fr = Frappe()
    try:
        capture["setup"] = ensure_setup(fr)
        capture["holiday_list"] = ensure_holiday_list(fr)
        capture["leave_type"] = ensure_leave_type(fr)
        capture["approver"] = ensure_approver(fr)
        names = ensure_employees(fr, manifest)
        capture["employees"] = names
        capture["allocations"] = ensure_allocations(fr, names)
        capture["leave_applications"] = ensure_leaves(fr, names)
        capture["read_back"] = read_back(fr, names)
        capture["outcome"] = "ok"
    except Exception as exc:  # the failure is the finding — capture, then re-raise
        capture["error"] = str(exc)
        raise
    finally:
        capture["exchanges"] = fr.log
        MANIFEST.write_text(json.dumps(manifest, indent=2))
        path = CAPTURE_DIR / f"run-{run_no:02d}.json"
        path.write_text(redact(json.dumps(capture, indent=2, ensure_ascii=False), fr), encoding="utf-8")
        print(json.dumps({k: v for k, v in capture.items() if k != "exchanges"}, indent=2, ensure_ascii=False))
        print(f"capture: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
