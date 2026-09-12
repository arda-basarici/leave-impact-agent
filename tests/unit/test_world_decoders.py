"""The world spec and the scenario specs read back from their sealed bytes — three separate
claims over one value: the projection of the assembled world is the expected value, decoding an
encoding yields the value, encoding a decoding of the sealed bytes yields the bytes — and the
decoders' strictness: a surplus field, a foreign id, a wrong discriminator, a malformed digest, a
duplicate scenario, an instant without its offset, each refused naming what was expected."""

import json
from datetime import date
from typing import cast
from zoneinfo import ZoneInfo

import pytest

from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.world import (
    DEFAULT_PARAMS,
    Bundle,
    PlantedWorldSpec,
    WorldSpec,
    assemble_world,
    bundle,
    canonical_bytes,
    decode_scenario_specs,
    decode_world_spec,
    encode_scenario_specs,
    encode_world_spec,
    planted_world_spec,
)

WORLD_START = date(2026, 1, 1)
REFERENCE_SEED = 7


@pytest.fixture(scope="module")
def world() -> WorldSpec:
    return assemble_world(REFERENCE_SEED, DEFAULT_PARAMS, WORLD_START)


@pytest.fixture(scope="module")
def sealed(world: WorldSpec) -> Bundle:
    return bundle(world)


@pytest.fixture(scope="module")
def planted(world: WorldSpec, sealed: Bundle) -> PlantedWorldSpec:
    return planted_world_spec(world, sealed.scenario_specs.digest, sealed.truth_manifest.digest)


def spec_json(sealed: Bundle) -> JsonObject:
    return cast(JsonObject, json.loads(sealed.world_spec.content))


# --- The three claims ---------------------------------------------------------------------


def test_the_projection_is_the_planted_world_and_nothing_truth_expects(
    world: WorldSpec, sealed: Bundle, planted: PlantedWorldSpec
) -> None:
    assert planted.org == world.org
    assert planted.plan == world.plan
    assert planted.slices == world.slices
    assert (planted.seed, planted.world_start) == (world.seed, world.world_start)
    for planting, scenario in zip(planted.scenarios, world.scenarios, strict=True):
        assert planting.scenario_id == scenario.spec.id
        assert planting.owned == scenario.owned
        assert planting.stable_interval == scenario.key.stable_interval
    assert planted.scenario_specs_digest == sealed.scenario_specs.digest
    assert planted.truth_manifest_digest == sealed.truth_manifest.digest
    assert not hasattr(planted, "facts") and not hasattr(planted.scenarios[0], "key")


def test_decoding_an_encoding_yields_the_value(planted: PlantedWorldSpec) -> None:
    assert decode_world_spec(canonical_bytes(encode_world_spec(planted))) == planted


def test_encoding_a_decoding_of_the_sealed_bytes_yields_the_bytes(sealed: Bundle) -> None:
    decoded = decode_world_spec(sealed.world_spec.content)
    assert canonical_bytes(encode_world_spec(decoded)) == sealed.world_spec.content
    specs = decode_scenario_specs(sealed.scenario_specs.content)
    assert canonical_bytes(encode_scenario_specs(specs)) == sealed.scenario_specs.content


def test_the_scenario_specs_decode_to_the_records_the_world_assembled(
    world: WorldSpec, sealed: Bundle
) -> None:
    assert decode_scenario_specs(sealed.scenario_specs.content) == tuple(
        scenario.spec for scenario in world.scenarios
    )


def test_an_instant_comes_back_in_its_named_zone(sealed: Bundle) -> None:
    decoded = decode_world_spec(sealed.world_spec.content)
    events = [p.entity for planting in decoded.scenarios for p in planting.owned.events]
    assert events, "the reference world plants at least one meeting"
    assert all(isinstance(event.start.tzinfo, ZoneInfo) for event in events)


# --- Strictness ---------------------------------------------------------------------------


def test_a_surplus_field_is_refused_naming_it(sealed: Bundle) -> None:
    data = spec_json(sealed)
    data["notes"] = "hand-edited"
    with pytest.raises(ValueError, match=r"surplus \['notes'\]"):
        decode_world_spec(canonical_bytes(data))


