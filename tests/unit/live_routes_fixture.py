"""What the surface's tests hand the services for the live path: the planning over the
publishable fixture's scenarios, the stores as the live rows and the live log sessions, a
window at fork 8's limit unless a test passes its own, and a key minter that counts.
Shared by the unit rigs over the in-memory stores and the integration rigs over the real
ones, which differ only in what they pass."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from leaveimpact.agent.log_events import FrozenInputs
from leaveimpact.app.live import StartKey
from leaveimpact.app.start import Planning
from leaveimpact.app.window import AddressWindow, MemoryWindow
from leaveimpact.core.ids import ScenarioId
from tests.unit.publishable_fixture import SCENARIO
from tests.unit.test_app_start import BASE, OTHER_SCENARIO, key, plan

SCENARIOS = frozenset({SCENARIO, OTHER_SCENARIO})
assert BASE.reservation_pico_usd is not None, "the base admission reserves"
RESERVATION: int = BASE.reservation_pico_usd
"""The reservation the fixture's planner freezes, the base admission's."""
PLANNING = Planning(SCENARIOS, plan, RESERVATION)  # type: ignore[arg-type]
"""The fixture's planner restates the base admission's inputs under the scenario asked."""
DECISION_FORM = {"decision": "approve", "payload_digest": "f" * 64}
"""A well-formed decision the sweep posts to a name nobody started."""


def never_planned(scenario_id: ScenarioId, run_id: str, attempt: int) -> FrozenInputs:
    """A planner no test expects to be called."""
    raise AssertionError("the planner was called")


class Minter:
    """Keys in sequence from one, each remembered, so a test knows what the index minted."""

    def __init__(self) -> None:
        self.minted: list[StartKey] = []

    def __call__(self) -> StartKey:
        minted = key(len(self.minted) + 1)
        self.minted.append(minted)
        return minted


def live_services(
    log: Any,
    store: Any,
    *,
    window: AddressWindow | None = None,
    mint: Callable[[], StartKey] | None = None,
    scenarios: frozenset[ScenarioId] = SCENARIOS,
) -> dict[str, Any]:
    """The live fields of ``Services`` by keyword: ``log`` is a log session or a callable
    making one, ``store`` the app store the two commands write."""
    sessions = log if callable(log) else (lambda: log)
    return {
        "planning": Planning(scenarios, plan, RESERVATION),  # type: ignore[arg-type]
        "live": store,
        "live_logs": sessions,
        "window": MemoryWindow() if window is None else window,
        "mint_key": Minter() if mint is None else mint,
    }


__all__ = ["DECISION_FORM", "PLANNING", "SCENARIOS", "Minter", "live_services", "never_planned"]
