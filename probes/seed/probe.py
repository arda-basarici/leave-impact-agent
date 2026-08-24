"""Seed spike: one command projects one org spec into all three systems, idempotently.

Pass criteria (probes/README.md, day 1 "seed-spike", extended 2026-08-24 before this
first run): (a) the same org — 5 people, 1 project, a week of meetings, 2 leaves —
visible in Frappe, Jira and Calendar, keyed by the same employee ids; (b) a second run
creates nothing anywhere (the manifest remembers what this principal owns); (c) world
dates live in `Opened On` / `Resolved On` date custom fields created and set over REST
on Jira Free, and JQL date arithmetic on them answers correctly; (d) stable-now —
`answer(now)` evaluated at two instants inside the declared stable interval returns
identical results.

The shape under test is the M1 generator's seam, not its code: spec → three independent
projections → manifest. The systems never see each other; consistency is by
construction (every projection reads the same spec, keyed by the same employee ids).
Fresh containers per the 2026-08-24 ruling: Frappe site `hr-w1` (created for this
spike), Jira project `W1` (created here over REST — if Free refuses the company-managed
template the failure is the finding and the fallback is one UI creation + rerun),
world-prefixed secondary calendars. Frappe is seeded as Administrator on purpose: the
generator is the world's god, and the approver-bypass wart is exactly what lets it
plant backdated approved leaves (the role-scoped principal is the AGENT's runtime
concern, not the seed's).

Time is world state (ruling 3): the spec declares `now` candidates and a stable
interval, and guarantees no world date falls inside the interval — that is what makes
the answers stable. `answer(now)` derives its week from `now` and asks each system a
question the investigator will ask: who is on leave in this week (Frappe), which issues
are open as of `now` per person (Jira, via JQL on the world date fields), which blocks
are busy (Calendar freeBusy).

Credentials come from the user environment (`LEAVE_IMPACT_FRAPPE_W1_SITE` / `_API_KEY`
/ `_API_SECRET`, `LEAVE_IMPACT_JIRA_SITE` / `_EMAIL` / `_TOKEN`, and the OAuth bundle
in `LEAVE_IMPACT_GOOGLE_DIR`), read from the Windows User scope when the shell predates
them. Mutable state this principal owns lives in
`%USERPROFILE%\\.config\\leave-impact\\seed\\manifest.json`, outside the captures.
A capture lands on every run under a sequence-stamped name, failures included.

Run:  uv run --with requests --with google-api-python-client --with google-auth-oauthlib \
          probes/seed/probe.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- the world spec ------------------------------------------------------------------

WORLD = "w1"
TZ = "Europe/Istanbul"

PEOPLE = {  # employee id → (full name, reports_to id or None)
    "emp_101": ("Seda Aksoy", None),  # the manager
    "emp_102": ("Baran Demir", "emp_101"),
    "emp_103": ("Ceren Kaya", "emp_101"),
    "emp_104": ("Deniz Yılmaz", "emp_101"),
    "emp_105": ("Emre Şahin", "emp_101"),
}

# Frappe (HRIS) slice.
COMPANY = "Seed Org W1"
COMPANY_ABBR = "SW1"
HOLIDAY_LIST = "W1 2026"
LEAVE_TYPE = "W1 Annual Leave"
APPROVER_EMAIL = "w1.approver@leave-impact.invalid"
ALLOCATION = {"from_date": "2026-01-01", "to_date": "2026-12-31", "new_leaves_allocated": 20}
LEAVES = [  # (employee id, from, to, posting_date — backdated on purpose)
    ("emp_102", "2026-09-07", "2026-09-11", "2026-08-10"),
    ("emp_104", "2026-09-10", "2026-09-10", "2026-08-20"),
]

# Jira slice. World dates are the custom fields, never Jira's own timestamps
# (CSV import backdates `created` only — demoted to cosmetic, DESIGN 2026-08-23).
PROJECT_KEY = "W1"
PROJECT_NAME = "Seed World w1"
OWNER_FIELD = "Synthetic Owner"  # site-global select, shared across worlds; options append
DATE_FIELDS = ("Opened On", "Resolved On")
ISSUES = [  # (slug, owner, opened_on, resolved_on or None) — all dates OUTSIDE the
    # stable interval below; that guarantee is what stable-now rests on.
    ("payment-retry-loop", "emp_102", "2026-08-12", None),
    ("billing-migration", "emp_102", "2026-07-01", None),
    ("vendor-timeout", "emp_103", "2026-08-20", None),
    ("q3-report-pipeline", "emp_104", "2026-08-25", None),
    ("onboarding-revamp", "emp_105", "2026-09-01", None),
    ("rotate-api-keys", "emp_102", "2026-06-10", "2026-07-02"),
    ("intake-form-bug", "emp_103", "2026-08-01", "2026-08-15"),
    ("licence-audit", "emp_101", "2026-05-05", "2026-09-04"),
]

# Calendar slice: the leave week itself, so the world holds a real overlap (Baran in
# meetings while on leave — the embryo of an impact question, planted, not scrubbed).
WEEK_START = datetime(2026, 9, 7, tzinfo=ZoneInfo(TZ))  # a Monday
MEETINGS = [  # (key, participant ids, day offset, hour, minute, duration minutes)
    ("standup", list(PEOPLE), 0, 9, 0, 15),
    ("standup", list(PEOPLE), 2, 9, 0, 15),
    ("standup", list(PEOPLE), 4, 9, 0, 15),
    ("sprint-planning", list(PEOPLE), 0, 10, 0, 60),
    ("customer-review", ["emp_102", "emp_104"], 1, 13, 0, 90),
    ("vendor-call", ["emp_103"], 1, 14, 0, 60),
    ("architecture-review", ["emp_103", "emp_105"], 2, 15, 0, 60),
    ("one-on-one", ["emp_101", "emp_105"], 3, 11, 0, 30),
]

# Time as world state: two `now` instants inside the declared stable interval — the
# spec plants no world date inside it, so answer(now1) must equal answer(now2).
STABLE_INTERVAL = ("2026-09-07T00:00+03:00", "2026-09-11T23:59+03:00")
NOW_1 = datetime(2026, 9, 8, 9, 30, tzinfo=ZoneInfo(TZ))
NOW_2 = datetime(2026, 9, 10, 17, 0, tzinfo=ZoneInfo(TZ))

CAPTURE_DIR = Path(__file__).resolve().parents[1] / "captures" / "seed-spike"
STATE_DIR = Path(os.environ.get("USERPROFILE", "~")).expanduser() / ".config" / "leave-impact" / "seed"
MANIFEST = STATE_DIR / "manifest.json"

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.app.created",
    "https://www.googleapis.com/auth/calendar.freebusy",
]


def full_name(emp_id: str) -> str:
    return PEOPLE[emp_id][0]


def option_value(emp_id: str) -> str:
    return f"{emp_id} — {full_name(emp_id)}"


# --- credentials and transport -------------------------------------------------------


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


class Rest:
    """Thin recording HTTP client both REST legs share; a non-ok status raises with the
    server's own message — the failure is the finding."""

    def __init__(self, base: str) -> None:
        self.base = base
        self.session = requests.Session()
        self.session.headers["Accept"] = "application/json"
        self.log: list[dict[str, Any]] = []

    def call(self, method: str, path: str, *, ok: tuple[int, ...] = (200, 201, 204), **kw: Any) -> Any:
        # Fail fast on a stalled connection, and retry CONNECTION-level faults only
        # (never HTTP errors): runs 2-4 died on intermittent edge resets that never
        # reached the origin's nginx. Safe because every write is find-or-create.
        kw.setdefault("timeout", (10, 60))
        for attempt in (1, 2, 3):
            try:
                response = self.session.request(method, self.base + path, **kw)
                break
            except (requests.ConnectionError, requests.Timeout) as exc:
                self.log.append({"method": method, "path": path, "transport_fault": f"attempt {attempt}: {type(exc).__name__}"})
                if attempt == 3:
                    raise
                time.sleep(2 * attempt)
        body: Any
        try:
            body = response.json() if response.content else None
        except ValueError:
            body = response.text[:500]
        self.log.append({"method": method, "path": path, "status": response.status_code, "response": body})
        if response.status_code not in ok:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {json.dumps(body, ensure_ascii=False)[:400]}")
        return body


