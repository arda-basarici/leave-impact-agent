"""Read principals: does each reader credential read the golden world and nothing more?

The M2 build plan's step 0 (the rulings of 2026-09-22): the validator and the
investigator each get their own credential per vendor, one that reads the world and
cannot write it, distinct from the generator's writing set. This probe is the
acceptance for those credentials, one vendor mode per run, one principal per run:

- ``frappe --principal <p>``: the reader's adapter-shaped reads (employees with their
  skill records, teams, leaves) equal the Administrator's field by field; the reader's
  role holds read only on the four doctypes and no permission anywhere else; the
  account is an enabled Website User with that one role and no User Permission; a
  create on each of the four doctypes is refused, and a write and a delete against a
  disposable employee the Administrator creates and removes in the same run.
- ``jira --principal <p>``: the reader's scoped token at Atlassian's gateway performs
  the validator's reads (issues, comments, components) equal to the generator's; the
  account's project permissions are captured as they are (the Free plan grants the
  account write permission, the token's scope withholds it); a known-valid issue create
  is refused against a disposable canary project after the generator proved the payload;
  the same create through the site URL characterizes the unsupported path.
- ``google --principal <p>``: the recorded exception (ruling 3b, 2026-09-24). No
  read-only scope exists over app-created calendars, and the read-only scope that does
  exist reaches the owner's personal calendar, so both readers hold the generator's
  grant: `calendar.app.created` and `calendar.freebusy` under the generator's client,
  one refresh token per consumer store. Read-only for Calendar rests on the code; what
  the credential bounds is reach, and that is what this mode measures: the granted
  scope set from the refresh response is exactly those two, the golden calendars are
  readable through the adapter, and an event list on the account's primary calendar
  and a calendar-list call are both refused.

Credentials enter only through the fixed ``LEAVE_IMPACT_*`` names the production wiring
reads, each vendor mode reading its own vendor's names (the operator sources a
git-ignored file first; no path or value is an argument; no dotenv is parsed here). The
reader under test is the ``LEAVE_IMPACT_`` set, the validator workflow's own names; the
reference credentials (the generator's, and Frappe's Administrator) carry a
``LEAVE_IMPACT_REFERENCE_`` prefix. The golden world's projected manifest is a local
copy named by ``LEAVE_IMPACT_WORLD_MANIFEST_FILE``.

Captures are attempt-stamped and never overwritten. Golden records never reach a
capture: the equivalence checks write counts, digests and equality verdicts. Every
capture is scanned for each secret this process loaded and for authorization-header
patterns before it is written, and refused on a hit. A failed check is still a capture:
the failure is the finding.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import sys
import uuid
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import httpx

from leaveimpact.adapters.calendar.adapter import (
    GOOGLE_CALENDAR_API,
    CalendarAdapter,
    CalendarCredential,
)
from leaveimpact.adapters.frappe.adapter import FrappeAdapter, FrappeCredential
from leaveimpact.adapters.jira.adapter import JiraAdapter, JiraCredential, JiraSite
from leaveimpact.adapters.manifest import ManifestStage, WorldManifest, decode_manifest
from leaveimpact.adapters.wiring import PREFIX, ConfigurationError
from leaveimpact.core.entities import Employee
from leaveimpact.core.enums import EmploymentType, Grade
from leaveimpact.core.ids import employee_id
from leaveimpact.core.worldtime import DateSpan, InstantSpan

CAPTURE_ROOT = Path(__file__).resolve().parents[1] / "captures"
READER_ROLE = "Leave Impact Reader"
READER_DOCTYPES = ("Employee", "Department", "Leave Application", "Employee Skill Map")
MUTATION_FLAGS = ("write", "create", "delete", "submit", "cancel", "amend")
JIRA_PERMISSIONS = (
    "BROWSE_PROJECTS",
    "CREATE_ISSUES",
    "EDIT_ISSUES",
    "DELETE_ISSUES",
    "ADD_COMMENTS",
    "TRANSITION_ISSUES",
)
GENERATOR_SCOPES = (
    "https://www.googleapis.com/auth/calendar.app.created",
    "https://www.googleapis.com/auth/calendar.freebusy",
)
# The Role Permission Manager's own report, whitelisted for System Manager: the rows for
# a role across doctypes, or a doctype's effective set (custom rows when any exist).
PERMISSION_REPORT = "frappe.core.page.permission_manager.permission_manager.get_permissions"
# Wide enough to hold any world: the reads are compared, not interpreted.
ALL_DATES = DateSpan(date(2000, 1, 1), date(2100, 1, 1))
ALL_INSTANTS = InstantSpan(datetime(2000, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC))
PROBE_EMPLOYEE = employee_id(999)
HEADER_PATTERN = re.compile(
    r"(?i)authorization|bearer\s+[A-Za-z0-9._-]{8,}|token\s+[A-Za-z0-9]{6,}:[A-Za-z0-9]{6,}"
)

Json = dict[str, Any]


# --- the capture: stamped, scanned, redacted ------------------------------------------


class Capture:
    """One run's evidence: assembled in memory, scanned and redacted, written once."""

    def __init__(self, directory: Path, stem: str) -> None:
        self.directory = directory
        self.stem = stem
        self.data: Json = {"outcome": "failed", "checks": {}}
        self._secrets: set[str] = set()
        self._redactions: dict[str, str] = {}

    def secret(self, value: str | None) -> None:
        """Register a value that must never appear in the capture."""
        if value:
            self._secrets.add(value)

    def redact(self, value: str | None, placeholder: str) -> None:
        """Register a non-secret identifier to replace with ``placeholder`` on write."""
        if value:
            self._redactions[value] = placeholder

    def check(self, name: str, **fields: Any) -> Json:
        record = dict(fields)
        self.data["checks"][name] = record
        print(f"{name}: {json.dumps(record, default=str, ensure_ascii=False)}")
        return record

    def write(self) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        attempt = len(list(self.directory.glob(f"{self.stem}-run-*.json"))) + 1
        path = self.directory / f"{self.stem}-run-{attempt:02d}.json"
        if path.exists():
            raise RuntimeError(f"{path} exists; a capture is never overwritten")
        text = json.dumps(
            {"attempt": attempt, **self.data}, indent=2, default=str, ensure_ascii=False
        )
        for value, placeholder in sorted(self._redactions.items(), key=lambda kv: -len(kv[0])):
            text = text.replace(value, placeholder)
        leaked = [secret for secret in self._secrets if secret in text]
        if leaked or HEADER_PATTERN.search(text):
            raise RuntimeError(
                "capture refused: it would contain a loaded secret or an authorization header"
            )
        path.write_text(text, encoding="utf-8")
        return path


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def short(value: str) -> str:
    """A non-reversible handle for an identifier the capture must not carry verbatim."""
    return digest(value)[:12]


