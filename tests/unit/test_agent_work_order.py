"""The work order's contract at its first boundary: the caller decodes the files, the order
states the cell, and ``perform`` reads the attempt's state before it builds anything beyond
the run log, so an attempt with no admission is a refusal naming the run and the attempt
with no world store, host or client composed. The composition past that point runs through
the agent's command line in its own suite and over the real stores at the integration
level; this suite holds the seam the command line and the demo's worker share."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from leaveimpact.agent.commands import WorkRequest
from leaveimpact.agent.log_transition import Rules
from leaveimpact.agent.work_order import WorkOrder, perform
from leaveimpact.agent.worker import HumanApproval
from leaveimpact.core.pricing import decode_price_table
from leaveimpact.core.run_record import SystemKind
from leaveimpact.core.run_timing import HarnessRevision, TreeState
from tests.unit.registration_fixture import DRAFT

ROOT = Path(__file__).resolve().parents[2]
PRICES = decode_price_table(json.loads((ROOT / "preregistration" / "prices.json").read_bytes()))
COMMIT = "a" * 40


class _AdmissionlessStore:
    """A store whose attempt holds no admission; the first thing the order reads."""

    def __init__(self) -> None:
        self.loaded: list[tuple[str, int]] = []

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> Any:
        self.loaded.append((run_id, attempt))
        return SimpleNamespace(inputs=None)


def test_an_order_reads_the_admission_first_and_refuses_an_attempt_without_one() -> None:
    order = WorkOrder(
        WorkRequest("run-12", 1, "nonce-1", "launch-1"),
        SystemKind.RULES_ONLY,
        "normal",
        "base",
        COMMIT,
        None,
        "eu-central-1",
        HarnessRevision(COMMIT, TreeState.CLEAN),
        HumanApproval(),
    )
    store = _AdmissionlessStore()
    with pytest.raises(ValueError, match="run run-12 attempt 1 holds no admission"):
        perform(order, DRAFT, PRICES, store=store, rules=Rules(None, None), env={})  # type: ignore[arg-type]
    assert store.loaded == [("run-12", 1)]