class Frappe(Rest):
    def __init__(self) -> None:
        super().__init__(user_env("LEAVE_IMPACT_FRAPPE_W1_SITE").rstrip("/"))
        self.session.headers["Authorization"] = (
            f"token {user_env('LEAVE_IMPACT_FRAPPE_W1_API_KEY')}:{user_env('LEAVE_IMPACT_FRAPPE_W1_API_SECRET')}"
        )

    def get_list(self, doctype: str, filters: dict[str, Any], fields: list[str] | None = None) -> list[dict[str, Any]]:
        params = {"filters": json.dumps(filters), "fields": json.dumps(fields or ["name"]), "limit_page_length": 100}
        return self.call("GET", f"/api/resource/{doctype}", params=params)["data"]

    def insert(self, doctype: str, doc: dict[str, Any]) -> dict[str, Any]:
        return self.call("POST", f"/api/resource/{doctype}", json=doc)["data"]

    def method(self, dotted: str, **kwargs: Any) -> Any:
        return self.call("POST", f"/api/method/{dotted}", json=kwargs)["message"]


class Jira(Rest):
    def __init__(self) -> None:
        super().__init__(user_env("LEAVE_IMPACT_JIRA_SITE").rstrip("/") + "/rest/api/3")
        self.session.auth = (user_env("LEAVE_IMPACT_JIRA_EMAIL"), user_env("LEAVE_IMPACT_JIRA_TOKEN"))

    def search(self, jql: str, fields: list[str]) -> list[dict[str, Any]]:
        page = self.call("POST", "/search/jql", json={"jql": jql, "fields": fields, "maxResults": 100})
        return page["issues"]


