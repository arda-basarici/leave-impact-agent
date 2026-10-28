"""Two settings of the production Compose file read as text: the forwarded-headers subnet
is the platform contract's `web` subnet row, as a literal, so a change to the row starts
here and a drift of the file from the row fails this test rather than the first
visitor's per-address count (the live-path commands step, fork 8); and the
investigator's vendor principals are named on the worker service alone, so the
public-facing web process can never be handed reader credentials it does not use (the
worker service step, fork 8)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB_SUBNET = "172.18.0.0/16"
"""The contract row: the proxy's `web` network, pinned by the platform's cloud-init since
2026-10-24 (`platform/projects/leave-impact/README.md`, row 27)."""


VENDOR_PREFIXES = ("LEAVE_IMPACT_FRAPPE_", "LEAVE_IMPACT_JIRA_", "LEAVE_IMPACT_GOOGLE_")
VENDOR_NAMES = frozenset(
    {
        "LEAVE_IMPACT_FRAPPE_BASE_URL",
        "LEAVE_IMPACT_FRAPPE_API_KEY",
        "LEAVE_IMPACT_FRAPPE_API_SECRET",
        "LEAVE_IMPACT_JIRA_BASE_URL",
        "LEAVE_IMPACT_JIRA_EMAIL",
        "LEAVE_IMPACT_JIRA_TOKEN",
        "LEAVE_IMPACT_GOOGLE_AUTHORIZED_USER_JSON",
    }
)
"""The seven names the investigator's host wiring reads (`adapters.wiring.hosts_from_env`):
the five parameters under /leave-agent/ and the two base URLs."""


def service_environment(name: str) -> dict[str, str]:
    """One service's `environment:` block as name to value, the literal and the
    interpolated alike."""
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    block = re.search(rf"^  {name}:\n(.*?)(?=^  \w+:|^networks:)", text, re.MULTILINE | re.DOTALL)
    assert block is not None, f"compose.yaml names the {name} service"
    return dict(re.findall(r"^      ([A-Z_]+): (.*)$", block.group(1), re.MULTILINE))


def app_environment() -> dict[str, str]:
    return service_environment("app")


def test_the_forwarded_headers_subnet_is_the_contracts_web_row() -> None:
    environment = app_environment()
    assert environment["FORWARDED_ALLOW_IPS"] == WEB_SUBNET
    assert "${" not in environment["FORWARDED_ALLOW_IPS"], (
        "a constant of the contract, not a parameter"
    )


def test_the_vendor_principals_are_named_on_the_worker_service_alone() -> None:
    """Once the deploy exports the principals for the worker, `compose up` would hand them
    to any service that names them; the app names none, by prefix and not only by the
    seven, and the worker names all seven."""
    app = app_environment()
    assert [name for name in app if name.startswith(VENDOR_PREFIXES)] == []
    worker = service_environment("worker")
    assert set(worker) >= VENDOR_NAMES
    assert [name for name in worker if name.startswith(VENDOR_PREFIXES)] == sorted(
        VENDOR_NAMES, key=list(worker).index
    )
