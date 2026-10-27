"""The demo configuration: the committed file is of the declared shape in its one written
form, names the golden world and never the measurement world, names the committed
registration by its digest and one of its cells by system and level, keeps live runs off,
and the decoder refuses what the file must not say."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import cast

import pytest

from leaveimpact.app.config import (
    DEMO,
    DEMO_CONFIGURATION_FORMAT,
    DemoConfiguration,
    committed_configuration,
    committed_configuration_bytes,
    decode_demo_configuration,
    demo_configuration_bytes,
    encode_demo_configuration,
)
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes
from leaveimpact.core.run_record import SystemKind
from tests.unit.registration_fixture import COMMITTED, COMMITTED_FILE

# The golden world the demo serves (FINDINGS: generator version 14, two verdicts); the
# measurement world is the registration's and stays embargoed.
GOLDEN_WORLD = "7b806ed6f405e2d4be39cd02e6f6e99353917c9904cac709cc8b4fee1cd83ad4"


def test_the_committed_configuration_is_the_rulings_values_in_one_written_form() -> None:
    configuration = committed_configuration(DEMO)
    assert configuration.served_world_version == GOLDEN_WORLD
    assert configuration.frappe_base_url == "https://hr-w3.ardabasarici.dev"
    assert configuration.system is SystemKind.AGENT and configuration.level == "base"
    assert configuration.region == "eu-central-1"
    assert configuration.ledger_id == "ledger-demo"
    assert configuration.daily_admissions == 5
    assert configuration.approval_wait_seconds == 15 * 60
    assert configuration.attempt_wall_seconds == 10 * 60
    assert configuration.live_runs is False
    assert demo_configuration_bytes(configuration) == committed_configuration_bytes(DEMO)


def test_the_served_world_is_never_the_measurement_world() -> None:
    """The amendment to the world's admission: the allowlist of one must not name the
    world the registration measures, whose runs stay embargoed."""
    assert committed_configuration().served_world_version != COMMITTED.world.version


def test_the_registration_digest_names_the_committed_registration_and_a_cell_of_it() -> None:
    """The digest is the SHA-256 of the committed registration's bytes, the one the public
    results also record; the system and level form a registered cell under the normal
    condition, so a visitor's run is admitted to a cell the registration knows."""
    configuration = committed_configuration()
    digest = hashlib.sha256(COMMITTED_FILE.read_bytes()).hexdigest()
    assert configuration.registration_digest == digest
    assert configuration.ledger_id != "ledger-development"
    places = {(cell.system, cell.condition, cell.level) for cell in COMMITTED.cells}
    assert (configuration.system, "normal", configuration.level) in places


def _data(**changes: object) -> JsonObject:
    data = dict(encode_demo_configuration(committed_configuration()))
    data.update(changes)
    return data


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"format_version": 1}, "format 2, got 1"),
        ({"extra": 1}, "surplus ['extra']"),
        ({"served_world_version": "7b80"}, "the served world version is a SHA-256"),
        ({"registration_digest": "X" * 64}, "the registration digest is a SHA-256"),
        ({"system": "investigator"}, "system is one of"),
        ({"level": " "}, "the registered level is a non-empty identifier"),
        ({"region": ""}, "the region is a non-empty identifier"),
        ({"ledger_id": ""}, "the demo's ledger id is a non-empty identifier"),
        ({"daily_admissions": 0}, "the daily admissions"),
        ({"daily_admissions": True}, "daily_admissions is an integer, got bool"),
        ({"approval_wait_seconds": -1}, "the approval wait"),
        ({"attempt_wall_seconds": 0}, "the attempt's wall bound"),
        ({"live_runs": "false"}, "live_runs is a boolean, got str"),
        ({"frappe_base_url": "http://hr-w3.ardabasarici.dev"}, "an https URL"),
        ({"frappe_base_url": "https://hr-w3.ardabasarici.dev/"}, "without a trailing slash"),
    ],
)
def test_the_decoder_refuses_what_the_file_must_not_say(changes: JsonObject, message: str) -> None:
    with pytest.raises(ValueError, match=message.replace("[", r"\[").replace("(", r"\(")):
        decode_demo_configuration(canonical_bytes(_data(**changes)))


def test_a_missing_field_is_named() -> None:
    data = _data()
    del data["ledger_id"]
    with pytest.raises(ValueError, match=r"missing \['ledger_id'\]"):
        decode_demo_configuration(json.dumps(data))


def test_the_type_refuses_what_the_decoder_would_before_a_file_states_it() -> None:
    """The constructor holds the value checks, so a configuration built in code is held to
    the file's bar."""
    configuration = committed_configuration()
    with pytest.raises(ValueError, match="the daily admissions"):
        replace(configuration, daily_admissions=0)
    with pytest.raises(ValueError, match="the served world version"):
        replace(configuration, served_world_version=WorldVersion("golden"))
    assert decode_demo_configuration(demo_configuration_bytes(configuration)) == configuration
    assert cast(int, encode_demo_configuration(configuration)["format_version"]) == (
        DEMO_CONFIGURATION_FORMAT
    )


def test_a_live_configuration_round_trips_with_the_flag_on() -> None:
    live = replace(committed_configuration(), live_runs=True)
    assert isinstance(live, DemoConfiguration)
    assert decode_demo_configuration(demo_configuration_bytes(live)).live_runs is True
