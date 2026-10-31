"""The demo's planner: the frozen inputs of a visitor's run, from the registration the
image ships, the committed price table and the served world's scenario specifications.

The public start (the live-path commands step) admits a run of one scenario under the
demo's cell, the configured system at the configured level under the normal condition,
on the served world. Its inputs are the launcher's own plan (``plan.plan_run``), the same
computation the operator's lifecycle runs, so the admission and the worker's effective
configuration are one computation run twice and a repeat of a start rebuilds
byte-identical inputs. The surface imports neither this package nor the world's codecs
(the import law: the demo surface is beside the launcher and blind to the benchmark), so
what it receives is a planner over scenario ids and the ids it may plan, built here for the
composition root above both shells.

``demo_planning_from_env`` is that root's reading of the environment the image and compose
give the service: the registration file and the price table the image ships, the
registration's commit the image was built with (the same value the operator's runner
computes from git, which no container can), and the served world's scenario
specifications from the world store, read once here and never per start. It then plans one
scenario and discards the plan, so what ``plan_run`` refuses at its first call (a cell the
registration does not run, a price table without the role's rates) refuses the service's
start and never a visitor's first request; the read happens under the live flag off too,
so every deploy proves the planner's inputs load before the flag is flipped.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from leaveimpact.adapters.object_store.layout import scenario_specs_key
from leaveimpact.adapters.wiring import world_store_from_env, world_store_reader
from leaveimpact.agent.log_events import FrozenInputs
from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.pricing import PriceTable, decode_price_table
from leaveimpact.core.registration import NORMAL_CONDITION, Registration
from leaveimpact.core.registration_json import decode_registration_bytes
from leaveimpact.core.run_record import SystemKind
from leaveimpact.core.run_timing import require_commit
from leaveimpact.launch.plan import RunCell, plan_run
from leaveimpact.world.decoders import decode_scenario_specs
from leaveimpact.world.scenario import ScenarioSpec

REGISTRATION_FILE = "LEAVEIMPACT_REGISTRATION_FILE"
REGISTRATION_COMMIT = "LEAVEIMPACT_REGISTRATION_COMMIT"
PRICES_FILE = "LEAVEIMPACT_PRICES_FILE"
"""The three names the Dockerfile sets: the registration and the price table at their paths
in the image, and the commit the registration was last changed at, baked at the build; the
surface reads the first under the same name for its own folding."""
PROBE_RUN_ID = "demo-probe"
"""The run id the composition plans once to prove the inputs; the plan is discarded."""

Planner = Callable[[ScenarioId, str, int], FrozenInputs]
"""The frozen inputs of a run of the scenario under the run id and attempt given."""


@dataclass(frozen=True, slots=True)
class DemoPlanning:
    """What the surface's start is handed: the scenario ids of the served world, the planner
    over them, and the reservation a plan under this registration freezes, which does not
    depend on the scenario (``core.pricing.run_reservation`` reads the caps, the role and the
    pricing basis), derived once here by planning the lowest scenario id under a fixed run
    id so the surface need not plan to quote it."""

    scenarios: frozenset[ScenarioId]
    plan: Planner
    reservation_pico_usd: int | None


RESERVATION_FIGURE_RUN = "reservation-figure"
"""The run id the reservation figure is planned under; never admitted, never logged."""


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

    reservation = plan(min(by_id), RESERVATION_FIGURE_RUN, 1).reservation_pico_usd
    return DemoPlanning(frozenset(by_id), plan, reservation)


def demo_planning_from_env(
    env: Mapping[str, str],
    *,
    world_version: WorldVersion,
    system: SystemKind,
    level: str,
    region: str,
) -> DemoPlanning:
    """The demo's planning from the service's environment: the registration file and the
    price table at the paths the image names, the registration's commit the build baked, and
    the served world's scenario specifications read once from the world store the
    environment names; one scenario planned and discarded, so the planner's own refusals
    surface here. ``ValueError`` names the variable that is missing, a file that does not
    read or decode, a commit that is not forty hex, a specs object the store lacks or that
    does not decode, a world with no scenario, or what ``plan_run`` refuses; the store
    wiring's ``ConfigurationError`` and the object reader's own faults (unreachable, access
    refused, misconfigured) pass through."""
    registration = decode_registration_bytes(_read(env, REGISTRATION_FILE, "the registration"))
    commit = require_commit(
        _required(env, REGISTRATION_COMMIT), "the commit the registration was last changed at"
    )
    prices = decode_price_table(json.loads(_read(env, PRICES_FILE, "the price table")))
    reader = world_store_reader(world_store_from_env(env))
    key = scenario_specs_key(world_version)
    stored = reader.get(key)
    if stored is None:
        raise ValueError(f"the world store holds no scenario specs at {key}")
    specifications = decode_scenario_specs(stored.content)
    if not specifications:
        raise ValueError(f"the scenario specs at {key} list no scenario to serve")
    planning = demo_planning(
        registration,
        registration_commit=commit,
        prices=prices,
        specifications=specifications,
        world_version=world_version,
        system=system,
        level=level,
        region=region,
    )
    planning.plan(min(planning.scenarios), PROBE_RUN_ID, 1)
    return planning


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is not set and the demo's planner needs it")
    return value


def _read(env: Mapping[str, str], name: str, what: str) -> bytes:
    path = _required(env, name)
    try:
        return Path(path).read_bytes()
    except OSError as error:
        raise ValueError(f"{name} names {path!r} for {what}: {error}") from error


__all__ = [
    "PRICES_FILE",
    "PROBE_RUN_ID",
    "REGISTRATION_COMMIT",
    "REGISTRATION_FILE",
    "DemoPlanning",
    "Planner",
    "demo_planning",
    "demo_planning_from_env",
]
