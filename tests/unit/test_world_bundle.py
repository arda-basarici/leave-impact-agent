"""The bundle of a world: three canonical artifacts whose digests the world spec cross-cites, a
world version over their realized bytes, the agent-visible file carrying legitimate run inputs
and no evaluator-only truth, the briefs and the materialization record in the evaluator-only
file and nowhere else — and the snapshot pair: a reference seed's semantic digest recorded
beside the generator version, so a changed meaning with an unchanged version fails the suite
and re-cutting the pair is the deliberate act that accompanies a bump."""

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
    assemble_semantic_world,
    assemble_world,
    bundle,
    canonical_bytes,
    compose,
    semantic_digest,
    world_version,
)
from leaveimpact.world.artifacts import document_bytes
from leaveimpact.world.briefs import CommentTarget
from tests.unit.prose_fixture import pending_scenario, record_for, semantic_world_of

WORLD_START = date(2026, 1, 1)
REFERENCE_SEED = 7

# The snapshot pair. Re-cut both together, on purpose, after inspecting what the generator
# now produces: bump GENERATOR_VERSION in world/version.py and record the new digest here.
# The semantic digest and not the world version, since the prose step: two runs of one seed
# share the former and differ in the latter by design.
SNAPSHOT_VERSION = GeneratorVersion("7")
SNAPSHOT_SEMANTIC_DIGEST = "4a4c1dd9329383d5b7ba03607b9c4714d07e8ec693d0bf50fbed83425c656d2f"


@pytest.fixture(scope="module")
def world() -> WorldSpec:
    return assemble_world(REFERENCE_SEED, DEFAULT_PARAMS, WORLD_START)


@pytest.fixture(scope="module")
def sealed(world: WorldSpec) -> Bundle:
    return bundle(world)


def test_the_reference_world_matches_the_snapshot_pair(world: WorldSpec) -> None:
    assert GENERATOR_VERSION == SNAPSHOT_VERSION, (
        "the generator version moved without re-cutting the reference world: inspect the "
        "semantic world for seed 7, then record its digest beside the new generator version"
    )
    semantic = assemble_semantic_world(REFERENCE_SEED, DEFAULT_PARAMS, WORLD_START)
    assert world.semantic_digest == semantic_digest(semantic)
    assert world.semantic_digest == SNAPSHOT_SEMANTIC_DIGEST, (
        f"the reference world's meaning changed under generator version {GENERATOR_VERSION}: "
        "a change to the organization, the plan, a class, a modifier, the slices, the briefs "
        "or the serialization moved the semantic digest; bump GENERATOR_VERSION and re-cut "
        "the snapshot pair together, never the digest alone"
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
    assert spec["provenance"]["plan_name"] == "tier1"
    assert spec["provenance"]["semantic_digest"] == SNAPSHOT_SEMANTIC_DIGEST
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
        assert set(record) == {"key", "authored_facts", "briefs"}
        assert record["key"]["scenario_id"] == scenario.key.scenario_id
        assert len(record["key"]["impacts"]) == len(scenario.key.impacts)
        assert record["briefs"] == []  # the structured tier writes no prose
        # One home per fact: the plantings and the stable interval are the world spec's.
        assert "stable_interval" not in record["key"]
    assert len(truth["facts"]["facts"]) == len(world.facts.facts)
    assert all("observable_from" in fact for fact in truth["facts"]["facts"])
    assert truth["materialization"] is None  # no model wrote anything


def test_the_briefs_and_the_record_seal_in_the_truth_manifest_and_nowhere_else() -> None:
    scenario = pending_scenario()
    [brief] = scenario.briefs
    body = "Deniz has been running the Kafka side of the retry-queue migration."
    composed = compose(semantic_world_of(scenario), {brief.id: body}, record_for({brief.id: body}))
    sealed = bundle(composed)
    truth = json.loads(sealed.truth_manifest.content)
    [row] = truth["scenarios"]
    [encoded] = row["briefs"]
    assert isinstance(brief.target, CommentTarget)
    assert encoded["target"] == {
        "kind": "comment",
        "id": brief.id,
        "work_item_id": brief.target.work_item_id,
        "position": 0,
        "world_date": "2026-03-01",
        "author_id": brief.target.author_id,
    }
    assert encoded["register"] == "ticket_comment"
    assert [r["role"] for r in encoded["required"]] == ["answer_changing"]
    assert {form["kind"] for form in encoded["namespace"]["forms"]} >= {"employee", "skill"}
    record = truth["materialization"]
    assert record["attempt_cap"] == 4
    assert [t["target_id"] for t in record["targets"]] == [brief.id]
    assert record["writer"]["settings"] == [{"name": "temperature", "value": 0.7}]
    # The world spec carries the composed comment and nothing of how it was accepted; the
    # agent-visible surfaces carry neither.
    spec = json.loads(sealed.world_spec.content)
    [planted] = spec["scenarios"][0]["owned"]["work_items"]
    assert planted["record"]["comments"][0]["text"].endswith(body)
    private = (b"materialization", b"briefs", b"propositions", b"accepted_body_digest")
    surfaces: list[bytes] = [sealed.world_spec.content, sealed.scenario_specs.content]
    surfaces.extend(document_bytes(p.entity) for p in composed.scenarios[0].owned.documents)
    for content in surfaces:
        for word in private:
            assert word not in content
    # The version covers the record: another accepted body is another world with one meaning.
    twice = {brief.id: body + " Twice."}
    other = compose(semantic_world_of(scenario), twice, record_for(twice))
    assert bundle(other).world_version != sealed.world_version
    assert other.semantic_digest == composed.semantic_digest


def test_canonical_bytes_are_compact_ordered_and_utf8(sealed: Bundle) -> None:
    assert canonical_bytes({"b": 1, "a": "é"}) == '{"b":1,"a":"é"}'.encode()
    assert bundle(assemble_world(REFERENCE_SEED, DEFAULT_PARAMS, WORLD_START)) == sealed