def google_service() -> Any:
    secret_dir = Path(user_env("LEAVE_IMPACT_GOOGLE_DIR"))
    token_path = secret_dir / "token-app-created+freebusy.json"
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GOOGLE_SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
    if creds is None or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(secret_dir / "client_secret.json"), GOOGLE_SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("calendar", "v3", credentials=creds)


# --- Frappe projection: people, allocations, leaves ----------------------------------


def seed_frappe(fr: Frappe, manifest: dict[str, Any], created: list[str]) -> dict[str, Any]:
    state = manifest.setdefault("frappe", {})

    if not fr.call("GET", "/api/resource/System Settings/System Settings")["data"].get("setup_complete"):
        fr.method(
            "frappe.desk.page.setup_wizard.setup_wizard.setup_complete",
            args={
                "language": "en", "country": "Türkiye", "timezone": TZ, "currency": "TRY",
                "company_name": COMPANY, "company_abbr": COMPANY_ABBR, "chart_of_accounts": "Standard",
                "fy_start_date": "2026-01-01", "fy_end_date": "2026-12-31",
                "full_name": "Administrator", "email": "admin@leave-impact.invalid",
            },
        )
        created.append("frappe:setup-wizard")

    if not fr.get_list("Holiday List", {"name": HOLIDAY_LIST}):
        fr.insert("Holiday List", {
            "holiday_list_name": HOLIDAY_LIST, "from_date": "2026-01-01", "to_date": "2026-12-31",
            "holidays": [{"holiday_date": "2026-08-30", "description": "Victory Day"},
                         {"holiday_date": "2026-10-29", "description": "Republic Day"}],
        })
        created.append("frappe:holiday-list")
    fr.method("frappe.client.set_value", doctype="Company", name=COMPANY,
              fieldname="default_holiday_list", value=HOLIDAY_LIST)
    # hrms 16 resolves holiday lists only through a SUBMITTED assignment (frappe-rest
    # probe run 2 proved the legacy fields are silently ignored).
    if not fr.get_list("Holiday List Assignment", {"applicable_for": "Company", "assigned_to": COMPANY, "docstatus": 1}):
        fr.insert("Holiday List Assignment", {
            "applicable_for": "Company", "assigned_to": COMPANY, "holiday_list": HOLIDAY_LIST,
            "from_date": "2026-01-01", "docstatus": 1,
        })
        created.append("frappe:holiday-assignment")

    if not fr.get_list("Leave Type", {"name": LEAVE_TYPE}):
        fr.insert("Leave Type", {"leave_type_name": LEAVE_TYPE, "max_continuous_days_allowed": 30})
        created.append("frappe:leave-type")

    if not fr.get_list("User", {"name": APPROVER_EMAIL}):
        fr.insert("User", {
            "email": APPROVER_EMAIL, "first_name": "W1 Approver", "send_welcome_email": 0,
            "user_type": "System User", "roles": [{"role": "Leave Approver"}, {"role": "HR User"}],
        })
        created.append("frappe:approver")

    # Employees keyed by employee_number (the world id); Frappe's HR-EMP-#### name is
    # vendor identity and goes to the manifest. reports_to in a second pass (links).
    names: dict[str, str] = state.setdefault("employees", {})
    for emp_id, (person, _) in PEOPLE.items():
        found = fr.get_list("Employee", {"employee_number": emp_id})
        if found:
            names[emp_id] = found[0]["name"]
            continue
        first, last = person.rsplit(" ", 1)
        doc = fr.insert("Employee", {
            "employee_number": emp_id, "first_name": first, "last_name": last,
            "gender": "Other", "date_of_birth": "1992-03-03", "date_of_joining": "2024-02-01",
            "company": COMPANY, "status": "Active", "holiday_list": HOLIDAY_LIST,
            "leave_approver": APPROVER_EMAIL,
        })
        names[emp_id] = doc["name"]
        created.append(f"frappe:employee:{emp_id}")
    for emp_id, (_, manager) in PEOPLE.items():
        if manager:
            fr.method("frappe.client.set_value", doctype="Employee", name=names[emp_id],
                      fieldname="reports_to", value=names[manager])

    for emp_id, name in names.items():
        if not fr.get_list("Leave Allocation", {"employee": name, "leave_type": LEAVE_TYPE, "docstatus": 1}):
            fr.insert("Leave Allocation", {"employee": name, "leave_type": LEAVE_TYPE, "docstatus": 1, **ALLOCATION})
            created.append(f"frappe:allocation:{emp_id}")

    for emp_id, from_date, to_date, posting in LEAVES:
        if fr.get_list("Leave Application", {"employee": names[emp_id], "from_date": from_date, "docstatus": 1}):
            continue
        fr.insert("Leave Application", {
            "employee": names[emp_id], "leave_type": LEAVE_TYPE, "from_date": from_date,
            "to_date": to_date, "posting_date": posting, "status": "Approved",
            "leave_approver": APPROVER_EMAIL, "description": f"seed {WORLD}", "docstatus": 1,
        })
        created.append(f"frappe:leave:{emp_id}:{from_date}")

    return {"employees": names}


