"""One OAuth consent under the generator's two Calendar scopes, as authorized-user JSON.

The read principals' ceremony (M2 build plan step 0, ruling 3b of 2026-09-24): Calendar
is the recorded exception, both readers holding the generator's grant, and each consumer
store gets its own refresh token under the generator's Desktop client. One run of this
helper is one such token:

    uv run --with google-auth-oauthlib python probes/read-principals/consent.py

with ``LEAVE_IMPACT_CONSENT_CLIENT_SECRET_FILE`` naming the client's downloaded JSON and
``LEAVE_IMPACT_CONSENT_OUTPUT_FILE`` where the authorized-user JSON goes (client id,
client secret, refresh token: the shape ``CalendarCredential.from_authorized_user_info``
reads). The scopes are fixed to ``calendar.app.created`` and ``calendar.freebusy``, the
generator's pair, both non-sensitive; ``include_granted_scopes`` is sent as false so the
request never merges with another grant, and ``prompt=consent`` forces the consent
screen so a refresh token is issued for a client the account already knows. Nothing is
printed but the granted scopes and the output path.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar.app.created",
    "https://www.googleapis.com/auth/calendar.freebusy",
]


def main() -> int:
    client_secret = Path(os.environ["LEAVE_IMPACT_CONSENT_CLIENT_SECRET_FILE"])
    output = Path(os.environ["LEAVE_IMPACT_CONSENT_OUTPUT_FILE"])
    if output.exists():
        print(f"{output} exists; a consent is never overwritten", file=sys.stderr)
        return 1
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    credentials = flow.run_local_server(port=0, include_granted_scopes="false", prompt="consent")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(credentials.to_json(), encoding="utf-8")
    print(f"granted scopes: {sorted(credentials.scopes or [])}")
    print(f"written: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