def canonical(observed: Iterable[Any]) -> tuple[int, str]:
    """Count and digest of a read, order-free: the domain values as sorted JSON lines."""
    lines = sorted(
        json.dumps(dataclasses.asdict(item.value), sort_keys=True, default=str) for item in observed
    )
    return len(lines), digest("\n".join(lines))


def equivalence(capture: Capture, name: str, reader: Any, reference: Any) -> bool:
    """``reader`` and ``reference`` produce the same read, judged by count and digest."""
    reader_count, reader_digest = canonical(reader)
    reference_count, reference_digest = canonical(reference)
    equal = reader_digest == reference_digest
    capture.check(
        name,
        reader_count=reader_count,
        reference_count=reference_count,
        reader_digest=reader_digest,
        reference_digest=reference_digest,
        equal=equal,
    )
    return equal


def response_record(response: httpx.Response) -> Json:
    """Status and the vendor's message, the body trimmed: what a refusal looks like."""
    body: Any
    try:
        body = response.json()
    except ValueError:
        body = response.text[:400]
    if isinstance(body, dict):
        body = {key: value for key, value in cast(Json, body).items() if key != "exc"}
    text = json.dumps(body, default=str, ensure_ascii=False)
    if len(text) > 600:
        body = text[:600] + "…"
    return {"status": response.status_code, "body": body}


# --- configuration ---------------------------------------------------------------------


def required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} is not set and this probe needs it")
    return value


def manifest_from_env(env: Mapping[str, str]) -> WorldManifest:
    name = PREFIX + "WORLD_MANIFEST_FILE"
    path = Path(required(env, name))
    try:
        return decode_manifest(path.read_bytes(), stage=ManifestStage.PROJECTED)
    except OSError as error:
        raise ConfigurationError(f"{name} names {path}, which cannot be read") from error