# --- Jira projection: project, fields, issues ----------------------------------------


def seed_jira(jira: Jira, manifest: dict[str, Any], created: list[str]) -> dict[str, Any]:
    state = manifest.setdefault("jira", {})

    # The world's own project — never assume an empty site (jira probe ruling). The
    # company-managed kanban template is what the probe project used (its screens are
    # what the custom fields land on); Free refusing it over REST would be a finding.
    existing = jira.call("GET", f"/project/{PROJECT_KEY}", ok=(200, 404))
    if not (isinstance(existing, dict) and existing.get("key") == PROJECT_KEY):
        me = jira.call("GET", "/myself")
        jira.call("POST", "/project", json={
            "key": PROJECT_KEY, "name": PROJECT_NAME, "projectTypeKey": "software",
            "projectTemplateKey": "com.pyxis.greenhopper.jira:gh-kanban-template",
            "leadAccountId": me["accountId"], "assigneeType": "UNASSIGNED",
        })
        created.append("jira:project")

    fields = {}
    for field_name, field_type, searcher in (
        (OWNER_FIELD, "select", "multiselectsearcher"),
        (DATE_FIELDS[0], "datepicker", "daterange"),
        (DATE_FIELDS[1], "datepicker", "daterange"),
    ):
        have = [f for f in jira.call("GET", "/field") if f["name"] == field_name and f.get("custom")]
        if have:
            fields[field_name] = have[0]["id"]
        else:
            made = jira.call("POST", "/field", json={
                "name": field_name,
                "description": f"World fact of the synthetic org (seed {WORLD}); not a Jira-native value.",
                "type": f"com.atlassian.jira.plugin.system.customfieldtypes:{field_type}",
                "searcherKey": f"com.atlassian.jira.plugin.system.customfieldtypes:{searcher}",
            })
            fields[field_name] = made["id"]
            created.append(f"jira:field:{field_name}")
    state["fields"] = fields
    owner_field = fields[OWNER_FIELD]

    # Options append per world on the shared select field — world-scoped ids keep them
    # unambiguous across worlds.
    contexts = jira.call("GET", f"/field/{owner_field}/context")["values"]
    context_id = contexts[0]["id"]
    have_options = {o["value"]: o["id"]
                    for o in jira.call("GET", f"/field/{owner_field}/context/{context_id}/option")["values"]}
    missing = [option_value(e) for e in PEOPLE if option_value(e) not in have_options]
    if missing:
        jira.call("POST", f"/field/{owner_field}/context/{context_id}/option",
                  json={"options": [{"value": v, "disabled": False} for v in missing]})
        created.append(f"jira:options:{len(missing)}")

    # All three fields onto every screen the template made for this project.
    screens = [s for s in jira.call("GET", f"/screens?queryString={PROJECT_KEY}")["values"]
               if s["name"].startswith(f"{PROJECT_KEY}:")]
    if not screens:
        raise RuntimeError(f"no screen named '{PROJECT_KEY}: …' — fields cannot be set on create")
    for screen in screens:
        tab = jira.call("GET", f"/screens/{screen['id']}/tabs")[0]
        on_tab = {f["id"] for f in jira.call("GET", f"/screens/{screen['id']}/tabs/{tab['id']}/fields")}
        for field_id in fields.values():
            if field_id not in on_tab:
                jira.call("POST", f"/screens/{screen['id']}/tabs/{tab['id']}/fields", json={"fieldId": field_id})

    keys: dict[str, str] = state.setdefault("issues", {})
    for slug, owner, opened_on, resolved_on in ISSUES:
        summary = f"[{WORLD}] {slug}"
        found = [i for i in jira.search(f'project = {PROJECT_KEY} AND summary ~ "\\"{summary}\\""', ["summary"])
                 if i["fields"]["summary"] == summary]
        if found:
            keys[slug] = found[0]["key"]
        else:
            payload: dict[str, Any] = {
                "project": {"key": PROJECT_KEY}, "issuetype": {"name": "Task"}, "summary": summary,
                "labels": [f"scenario-seed-{WORLD}"],
                fields[OWNER_FIELD]: {"value": option_value(owner)},
                fields["Opened On"]: opened_on,
            }
            if resolved_on:
                payload[fields["Resolved On"]] = resolved_on
            made = jira.call("POST", "/issue", json={"fields": payload})
            keys[slug] = made["key"]
            created.append(f"jira:issue:{slug}")
        if resolved_on:  # world-resolved issues also sit in Done, so status agrees
            status = jira.call("GET", f"/issue/{keys[slug]}?fields=status")["fields"]["status"]["name"]
            if status != "Done":
                transitions = jira.call("GET", f"/issue/{keys[slug]}/transitions")["transitions"]
                done = [t for t in transitions if t["to"]["name"] == "Done"]
                if not done:
                    raise RuntimeError(f"no transition to Done for {keys[slug]} (workflow: {[t['to']['name'] for t in transitions]})")
                jira.call("POST", f"/issue/{keys[slug]}/transitions", json={"transition": {"id": done[0]["id"]}})
                created.append(f"jira:transition:{slug}")

    return {"fields": fields, "issues": keys}


