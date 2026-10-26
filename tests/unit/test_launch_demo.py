"""The demo's planner over the committed registration and price table: the served world's
scenario ids and a plan of the configured cell under the normal condition that is the
lifecycle's own (the run id, the attempt, the served world and the scenario as given, a
reservation made, the registration's commit frozen), identical on a repeat, and a
``KeyError`` for a scenario outside the specifications."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from leaveimpact.core.ids import leave_id, scenario_id
from leaveimpact.core.pricing import decode_price_table
from leaveimpact.core.registration import NORMAL_CONDITION
from leaveimpact.core.worldtime import DateSpan
from leaveimpact.launch.demo import DemoPlanning, demo_planning
from leaveimpact.launch.plan import RunCell, plan_run
from leaveimpact.world.scenario import ScenarioSpec
from tests.unit.publishable_fixture import CONFIGURATION, SERVED
from tests.unit.registration_fixture import COMMITTED

ROOT = Path(__file__).resolve().parents[2]
PRICES = decode_price_table(json.loads((ROOT / "preregistration" / "prices.json").read_bytes()))
COMMIT = "c" * 40
REGION = "eu-central-1"
WINDOW = DateSpan(date(2026, 3, 1), date(2026, 3, 14))
SPECIFICATIONS = (
    ScenarioSpec(
        scenario_id(3), leave_id(1), datetime(2026, 3, 5, 6, tzinfo=UTC), "Europe/Istanbul", WINDOW
    ),
    ScenarioSpec(
        scenario_id(4), leave_id(2), datetime(2026, 3, 6, 6, tzinfo=UTC), "Europe/Istanbul", WINDOW
    ),
)


def planning() -> DemoPlanning:
    return demo_planning(
        COMMITTED,
        registration_commit=COMMIT,
        prices=PRICES,
        specifications=SPECIFICATIONS,
        world_version=SERVED,
        system=CONFIGURATION.system,
        level=CONFIGURATION.level,
        region=REGION,
    )


def test_the_planning_lists_the_ids_and_plans_the_demos_cell_as_the_lifecycle_would() -> None:
    demo = planning()
    assert demo.scenarios == frozenset({scenario_id(3), scenario_id(4)})
    inputs = demo.plan(scenario_id(3), "demo-x", 1)
    assert (inputs.run_id, inputs.attempt) == ("demo-x", 1)
    assert (inputs.context.world_version, inputs.context.scenario_id) == (SERVED, scenario_id(3))
    assert inputs.context.leave_id == leave_id(1) and inputs.context.now == SPECIFICATIONS[0].now
    assert inputs.reservation_pico_usd is not None and inputs.preregistration_commit == COMMIT
    assert inputs.corpus_level == CONFIGURATION.level
    lifecycle = plan_run(
        COMMITTED,
        registration_commit=COMMIT,
        prices=PRICES,
        cell=RunCell(CONFIGURATION.system, NORMAL_CONDITION, CONFIGURATION.level),
        spec=SPECIFICATIONS[0],
        world_version=SERVED,
        run_id="demo-x",
        attempt=1,
        region=REGION,
    )
    assert inputs == lifecycle.inputs


def test_a_repeat_plans_byte_identical_inputs_and_an_unknown_scenario_is_refused() -> None:
    demo = planning()
    assert demo.plan(scenario_id(4), "demo-y", 1) == demo.plan(scenario_id(4), "demo-y", 1)
    with pytest.raises(KeyError):
        demo.plan(scenario_id(9), "demo-z", 1)
