"""Calendar probe: one OAuth principal, one secondary calendar per synthetic person.

Pass criterion (probes/README.md, day 1 "calendar"): events on >= 3 synthetic people's
calendars, overlaps listed back via freeBusy.query, the refresh-token lifetime ruled,
the `calendar.app.created` scope tried.

Secrets never enter the repo: the OAuth client JSON and the consent token live in the
directory named by LEAVE_IMPACT_GOOGLE_DIR. Every write is idempotent — calendars are
looked up by name, events carry deterministic ids — so a second run changes nothing,
which rehearses the seed-spike's no-duplicates criterion.

Run:  uv run --with google-api-python-client --with google-auth-oauthlib \
          probes/calendar/probe.py [--scope app-created|app-created+freebusy|full] [--status testing|production]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = {
    "app-created": ["https://www.googleapis.com/auth/calendar.app.created"],
    "app-created+freebusy": [
        "https://www.googleapis.com/auth/calendar.app.created",
        "https://www.googleapis.com/auth/calendar.freebusy",
    ],
    "full": ["https://www.googleapis.com/auth/calendar"],
}
CAPTURE_DIR = Path(__file__).resolve().parents[1] / "captures" / "calendar"
PEOPLE = ["Probe Alice", "Probe Bob", "Probe Carol"]
TZ = "Europe/Istanbul"

# A fixed week so reruns address the same events. Tuesday 13:00–15:00 is the planted
# overlap: Alice + Bob share the customer review while Carol's call starts inside it.
WEEK_START = datetime(2026, 9, 7, tzinfo=UTC)  # a Monday
MEETINGS = [
    ("standup", ["Probe Alice", "Probe Bob", "Probe Carol"], 1, 9, 0, 15),
    ("customer-review", ["Probe Alice", "Probe Bob"], 1, 13, 0, 120),
    ("vendor-call", ["Probe Carol"], 1, 14, 0, 60),
    ("architecture", ["Probe Alice"], 2, 15, 0, 60),
]


def credentials(secret_dir: Path, scope_key: str) -> Credentials:
    token_path = secret_dir / f"token-{scope_key}.json"
    scopes = SCOPES[scope_key]
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        if creds.valid:
            return creds
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
            return creds
    flow = InstalledAppFlow.from_client_secrets_file(str(secret_dir / "client_secret.json"), scopes)
    creds = flow.run_local_server(port=0)
    token_path.write_text(creds.to_json())
    return creds


CALENDAR_MAP = CAPTURE_DIR / "calendars.json"


def ensure_calendar(svc, name: str) -> str:
    # `calendar.app.created` cannot list calendars (finding: calendarList.list -> 403),
    # so the app must remember the ids it created — the generator's manifest will do
    # the same. Remembered ids are verified with calendars.get before reuse.
    known = json.loads(CALENDAR_MAP.read_text()) if CALENDAR_MAP.exists() else {}
    if name in known:
        svc.calendars().get(calendarId=known[name]).execute()
        return known[name]
    created = svc.calendars().insert(body={"summary": name, "timeZone": TZ}).execute()
    known[name] = created["id"]
    CALENDAR_MAP.parent.mkdir(parents=True, exist_ok=True)
    CALENDAR_MAP.write_text(json.dumps(known, indent=2))
    return created["id"]


def event_id(calendar_id: str, key: str) -> str:
    # Calendar ids must be base32hex (a-v, 0-9), 5..1024 chars.
    digest = hashlib.sha1(f"{calendar_id}:{key}".encode()).hexdigest()
    return "".join("0123456789abcdefghijklmnopqrstuv"[int(c, 16)] for c in digest)


def ensure_event(svc, calendar_id: str, key: str, summary: str, start: datetime, minutes: int,
                 participants: list[str]) -> str:
    body = {
        "id": event_id(calendar_id, key),
        "summary": summary,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": (start + timedelta(minutes=minutes)).isoformat()},
        # World facts only — participants are what a colleague could read off the
        # invite. Answer-key facts (importance, expected outcome) never enter here.
        "extendedProperties": {"private": {"participants": ";".join(participants)}},
    }
    try:
        svc.events().insert(calendarId=calendar_id, body=body).execute()
        return "created"
    except HttpError as err:
        if err.resp.status == 409:
            return "exists"
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=SCOPES, default="app-created")
    parser.add_argument("--status", choices=["testing", "production"], required=True,
                        help="the consent screen's publishing status at run time (recorded)")
    args = parser.parse_args()

    secret_dir = Path(os.environ["LEAVE_IMPACT_GOOGLE_DIR"])
    creds = credentials(secret_dir, args.scope)
    svc = build("calendar", "v3", credentials=creds)

    calendars = {name: ensure_calendar(svc, name) for name in PEOPLE}
    print("calendars:", json.dumps(calendars, indent=2))

    results = []
    for key, who, day, hour, minute, minutes in MEETINGS:
        start = WEEK_START + timedelta(days=day, hours=hour, minutes=minute)
        for person in who:
            outcome = ensure_event(svc, calendars[person], key, key, start, minutes, who)
            results.append({"person": person, "event": key, "outcome": outcome})
    print("events:", json.dumps(results, indent=2))

    window = {"timeMin": WEEK_START.isoformat(), "timeMax": (WEEK_START + timedelta(days=7)).isoformat()}
    busy = svc.freebusy().query(body={**window, "items": [{"id": cid} for cid in calendars.values()]}).execute()
    listings = {name: svc.events().list(calendarId=cid, singleEvents=True, orderBy="startTime", **window)
                .execute().get("items", []) for name, cid in calendars.items()}

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    (CAPTURE_DIR / f"run-{args.scope}-{args.status}.json").write_text(json.dumps({
        "scope": SCOPES[args.scope], "consent_screen_status": args.status,
        "has_refresh_token": bool(creds.refresh_token),
        "calendars": calendars, "events": results, "freebusy": busy["calendars"],
        "listings": {n: [(e["summary"], e["start"], e["end"]) for e in items] for n, items in listings.items()},
    }, indent=2, default=str), encoding="utf-8")
    print("freebusy:", json.dumps(busy["calendars"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