@dataclasses.dataclass(frozen=True)
class FrappePrincipal:
    base_url: str
    credential: FrappeCredential


@dataclasses.dataclass(frozen=True)
class JiraPrincipal:
    base_url: str
    credential: JiraCredential


def frappe_principal(env: Mapping[str, str], prefix: str, capture: Capture) -> FrappePrincipal:
    """The Frappe site and key pair under ``prefix`` (the reader's, or the reference's)."""
    credential = FrappeCredential(
        api_key=required(env, prefix + "FRAPPE_API_KEY"),
        api_secret=required(env, prefix + "FRAPPE_API_SECRET"),
    )
    base_url = required(env, prefix + "FRAPPE_BASE_URL").rstrip("/")
    capture.secret(credential.api_key)
    capture.secret(credential.api_secret)
    capture.redact(base_url, "https://<frappe-site>")
    return FrappePrincipal(base_url, credential)


def jira_principal(env: Mapping[str, str], prefix: str, capture: Capture) -> JiraPrincipal:
    """The Jira base URL and account under ``prefix``: the gateway root for a scoped token."""
    credential = JiraCredential(
        email=required(env, prefix + "JIRA_EMAIL"), api_token=required(env, prefix + "JIRA_TOKEN")
    )
    base_url = required(env, prefix + "JIRA_BASE_URL").rstrip("/")
    capture.secret(credential.api_token)
    capture.redact(credential.email, f"<jira-account {short(credential.email)}>")
    return JiraPrincipal(base_url, credential)


def calendar_principal(env: Mapping[str, str], prefix: str, capture: Capture) -> CalendarCredential:
    """The authorized-user JSON the name under ``prefix`` points at, as the wiring reads it."""
    name = prefix + "GOOGLE_AUTHORIZED_USER_FILE"
    path = Path(required(env, name))
    try:
        info = cast(Json, json.loads(path.read_text(encoding="utf-8")))
        credential = CalendarCredential.from_authorized_user_info(info)
    except OSError as error:
        raise ConfigurationError(f"{name} names {path}, which cannot be read") from error
    except (ValueError, KeyError, TypeError) as error:
        raise ConfigurationError(f"{name} names {path}: not authorized-user JSON") from error
    capture.secret(credential.refresh_token)
    capture.secret(credential.client_secret)
    capture.redact(credential.client_id, f"<client-id {short(credential.client_id)}>")
    return credential


READER = PREFIX
REFERENCE = PREFIX + "REFERENCE_"


# --- Frappe -----------------------------------------------------------------------------


def frappe_raw(base_url: str, credential: FrappeCredential) -> httpx.Client:
    return httpx.Client(
        base_url=base_url,
        headers={"Authorization": credential.authorization, "Accept": "application/json"},
        timeout=60,
    )


def frappe_list(
    client: httpx.Client, doctype: str, filters: list[Any], fields: list[str]
) -> list[Json]:
    response = client.get(
        f"/api/resource/{doctype}",
        params={
            "filters": json.dumps(filters),
            "fields": json.dumps(fields),
            "limit_page_length": 500,
        },
    )
    response.raise_for_status()
    return cast(list[Json], response.json()["data"])


def frappe_method(client: httpx.Client, method: str, **params: str) -> Any:
    response = client.get(f"/api/method/{method}", params=params)
    response.raise_for_status()
    return response.json()["message"]


