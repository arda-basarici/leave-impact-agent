"""The served side's levels object: what the corpus cache reads of a world's pool and levels.

The pool's order and the levels are on the world spec, in the truth bucket; the instance
reads the world bucket alone, so the world seals a projection of them beside its documents
(the M2 step 9 design, fork 1). These tests hold that the object round-trips, that a world
with no pool states the base level over an empty pool rather than nothing, that membership
derived from the object equals membership derived from the spec, and that the record
refuses what cannot describe one world.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from leaveimpact.core.ids import DocumentId
from leaveimpact.world import DEFAULT_PARAMS, assemble_semantic_world, assemble_world, compose
from leaveimpact.world.artifacts import LEVELS, encode_levels, levels_bytes
from leaveimpact.world.decoders import decode_levels
from leaveimpact.world.filler import with_filler
from leaveimpact.world.levels import (
    BASE_CORPUS_LEVELS,
    BASE_LEVELS,
    CorpusLevels,
    SealedLevel,
    corpus_levels_of,
    level_members,
)
from tests.unit.filler_fixture import filler_documents


def test_a_padded_world_s_levels_object_round_trips_and_derives_the_spec_s_membership() -> None:
    semantic = assemble_semantic_world(7, DEFAULT_PARAMS, date(2026, 1, 1))
    pool = filler_documents(semantic, 3)
    padded = compose(with_filler(semantic, pool), {}, None)
    levels = corpus_levels_of(padded.filler, padded.levels)

    assert decode_levels(levels_bytes(levels)) == levels
    assert levels.pool == tuple(p.entity.id for p in pool), "the pool in its sealed order"
    assert levels.levels == padded.levels
    owned = [planted.entity.id for s in padded.scenarios for planted in s.owned.documents]
    for level in padded.levels:
        from_object = level_members(level.name, levels.levels, owned, levels.pool)
        from_spec = level_members(level.name, padded.levels, owned, [p.entity.id for p in pool])
        assert from_object == from_spec


def test_a_world_with_no_pool_seals_the_base_level_over_an_empty_pool() -> None:
    world = assemble_world(7, DEFAULT_PARAMS, date(2026, 1, 1))
    levels = corpus_levels_of(world.filler, world.levels)
    assert levels == BASE_CORPUS_LEVELS == CorpusLevels(BASE_LEVELS, ())
    encoded = json.loads(levels_bytes(levels))
    assert encoded == {
        "artifact": LEVELS,
        "levels": [{"name": "base", "filler_count": 0}],
        "pool": [],
    }
    assert levels.filler_count("base") == 0
    assert levels.filler_count("padded") is None, "a level never sealed answers nothing"


@pytest.mark.parametrize(
    ("levels", "pool", "message"),
    [
        ((SealedLevel("base", 0), SealedLevel("base", 0)), (), "sealed once"),
        ((SealedLevel("padded", 0),), (), "base level is always sealed"),
        ((SealedLevel("base", 0), SealedLevel("padded", 2)), ("doc_009",), "at most the pool's 1"),
        ((SealedLevel("base", 0),), ("doc_009", "doc_009"), "pool document is sealed once"),
        ((SealedLevel("base", 0),), ("emp_001",), "holds document ids"),
    ],
)
def test_a_record_that_cannot_describe_one_world_is_refused(
    levels: tuple[SealedLevel, ...], pool: tuple[str, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        CorpusLevels(levels, tuple(DocumentId(id) for id in pool))


def test_the_decoder_refuses_another_artifact_and_a_surplus_field() -> None:
    good = encode_levels(BASE_CORPUS_LEVELS)
    with pytest.raises(ValueError, match="sealed as levels.json"):
        decode_levels(json.dumps({**good, "artifact": "scenario-specs.json"}))
    with pytest.raises(ValueError, match="rank"):
        decode_levels(json.dumps({**good, "rank": 1}))