# --- Calendar projection: one secondary calendar per person, the meeting week --------


def event_id(calendar_id: str, key: str) -> str:
    digest = hashlib.sha1(f"{calendar_id}:{key}".encode()).hexdigest()
    return "".join("0123456789abcdefghijklmnopqrstuv"[int(c, 16)] for c in digest)


def seed_calendar(svc: Any, manifest: dict[str, Any], created: list[str]) -> dict[str, Any]:
    state = manifest.setdefault("calendar", {})
    calendars: dict[str, str] = state.setdefault("calendars", {})

    # `calendar.app.created` cannot list calendars, so the manifest is the only index;
    # a remembered id is verified with calendars.get — a 404 there is a real fault.
    for emp_id in PEOPLE:
        summary = f"{WORLD.upper()} {full_name(emp_id)}"
        if emp_id in calendars:
            svc.calendars().get(calendarId=calendars[emp_id]).execute()
            continue
        made = svc.calendars().insert(body={"summary": summary, "timeZone": TZ}).execute()
        calendars[emp_id] = made["id"]
        created.append(f"calendar:{emp_id}")

    for n, (key, who, day, hour, minute, minutes) in enumerate(MEETINGS):
        start = WEEK_START + timedelta(days=day, hours=hour, minutes=minute)
        for emp_id in who:
            body = {
                "id": event_id(calendars[emp_id], f"{key}:{n}"),
                "summary": key,
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": (start + timedelta(minutes=minutes)).isoformat()},
                # World facts only — what a colleague could read off the invite.
                "extendedProperties": {"private": {"participants": ";".join(who)}},
            }
            try:
                svc.events().insert(calendarId=calendars[emp_id], body=body).execute()
                created.append(f"calendar-event:{emp_id}:{key}:{n}")
            except HttpError as err:
                if err.resp.status != 409:
                    raise
                patch = {k: v for k, v in body.items() if k != "id"}
                svc.events().patch(calendarId=calendars[emp_id], eventId=body["id"], body=patch).execute()

    return {"calendars": calendars}