def probe_frappe(env: Mapping[str, str], principal: str, capture: Capture) -> None:
    manifest = manifest_from_env(env)
    reader_site = frappe_principal(env, READER, capture)
    reference_site = frappe_principal(env, REFERENCE, capture)
    account = required(env, PREFIX + "PROBE_FRAPPE_READER_EMAIL")
    config = manifest.systems.frappe
    capture.data["principal"] = principal
    capture.data["world_version"] = manifest.world_version
    capture.data["reader_account"] = account

    reader = FrappeAdapter(
        base_url=reader_site.base_url, credential=reader_site.credential, config=config
    )
    admin = FrappeAdapter(
        base_url=reference_site.base_url, credential=reference_site.credential, config=config
    )
    raw_reader = frappe_raw(reader_site.base_url, reader_site.credential)
    raw_admin = frappe_raw(reference_site.base_url, reference_site.credential)
    try:
        # The credential must be the account the run claims to test: the first passing run
        # was produced with the other reader's key pair left in the operator's session, and
        # only the vendor's messages naming the other account gave it away.
        logged_in_as = str(frappe_method(raw_reader, "frappe.auth.get_logged_user"))
        if logged_in_as != account:
            raise ConfigurationError(
                f"the reader credential authenticates as {logged_in_as}, not {account}: "
                "the LEAVE_IMPACT_FRAPPE_API_KEY and _SECRET in the environment are another user's"
            )
        capture.check("credential_identity", account=account, credential_is_account=True)
        capture.check(
            "distinct_credentials",
            distinct=reader_site.credential.api_key != reference_site.credential.api_key,
        )
        # (a) read equivalence on the four doctypes, through the adapter's own reads
        reference_employees = admin.employees()
        team_ids = sorted({person.value.team_id for person in reference_employees})
        equivalence(capture, "employees_equal", reader.employees(), reference_employees)
        equivalence(
            capture,
            "teams_equal",
            [team for team in (reader.team(id) for id in team_ids) if team is not None],
            [team for team in (admin.team(id) for id in team_ids) if team is not None],
        )
        equivalence(
            capture, "leaves_equal", reader.leaves_within(ALL_DATES), admin.leaves_within(ALL_DATES)
        )

        # (b) proof: the role's permission rows, the account, its user permissions
        role_rows = cast(list[Json], frappe_method(raw_admin, PERMISSION_REPORT, role=READER_ROLE))
        rows_elsewhere = [row for row in role_rows if row.get("parent") not in READER_DOCTYPES]
        mutation_granted = [
            {"doctype": row.get("parent"), "flag": flag}
            for row in role_rows
            for flag in MUTATION_FLAGS
            if row.get(flag)
        ]
        capture.check(
            "role_permissions",
            rows=[
                {
                    key: row.get(key)
                    for key in ("parent", "permlevel", "if_owner", "read", *MUTATION_FLAGS)
                }
                for row in role_rows
            ],
            doctypes_with_read=sorted({str(row["parent"]) for row in role_rows if row.get("read")}),
            rows_elsewhere=rows_elsewhere,
            mutation_granted=mutation_granted,
            read_only_on_four=(
                not rows_elsewhere
                and not mutation_granted
                and {str(row["parent"]) for row in role_rows if row.get("read")}
                == set(READER_DOCTYPES)
            ),
        )
        customized = {
            doctype: frappe_method(raw_admin, PERMISSION_REPORT, doctype=doctype)
            for doctype in READER_DOCTYPES
        }
        capture.check(
            "customized_permission_sets",
            **{
                doctype: [
                    {
                        key: row.get(key)
                        for key in ("role", "permlevel", "if_owner", "read", *MUTATION_FLAGS)
                    }
                    for row in cast(list[Json], rows)
                ]
                for doctype, rows in customized.items()
            },
        )
        user = raw_admin.get(f"/api/resource/User/{account}")
        user.raise_for_status()
        user_doc = cast(Json, user.json()["data"])
        assigned = sorted(
            str(row.get("role")) for row in cast(list[Json], user_doc.get("roles", []))
        )
        user_permissions = frappe_list(
            raw_admin, "User Permission", [["user", "=", account]], ["name", "allow", "for_value"]
        )
        capture.check(
            "account",
            enabled=user_doc.get("enabled"),
            user_type=user_doc.get("user_type"),
            assigned_roles=assigned,
            only_the_reader_role=assigned == [READER_ROLE],
            user_permissions=user_permissions,
            no_user_permissions=not user_permissions,
        )

        # (c) demonstration: creates refused on each doctype, no setup needed
        create_payloads = {
            "Employee": {"first_name": "Probe"},
            "Department": {"department_name": "Probe"},
            "Leave Application": {"employee": PROBE_EMPLOYEE},
            "Employee Skill Map": {"employee": PROBE_EMPLOYEE},
        }
        creates: Json = {}
        for doctype, payload in create_payloads.items():
            response = raw_reader.post(f"/api/resource/{doctype}", json=payload)
            creates[doctype] = response_record(response)
            if response.is_success:
                name = cast(Json, response.json()["data"]).get("name")
                creates[doctype]["unexpected_record_deleted"] = raw_admin.delete(
                    f"/api/resource/{doctype}/{name}"
                ).status_code
        capture.check(
            "creates_refused",
            **creates,
            all_refused=all(record["status"] == 403 for record in creates.values()),
        )

        # then a write and a delete against a disposable employee the Administrator owns
        sample = reference_employees[0].value
        skilled = next((p.value.skills for p in reference_employees if p.value.skills), None)
        disposable = Employee(
            id=PROBE_EMPLOYEE,
            name="Probe Disposable",
            team_id=sample.team_id,
            manager_id=None,
            skills=skilled[:1] if skilled else None,
            location=sample.location,
            country=sample.country,
            timezone=sample.timezone,
            grade=Grade.MID,
            employment_type=EmploymentType.EMPLOYEE,
        )
        admin.add_employee(disposable)
        try:
            names = frappe_list(
                raw_admin, "Employee", [["employee_number", "=", PROBE_EMPLOYEE]], ["name"]
            )
            employee_name = str(names[0]["name"])
            write = raw_reader.put(
                f"/api/resource/Employee/{employee_name}", json={"custom_location": "probe-written"}
            )
            delete = raw_reader.delete(f"/api/resource/Employee/{employee_name}")
            after = frappe_list(
                raw_admin,
                "Employee",
                [["employee_number", "=", PROBE_EMPLOYEE]],
                ["name", "custom_location"],
            )
            capture.check(
                "disposable_mutations_refused",
                write=response_record(write),
                delete=response_record(delete),
                still_present_unchanged=bool(after)
                and after[0].get("custom_location") == sample.location,
                both_refused=write.status_code == 403 and delete.status_code == 403,
            )
        finally:
            maps = frappe_list(
                raw_admin, "Employee Skill Map", [["employee", "=", PROBE_EMPLOYEE]], ["name"]
            )
            for row in maps:
                raw_admin.delete(
                    f"/api/resource/Employee Skill Map/{row['name']}"
                ).raise_for_status()
            for row in frappe_list(
                raw_admin, "Employee", [["employee_number", "=", PROBE_EMPLOYEE]], ["name"]
            ):
                raw_admin.delete(f"/api/resource/Employee/{row['name']}").raise_for_status()
            remaining = frappe_list(
                raw_admin, "Employee", [["employee_number", "=", PROBE_EMPLOYEE]], ["name"]
            )
            capture.check("disposable_removed", removed=not remaining)
        capture.data["outcome"] = "ok"
    finally:
        reader.close()
        admin.close()
        raw_reader.close()
        raw_admin.close()


