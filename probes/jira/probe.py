"""Jira probe: synthetic employees as a single-select custom field, `assignee` unassigned.

Pass criteria (probes/README.md, day 1 "jira"): (a) a `Synthetic Owner` select field
created over REST on Free, options added, the field on the project's screen; (b) issues
created with an option set, no assignee, a scenario label; (c) exact JQL on the field;
(d) a comment naming a synthetic person round-trips; (e) CSV-imported issues with
backdated `created`/`resolved` read back as-is (`--readback-csv`, after the manual
import); (f) a second run creates no duplicates.

Credentials come from the user environment (`LEAVE_IMPACT_JIRA_SITE` / `_EMAIL` /
`_TOKEN`), read from the Windows User scope when the shell predates them — never from
a file in the tree. Mutable state owned by this principal (field id, option ids, issue
keys) lives in `%USERPROFILE%\\.config\\leave-impact\\jira\\manifest.json`, outside the
captures: evidence is what the systems answered, not what the script remembered. Every
write is find-or-create, so the second run is the no-duplicates criterion itself. A
capture lands on every run under a sequence-stamped name, failures included — the
failure is the finding.

Run:  uv run --with requests probes/jira/probe.py [--readback-csv] [--write-csv]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

PROJECT_KEY = "PRB"
FIELD_NAME = "Synthetic Owner"
PEOPLE = {
    "emp_001": "Probe Alice",
    "emp_002": "Probe Bob",
    "emp_003": "Probe Carol",
}
SCENARIO_LABEL = "scenario-probe-01"
CSV_LABELS = ("scenario-probe-csv", "scenario-probe-csv2")  # run 1 (format mis-set) and run 2
# (slug, owner) — deterministic summaries make reruns find their own issues.
ISSUES = [
    ("migrate-billing-worker", "emp_001"),
    ("rotate-payment-keys", "emp_001"),
    ("vendor-api-timeout", "emp_002"),
    ("onboarding-docs", "emp_003"),
]
COMMENT = "[2026-09-08, Probe Bob] blocked on the vendor API until the sandbox is reset"
CSV_ROWS = [  # summary, owner, created, resolved — the backdating under test
    ("csv-old-incident", "emp_002", "2026-03-03 10:00", "2026-03-05 16:30"),
    ("csv-old-refactor", "emp_001", "2026-05-12 09:15", "2026-05-20 12:00"),
    ("csv-old-audit", "emp_003", "2026-06-01 14:00", "2026-06-02 11:45"),
    # second import, the wizard's own `dd/MMM/yy H:mm` format (the first landed at import
    # time because the format field was left on its default with an AM/PM marker)
    ("csv2-old-incident", "emp_002", "2026-03-03 10:00", "2026-03-05 04:30"),
    ("csv2-old-refactor", "emp_001", "2026-05-12 09:15", "2026-05-20 12:00"),
    ("csv2-old-audit", "emp_003", "2026-06-01 02:00", "2026-06-02 11:45"),
]

CAPTURE_DIR = Path(__file__).resolve().parents[1] / "captures" / "jira"
STATE_DIR = Path(os.environ.get("USERPROFILE", "~")).expanduser() / ".config" / "leave-impact" / "jira"
MANIFEST = STATE_DIR / "manifest.json"


def option_value(emp_id: str) -> str:
    return f"{emp_id} — {PEOPLE[emp_id]}"  # "emp_001 — Probe Alice"


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


class Jira:
    """Thin REST v3 client that records every exchange for the capture."""

    def __init__(self) -> None:
        self.base = user_env("LEAVE_IMPACT_JIRA_SITE").rstrip("/") + "/rest/api/3"
        self.session = requests.Session()
        self.session.auth = (user_env("LEAVE_IMPACT_JIRA_EMAIL"), user_env("LEAVE_IMPACT_JIRA_TOKEN"))
        self.session.headers["Accept"] = "application/json"
        self.log: list[dict[str, Any]] = []

    def call(self, method: str, path: str, *, ok: tuple[int, ...] = (200, 201, 204), **kw: Any) -> Any:
        response = self.session.request(method, self.base + path, **kw)
        body: Any
        try:
            body = response.json() if response.content else None
        except ValueError:
            body = response.text[:500]
        self.log.append({"method": method, "path": path, "status": response.status_code, "response": body})
        if response.status_code not in ok:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {json.dumps(body)[:400]}")
        return body

    def search(self, jql: str, fields: list[str]) -> list[dict[str, Any]]:
        page = self.call("POST", "/search/jql", json={"jql": jql, "fields": fields, "maxResults": 100})
        return page["issues"]


# --- the steps, each find-or-create --------------------------------------------------


def ensure_field(jira: Jira, manifest: dict[str, Any]) -> str:
    fields = jira.call("GET", "/field")
    existing = [f for f in fields if f["name"] == FIELD_NAME and f.get("custom")]
    if existing:
        field_id = existing[0]["id"]
    else:
        created = jira.call(
            "POST",
            "/field",
            json={
                "name": FIELD_NAME,
                "description": "Synthetic employee who owns this work (probe; not an Atlassian user).",
                "type": "com.atlassian.jira.plugin.system.customfieldtypes:select",
                "searcherKey": "com.atlassian.jira.plugin.system.customfieldtypes:multiselectsearcher",
            },
        )
        field_id = created["id"]
    manifest["field_id"] = field_id
    return field_id


def ensure_options(jira: Jira, field_id: str, manifest: dict[str, Any]) -> dict[str, str]:
    contexts = jira.call("GET", f"/field/{field_id}/context")["values"]
    context_id = contexts[0]["id"]
    have = {o["value"]: o["id"] for o in jira.call("GET", f"/field/{field_id}/context/{context_id}/option")["values"]}
    missing = [option_value(e) for e in PEOPLE if option_value(e) not in have]
    if missing:
        added = jira.call(
            "POST",
            f"/field/{field_id}/context/{context_id}/option",
            json={"options": [{"value": v, "disabled": False} for v in missing]},
        )
        have.update({o["value"]: o["id"] for o in added["options"]})
    manifest["context_id"] = context_id
    manifest["options"] = {e: have[option_value(e)] for e in PEOPLE}
    return manifest["options"]


def ensure_on_screens(jira: Jira, field_id: str) -> list[str]:
    """Add the field to every screen the project template created (Free's classic Kanban
    template makes one `PRB: …` screen used for create, edit and view)."""
    screens = [s for s in jira.call("GET", f"/screens?queryString={PROJECT_KEY}")["values"] if s["name"].startswith(f"{PROJECT_KEY}:")]
    placed = []
    for screen in screens:
        tab = jira.call("GET", f"/screens/{screen['id']}/tabs")[0]
        on_tab = {f["id"] for f in jira.call("GET", f"/screens/{screen['id']}/tabs/{tab['id']}/fields")}
        if field_id not in on_tab:
            jira.call("POST", f"/screens/{screen['id']}/tabs/{tab['id']}/fields", json={"fieldId": field_id})
        placed.append(screen["name"])
    if not placed:
        raise RuntimeError(f"no screen named '{PROJECT_KEY}: …' found — the field cannot be set on create")
    return placed


def ensure_issues(jira: Jira, field_id: str, manifest: dict[str, Any]) -> dict[str, str]:
    keys: dict[str, str] = manifest.setdefault("issues", {})
    for slug, owner in ISSUES:
        summary = f"[probe] {slug}"
        found = jira.search(f'project = {PROJECT_KEY} AND summary ~ "\\"{summary}\\""', ["summary"])
        found = [i for i in found if i["fields"]["summary"] == summary]
        if found:
            keys[slug] = found[0]["key"]
            continue
        created = jira.call(
            "POST",
            "/issue",
            json={
                "fields": {
                    "project": {"key": PROJECT_KEY},
                    "issuetype": {"name": "Task"},
                    "summary": summary,
                    "labels": [SCENARIO_LABEL],
                    field_id: {"value": option_value(owner)},
                }
            },
        )
        keys[slug] = created["key"]
    return keys


def check_jql(jira: Jira, field_id: str, keys: dict[str, str]) -> dict[str, Any]:
    """Exact JQL per person must return that person's issues and nothing else."""
    results: dict[str, Any] = {}
    for emp_id in PEOPLE:
        expected = {keys[slug] for slug, owner in ISSUES if owner == emp_id}
        issues = jira.search(
            f'project = {PROJECT_KEY} AND labels = {SCENARIO_LABEL} AND "{FIELD_NAME}" = "{option_value(emp_id)}"',
            ["summary", "assignee", "labels", field_id],
        )
        got = {i["key"] for i in issues}
        results[emp_id] = {
            "expected": sorted(expected),
            "got": sorted(got),
            "exact": got == expected,
            "all_unassigned": all(i["fields"]["assignee"] is None for i in issues),
        }
    return results


