"""The disclosure mark (the generator step's ruling 5): a world is sealed open or embargoed,
the mark rides the composed world and the world spec's provenance and never the semantic
encoding, an open world's file carries no such key and a file sealed before the mark
existed reads as open, and a resume carries the sealed mark into the world it rebuilds."""

import json
from datetime import date
from typing import cast

import pytest

from leaveimpact.adapters.object_store.layout import truth_manifest_key, world_spec_key
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.generator.resume import resume_world
from leaveimpact.world import (
    DEFAULT_PARAMS,
    Disclosure,
    SemanticWorld,
    assemble_semantic_world,
    bundle,
    compose,
    decode_world_spec,
    encode_semantic_world,
    semantic_digest,
)
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.prose_fixture import pending_scenario, record_for, semantic_world_of
from tests.unit.test_generator_resume import BODY, SkillInComment

WORLD_START = date(2026, 1, 1)


@pytest.fixture(scope="module")
def semantic() -> SemanticWorld:
    return assemble_semantic_world(3, DEFAULT_PARAMS, WORLD_START)


def spec_json(content: bytes) -> JsonObject:
    return cast(JsonObject, json.loads(content))


def test_a_world_is_open_unless_composed_embargoed(semantic: SemanticWorld) -> None:
    assert compose(semantic, {}, None).disclosure is Disclosure.OPEN
    embargoed = compose(semantic, {}, None, Disclosure.EMBARGOED)
    assert embargoed.disclosure is Disclosure.EMBARGOED


def test_the_mark_is_in_the_spec_s_provenance_only_when_it_is_an_embargo(
    semantic: SemanticWorld,
) -> None:
    open_spec = spec_json(bundle(compose(semantic, {}, None)).world_spec.content)
    sealed = spec_json(bundle(compose(semantic, {}, None, Disclosure.EMBARGOED)).world_spec.content)
    assert "disclosure" not in cast(JsonObject, open_spec["provenance"])
    assert cast(JsonObject, sealed["provenance"])["disclosure"] == "embargoed"


def test_the_semantic_encoding_and_digest_do_not_see_the_mark(semantic: SemanticWorld) -> None:
    # One seed, one semantic digest, whatever the world is sealed under: resume proves
    # against this digest, and the mark is the recipe's choice, not the seed's.
    open_world = compose(semantic, {}, None)
    embargoed = compose(semantic, {}, None, Disclosure.EMBARGOED)
    assert open_world.semantic_digest == embargoed.semantic_digest == semantic_digest(semantic)
    assert "disclosure" not in cast(JsonObject, encode_semantic_world(semantic)["provenance"])


def test_a_sealed_mark_decodes_and_an_absent_one_reads_open(semantic: SemanticWorld) -> None:
    sealed = bundle(compose(semantic, {}, None, Disclosure.EMBARGOED))
    assert decode_world_spec(sealed.world_spec.content).disclosure is Disclosure.EMBARGOED
    # A file sealed before the mark existed holds no such key and is what an open
    # generator built, not a default: the open world's own file is that shape.
    before = bundle(compose(semantic, {}, None))
    assert decode_world_spec(before.world_spec.content).disclosure is Disclosure.OPEN


def test_a_name_no_mark_has_is_refused(semantic: SemanticWorld) -> None:
    sealed = bundle(compose(semantic, {}, None, Disclosure.EMBARGOED))
    data = spec_json(sealed.world_spec.content)
    cast(JsonObject, data["provenance"])["disclosure"] = "secret"
    with pytest.raises(ValueError, match="disclosure is one of"):
        decode_world_spec(json.dumps(data).encode("utf-8"))


def test_a_resume_carries_the_sealed_mark() -> None:
    scenario = pending_scenario(SkillInComment())
    [brief] = scenario.briefs
    world = compose(
        semantic_world_of(scenario),
        {brief.id: BODY},
        record_for({brief.id: BODY}),
        Disclosure.EMBARGOED,
    )
    sealed = bundle(world)
    store = InMemoryObjectStore()
    store.put_if_absent(world_spec_key(sealed.world_version), sealed.world_spec.content)
    store.put_if_absent(truth_manifest_key(sealed.world_version), sealed.truth_manifest.content)

    def assembly(seed: int, params: object, start: object, plan: object, filler: object):  # noqa: ANN202
        return semantic_world_of(pending_scenario(SkillInComment()))

    resumed, rebuilt = resume_world(sealed.world_version, store, assembly)
    assert resumed.disclosure is Disclosure.EMBARGOED
    assert rebuilt.world_version == sealed.world_version
