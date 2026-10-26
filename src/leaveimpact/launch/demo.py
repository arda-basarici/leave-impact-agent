"""The demo's planner: the frozen inputs of a visitor's run, from the registration the
image ships, the committed price table and the served world's scenario specifications.

The public start (the live-path commands step) admits a run of one scenario under the
demo's cell, the configured system at the configured level under the normal condition,
on the served world. Its inputs are the launcher's own plan (``plan.plan_run``), the same
computation the operator's lifecycle runs, so the admission and the worker's effective
configuration are one computation run twice and a repeat of a start rebuilds
byte-identical inputs. The surface imports neither this package nor the world's codecs
(the import law: the demo surface is beside the launcher and blind to the benchmark), so
what it receives is a planner over scenario ids and the ids it may plan, built here by the
composition root above both shells.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from leaveimpact.agent.log_events import FrozenInputs
from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.pricing import PriceTable
from leaveimpact.core.registration import NORMAL_CONDITION, Registration
from leaveimpact.core.run_record import SystemKind
from leaveimpact.launch.plan import RunCell, plan_run
from leaveimpact.world.scenario import ScenarioSpec

Planner = Callable[[ScenarioId, str, int], FrozenInputs]
"""The frozen inputs of a run of the scenario under the run id and attempt given."""


@dataclass(frozen=True, slots=True)
class DemoPlanning:
    """What the surface's start is handed: the scenario ids of the served world and the
    planner over them."""

    scenarios: frozenset[ScenarioId]
    plan: Planner


def demo_planning(
    registration: Registration,
    *,
    registration_commit: str,
    prices: PriceTable,
    specifications: Iterable[ScenarioSpec],
    world_version: WorldVersion,
    system: SystemKind,
    level: str,
    region: str,
) -> DemoPlanning:
    """The planning of the demo's cell over ``specifications``, the served world's: a
    planner that refuses a scenario id outside them with ``KeyError`` and otherwise plans
    the run as the lifecycle would; what ``plan_run`` refuses (a cell the registration does
    not run, pending roles, a price table without the role's rates), it refuses at the
    first call."""
    by_id = {spec.id: spec for spec in specifications}
    cell = RunCell(system, NORMAL_CONDITION, level)

    def plan(scenario_id: ScenarioId, run_id: str, attempt: int) -> FrozenInputs:
        return plan_run(
            registration,
            registration_commit=registration_commit,
            prices=prices,
            cell=cell,
            spec=by_id[scenario_id],
            world_version=world_version,
            run_id=run_id,
            attempt=attempt,
            region=region,
        ).inputs

    return DemoPlanning(frozenset(by_id), plan)


__all__ = ["DemoPlanning", "Planner", "demo_planning"]