# --- verify: answer(now), asked twice ------------------------------------------------


def answer(now: datetime, fr: Frappe, jira: Jira, svc: Any, manifest: dict[str, Any]) -> dict[str, Any]:
    """The investigator's questions, derived from `now` alone: on-leave set for now's
    week, open issues per person as of now (JQL date arithmetic on the world date
    fields — criterion (c)), busy blocks for now's week."""
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)
    names = manifest["frappe"]["employees"]
    by_name = {v: k for k, v in names.items()}

    rows = fr.get_list(
        "Leave Application",
        {"docstatus": 1, "from_date": ["<", str(week_end.date())], "to_date": [">=", str(week_start.date())]},
        ["employee", "from_date", "to_date"],
    )
    on_leave = sorted({by_name[r["employee"]] for r in rows if r["employee"] in by_name})

    now_date = str(now.date())
    open_issues = {}
    for emp_id in PEOPLE:
        issues = jira.search(
            f'project = {PROJECT_KEY} AND "{OWNER_FIELD}" = "{option_value(emp_id)}" '
            f'AND "Opened On" <= "{now_date}" '
            f'AND ("Resolved On" IS EMPTY OR "Resolved On" > "{now_date}")',
            ["summary"],
        )
        open_issues[emp_id] = sorted(i["key"] for i in issues)

    calendars = manifest["calendar"]["calendars"]
    busy = svc.freebusy().query(body={
        "timeMin": week_start.isoformat(), "timeMax": week_end.isoformat(),
        "items": [{"id": cid} for cid in calendars.values()],
    }).execute()
    busy_blocks = {emp_id: busy["calendars"].get(cid, {}).get("busy", [])
                   for emp_id, cid in calendars.items()}

    return {"week": [str(week_start.date()), str(week_end.date())],
            "on_leave": on_leave, "open_issues": open_issues, "busy": busy_blocks}


