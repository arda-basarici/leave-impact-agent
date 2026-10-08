"""The scope matcher read from the assembly's side: over the semantic world, before any prose
exists, it finds the same scope the evaluator's index finds over the composed world and
reports nothing, a pending clause waiting for the load while a pending section still counts
as its document's one; and a title that contains a planted one steals the resolution."""

from __future__ import annotations

from dataclasses import replace

import pytest

from leaveimpact.core import EntityKind, EntityRef, clause_ref, document_ref
from leaveimpact.core.ids import document_id
from leaveimpact.evaluator.world_index import index_world
from leaveimpact.world import (
    DEFAULT_PARAMS,
    SectionTarget,
    SemanticWorld,
    WorldSpec,
    assemble_semantic_world,
)
from leaveimpact.world.scope import (
    ProblemKind,
    ScopePart,
    planted_parts,
    planted_titles,
    scope_problems,
)
from tests.unit.throwaway_world import REFERENCE_SEED, WORLD_START, composed_world


@pytest.fixture(scope="module")
def semantic() -> SemanticWorld:
    return assemble_semantic_world(REFERENCE_SEED, DEFAULT_PARAMS, WORLD_START, "golden")


@pytest.fixture(scope="module")
def composed() -> WorldSpec:
    return composed_world("golden")


def test_the_assembly_reading_finds_the_composed_scope_and_no_problem(
    semantic: SemanticWorld, composed: WorldSpec
) -> None:
    scope, problems = scope_problems(
        semantic.scenarios, planted_titles(semantic.scenarios), planted_parts(semantic.scenarios)
    )
    index, index_problems = index_world(composed.org, composed.scenarios)
    assert problems == [] and index_problems == ()
    assert scope == dict(index.scope)


def test_a_pending_section_target_counts_as_the_section_its_document_holds(
    semantic: SemanticWorld,
) -> None:
    # The golden plan scopes at least one clause by a section a model still owes: the
    # target is absent from every planted record and present only as a brief.
    pending = {
        clause_ref(brief.target.id)
        for scenario in semantic.scenarios
        for brief in scenario.briefs
        if isinstance(brief.target, SectionTarget)
    }
    targets = {
        constraint.applies_to
        for scenario in semantic.scenarios
        for constraint in scenario.key.constraints
    }
    assert pending & targets, "the golden plan scopes no clause by a pending section"
    parts = planted_parts(semantic.scenarios)
    assert all(parts[ref].text is None for ref in pending & targets)
    _, problems = scope_problems(semantic.scenarios, planted_titles(semantic.scenarios), parts)
    assert problems == []


def test_a_pending_clause_is_skipped_and_an_empty_one_is_not(semantic: SemanticWorld) -> None:
    # The golden plan's requirement clauses are template-written, so the pending reading is
    # made: a requirement clause with its text withdrawn passes the fourth property until
    # the load, while the same clause composed to an empty text fails it at once.
    titles = planted_titles(semantic.scenarios)
    parts = planted_parts(semantic.scenarios)
    scope, problems = scope_problems(semantic.scenarios, titles, parts)
    assert problems == []
    clause = next(clause for clause in scope if parts[clause_ref(clause)].text is not None)
    parent = parts[clause_ref(clause)].parent
    pending = {**parts, clause_ref(clause): ScopePart(parent, None)}
    _, waiting = scope_problems(semantic.scenarios, titles, pending)
    assert waiting == []
    composed_empty = {**parts, clause_ref(clause): ScopePart(parent, "")}
    _, found = scope_problems(semantic.scenarios, titles, composed_empty)
    assert [problem.kind for problem in found] == [ProblemKind.SCOPE_NOT_STATED_BY_THE_CLAUSE]
    assert found[0].detail.startswith(f"{clause} is scoped to")


def test_a_title_containing_a_planted_one_steals_the_clause_s_resolution(
    semantic: SemanticWorld,
) -> None:
    titles = planted_titles(semantic.scenarios)
    parts = planted_parts(semantic.scenarios)
    scope, _ = scope_problems(semantic.scenarios, titles, parts)
    clause, target = next(
        (clause, target)
        for clause, target in scope.items()
        if parts[clause_ref(clause)].text is not None and target.kind is EntityKind.WORK_ITEM
    )
    text = parts[clause_ref(clause)].text
    assert text is not None and titles[target] in text
    # A filler document whose title is the clause's text up to and past the target's title
    # contains that title, so the longest-found rule resolves to the filler document.
    start = text.index(titles[target])
    stealing: EntityRef = document_ref(document_id(9001))
    widened = {**titles, stealing: text[start : start + len(titles[target]) + 4]}
    _, found = scope_problems(semantic.scenarios, widened, parts)
    stated = [
        problem for problem in found if problem.kind is ProblemKind.SCOPE_NOT_STATED_BY_THE_CLAUSE
    ]
    assert any(
        problem.detail.startswith(f"{clause} is scoped to {target.id}") for problem in stated
    )
    assert any(stealing.id in problem.detail for problem in stated)


def test_the_titles_of_a_filler_pool_join_the_universe(semantic: SemanticWorld) -> None:
    pool_document = next(
        planted for scenario in semantic.scenarios for planted in scenario.owned.documents
    )
    as_filler = replace(
        pool_document, entity=replace(pool_document.entity, id=document_id(9002), title="Filler")
    )
    titles = planted_titles(semantic.scenarios, (as_filler,))
    assert titles[document_ref(document_id(9002))] == "Filler"
