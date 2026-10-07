"""The filler pool and the corpus levels on the world: attached after assembly, stripped for
the unchanged-answers claim, sealed and decoded in both shapes, composed like any part.

The pool here is hand-built with stand-in sections: what the generator will put in it is the
next build group's; these tests hold the world's own statements about a pool, whoever made it.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date

import pytest

from leaveimpact.core.ids import document_id
from leaveimpact.world import (
    BASE_LEVELS,
    SealedLevel,
    SemanticWorld,
    WorldSpec,
    assemble_semantic_world,
    bundle,
    compose,
    decode_world_spec,
    encode_semantic_world,
    encode_world_spec,
    level_members,
    scope_handle_problems,
    semantic_digest,
    strip_filler,
    with_filler,
    world_documents,
)
from leaveimpact.world.levels import check_pool
from leaveimpact.world.org import DEFAULT_PARAMS
from leaveimpact.world.truth_decoder import decode_truth_manifest
from tests.unit.filler_fixture import (
    PADDED,
    filler_brief,
    filler_documents,
    next_numbers,
    stand_in_bodies,
)
from tests.unit.prose_fixture import record_for

WORLD_START = date(2026, 1, 1)


@pytest.fixture(scope="module")
def semantic() -> SemanticWorld:
    return assemble_semantic_world(7, DEFAULT_PARAMS, WORLD_START, "golden")


# --- The two transforms and the enumeration ----------------------------------------------


def test_filler_attached_and_stripped_is_the_world_the_seed_produced(
    semantic: SemanticWorld,
) -> None:
    padded = with_filler(semantic, filler_documents(semantic, 3), levels=(*BASE_LEVELS, PADDED))
    assert padded != semantic
    assert strip_filler(padded) == semantic


def test_the_world_documents_are_the_owned_in_scenario_order_then_the_pool_in_rank(
    semantic: SemanticWorld,
) -> None:
    pool = filler_documents(semantic, 3)
    padded = with_filler(semantic, pool)
    owned = [p for s in semantic.scenarios for p in s.owned.documents]
    assert world_documents(padded) == (*owned, *pool)
    assert world_documents(semantic) == tuple(owned)


def test_a_world_assembled_without_a_pool_seals_the_base_level_alone(
    semantic: SemanticWorld,
) -> None:
    assert semantic.filler == ()
    assert semantic.filler_briefs == ()
    assert semantic.levels == BASE_LEVELS


def test_a_composed_world_takes_no_pool_and_gives_none_up(semantic: SemanticWorld) -> None:
    """A composed world's digest and record are of the world it was composed from, so a pool
    changed after composition is provenance the resume path refuses: attach before composing."""
    bodies = stand_in_bodies(semantic)
    composed = compose(semantic, bodies, record_for(bodies))
    with pytest.raises(TypeError, match="before composition"):
        with_filler(composed, filler_documents(semantic, 1))
    with pytest.raises(TypeError, match="before composition"):
        strip_filler(composed)


# --- The invariants ------------------------------------------------------------------------


def test_filler_minted_below_a_planted_document_is_refused(semantic: SemanticWorld) -> None:
    pool = filler_documents(semantic, 1)
    [planted] = pool
    early = replace(planted, entity=replace(planted.entity, id=document_id(1)))
    with pytest.raises(ValueError, match="minted after every planted document"):
        with_filler(semantic, (early,))


def test_a_filler_id_shared_with_a_planted_document_is_refused(semantic: SemanticWorld) -> None:
    owned = next(p for s in semantic.scenarios for p in s.owned.documents)
    with pytest.raises(ValueError, match="minted after every planted document"):
        with_filler(semantic, (owned,))


def test_a_level_beyond_the_pool_is_refused(semantic: SemanticWorld) -> None:
    with pytest.raises(ValueError, match="at most the pool's 1 documents"):
        with_filler(semantic, filler_documents(semantic, 1), levels=(*BASE_LEVELS, PADDED))


def test_a_level_name_sealed_twice_and_a_missing_base_are_refused(semantic: SemanticWorld) -> None:
    pool = filler_documents(semantic, 2)
    with pytest.raises(ValueError, match="a level is sealed once"):
        with_filler(semantic, pool, levels=(*BASE_LEVELS, PADDED, PADDED))
    with pytest.raises(ValueError, match="base level is always sealed"):
        with_filler(semantic, pool, levels=(PADDED,))


def test_the_base_level_holds_no_filler() -> None:
    with pytest.raises(ValueError, match="no filler added"):
        SealedLevel("base", 1)


def test_a_filler_brief_targets_a_filler_document(semantic: SemanticWorld) -> None:
    owned = next(p.entity for s in semantic.scenarios for p in s.owned.documents)
    _, first_clause = next_numbers(semantic)
    with pytest.raises(ValueError, match="targets a section of a filler document"):
        with_filler(
            semantic, filler_documents(semantic, 1), briefs=(filler_brief(owned, first_clause),)
        )


def test_check_pool_accepts_an_empty_pool_with_the_base_level() -> None:
    check_pool((), BASE_LEVELS, (), ["doc_001"])


# --- Membership ----------------------------------------------------------------------------


def test_a_level_holds_every_planted_document_and_the_first_count_of_the_pool(
    semantic: SemanticWorld,
) -> None:
    pool = filler_documents(semantic, 3)
    padded = with_filler(semantic, pool, levels=(*BASE_LEVELS, PADDED))
    owned_ids = [p.entity.id for s in padded.scenarios for p in s.owned.documents]
    pool_ids = [p.entity.id for p in pool]
    assert level_members("base", padded.levels, owned_ids, pool_ids) == frozenset(owned_ids)
    assert level_members("padded", padded.levels, owned_ids, pool_ids) == frozenset(
        owned_ids + pool_ids[:2]
    )
    assert level_members("huge", padded.levels, owned_ids, pool_ids) is None


# --- Sealing and decoding, both shapes ----------------------------------------------------


def test_a_world_without_a_pool_encodes_without_the_pool_s_names(semantic: SemanticWorld) -> None:
    bodies = stand_in_bodies(semantic)
    sealed = bundle(compose(semantic, bodies, record_for(bodies)))
    spec = json.loads(sealed.world_spec.content)
    truth = json.loads(sealed.truth_manifest.content)
    assert "filler" not in spec and "levels" not in spec
    assert "filler_briefs" not in truth
    assert "filler" not in encode_semantic_world(semantic)
    decoded = decode_world_spec(sealed.world_spec.content)
    assert decoded.filler == () and decoded.levels == BASE_LEVELS
    assert decode_truth_manifest(sealed.truth_manifest.content).filler_briefs == ()


def test_a_world_with_a_pool_round_trips_through_the_spec_and_the_manifest(
    semantic: SemanticWorld,
) -> None:
    pool = filler_documents(semantic, 3, pending=1)
    _, first_clause = next_numbers(semantic)
    brief = filler_brief(pool[0].entity, first_clause + 10)
    padded = with_filler(semantic, pool, briefs=(brief,), levels=(*BASE_LEVELS, PADDED))
    bodies = {**stand_in_bodies(semantic), brief.id: "Stand-in filler prose."}
    composed = compose(padded, bodies, record_for(bodies))
    sealed = bundle(composed)
    decoded = decode_world_spec(sealed.world_spec.content)
    assert decoded.levels == (*BASE_LEVELS, PADDED)
    assert [p.entity.id for p in decoded.filler] == [p.entity.id for p in pool]
    [written] = decoded.filler[0].entity.sections
    assert written.text == "Stand-in filler prose."
    manifest = decode_truth_manifest(sealed.truth_manifest.content)
    assert manifest.filler_briefs == (brief,)
    assert encode_world_spec(decoded) == json.loads(sealed.world_spec.content)


def test_the_semantic_digest_moves_with_the_pool_and_the_pins_do_not(
    semantic: SemanticWorld,
) -> None:
    padded = with_filler(semantic, filler_documents(semantic, 1))
    assert semantic_digest(padded) != semantic_digest(semantic)
    assert semantic_digest(strip_filler(padded)) == semantic_digest(semantic)


# --- Composition ---------------------------------------------------------------------------


def test_a_filler_brief_is_pending_until_composed(semantic: SemanticWorld) -> None:
    pool = filler_documents(semantic, 1, pending=1)
    _, first_clause = next_numbers(semantic)
    brief = filler_brief(pool[0].entity, first_clause)
    padded = with_filler(semantic, pool, briefs=(brief,))
    assert padded.pending_ids == semantic.pending_ids | {brief.id}
    bodies = stand_in_bodies(semantic)
    with pytest.raises(ValueError, match=f"missing \\['{brief.id}'\\]"):
        compose(padded, bodies, record_for(bodies))


def test_a_composed_world_refuses_a_filler_part_that_was_not_written(
    semantic: SemanticWorld,
) -> None:
    pool = filler_documents(semantic, 1, pending=1)
    _, first_clause = next_numbers(semantic)
    brief = filler_brief(pool[0].entity, first_clause)
    padded = with_filler(semantic, pool, briefs=(brief,))
    bodies = {**stand_in_bodies(semantic), brief.id: "Stand-in filler prose."}
    composed = compose(padded, bodies, record_for(bodies))
    with pytest.raises(
        ValueError, match=f"the filler pool: briefed parts not composed: \\['{brief.id}'\\]"
    ):
        WorldSpec(
            seed=composed.seed,
            world_start=composed.world_start,
            org=composed.org,
            slices=composed.slices,
            plan=composed.plan,
            plan_name=composed.plan_name,
            scenarios=composed.scenarios,
            facts=composed.facts,
            generator_version=composed.generator_version,
            interpreter=composed.interpreter,
            vocabulary_digest=composed.vocabulary_digest,
            semantic_digest=composed.semantic_digest,
            materialization=composed.materialization,
            filler=pool,
            filler_briefs=composed.filler_briefs,
            levels=composed.levels,
        )


# --- The handle guard ----------------------------------------------------------------------


def test_a_filler_title_equal_to_a_planted_handle_makes_the_handle_ambiguous(
    semantic: SemanticWorld,
) -> None:
    """Colliding a filler title with each planted document's title in turn: the titles used
    as handles report, every report counts the filler document, and the rest stay silent."""
    assert scope_handle_problems(semantic.scenarios) == []
    [filler] = filler_documents(semantic, 1)
    reported = 0
    for title in {p.entity.title for s in semantic.scenarios for p in s.owned.documents}:
        collided = replace(filler, entity=replace(filler.entity, title=title))
        problems = scope_handle_problems(semantic.scenarios, (collided,))
        reported += bool(problems)
        assert all(repr(title) in p and "names 2 documents" in p for p in problems)
    assert reported > 0