# --- Jira -------------------------------------------------------------------------------


def jira_raw(base_url: str, credential: JiraCredential) -> httpx.Client:
    return httpx.Client(
        base_url=base_url.rstrip("/") + "/rest/api/3",
        auth=credential.auth,
        headers={"Accept": "application/json"},
        timeout=60,
    )


def jira_permissions(client: httpx.Client, project_key: str) -> Json:
    response = client.get(
        "/mypermissions",
        params={"projectKey": project_key, "permissions": ",".join(JIRA_PERMISSIONS)},
    )
    if not response.is_success:
        return response_record(response)
    granted = cast(Json, response.json().get("permissions", {}))
    return {
        name: bool(cast(Json, granted.get(name, {})).get("havePermission"))
        for name in JIRA_PERMISSIONS
    }


def canary_issue(project_key: str, marker: str) -> Json:
    return {
        "fields": {
            "project": {"key": project_key},
            "summary": f"leave-impact read-principals probe {marker}",
            "issuetype": {"name": "Task"},
        }
    }


def delete_issue(cleanup: httpx.Client, key: str) -> Json:
    """Delete ``key`` through ``cleanup``; the key stays on record unless the delete succeeded."""
    status = cleanup.delete(f"/issue/{key}").status_code
    return {"key": "<deleted>" if status == 204 else key, "delete_status": status}


def attempt_create(client: httpx.Client, cleanup: httpx.Client, payload: Json) -> Json:
    """One create attempt; anything created is deleted at once through ``cleanup``."""
    response = client.post("/issue", json=payload)
    record = response_record(response)
    if response.is_success:
        record["body"] = delete_issue(cleanup, str(cast(Json, response.json()).get("key")))
        record["unexpected_creation"] = True
    return record


