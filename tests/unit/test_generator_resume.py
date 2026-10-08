"""Resume: a sealed pending world's two truth objects rebuild the very world and bundle that
were sealed, through the same compose and bundle, the record read by the truth manifest's one
decoder; and every proof refuses by name — no object, another generator version, a truth
manifest the spec does not cite, a version the rebuilt realization does not match."""

import traceback
from datetime import date

import pytest

from leaveimpact.adapters.object_store.layout import truth_manifest_key, world_spec_key
from leaveimpact.core.ids import WorldVersion
from leaveimpact.generator.resume import ResumeRefused, resume_world
from leaveimpact.world import (
    DEFAULT_PARAMS,
    GENERATOR_VERSION,
    Bundle,
    Disclosure,
    SemanticWorld,
    WorldSpec,
    assemble_semantic_world,
    assemble_world,
    bundle,
    compose,
    semantic_digest,
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


def fixture_assembly(
    seed: int, params: object, start: object, plan: object, filler: object
) -> SemanticWorld:
    """The stand-in reassembly: the fixture world is one no seed produces on its own."""
    return semantic_world_of(pending_scenario(SkillInComment()))


def truth_store(sealed: Bundle) -> InMemoryObjectStore:
    store = InMemoryObjectStore()
    store.put_if_absent(world_spec_key(sealed.world_version), sealed.world_spec.content)
    store.put_if_absent(truth_manifest_key(sealed.world_version), sealed.truth_manifest.content)
    return store


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
    # The current version's literal, so a bump cannot turn this test into a no-op replace.
    current = f'"generator_version":"{GENERATOR_VERSION}"'.encode()
    older = sealed.world_spec.content.replace(current, b'"generator_version":"0"', 1)
    assert older != sealed.world_spec.content
    store = InMemoryObjectStore()
    store.put_if_absent(world_spec_key(version), older)
    store.put_if_absent(truth_manifest_key(version), sealed.truth_manifest.content)
    with pytest.raises(ResumeRefused, match="resume is not a migration"):
        resume_world(version, store)


def test_a_pooled_world_resumes_through_the_default_assembler_and_reproduces_its_pool() -> None:
    # The generator's own pool, minted inside the assembly from the plan the provenance seals:
    # the default reassembly rebuilds the same pool, and the proof of the semantic digest holds.
    from leaveimpact.world import FillerPlan, SealedLevel, assemble_semantic_world
    from tests.unit.filler_fixture import stand_in_bodies

    plan = FillerPlan(3, 1, (SealedLevel("padded", 2),))
    semantic = assemble_semantic_world(7, DEFAULT_PARAMS, WORLD_START, "golden", plan)
    bodies = stand_in_bodies(semantic)
    world = compose(semantic, bodies, record_for(bodies))
    sealed = bundle(world)
    resumed, rebuilt = resume_world(sealed.world_version, truth_store(sealed))
    assert resumed == world and rebuilt == sealed
    assert resumed.filler_plan == plan and len(resumed.filler) == 3


def test_a_world_with_a_pool_resumes_with_the_filler_prose_lifted() -> None:
    from leaveimpact.world import with_filler
    from tests.unit.filler_fixture import filler_brief, filler_documents, next_numbers

    scenario = pending_scenario(SkillInComment())
    semantic = semantic_world_of(scenario)
    [brief] = scenario.briefs
    pool = filler_documents(semantic, 1, pending=1)
    _, first_clause = next_numbers(semantic)
    filler = filler_brief(pool[0].entity, first_clause + 1)
    padded = with_filler(semantic, pool, briefs=(filler,))
    bodies = {brief.id: BODY, filler.id: "Cover is named before the change window."}
    world = compose(padded, bodies, record_for(bodies))
    sealed = bundle(world)

    def padded_assembly(
        seed: int, params: object, start: object, plan: object, filler: object
    ) -> SemanticWorld:
        return padded

    resumed, rebuilt = resume_world(sealed.world_version, truth_store(sealed), padded_assembly)
    assert resumed == world
    assert rebuilt == sealed


def test_an_embargoed_world_s_mismatch_withholds_both_digests() -> None:
    # The generator's log is public, and the sealed semantic digest is a function of the
    # seed (the generator step's ruling 5, its group 4 review); an open world's names both.
    scenario = pending_scenario(SkillInComment())
    [brief] = scenario.briefs
    prose, record = {brief.id: BODY}, record_for({brief.id: BODY})
    other = assemble_semantic_world(4, DEFAULT_PARAMS, date(2026, 1, 1))

    def another_world(
        seed: int, params: object, start: object, plan: object, filler: object
    ) -> SemanticWorld:
        return other

    embargoed = bundle(compose(semantic_world_of(scenario), prose, record, Disclosure.EMBARGOED))
    with pytest.raises(ResumeRefused, match="digests withheld, the world is embargoed") as refused:
        resume_world(embargoed.world_version, truth_store(embargoed), another_world)
    printed = "".join(traceback.format_exception(refused.value))
    sealed_digest = semantic_digest(semantic_world_of(scenario))
    assert sealed_digest not in printed and semantic_digest(other) not in printed
    open_world = bundle(compose(semantic_world_of(scenario), prose, record))
    with pytest.raises(ResumeRefused, match=f"{semantic_digest(other)} against {sealed_digest}"):
        resume_world(open_world.world_version, truth_store(open_world), another_world)
