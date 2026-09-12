"""The bundle of a world: three canonical artifacts whose digests the world spec cross-cites, a
world version over their realized bytes, the agent-visible file carrying legitimate run inputs
and no evaluator-only truth — and the snapshot pair: a reference seed's world version recorded
beside the generator version, so a changed realization with an unchanged version fails the
suite and re-cutting the pair is the deliberate act that accompanies a bump."""

import json
from datetime import date

import pytest

from leaveimpact.world import (
    DEFAULT_PARAMS,
    GENERATOR_VERSION,
    SCENARIO_SPECS,
    TRUTH_MANIFEST,
    WORLD_SPEC,
    Bundle,
    GeneratorVersion,
    WorldSpec,
    assemble_world,
    bundle,
    canonical_bytes,
    world_version,
)

WORLD_START = date(2026, 1, 1)
REFERENCE_SEED = 7

# The snapshot pair. Re-cut both together, on purpose, after inspecting what the generator
# now produces: bump GENERATOR_VERSION in world/version.py and record the new hash here.
SNAPSHOT_VERSION = GeneratorVersion("4")
SNAPSHOT_WORLD_VERSION = "c79ef68c964a1caaaea8bbd2ebf36381258139816cd7d25ad9028e49905f0944"


@pytest.fixture(scope="module")
def world() -> WorldSpec:
    return assemble_world(REFERENCE_SEED, DEFAULT_PARAMS, WORLD_START)


@pytest.fixture(scope="module")
def sealed(world: WorldSpec) -> Bundle:
    return bundle(world)


def test_the_reference_world_matches_the_snapshot_pair(sealed: Bundle) -> None:
    assert GENERATOR_VERSION == SNAPSHOT_VERSION, (
        "the generator version moved without re-cutting the reference world: inspect the "
        "bundle for seed 7, then record its world version beside the new generator version"
    )
    assert sealed.world_version == SNAPSHOT_WORLD_VERSION, (
        f"the reference world's realization changed under generator version {GENERATOR_VERSION}: "
        "a change to the organization, the plan, a class, a modifier, the slices or the "
        "serialization moved the bytes; bump GENERATOR_VERSION and re-cut the snapshot pair "
        "together, never the hash alone"
    )


def test_the_world_spec_cites_the_other_two_files_by_digest(sealed: Bundle) -> None:
    spec = json.loads(sealed.world_spec.content)
    assert spec["artifact"] == WORLD_SPEC
    assert spec["artifacts"] == {
        SCENARIO_SPECS: sealed.scenario_specs.digest,
        TRUTH_MANIFEST: sealed.truth_manifest.digest,
    }
    assert spec["provenance"]["generator_version"] == GENERATOR_VERSION
    assert spec["provenance"]["seed"] == REFERENCE_SEED
    assert len(spec["plan"]) == len(spec["slices"]) == len(spec["scenarios"]) == 10


def test_the_world_spec_carries_every_planting_dated_and_each_stable_interval(
    sealed: Bundle, world: WorldSpec
) -> None:
    spec = json.loads(sealed.world_spec.content)
    for row, scenario in zip(spec["scenarios"], world.scenarios, strict=True):
        assert row["scenario_id"] == scenario.spec.id
        assert row["stable_interval"] == {
            "start": scenario.key.stable_interval.start.isoformat(),
            "end": scenario.key.stable_interval.end.isoformat(),
        }
        assert len(row["owned"]["leaves"]) == len(scenario.owned.leaves)
        assert all("observable_from" in planted for planted in row["owned"]["leaves"])
    for word in (b"must_assess", b"outcome", b"distractor", b"required_sources", b"verdict"):
        assert word not in sealed.world_spec.content


def test_the_version_names_the_realization_and_never_sits_inside_it(sealed: Bundle) -> None:
    assert sealed.world_version == world_version(sealed.artifacts)
    assert sealed.world_version not in {a.digest for a in sealed.artifacts}
    for artifact in sealed.artifacts:
        assert sealed.world_version.encode() not in artifact.content
    # A single byte in any file moves the version.
    tampered = tuple(
        artifact.__class__(artifact.name, artifact.content + b" ", artifact.digest)
        for artifact in sealed.artifacts
    )
    assert world_version(tampered) != sealed.world_version


def test_the_agent_visible_file_carries_run_inputs_and_no_evaluator_truth(sealed: Bundle) -> None:
    specs = json.loads(sealed.scenario_specs.content)
    assert specs["artifact"] == SCENARIO_SPECS
    assert {tuple(sorted(row)) for row in specs["scenarios"]} == {
        ("id", "leave_id", "now", "reference_timezone", "window")
    }
    for word in (b"must_assess", b"outcome", b"distractor", b"required_sources", b"verdict"):
        assert word not in sealed.scenario_specs.content


def test_the_truth_manifest_holds_keys_authored_facts_and_the_dated_fact_base_and_no_planting(
    sealed: Bundle, world: WorldSpec
) -> None:
    truth = json.loads(sealed.truth_manifest.content)
    assert truth["artifact"] == TRUTH_MANIFEST
    assert len(truth["scenarios"]) == len(world.scenarios)
    for record, scenario in zip(truth["scenarios"], world.scenarios, strict=True):
        assert set(record) == {"key", "authored_facts"}
        assert record["key"]["scenario_id"] == scenario.key.scenario_id
        assert len(record["key"]["impacts"]) == len(scenario.key.impacts)
        # One home per fact: the plantings and the stable interval are the world spec's.
        assert "stable_interval" not in record["key"]
    assert len(truth["facts"]["facts"]) == len(world.facts.facts)
    assert all("observable_from" in fact for fact in truth["facts"]["facts"])


def test_canonical_bytes_are_compact_ordered_and_utf8(sealed: Bundle) -> None:
    assert canonical_bytes({"b": 1, "a": "é"}) == '{"b":1,"a":"é"}'.encode()
    assert bundle(assemble_world(REFERENCE_SEED, DEFAULT_PARAMS, WORLD_START)) == sealed