def verify(fr: Frappe, jira: Jira, svc: Any, manifest: dict[str, Any]) -> dict[str, Any]:
    first = answer(NOW_1, fr, jira, svc, manifest)
    second = answer(NOW_2, fr, jira, svc, manifest)
    expected_open = {emp_id: sorted(manifest["jira"]["issues"][slug]
                                    for slug, owner, _, resolved in ISSUES
                                    if owner == emp_id and resolved is None)
                     for emp_id in PEOPLE}
    return {
        "stable_interval": list(STABLE_INTERVAL),
        "now_1": NOW_1.isoformat(), "now_2": NOW_2.isoformat(),
        "answer_1": first, "answer_2": second,
        "stable_now": first == second,
        "expected_on_leave": sorted({e for e, *_ in LEAVES}),
        "on_leave_exact": first["on_leave"] == sorted({e for e, *_ in LEAVES}),
        "expected_open_issues": expected_open,
        "open_issues_exact": first["open_issues"] == expected_open,
    }


# --- main ----------------------------------------------------------------------------


def redact(text: str, fr: Frappe, jira: Jira) -> str:
    text = text.replace(fr.base, "https://<frappe-site>")
    return text.replace(jira.base, "https://<jira-site>/rest/api/3")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    run_no = len(list(CAPTURE_DIR.glob("run-*.json"))) + 1
    created: list[str] = []  # every create across all three systems; run 2 must add none
    capture: dict[str, Any] = {"run": run_no, "world": WORLD, "outcome": "failed"}
    fr, jira = Frappe(), Jira()
    try:
        svc = google_service()
        capture["frappe"] = seed_frappe(fr, manifest, created)
        print("frappe:", json.dumps(capture["frappe"], indent=2, ensure_ascii=False))
        capture["jira"] = seed_jira(jira, manifest, created)
        print("jira:", json.dumps(capture["jira"], indent=2, ensure_ascii=False))
        capture["calendar"] = seed_calendar(svc, manifest, created)
        print("calendar:", json.dumps(capture["calendar"], indent=2, ensure_ascii=False))
        capture["verify"] = verify(fr, jira, svc, manifest)
        print("verify:", json.dumps(capture["verify"], indent=2, ensure_ascii=False))
        capture["outcome"] = "ok"
    except Exception as exc:  # the failure is the finding — capture, then re-raise
        capture["error"] = str(exc)
        raise
    finally:
        capture["created"] = created
        capture["created_count"] = len(created)
        capture["exchanges"] = {"frappe": fr.log, "jira": jira.log}
        MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        path = CAPTURE_DIR / f"run-{run_no:02d}.json"
        path.write_text(redact(json.dumps(capture, indent=2, ensure_ascii=False, default=str), fr, jira),
                        encoding="utf-8")
        print(f"created this run: {len(created)}")
        print("capture:", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