def ensure_comment(jira: Jira, issue_key: str) -> dict[str, Any]:
    comments = jira.call("GET", f"/issue/{issue_key}/comment")["comments"]
    texts = [_adf_text(c["body"]) for c in comments]
    if COMMENT not in texts:
        body = {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": COMMENT}]}]}
        jira.call("POST", f"/issue/{issue_key}/comment", json={"body": body})
        comments = jira.call("GET", f"/issue/{issue_key}/comment")["comments"]
        texts = [_adf_text(c["body"]) for c in comments]
    return {"issue": issue_key, "round_trip": COMMENT in texts, "author_is_service_account": [c["author"]["displayName"] for c in comments]}


def _adf_text(body: dict[str, Any]) -> str:
    parts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "text":
                parts.append(node["text"])
            for child in node.get("content", []):
                walk(child)

    walk(body)
    return "".join(parts)


def write_csv(field_id: str) -> Path:
    """The file for the manual import wizard (Settings → System → External System Import
    → CSV); map Created/Resolved to the system date fields, format `yyyy-MM-dd HH:mm`."""
    path = STATE_DIR / "backdated.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Summary", "Issue Type", "Project Key", "Labels", "Status", "Resolution", FIELD_NAME, "Created", "Resolved"])
        for summary, owner, created, resolved in CSV_ROWS[:3]:
            w.writerow([f"[probe] {summary}", "Task", PROJECT_KEY, CSV_LABELS[0], "Done", "Done", option_value(owner), created, resolved])
    return path


