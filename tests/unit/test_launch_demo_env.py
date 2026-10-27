"""The demo planning composed from the service's environment: the registration and the
price table at the paths the image names, the registration's commit the build baked, and
the served world's scenario specifications read from the world store, the planning equal
to the launcher's plan over the same specification; the refusals by name (each variable
missing, a commit that is not forty hex, a file that does not read, a world the store
holds no specs for) and the planner's own refusal surfaced by the probe plan at the
composition, never at a visitor's first request."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leaveimpact.adapters.object_store.layout import scenario_specs_key
from leaveimpact.adapters.object_store.local import LocalObjectReader
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.pricing import decode_price_table
from leaveimpact.core.registration import NORMAL_CONDITION
from leaveimpact.launch.demo import (
    PRICES_FILE,
    REGISTRATION_COMMIT,
    REGISTRATION_FILE,
    demo_planning_from_env,
)
from leaveimpact.launch.plan import RunCell, plan_run
from leaveimpact.world.decoders import decode_scenario_specs
from tests.unit.launch_fixture import SealedDevelopment, seal_development
from tests.unit.publishable_fixture import CONFIGURATION
from tests.unit.registration_fixture import COMMITTED, COMMITTED_FILE

ROOT = Path(__file__).resolve().parents[2]
PRICES_PATH = ROOT / "preregistration" / "prices.json"
COMMIT = "c" * 40


@pytest.fixture(scope="module")
def development(tmp_path_factory: pytest.TempPathFactory) -> SealedDevelopment:
    return seal_development(tmp_path_factory.mktemp("development"))


def environment(development: SealedDevelopment, **changes: str) -> dict[str, str]:
    env = {
        "LEAVE_IMPACT_OBJECT_STORE_ROOT": str(development.root),
        REGISTRATION_FILE: str(COMMITTED_FILE),
        REGISTRATION_COMMIT: COMMIT,
        PRICES_FILE: str(PRICES_PATH),
    }
    env.update(changes)
    return env


def compose(development: SealedDevelopment, env: dict[str, str], **changes: object):  # noqa: ANN201
    fields: dict[str, object] = {
        "world_version": development.version,
        "system": CONFIGURATION.system,
        "level": CONFIGURATION.level,
        "region": CONFIGURATION.region,
    }
    fields.update(changes)
    return demo_planning_from_env(env, **fields)  # type: ignore[arg-type]


def test_the_planning_from_the_environment_is_the_launchers_plan_over_the_stores_specs(
    development: SealedDevelopment,
) -> None:
    planning = compose(development, environment(development))
    stored = LocalObjectReader(development.root / "world").get(
        scenario_specs_key(development.version)
    )
    assert stored is not None
    specifications = decode_scenario_specs(stored.content)
    assert planning.scenarios == frozenset(spec.id for spec in specifications)
    first = min(specifications, key=lambda spec: spec.id)
    expected = plan_run(
        COMMITTED,
        registration_commit=COMMIT,
        prices=decode_price_table(json.loads(PRICES_PATH.read_bytes())),
        cell=RunCell(CONFIGURATION.system, NORMAL_CONDITION, CONFIGURATION.level),
        spec=first,
        world_version=development.version,
        run_id="demo-x",
        attempt=1,
        region=CONFIGURATION.region,
    )
    assert planning.plan(first.id, "demo-x", 1) == expected.inputs


@pytest.mark.parametrize("name", [REGISTRATION_FILE, REGISTRATION_COMMIT, PRICES_FILE])
def test_a_missing_variable_is_named(development: SealedDevelopment, name: str) -> None:
    with pytest.raises(ValueError, match=f"{name} is not set"):
        compose(development, environment(development, **{name: " "}))


def test_a_commit_that_is_not_forty_hex_and_a_file_that_does_not_read_are_refused(
    development: SealedDevelopment, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match="forty-hex git commit"):
        compose(development, environment(development, **{REGISTRATION_COMMIT: "abc123"}))
    missing = str(tmp_path / "prices.none")
    with pytest.raises(ValueError, match=f"{PRICES_FILE} names .* for the price table"):
        compose(development, environment(development, **{PRICES_FILE: missing}))


def test_a_world_the_store_holds_no_specs_for_is_refused_by_its_key(
    development: SealedDevelopment,
) -> None:
    other = WorldVersion("d" * 64)
    with pytest.raises(ValueError, match=scenario_specs_key(other)):
        compose(development, environment(development), world_version=other)


def test_the_planners_own_refusal_surfaces_at_the_composition(
    development: SealedDevelopment, tmp_path: Path
) -> None:
    """A price table without the role's rates in the region is ``plan_run``'s refusal on the
    first plan; the composition plans one scenario so it refuses here, not under a visitor."""
    table = json.loads(PRICES_PATH.read_bytes())
    table["rates"] = []
    empty = tmp_path / "prices.json"
    empty.write_text(json.dumps(table), encoding="utf-8")
    with pytest.raises(ValueError):
        compose(development, environment(development, **{PRICES_FILE: str(empty)}))
