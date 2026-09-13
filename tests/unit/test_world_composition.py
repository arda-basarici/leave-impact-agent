"""Composition: a world without pending prose composes into the entities it was assembled with and
carries no record; a world with a pending comment composes the model's body under the canonical
prefix at the target's position, and the composed world's invariant holds; and the contract —
a body for every brief, a brief for every body, no blank text, the record naming exactly the
pending targets, a part promised but absent refused however the world was built."""

from dataclasses import replace

import pytest

from leaveimpact.core import parse_comment
from leaveimpact.world import (
    DEFAULT_PARAMS,
    ProseContractError,
    WorldSpec,
    assemble_semantic_world,
    assemble_world,
    compose,
)
from tests.unit.prose_fixture import (
    ORG,
    WORLD_START,
    SkillInComment,
    pending_scenario,
    record_for,
    semantic_world_of,
)

BODY = "Deniz picked up the Kafka side of the retry-queue migration and has been running it."


def test_a_world_without_pending_prose_composes_into_itself_with_no_record() -> None:
    semantic = assemble_semantic_world(7, DEFAULT_PARAMS, WORLD_START)
    assert semantic.pending_ids == frozenset()
    composed = compose(semantic, {}, None)
    assert composed.scenarios == semantic.scenarios
    assert composed.materialization is None
    assert assemble_world(7, DEFAULT_PARAMS, WORLD_START) == composed


def test_a_pending_comment_is_composed_under_the_canonical_prefix_at_its_position() -> None:
    scenario = pending_scenario()
    semantic = semantic_world_of(scenario)
    [brief] = scenario.briefs
    assert semantic.pending_ids == {brief.id}
    composed = compose(semantic, {brief.id: BODY}, record_for({brief.id: BODY}))
    [planted] = composed.scenarios[0].owned.work_items
    [comment] = planted.entity.comments
    author = next(e for e in ORG.employees if e.id == comment.author_id)
    assert comment.text == f"[{brief.id}, {comment.world_date}, {author.id} — {author.name}] {BODY}"
    assert parse_comment(comment.text) == comment
    assert composed.scenarios[0].briefs == scenario.briefs
    assert composed.materialization is not None
    assert composed.materialization.target_ids == {brief.id}


def test_prose_is_composed_for_exactly_the_pending_targets() -> None:
    scenario = pending_scenario()
    semantic = semantic_world_of(scenario)
    [brief] = scenario.briefs
    with pytest.raises(ProseContractError, match=f"missing \\['{brief.id}'\\], unexpected \\[\\]"):
        compose(semantic, {}, None)
    with pytest.raises(ProseContractError, match="unexpected \\['comment_999'\\]"):
        compose(semantic, {brief.id: BODY, "comment_999": BODY}, record_for({brief.id: BODY}))
    with pytest.raises(ProseContractError, match="a composed body is not blank"):
        compose(semantic, {brief.id: "   "}, record_for({brief.id: BODY}))


def test_the_record_names_exactly_the_pending_targets() -> None:
    scenario = pending_scenario()
    semantic = semantic_world_of(scenario)
    [brief] = scenario.briefs
    with pytest.raises(
        ValueError, match="the materialization record covers \\[\\] and the briefs name"
    ):
        compose(semantic, {brief.id: BODY}, None)
    with pytest.raises(ValueError, match="the materialization record covers"):
        compose(
            semantic, {brief.id: BODY}, record_for({brief.id: BODY}, extra_targets=["comment_999"])
        )


def test_a_composed_world_holds_every_briefed_part_however_it_was_built() -> None:
    scenario = pending_scenario()
    semantic = semantic_world_of(scenario)
    [brief] = scenario.briefs
    composed = compose(semantic, {brief.id: BODY}, record_for({brief.id: BODY}))
    [planted] = composed.scenarios[0].owned.work_items
    stripped = replace(planted, entity=replace(planted.entity, comments=()))
    owned = replace(composed.scenarios[0].owned, work_items=(stripped,))
    with pytest.raises(ValueError, match=f"briefed parts not composed: \\['{brief.id}'\\]"):
        WorldSpec(
            seed=composed.seed,
            world_start=composed.world_start,
            org=composed.org,
            slices=composed.slices,
            plan=composed.plan,
            scenarios=(replace(composed.scenarios[0], owned=owned),),
            facts=composed.facts,
            generator_version=composed.generator_version,
            interpreter=composed.interpreter,
            vocabulary_digest=composed.vocabulary_digest,
            semantic_digest=composed.semantic_digest,
            materialization=composed.materialization,
        )


def test_assembling_a_world_that_needs_a_model_without_prose_is_refused_by_name() -> None:
    scenario = pending_scenario(SkillInComment())
    semantic = semantic_world_of(scenario)
    with pytest.raises(ProseContractError, match="missing"):
        compose(semantic, {}, None)