def test_a_missing_field_is_refused_naming_it(sealed: Bundle) -> None:
    data = spec_json(sealed)
    first = cast(list[JsonObject], data["scenarios"])[0]
    del first["stable_interval"]
    with pytest.raises(ValueError, match=r"missing \['stable_interval'\]"):
        decode_world_spec(canonical_bytes(data))


def test_the_wrong_discriminator_is_refused(sealed: Bundle) -> None:
    with pytest.raises(ValueError, match="the scenario specs is sealed as scenario-specs.json"):
        decode_scenario_specs(sealed.world_spec.content)


def test_a_vendor_key_where_a_world_id_belongs_is_refused(sealed: Bundle) -> None:
    data = spec_json(sealed)
    org = cast(JsonObject, data["org"])
    cast(list[JsonObject], org["employees"])[0]["id"] = "LIA-42"
    with pytest.raises(ValueError, match="'LIA-42' is not a emp_ id"):
        decode_world_spec(canonical_bytes(data))


def test_a_malformed_cited_digest_is_refused(sealed: Bundle) -> None:
    data = spec_json(sealed)
    cast(JsonObject, data["artifacts"])["truth-manifest.json"] = "deadbeef"
    with pytest.raises(ValueError, match="truth_manifest_digest is a SHA-256 hex"):
        decode_world_spec(canonical_bytes(data))


def test_a_duplicated_scenario_is_refused(sealed: Bundle) -> None:
    data = spec_json(sealed)
    for key in ("scenarios", "plan", "slices"):
        rows = cast(list[JsonObject], data[key])
        rows.append(rows[0])
    with pytest.raises(ValueError, match="scenario ids are unique"):
        decode_world_spec(canonical_bytes(data))
    specs = cast(JsonObject, json.loads(sealed.scenario_specs.content))
    rows = cast(list[JsonObject], specs["scenarios"])
    rows.append(rows[0])
    with pytest.raises(ValueError, match="scenario ids are unique"):
        decode_scenario_specs(canonical_bytes(specs))


def test_an_instant_without_its_offset_is_refused(sealed: Bundle) -> None:
    specs = cast(JsonObject, json.loads(sealed.scenario_specs.content))
    now = cast(JsonObject, cast(list[JsonObject], specs["scenarios"])[0]["now"])
    now["at"] = "2026-01-05T09:00:00"
    with pytest.raises(ValueError, match="now carries its offset"):
        decode_scenario_specs(canonical_bytes(specs))


def test_an_unknown_zone_is_refused_naming_it_and_never_leaks_a_key_error(sealed: Bundle) -> None:
    specs = cast(JsonObject, json.loads(sealed.scenario_specs.content))
    now = cast(JsonObject, cast(list[JsonObject], specs["scenarios"])[0]["now"])
    now["timezone"] = "Nowhere/Place"
    with pytest.raises(ValueError, match="not an IANA timezone key: 'Nowhere/Place'"):
        decode_scenario_specs(canonical_bytes(specs))


def test_an_offset_that_is_not_the_zones_is_refused_not_normalized(sealed: Bundle) -> None:
    specs = cast(JsonObject, json.loads(sealed.scenario_specs.content))
    now = cast(JsonObject, cast(list[JsonObject], specs["scenarios"])[0]["now"])
    at = cast(str, now["at"])
    assert at.endswith("+03:00") and now["timezone"] == "Europe/Istanbul"
    now["at"] = at[: -len("+03:00")] + "+00:00"
    with pytest.raises(ValueError, match="now reads .*\\+00:00', which Europe/Istanbul writes as"):
        decode_scenario_specs(canonical_bytes(specs))


def test_a_boolean_where_a_count_belongs_is_refused(sealed: Bundle) -> None:
    data = spec_json(sealed)
    cast(JsonObject, data["provenance"])["interpreter"] = [3, True]
    with pytest.raises(ValueError, match="interpreter is a pair of integers"):
        decode_world_spec(canonical_bytes(data))
