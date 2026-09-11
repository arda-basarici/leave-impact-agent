"""Every committed cassette is scrubbed — a gate, so the discipline never rests on review alone.

Walks every cassette under ``tests`` and checks two things. Structurally: every
Authorization and Cookie request header reads as the placeholder, no response carries
Set-Cookie, and every secret-shaped key in a JSON body reads as the placeholder.
Textually: no token signature (an Atlassian API token, a Google access or refresh
token, a Frappe token header) and no real sandbox host survives anywhere in the file —
the second net catches a secret that arrived somewhere the structural scrub did not
look. With no cassette committed yet the walk is empty and the test passes vacuously,
the intended state until the first adapter lands.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

import yaml

from tests.recording import FILTERED_HEADERS, REDACTED, SANDBOXES, SECRET_JSON_KEYS

TESTS = Path(__file__).resolve().parents[1]
CASSETTES = sorted(TESTS.rglob("cassettes/**/*.yaml"))

# Signatures a secret carries regardless of where it lands in a file.
_SIGNATURES = {
    "an Atlassian API token": re.compile(r"ATATT3"),
    "a Google access token": re.compile(r"ya29\."),
    "a Google refresh token": re.compile(r"\b1//0"),
    "a Frappe token header": re.compile(r"\btoken \w+:\w+"),
}


def _interactions(path: Path) -> list[dict[str, Any]]:
    loaded: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    interactions: list[dict[str, Any]] = loaded.get("interactions", []) if loaded else []
    return interactions


def _header_values(headers: dict[str, Any], name: str) -> list[str]:
    values: list[str] = []
    for key, value in headers.items():
        if key.lower() != name:
            continue
        values.extend(value if isinstance(value, list) else [value])  # type: ignore[list-item]
    return values


def _secret_values(value: Any) -> list[tuple[str, Any]]:
    """Every (key, value) under a secret-shaped key, at any depth."""
    found: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        items = cast(dict[str, Any], value)
        for key, item in items.items():
            if key in SECRET_JSON_KEYS:
                found.append((key, item))
            found.extend(_secret_values(item))
    elif isinstance(value, list):
        elements = cast(list[Any], value)
        for item in elements:
            found.extend(_secret_values(item))
    return found


def _json_body(body: Any) -> Any:
    raw: Any = cast(dict[str, Any], body).get("string") if isinstance(body, dict) else body
    if not isinstance(raw, bytes | str) or not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def test_cassettes_carry_no_secret() -> None:
    problems: list[str] = []
    for path in CASSETTES:
        where = path.relative_to(TESTS).as_posix()
        for number, interaction in enumerate(_interactions(path), start=1):
            request: dict[str, Any] = interaction.get("request", {})
            response: dict[str, Any] = interaction.get("response", {})
            for name in FILTERED_HEADERS:
                for value in _header_values(request.get("headers", {}), name):
                    if value != REDACTED:
                        problems.append(f"{where} #{number}: request header {name} not redacted")
            if _header_values(response.get("headers", {}), "set-cookie"):
                problems.append(f"{where} #{number}: response carries Set-Cookie")
            for body in (request.get("body"), response.get("body")):
                for key, value in _secret_values(_json_body(body)):
                    if value not in (None, REDACTED):
                        problems.append(f"{where} #{number}: JSON key {key} not redacted")
    assert not problems, "secrets survived scrubbing:\n" + "\n".join(problems)


def test_cassettes_carry_no_token_signature_or_real_host() -> None:
    real_hosts = [
        urlsplit(sandbox.real_base_url).hostname or ""
        for sandbox in SANDBOXES
        if sandbox.real_base_url
    ]
    problems: list[str] = []
    for path in CASSETTES:
        where = path.relative_to(TESTS).as_posix()
        text = path.read_text(encoding="utf-8")
        for what, signature in _SIGNATURES.items():
            if signature.search(text):
                problems.append(f"{where}: carries {what}")
        for host in real_hosts:
            if host and host in text:
                problems.append(f"{where}: names a real sandbox host")
    assert not problems, "\n".join(problems)
