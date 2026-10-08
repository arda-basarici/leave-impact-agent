"""The unchanged-answers claims, evaluator side: a world with a filler pool grades every
scenario exactly as the world without one, and the only thing the pool adds to the index is
its own records. And the second guard at load: a filler title inside a planted requirement
clause's text refuses the world."""

from __future__ import annotations

from dataclasses import replace

import pytest

from leaveimpact.core import RunCondition, Source
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import DocumentId
from leaveimpact.core.refs import clause_ref
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.retrieval_targets import retrieval_targets
from leaveimpact.evaluator.sealed_world import SealedWorld, WorldNotIndexed, load_sealed_world
from leaveimpact.evaluator.world_index import ProblemKind
from leaveimpact.world import DEFAULT_PARAMS, Scenario, assemble_semantic_world, bundle, compose
from tests.unit.filler_fixture import padded_world, stand_in_bodies
from tests.unit.prose_fixture import record_for
from tests.unit.reads_fixture import fakes_holding, systems_holding
from tests.unit.throwaway_world import (
    REFERENCE_SEED,
    WORLD_START,
    composed_world_with_filler,
    loaded_world,
    loaded_world_with_filler,
    sealed_stores,
)

NORMAL = RunCondition.all_reachable()
CONDITIONS = (NORMAL, NORMAL.without(Source.JIRA), NORMAL.without(Source.CALENDAR))


@pytest.fixture(scope="module")
def plain() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def padded() -> SealedWorld:
    return loaded_world_with_filler(3)


def answer(world: SealedWorld, scenario: Scenario, condition: RunCondition) -> Answerable:
    oracle = oracle_for(world, scenario, condition)
    assert isinstance(oracle, Answerable)
    return oracle


def test_the_pool_adds_its_own_records_to_the_index_and_nothing_else(
    plain: SealedWorld, padded: SealedWorld
) -> None:
    assert set(padded.index.records) - set(plain.index.records) == set(padded.filler)
    assert set(plain.index.records) <= set(padded.index.records)
    assert padded.index.scope == plain.index.scope
    assert padded.index.statements == plain.index.statements
    assert padded.index.carried == plain.index.carried


def test_every_key_and_every_retrieval_target_is_unchanged_by_the_pool(
    plain: SealedWorld, padded: SealedWorld
) -> None:
    assert [s.key for s in padded.scenarios] == [s.key for s in plain.scenarios]
    for before, after in zip(plain.scenarios, padded.scenarios, strict=True):
        for condition in CONDITIONS:
            assert retrieval_targets(padded, answer(padded, after, condition)) == (
                retrieval_targets(plain, answer(plain, before, condition))
            )


def test_a_filler_title_inside_a_planted_requirement_clause_refuses_the_world_at_load() -> None:
    world = composed_world_with_filler(3)
    semantic = padded_world(
        assemble_semantic_world(REFERENCE_SEED, DEFAULT_PARAMS, WORLD_START, "golden")
    )
    clause = next(iter(world.scenarios[10].key.constraints)).clause_id
    text = next(
        section.text
        for s in world.scenarios
        for p in s.owned.documents
        for section in p.entity.sections
        if section.id == clause
    )
    assert clause_ref(clause).kind is EntityKind.CLAUSE
    [first, *rest] = semantic.filler
    collided = replace(first, entity=replace(first.entity, title=text[:12]))
    bodies = stand_in_bodies(semantic)
    sealed = bundle(
        compose(replace(semantic, filler=(collided, *rest)), bodies, record_for(bodies))
    )
    stores = sealed_stores(sealed)
    with pytest.raises(WorldNotIndexed) as refused:
        load_sealed_world(sealed.world_version, stores.truth, stores.world)
    kinds = {problem.kind for problem in refused.value.problems}
    assert ProblemKind.SCOPE_NOT_STATED_BY_THE_CLAUSE in kinds


def test_the_reads_fixtures_hold_the_pool_s_documents_beside_the_planted_ones(
    padded: SealedWorld,
) -> None:
    """A read of a filler document by id answers through both fixtures, and the documents
    port holds exactly the world's document records, the pool's included (the group 5
    review: the fixture had copied the scenarios' own documents alone, so a padded world's
    pool read as absent)."""
    documents = [ref for ref in padded.index.records if ref.kind is EntityKind.DOCUMENT]
    assert len(padded.filler) == 3 and set(padded.filler) <= set(documents)
    for systems in (systems_holding(padded), fakes_holding(padded)):
        for ref in padded.filler:
            found = systems.documents.document(DocumentId(ref.id))
            assert found is not None and found.value.id == ref.id
        assert systems.documents.held_document_ids() == {ref.id for ref in documents}