def ensure_canary_admin(client: httpx.Client, project_key: str) -> Json:
    """The generator account in the canary project's Administrators role, so it can delete.

    Delete Issues sits with that role on the site's one permission scheme, and a project
    created over REST gives its lead no role: the first run's proof issue could not be
    removed by anyone. Granted on the canary project only; the golden project keeps the
    property that no REST principal deletes its issues.
    """
    me = str(cast(Json, client.get("/myself").json())["accountId"])
    roles = cast(Json, client.get(f"/project/{project_key}/role").json())
    role_id = str(roles["Administrators"]).rstrip("/").rsplit("/", 1)[-1]
    actors = cast(
        list[Json],
        cast(Json, client.get(f"/project/{project_key}/role/{role_id}").json()).get("actors", []),
    )
    held = any(cast(Json, actor.get("actorUser") or {}).get("accountId") == me for actor in actors)
    if not held:
        client.post(
            f"/project/{project_key}/role/{role_id}", json={"user": [me]}
        ).raise_for_status()
    return {"role": "Administrators", "generator_was_member": held, "generator_is_member": True}


def probe_jira(env: Mapping[str, str], principal: str, capture: Capture) -> None:
    manifest = manifest_from_env(env)
    reader_site = jira_principal(env, READER, capture)
    reference_site = jira_principal(env, REFERENCE, capture)
    capture.redact(reader_site.base_url, "https://<jira-gateway>")
    capture.redact(reference_site.base_url, "https://<jira-site>")
    canary_project = required(env, PREFIX + "PROBE_JIRA_CANARY_PROJECT")
    config = manifest.systems.jira
    capture.data["principal"] = principal
    capture.data["world_version"] = manifest.world_version
    capture.data["gateway_host"] = httpx.URL(reader_site.base_url).host
    capture.data["canary_project"] = canary_project

    reader = JiraAdapter(
        base_url=reader_site.base_url, credential=reader_site.credential, config=config
    )
    generator = JiraAdapter(
        base_url=reference_site.base_url, credential=reference_site.credential, config=config
    )
    raw_reader = jira_raw(reader_site.base_url, reader_site.credential)
    raw_reader_at_site = jira_raw(reference_site.base_url, reader_site.credential)
    raw_generator = jira_raw(reference_site.base_url, reference_site.credential)
    try:
        # The canary project: company-managed on the same site, so on the Free plan it
        # shares the one permission scheme every project has; created once by the
        # generator principal through the adapter's own project creation, kept standing.
        site = JiraSite(base_url=reference_site.base_url, credential=reference_site.credential)
        try:
            site.ensure_project(canary_project, "Leave Impact read-principals canary")
        finally:
            site.close()
        capture.check(
            "canary_project_present",
            key=canary_project,
            **ensure_canary_admin(raw_generator, canary_project),
        )
        capture.check(
            "distinct_credentials",
            distinct=reader_site.credential != reference_site.credential,
        )
        # (a) the validator's reads through the adapter, at the gateway, equal the generator's
        equivalence(capture, "work_items_equal", reader.work_items(), generator.work_items())
        equivalence(capture, "components_equal", reader.components(), generator.components())

        # (b) the account's permissions as Jira grants them: the limitation made visible
        capture.check(
            "account_permissions",
            golden_project=jira_permissions(raw_reader, config.project_key),
            canary_project=jira_permissions(raw_reader, canary_project),
        )

        # (c) a known-valid create: the generator proves the payload, the reader is refused
        payload = canary_issue(canary_project, uuid.uuid4().hex[:12])
        proof = raw_generator.post("/issue", json=payload)
        proof_record = response_record(proof)
        if proof.is_success:
            proof_record["body"] = delete_issue(
                raw_generator, str(cast(Json, proof.json()).get("key"))
            )
        refused = attempt_create(raw_reader, raw_generator, payload)
        capture.check(
            "create_refused_at_gateway",
            payload_proven_by_generator=proof.is_success,
            generator=proof_record,
            reader=refused,
            refused=proof.is_success and not 200 <= int(refused["status"]) < 300,
        )
        # characterization only: the site URL is not a supported path for a scoped token
        capture.check(
            "site_url_characterization",
            read=response_record(raw_reader_at_site.get("/myself")),
            create=attempt_create(raw_reader_at_site, raw_generator, payload),
        )
        capture.data["outcome"] = "ok"
    finally:
        reader.close()
        generator.close()
        raw_reader.close()
        raw_reader_at_site.close()
        raw_generator.close()


# --- Google Calendar --------------------------------------------------------------------


