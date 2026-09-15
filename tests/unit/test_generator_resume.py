"""Resume: a sealed pending world's two truth objects rebuild the very world and bundle that
were sealed, through the same compose and bundle; the record round-trips through the generator's
own decoder; and every proof refuses by name — no object, another generator version, a truth
manifest the spec does not cite, a version the rebuilt realization does not match."""

import json
from dataclasses import replace

import pytest

from leaveimpact.adapters.object_store.layout import truth_manifest_key, world_spec_key
from leaveimpact.core.ids import WorldVersion
from leaveimpact.generator.resume import ResumeRefused, resume_world
from leaveimpact.generator.truth_record import decode_materialization
from leaveimpact.world import (
    DEFAULT_PARAMS,
    Bundle,
    GuardName,
    MaterializationMetrics,
    Refusal,
    RefusalReason,
    SemanticWorld,
    WorldSpec,
    assemble_world,
    bundle,
    compose,
)
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.prose_fixture import (
    WORLD_START,
    SkillInComment,
    pending_scenario,
    record_for,
    semantic_world_of,
)

BODY = "Deniz here: I built the Kafka side of the retry queue migration myself."


@pytest.fixture(scope="module")
def sealed_world() -> tuple[WorldSpec, Bundle]:
    scenario = pending_scenario(SkillInComment())
    [brief] = scenario.briefs
    world = compose(semantic_world_of(scenario), {brief.id: BODY}, record_for({brief.id: BODY}))
    return world, bundle(world)


def fixture_assembly(seed: int, params: object, start: object, plan: object) -> SemanticWorld:
    """The stand-in reassembly: the fixture world is one no seed produces on its own."""
    return semantic_world_of(pending_scenario(SkillInComment()))


def truth_store(sealed: Bundle) -> InMemoryObjectStore:
    store = InMemoryObjectStore()
    store.put_if_absent(world_spec_key(sealed.world_version), sealed.world_spec.content)
    store.put_if_absent(truth_manifest_key(sealed.world_version), sealed.truth_manifest.content)
    return store


def test_the_record_round_trips_through_the_generators_decoder(
    sealed_world: tuple[WorldSpec, Bundle],
) -> None:
    world, sealed = sealed_world
    assert decode_materialization(sealed.truth_manifest.content) == world.materialization
    # The fixture's record carries no counters, the shape of every record sealed before
    # they existed: its bytes hold no field for them, so a resume re-derives the same bytes.
    assert "metrics" not in json.loads(sealed.truth_manifest.content)["materialization"]


def test_the_records_counters_round_trip_when_sealed() -> None:
    scenario = pending_scenario(SkillInComment())
    [brief] = scenario.briefs
    counters = MaterializationMetrics(
        **{**dict.fromkeys(MaterializationMetrics.__slots__, 0), "writer_attempts": 5}
    )
    record = replace(record_for({brief.id: BODY}), metrics=counters)
    world = compose(semantic_world_of(scenario), {brief.id: BODY}, record)
    sealed = bundle(world)
    assert json.loads(sealed.truth_manifest.content)["materialization"]["metrics"] == {
        **dict.fromkeys(MaterializationMetrics.__slots__, 0),
        "writer_attempts": 5,
    }
    assert decode_materialization(sealed.truth_manifest.content) == record


def test_a_refusals_reasons_round_trip_and_an_older_row_decodes_them_as_unavailable() -> None:
    scenario = pending_scenario(SkillInComment())
    [brief] = scenario.briefs
    refused = Refusal(
        1,
        GuardName.EXTRACTION,
        2,
        ((RefusalReason.OTHER_CLAIM, 1), (RefusalReason.UNTYPED_PROPOSITION, 1)),
    )
    base = record_for({brief.id: BODY})
    [accepted] = base.targets
    record = replace(base, targets=(replace(accepted, attempts=2, refusals=(refused,)),))
    world = compose(semantic_world_of(scenario), {brief.id: BODY}, record)
    content = bundle(world).truth_manifest.content
    [row] = json.loads(content)["materialization"]["targets"][0]["refusals"]
    assert row["reasons"] == [
        {"reason": "other_claim", "count": 1},
        {"reason": "untyped_proposition", "count": 1},
    ]
    assert decode_materialization(content) == record
    # The measurement world's rows: attempt, guard, count and nothing else.
    older = json.loads(content)
    del older["materialization"]["targets"][0]["refusals"][0]["reasons"]
    decoded = decode_materialization(json.dumps(older))
    assert decoded is not None
    [target] = decoded.targets
    assert target.refusals == (Refusal(1, GuardName.EXTRACTION, 2),)
    assert target.refusals[0].reasons is None


def test_a_world_without_prose_resumes_from_its_seed_alone() -> None:
    world = assemble_world(7, DEFAULT_PARAMS, WORLD_START)
    sealed = bundle(world)
    resumed, rebuilt = resume_world(sealed.world_version, truth_store(sealed))
    assert resumed == world and rebuilt == sealed


def test_a_sealed_version_resumes_to_the_very_world_and_bundle_with_its_prose_lifted(
    sealed_world: tuple[WorldSpec, Bundle],
) -> None:
    world, sealed = sealed_world
    resumed, rebuilt = resume_world(sealed.world_version, truth_store(sealed), fixture_assembly)
    assert resumed == world
    assert rebuilt == sealed


def test_resume_refuses_by_name_when_a_proof_fails(sealed_world: tuple[WorldSpec, Bundle]) -> None:
    _, sealed = sealed_world
    version = sealed.world_version
    with pytest.raises(ResumeRefused, match="no sealed world spec"):
        resume_world(version, InMemoryObjectStore(), fixture_assembly)
    only_spec = InMemoryObjectStore()
    only_spec.put_if_absent(world_spec_key(version), sealed.world_spec.content)
    with pytest.raises(ResumeRefused, match="no sealed truth manifest"):
        resume_world(version, only_spec, fixture_assembly)
    # A truth manifest the spec does not cite.
    swapped = InMemoryObjectStore()
    swapped.put_if_absent(world_spec_key(version), sealed.world_spec.content)
    swapped.put_if_absent(truth_manifest_key(version), sealed.truth_manifest.content + b" ")
    with pytest.raises(ResumeRefused, match="not the one the world spec cites"):
        resume_world(version, swapped, fixture_assembly)
    # A reassembly that means something else.
    with pytest.raises(ResumeRefused, match="reassembled semantic world differs"):
        resume_world(version, truth_store(sealed))
    # A version the rebuilt realization does not match.
    other = WorldVersion("f" * 64)
    misnamed = InMemoryObjectStore()
    misnamed.put_if_absent(world_spec_key(other), sealed.world_spec.content)
    misnamed.put_if_absent(truth_manifest_key(other), sealed.truth_manifest.content)
    with pytest.raises(ResumeRefused, match="does not round-trip to the bundle named"):
        resume_world(other, misnamed, fixture_assembly)


def test_resume_is_not_a_migration(sealed_world: tuple[WorldSpec, Bundle]) -> None:
    _, sealed = sealed_world
    version = sealed.world_version
    older = sealed.world_spec.content.replace(
        b'"generator_version":"6"', b'"generator_version":"5"', 1
    )
    assert older != sealed.world_spec.content
    store = InMemoryObjectStore()
    store.put_if_absent(world_spec_key(version), older)
    store.put_if_absent(truth_manifest_key(version), sealed.truth_manifest.content)
    with pytest.raises(ResumeRefused, match="resume is not a migration"):
        resume_world(version, store)