def readback_csv(jira: Jira, field_id: str) -> list[dict[str, Any]]:
    labels = ", ".join(CSV_LABELS)
    issues = jira.search(f"labels in ({labels})", ["summary", "project", "created", "resolutiondate", "status", field_id])
    wanted = {f"[probe] {s}": (c, r) for s, _, c, r in CSV_ROWS}
    return [
        {
            "key": i["key"],
            "project": i["fields"]["project"]["key"],
            "summary": i["fields"]["summary"],
            "wanted_created": wanted.get(i["fields"]["summary"], ("?", "?"))[0],
            "created": i["fields"]["created"],
            "wanted_resolved": wanted.get(i["fields"]["summary"], ("?", "?"))[1],
            "resolutiondate": i["fields"]["resolutiondate"],
            "owner": (i["fields"].get(field_id) or {}).get("value"),
        }
        for i in issues
    ]


# --- orchestration -------------------------------------------------------------------


def redact(text: str, jira: Jira) -> str:
    """Targeting identifiers stay out of the public repo: the site host, the account id
    and e-mail of the principal, avatar URLs. Issue keys and synthetic names are evidence."""
    import re

    host = jira.base.split("/rest/")[0]
    text = text.replace(host, "https://<site>")
    text = re.sub(r'"accountId": "[^"]+"', '"accountId": "<accountId>"', text)
    text = re.sub(r'"emailAddress": "[^"]+"', '"emailAddress": "<email>"', text)
    text = re.sub(r'"avatarUrls": \{[^}]*\}', '"avatarUrls": {}', text)
    return re.sub(r"accountId=[0-9a-f:-]+", "accountId=<accountId>", text)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # em dashes on a cp1252 console
    parser = argparse.ArgumentParser()
    parser.add_argument("--readback-csv", action="store_true", help="read the manually imported backdated issues")
    parser.add_argument("--write-csv", action="store_true", help="only write the CSV for the import wizard")
    args = parser.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    mode = "readback-csv" if args.readback_csv else "write-csv" if args.write_csv else "model"
    run_no = len(list(CAPTURE_DIR.glob("run-*.json"))) + 1
    capture: dict[str, Any] = {"run": run_no, "mode": mode, "outcome": "failed"}
    jira = Jira()
    try:
        field_id = ensure_field(jira, manifest)
        capture["field"] = {"id": field_id, "options": ensure_options(jira, field_id, manifest)}
        if args.write_csv:
            capture["csv"] = str(write_csv(field_id))
        elif args.readback_csv:
            capture["csv_readback"] = readback_csv(jira, field_id)
        else:
            capture["screens"] = ensure_on_screens(jira, field_id)
            keys = ensure_issues(jira, field_id, manifest)
            capture["issues"] = keys
            capture["jql"] = check_jql(jira, field_id, keys)
            capture["comment"] = ensure_comment(jira, keys["migrate-billing-worker"])
            capture["issue_count"] = len(jira.search(f"project = {PROJECT_KEY} AND labels = {SCENARIO_LABEL}", ["summary"]))
        capture["outcome"] = "ok"
    except Exception as exc:  # the failure is the finding — capture, then re-raise
        capture["error"] = str(exc)
        raise
    finally:
        capture["exchanges"] = jira.log
        MANIFEST.write_text(json.dumps(manifest, indent=2))
        path = CAPTURE_DIR / f"run-{run_no:02d}-{mode}.json"
        path.write_text(redact(json.dumps(capture, indent=2, ensure_ascii=False), jira), encoding="utf-8")
        print(json.dumps({k: v for k, v in capture.items() if k != "exchanges"}, indent=2, ensure_ascii=False))
        print(f"capture: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
