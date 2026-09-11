"""Cassette discipline: where a sandbox lives, and what never enters a committed cassette.

Adapter integration tests replay recorded HTTP (vcrpy through pytest-recording), and the
same tests re-record against the real sandboxes under a record mode (``just
test-record``). Two things have to hold for a cassette to be committable, and both live
here so every recorded test inherits them through the ``vcr_config`` fixture in
``conftest``.

**The host.** A sandbox is addressed by an environment variable when recording and by a
placeholder host otherwise. The request scrub rewrites the real host to the placeholder
before a request is written or matched, so the committed cassette names no real site,
and a replay — whose requests already carry the placeholder, because the test built the
adapter without the variable — matches it. The sandbox sites are the stream's, not the
repo's, the same rule the probes' captures followed. The gate for this is structural:
every request in a committed cassette must address a host on ``ALLOWED_CASSETTE_HOSTS``
— the placeholders and Google's public API hosts — because CI does not know the real
sites and a check that needed them would pass vacuously there (a review finding).

**The secrets.** Authorization and cookie request headers are filtered by name; the
form fields of a Google token refresh (the client secret, the refresh token) are filtered
by name; a JSON response body has its secret-shaped keys — an access token, a refresh
token, an identity token, a client secret, an API key or secret, an account email —
replaced before the body is written; and a response's Set-Cookie header is dropped
outright. The cassette-safety unit test walks every committed cassette and fails the
build if a secret-shaped value survived: the scrub is the mechanism, the test is the
gate, and neither rests on review alone.

Network access is blocked for every test by default (``--block-network`` in the
pytest options, the loopback and the Compose service name allowed for PostgreSQL), so
only a vcr-marked test under a record mode ever reaches a sandbox. The block patches
Python-level socket connects, which is exactly the HTTP paths — httpx, requests, the
Google client's httplib2 — and not psycopg's C library, which the allow-list covers
anyway.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urlsplit

REDACTED = "REDACTED"
FILTERED_HEADERS = ("authorization", "cookie")
FILTERED_FORM_FIELDS = ("client_secret", "refresh_token")
SECRET_JSON_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
        "api_key",
        "api_secret",
        "emailAddress",
    }
)


@dataclass(frozen=True, slots=True)
class Sandbox:
    """A real external site named by an environment variable, or its placeholder when unset."""

    env: str
    placeholder: str

    @property
    def real_base_url(self) -> str | None:
        """The site as the environment names it, scheme included, or ``None`` when absent."""
        value = os.environ.get(self.env, "").strip().rstrip("/")
        if not value:
            return None
        return value if "://" in value else f"https://{value}"

    @property
    def base_url(self) -> str:
        """The real site when recording, else the placeholder: where the adapter points."""
        return self.real_base_url or self.placeholder

    @property
    def recording(self) -> bool:
        return self.real_base_url is not None


FRAPPE = Sandbox("LEAVE_IMPACT_FRAPPE_W1_SITE", "https://frappe.sandbox.invalid")
JIRA = Sandbox("LEAVE_IMPACT_JIRA_SITE", "https://jira.sandbox.invalid")
SANDBOXES = (FRAPPE, JIRA)
# Google's endpoints are public and never rewritten; everything else must be a placeholder.
PUBLIC_API_HOSTS = frozenset({"www.googleapis.com", "oauth2.googleapis.com"})
ALLOWED_CASSETTE_HOSTS = PUBLIC_API_HOSTS | frozenset(
    urlsplit(sandbox.placeholder).hostname or "" for sandbox in SANDBOXES
)


def scrub_request(request: Any) -> Any:
    """Rewrite a real sandbox host to its placeholder; applied on record and on match alike.

    The URI and the ``Host`` header both carry it — the header is where the first
    recorded cassette leaked the site after the URI was clean, caught by the gate.
    """
    for sandbox in SANDBOXES:
        real = sandbox.real_base_url
        if not real or not request.uri.startswith(real):
            continue
        request.uri = sandbox.placeholder + request.uri[len(real) :]
        placeholder_host = urlsplit(sandbox.placeholder).hostname or ""
        for name in [name for name in request.headers if name.lower() == "host"]:
            request.headers[name] = placeholder_host
    return request


def scrub_response(response: dict[str, Any]) -> dict[str, Any]:
    """Drop Set-Cookie and redact secret-shaped keys in a JSON body before it is written."""
    headers: dict[str, Any] = response.get("headers", {})
    for name in [name for name in headers if name.lower() == "set-cookie"]:
        del headers[name]
    body: dict[str, Any] = response.get("body", {})
    raw = body.get("string")
    if isinstance(raw, bytes | str):
        try:
            parsed: Any = json.loads(raw)
        except ValueError:
            return response
        redacted = json.dumps(redact(parsed))
        body["string"] = redacted.encode() if isinstance(raw, bytes) else redacted
    return response


def redact(value: Any) -> Any:
    """The same JSON value with every secret-shaped key's value replaced, at any depth.

    >>> redact({"access_token": "ya29.x", "items": [{"id": 1, "api_key": "k"}]})
    {'access_token': 'REDACTED', 'items': [{'id': 1, 'api_key': 'REDACTED'}]}
    """
    if isinstance(value, dict):
        items = cast(dict[str, Any], value)
        return {
            key: (REDACTED if key in SECRET_JSON_KEYS and item is not None else redact(item))
            for key, item in items.items()
        }
    if isinstance(value, list):
        elements = cast(list[Any], value)
        return [redact(item) for item in elements]
    return value


def vcr_config() -> dict[str, Any]:
    """The vcrpy configuration every recorded test runs under."""
    return {
        "filter_headers": [(name, REDACTED) for name in FILTERED_HEADERS],
        "filter_post_data_parameters": [(name, REDACTED) for name in FILTERED_FORM_FIELDS],
        "before_record_request": scrub_request,
        "before_record_response": scrub_response,
        "decode_compressed_response": True,
    }