def refresh(credential: CalendarCredential, capture: Capture) -> tuple[Json, str | None]:
    """The refresh response as a record (scope, expiry, or the error) and the access token."""
    response = httpx.post(
        credential.token_uri,
        data={
            "client_id": credential.client_id,
            "client_secret": credential.client_secret,
            "refresh_token": credential.refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=60,
    )
    body = (
        cast(Json, response.json())
        if response.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    token = body.get("access_token")
    capture.secret(token)
    record: Json = {"status": response.status_code}
    if response.is_success:
        record["scope"] = sorted(str(body.get("scope", "")).split())
        record["expires_in"] = body.get("expires_in")
    else:
        record["error"] = body.get("error")
        record["error_description"] = body.get("error_description")
    return record, token


def google_get(path: str, access_token: str, params: dict[str, str] | None = None) -> Json:
    response = httpx.get(
        f"{GOOGLE_CALENDAR_API}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
        timeout=60,
    )
    record = response_record(response)
    if response.is_success:
        # a success here is a reach the token was not supposed to have: keep the fact,
        # never the owner's calendar data
        record["body"] = "<omitted: the call succeeded>"
    return record


def probe_google(env: Mapping[str, str], principal: str, capture: Capture) -> None:
    manifest = manifest_from_env(env)
    credential = calendar_principal(env, READER, capture)
    config = manifest.systems.calendar
    for calendar_id in config.calendar_by_employee.values():
        capture.redact(calendar_id, f"<calendar {short(calendar_id)}>")
    capture.data["principal"] = principal
    capture.data["world_version"] = manifest.world_version
    capture.data["client"] = short(credential.client_id)

    # (a) the granted scope set, from the refresh response, never a token
    granted, access_token = refresh(credential, capture)
    capture.check(
        "granted_scope",
        **granted,
        exactly_the_generator_scopes=sorted(granted.get("scope", [])) == sorted(GENERATOR_SCOPES),
    )
    if access_token is None:
        raise RuntimeError("the token did not refresh; nothing below can be measured")

    # (b) the golden calendars are readable through the adapter's own read
    reader = CalendarAdapter(credential=credential, config=config)
    try:
        events = reader.events_within(ALL_INSTANTS)
        count, event_digest = canonical(events)
        got = reader.event(events[0].value.id) if events else None
        capture.check(
            "golden_calendars_readable",
            calendars=len(config.calendar_by_employee),
            events=count,
            digest=event_digest,
            event_get_ok=got is not None,
        )
    finally:
        reader.close()

    # (c) the reach bound, measured: the owner's primary calendar and the calendar list
    primary = google_get(
        "/calendars/primary/events",
        access_token,
        {"maxResults": "1", "timeMin": "2000-01-01T00:00:00Z", "timeMax": "2100-01-01T00:00:00Z"},
    )
    listing = google_get("/users/me/calendarList", access_token, {"maxResults": "1"})
    # Google hides a calendar the scope cannot see rather than refusing it: the primary
    # calendar answers 404 under the app-created scope (measured 2026-09-24), the
    # calendar list an explicit 403 for insufficient scopes. Either is the reach refused.
    capture.check(
        "reach_bounded_to_app_created",
        primary_calendar=primary,
        calendar_list=listing,
        both_refused=primary["status"] in (403, 404) and listing["status"] == 403,
    )
    capture.data["outcome"] = "ok"


# --- main -------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("vendor", choices=("frappe", "jira", "google"))
    parser.add_argument("--principal", choices=("validator", "investigator"), required=True)
    args = parser.parse_args(argv)
    env = os.environ
    capture = Capture(CAPTURE_ROOT / f"{args.principal}-principals", args.vendor)
    probes: dict[str, Callable[[Mapping[str, str], str, Capture], None]] = {
        "frappe": probe_frappe,
        "jira": probe_jira,
        "google": probe_google,
    }

    def run() -> None:
        probes[args.vendor](env, args.principal, capture)

    capture.data["started_at"] = datetime.now(UTC).isoformat()
    try:
        run()
    except ConfigurationError as error:  # nothing was probed: no capture, the message says what
        print(f"configuration: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # the failure is the finding: capture, then re-raise
        capture.data["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        if capture.data["checks"]:
            try:
                print(f"capture: {capture.write()}")
            except RuntimeError as refused:
                print(f"capture refused: {refused}", file=sys.stderr)
    return 0 if capture.data["outcome"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
