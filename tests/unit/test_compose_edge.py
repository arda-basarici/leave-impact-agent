"""The edge's one setting in the production Compose file: the forwarded-headers subnet is
the platform contract's `web` subnet row, as a literal, so a change to the row starts here
and a drift of the file from the row fails this test rather than the first visitor's
per-address count (the live-path commands step, fork 8)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB_SUBNET = "172.18.0.0/16"
"""The contract row: the proxy's `web` network, pinned by the platform's cloud-init since
2026-10-24 (`platform/projects/leave-impact/README.md`, row 27)."""


def app_environment() -> dict[str, str]:
    """The app service's `environment:` block as name to value, the literal and the
    interpolated alike."""
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    block = re.search(r"^  app:\n(.*?)^  postgres:", text, re.MULTILINE | re.DOTALL)
    assert block is not None, "compose.yaml names the app service before postgres"
    return dict(re.findall(r"^      ([A-Z_]+): (.*)$", block.group(1), re.MULTILINE))


def test_the_forwarded_headers_subnet_is_the_contracts_web_row() -> None:
    environment = app_environment()
    assert environment["FORWARDED_ALLOW_IPS"] == WEB_SUBNET
    assert "${" not in environment["FORWARDED_ALLOW_IPS"], (
        "a constant of the contract, not a parameter"
    )
